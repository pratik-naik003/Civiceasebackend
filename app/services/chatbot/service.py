import json
import re
from typing import Any, TypedDict

try:
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:  # pragma: no cover
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.schema import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chatbot import ChatMessage, ChatSession
from app.models.issue import IssuePhoto
from app.models.user import User
from app.schemas.chatbot import ComplaintDraftResponse
from app.schemas.issue import Location
from app.services.ai.cerebras_client import CerebrasClient
from app.services.issue_service import IssueService


class ComplaintDraft(BaseModel):
    title: str | None = None
    description: str | None = None
    location: Location | None = None
    photo_keys: list[str] = Field(default_factory=list)
    submitted_issue_id: int | None = None

    @property
    def ready_to_submit(self) -> bool:
        return bool((self.description or "").strip() and self.location and self.photo_keys)


class PlannerAction(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    assistant_reply: str
    conversation_title: str | None = None
    actions: list[PlannerAction] = Field(default_factory=list)


class ToolExecutionEvent(BaseModel):
    tool: str
    status: str
    message: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatbotState(TypedDict, total=False):
    session_id: str
    user_text: str
    incoming_photo_keys: list[str]
    incoming_location: dict[str, Any] | None
    session: ChatSession
    draft: ComplaintDraft
    history: list[Any]
    plan: PlannerOutput
    assistant_reply: str
    conversation_title: str | None
    created_issue_id: int | None
    tool_events: list[ToolExecutionEvent]
    user_message: ChatMessage
    assistant_message: ChatMessage


class ComplaintChatbotService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user
        self.issue_service = IssueService(db)
        self.client = CerebrasClient(model=settings.chatbot_cerebras_model)
        self.graph = self._build_graph()
        self.planner_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are CivicEase AI, a concise civic-support chatbot. "
                    "There are two modes. Mode 1 is normal civic Q&A: if the user asks for information, guidance, steps, or explanation, answer directly and return no tool actions. "
                    "Do not begin a complaint draft unless the user explicitly asks to create, file, report, or submit a complaint or issue, or they clearly share complaint evidence for that purpose. "
                    "Mode 2 is complaint intake: if the user wants to create, file, report, or submit a complaint, treat their message as the complaint description, derive a short title automatically, and use set_complaint_details(title, description). "
                    "Do not ask the user to provide a separate title. The current draft already includes any location or photo evidence shared in this turn. "
                    "Never invent location coordinates or photo keys. Do not claim to visually analyze uploaded images. "
                    "Use the available tools only when needed. Only call submit_issue if the draft has a meaningful description, one location, and at least one photo key. "
                    "If complaint information is missing, ask only for the missing item in one short sentence. "
                    "Allowed tools: set_complaint_details(title, description), submit_issue(), clear_complaint_draft(). "
                    "Return strict JSON with keys assistant_reply, conversation_title, actions."
                ),
                MessagesPlaceholder("history"),
                (
                    "human",
                    "Latest user message: {latest_message}\n"
                    "Current complaint draft JSON: {draft_json}\n"
                    "Current turn context JSON: {turn_context_json}\n"
                    "Return JSON in this shape exactly: "
                    "{{\"assistant_reply\":\"...\",\"conversation_title\":null,\"actions\":[{{\"tool\":\"set_complaint_details\",\"args\":{{\"title\":\"...\",\"description\":\"...\"}}}}]}}"
                ),
            ]
        )

    def _build_graph(self):
        graph = StateGraph(ChatbotState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("plan", self._plan)
        graph.add_node("execute_tools", self._execute_tools)
        graph.add_node("persist", self._persist)
        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "plan")
        graph.add_edge("plan", "execute_tools")
        graph.add_edge("execute_tools", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def create_session(self) -> ChatSession:
        session = ChatSession(user_id=self.user.id, draft_json=ComplaintDraft().model_dump_json())
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str) -> ChatSession:
        session = self.db.get(ChatSession, session_id)
        if not session or session.user_id != self.user.id:
            raise ValueError("Chat session not found")
        return session

    def run_turn(
        self,
        session_id: str,
        *,
        message: str,
        photo_keys: list[str] | None = None,
        location: Location | None = None,
    ) -> dict[str, Any]:
        state: ChatbotState = {
            "session_id": session_id,
            "user_text": message.strip(),
            "incoming_photo_keys": photo_keys or [],
            "incoming_location": location.model_dump() if location else None,
            "created_issue_id": None,
            "tool_events": [],
        }
        return self.graph.invoke(state)

    def stream_turn(
        self,
        session_id: str,
        *,
        message: str,
        photo_keys: list[str] | None = None,
        location: Location | None = None,
    ):
        state: ChatbotState = {
            "session_id": session_id,
            "user_text": message.strip(),
            "incoming_photo_keys": photo_keys or [],
            "incoming_location": location.model_dump() if location else None,
            "created_issue_id": None,
            "tool_events": [],
        }

        yield {"type": "status", "message": "Loading conversation"}
        state = self._load_context(state)

        yield {"type": "status", "message": "Planning response"}
        state = self._plan(state)

        for index, action in enumerate(state["plan"].actions):
            yield {
                "type": "tool_call",
                "stream_id": index,
                "tool": action.tool,
                "status": "running",
                "args": action.args,
            }

        if state["plan"].actions:
            yield {"type": "status", "message": "Running tools"}

        state = self._execute_tools(state)

        for index, event in enumerate(state.get("tool_events", [])):
            payload = event.model_dump()
            payload.update({"type": "tool_result", "stream_id": index})
            yield payload

        yield {"type": "status", "message": "Streaming response"}
        state = self._persist(state)

        assistant_text = state["assistant_message"].content or ""
        for delta in self._stream_text_chunks(assistant_text):
            yield {"type": "assistant_delta", "delta": delta}

        yield {"type": "complete", "turn": self.build_turn_response(state)}

    def build_session_response(self, session: ChatSession) -> dict[str, Any]:
        session = self.get_session(session.id)
        draft = self._load_draft(session)
        return {
            "session_id": session.id,
            "title": session.title,
            "draft": self._draft_response(draft).model_dump(),
            "messages": [self._message_to_response(message) for message in session.messages],
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def build_turn_response(self, state: dict[str, Any]) -> dict[str, Any]:
        draft: ComplaintDraft = state["draft"]
        return {
            "session_id": state["session"].id,
            "user_message": self._message_to_response(state["user_message"]),
            "assistant_message": self._message_to_response(state["assistant_message"]),
            "draft": self._draft_response(draft).model_dump(),
            "created_issue_id": state.get("created_issue_id"),
        }

    def _load_context(self, state: ChatbotState) -> ChatbotState:
        session = self.get_session(state["session_id"])
        draft = self._load_draft(session)

        incoming_location = state.get("incoming_location")
        if incoming_location:
            draft.location = Location.model_validate(incoming_location)

        incoming_photo_keys = state.get("incoming_photo_keys", [])
        if incoming_photo_keys:
            draft.photo_keys = list(dict.fromkeys([*draft.photo_keys, *incoming_photo_keys]))

        history_messages = []
        for message in session.messages[-settings.chatbot_history_window :]:
            text = message.content or ""
            if message.role == "assistant":
                history_messages.append(AIMessage(content=text))
            else:
                history_messages.append(HumanMessage(content=text))

        state["session"] = session
        state["draft"] = draft
        state["history"] = history_messages
        return state

    def _plan(self, state: ChatbotState) -> ChatbotState:
        draft: ComplaintDraft = state["draft"]
        latest_message = state.get("user_text") or "(no text provided)"
        turn_context_json = json.dumps(
            {
                "photo_keys": state.get("incoming_photo_keys", []),
                "location": state.get("incoming_location"),
            },
            ensure_ascii=False,
        )

        llm_plan = self._plan_with_llm(
            history=state.get("history", []),
            latest_message=latest_message,
            draft=draft,
            turn_context_json=turn_context_json,
        )
        rule_plan = self._plan_with_rules(state.get("user_text", ""), draft)

        if not llm_plan:
            plan = rule_plan
        else:
            llm_tools = {action.tool for action in llm_plan.actions}
            rule_tools = {action.tool for action in rule_plan.actions}
            if rule_tools and (not llm_tools or ("submit_issue" in rule_tools and "submit_issue" not in llm_tools)):
                plan = rule_plan
            else:
                plan = llm_plan

        state["plan"] = plan
        state["assistant_reply"] = plan.assistant_reply.strip() or "How can I help you with CivicEase today?"
        state["conversation_title"] = plan.conversation_title
        return state

    def _execute_tools(self, state: ChatbotState) -> ChatbotState:
        draft: ComplaintDraft = state["draft"]
        plan: PlannerOutput = state["plan"]
        created_issue_id: int | None = None
        tool_events: list[ToolExecutionEvent] = []

        for action in plan.actions:
            if action.tool == "set_complaint_details":
                title = (action.args.get("title") or "").strip()
                description = (action.args.get("description") or "").strip()
                if title:
                    draft.title = title
                if description:
                    draft.description = description
                tool_events.append(
                    ToolExecutionEvent(
                        tool="set_complaint_details",
                        status="completed",
                        message="Saved complaint details to the draft.",
                        args={
                            "title": title,
                            "description_present": bool(description),
                        },
                    )
                )
                continue

            if action.tool == "clear_complaint_draft":
                draft = ComplaintDraft()
                tool_events.append(
                    ToolExecutionEvent(
                        tool="clear_complaint_draft",
                        status="completed",
                        message="Cleared the complaint draft.",
                        args={},
                    )
                )
                continue

            if action.tool == "submit_issue":
                if not draft.ready_to_submit:
                    missing = []
                    if not (draft.description or "").strip():
                        missing.append("issue description")
                    if not draft.location:
                        missing.append("location")
                    if not draft.photo_keys:
                        missing.append("photo evidence")
                    state["assistant_reply"] = f"I still need {', '.join(missing)} before I can create the complaint."
                    tool_events.append(
                        ToolExecutionEvent(
                            tool="submit_issue",
                            status="blocked",
                            message=f"Cannot submit yet. Missing {', '.join(missing)}.",
                            args={"missing": missing},
                        )
                    )
                    continue

                title = (draft.title or "").strip() or self._derive_title(draft.description or "Municipal complaint")
                primary_photo_key = draft.photo_keys[0]
                extra_photo_keys = draft.photo_keys[1:]

                issue = self.issue_service.create_issue(
                    reporter_id=self.user.id,
                    title=title,
                    description=(draft.description or "").strip(),
                    lat=draft.location.lat if draft.location else None,
                    lng=draft.location.lng if draft.location else None,
                    photo_key=primary_photo_key,
                )
                for photo_key in extra_photo_keys:
                    self.db.add(IssuePhoto(issue_id=issue.id, photo_key=photo_key))
                if extra_photo_keys:
                    self.db.commit()

                created_issue_id = issue.id
                draft = ComplaintDraft(submitted_issue_id=issue.id)
                state["assistant_reply"] = f"I created your complaint successfully. Your issue ID is #{issue.id}."
                tool_events.append(
                    ToolExecutionEvent(
                        tool="submit_issue",
                        status="completed",
                        message=f"Submitted complaint #{issue.id}.",
                        args={"issue_id": issue.id},
                    )
                )
                continue

            tool_events.append(
                ToolExecutionEvent(
                    tool=action.tool,
                    status="ignored",
                    message="Tool is not supported by the complaint agent.",
                    args=action.args,
                )
            )

        state["draft"] = draft
        state["created_issue_id"] = created_issue_id
        state["tool_events"] = tool_events
        return state

    def _persist(self, state: ChatbotState) -> ChatbotState:
        session: ChatSession = state["session"]
        draft: ComplaintDraft = state["draft"]
        user_text = state.get("user_text", "").strip() or self._context_only_user_message(state)
        assistant_text = state.get("assistant_reply", "").strip() or "How can I help you with CivicEase today?"

        if not session.title:
            session.title = (state.get("conversation_title") or self._derive_title(user_text)).strip()[:255] or "New chat"

        session.draft_json = draft.model_dump_json()
        self.db.add(session)

        user_meta = json.dumps(
            {
                "photo_keys": state.get("incoming_photo_keys", []),
                "location": state.get("incoming_location"),
            }
        )
        assistant_meta = json.dumps(
            {
                "created_issue_id": state.get("created_issue_id"),
                "tool_events": [event.model_dump() for event in state.get("tool_events", [])],
            }
        )

        user_message = ChatMessage(session_id=session.id, role="user", content=user_text, meta_json=user_meta)
        assistant_message = ChatMessage(session_id=session.id, role="assistant", content=assistant_text, meta_json=assistant_meta)
        self.db.add(user_message)
        self.db.add(assistant_message)
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)

        state["session"] = session
        state["user_message"] = user_message
        state["assistant_message"] = assistant_message
        return state

    def _plan_with_llm(
        self,
        *,
        history: list[Any],
        latest_message: str,
        draft: ComplaintDraft,
        turn_context_json: str,
    ) -> PlannerOutput | None:
        if not self.client.enabled:
            return None

        try:
            formatted_messages = self.planner_prompt.format_messages(
                history=history,
                latest_message=latest_message,
                draft_json=draft.model_dump_json(indent=2),
                turn_context_json=turn_context_json,
            )
            response = self.client.complete(
                [self._message_to_openai_payload(message) for message in formatted_messages],
                temperature=0.1,
                json_response=True,
            )
            return PlannerOutput.model_validate_json(response.content)
        except (ValidationError, json.JSONDecodeError, RuntimeError, KeyError, ValueError):
            return None
        except Exception:
            return None

    def _plan_with_rules(self, message: str, draft: ComplaintDraft) -> PlannerOutput:
        normalized = (message or "").strip()
        lower = normalized.lower()
        actions: list[PlannerAction] = []

        if any(trigger in lower for trigger in ["clear chat", "clear draft", "start over", "reset complaint"]):
            return PlannerOutput(
                assistant_reply="I cleared the current complaint draft. You can start a new one now.",
                actions=[PlannerAction(tool="clear_complaint_draft", args={})],
            )

        complaint_intent_phrases = [
            "create complaint",
            "submit complaint",
            "file complaint",
            "report complaint",
            "report this",
            "report it",
            "create issue",
            "submit issue",
            "file issue",
            "report issue",
            "lodge complaint",
            "register complaint",
        ]
        complaint_intent = any(trigger in lower for trigger in complaint_intent_phrases)
        request_submit = any(trigger in lower for trigger in ["create complaint", "submit complaint", "file complaint", "create issue", "submit issue"])

        if normalized and self._looks_like_issue_description(normalized):
            actions.append(
                PlannerAction(
                    tool="set_complaint_details",
                    args={
                        "title": self._derive_title(normalized),
                        "description": normalized,
                    },
                )
            )

        if request_submit and (draft.ready_to_submit or actions):
            actions.append(PlannerAction(tool="submit_issue", args={}))
            return PlannerOutput(
                assistant_reply="I am creating your complaint now.",
                conversation_title=self._derive_title(normalized or draft.title or "Complaint"),
                actions=actions,
            )

        if complaint_intent or actions:
            missing = []
            next_description = normalized if self._looks_like_issue_description(normalized) else draft.description
            if not (next_description or "").strip():
                missing.append("the issue details")
            if not draft.location:
                missing.append("your location")
            if not draft.photo_keys:
                missing.append("at least one photo")

            if missing:
                return PlannerOutput(
                    assistant_reply=f"I noted this complaint. Please share {', '.join(missing)} so I can create it.",
                    conversation_title=self._derive_title(normalized or "Complaint"),
                    actions=actions,
                )

            return PlannerOutput(
                assistant_reply="I have the complaint details. Say create complaint and I will submit it.",
                conversation_title=self._derive_title(normalized or draft.title or "Complaint"),
                actions=actions,
            )

        return PlannerOutput(
            assistant_reply=(
                "I can answer civic questions and also create a complaint for you. Describe the issue, attach a photo, share location, and then ask me to create the complaint."
            ),
            conversation_title=self._derive_title(normalized) if normalized else None,
            actions=[],
        )

    def _stream_text_chunks(self, text: str, chunk_size: int = 28) -> list[str]:
        if not text:
            return []

        parts = re.findall(r"\S+\s*", text)
        chunks: list[str] = []
        buffer = ""
        for part in parts:
            if buffer and len(buffer) + len(part) > chunk_size:
                chunks.append(buffer)
                buffer = part
            else:
                buffer += part
        if buffer:
            chunks.append(buffer)
        return chunks

    def _context_only_user_message(self, state: ChatbotState) -> str:
        photo_count = len(state.get("incoming_photo_keys", []))
        has_location = bool(state.get("incoming_location"))
        parts = []
        if photo_count:
            parts.append(f"Shared {photo_count} photo evidence item{'s' if photo_count != 1 else ''}.")
        if has_location:
            parts.append("Shared current location.")
        return " ".join(parts) or "Shared complaint context."

    def _derive_title(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return "New complaint"
        words = cleaned.split(" ")[:8]
        title = " ".join(words).rstrip(".?!")
        if not title:
            return "New complaint"
        return title[0].upper() + title[1:]

    def _looks_like_issue_description(self, text: str) -> bool:
        cleaned = (text or "").strip()
        if len(cleaned) < 10:
            return False

        lower = cleaned.lower()
        question_starters = (
            "what ",
            "how ",
            "when ",
            "where ",
            "why ",
            "who ",
            "can ",
            "could ",
            "should ",
            "is ",
            "are ",
            "will ",
            "do ",
            "does ",
            "did ",
            "which ",
        )
        explicit_complaint_phrases = (
            "create complaint",
            "submit complaint",
            "file complaint",
            "report complaint",
            "create issue",
            "submit issue",
            "file issue",
            "report issue",
            "lodge complaint",
            "register complaint",
        )
        if (lower.endswith("?") or lower.startswith(question_starters)) and not any(
            phrase in lower for phrase in explicit_complaint_phrases
        ):
            return False

        generic_phrases = {
            "create complaint",
            "submit complaint",
            "create issue",
            "submit issue",
            "help me",
            "hi",
            "hello",
        }
        return lower not in generic_phrases

    def _load_draft(self, session: ChatSession) -> ComplaintDraft:
        if not session.draft_json:
            return ComplaintDraft()
        try:
            return ComplaintDraft.model_validate_json(session.draft_json)
        except ValidationError:
            return ComplaintDraft()

    def _draft_response(self, draft: ComplaintDraft) -> ComplaintDraftResponse:
        return ComplaintDraftResponse(
            title=draft.title,
            description=draft.description,
            location=draft.location,
            photo_keys=draft.photo_keys,
            ready_to_submit=draft.ready_to_submit,
            submitted_issue_id=draft.submitted_issue_id,
        )

    def _message_to_openai_payload(self, message: Any) -> dict[str, str]:
        role_map = {"human": "user", "ai": "assistant", "system": "system"}
        return {
            "role": role_map.get(getattr(message, "type", "human"), "user"),
            "content": str(message.content),
        }

    def _message_to_response(self, message: ChatMessage) -> dict[str, Any]:
        meta = self._safe_json_loads(message.meta_json)
        photo_keys = meta.get("photo_keys", []) if isinstance(meta, dict) else []
        photo_urls = [
            signed_url
            for signed_url in [self.issue_service.get_photo_url(photo_key) for photo_key in photo_keys]
            if signed_url
        ]
        location = meta.get("location") if isinstance(meta, dict) else None
        tool_events = meta.get("tool_events", []) if isinstance(meta, dict) else []
        created_issue_id = meta.get("created_issue_id") if isinstance(meta, dict) else None
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "photo_keys": photo_keys,
            "photo_urls": photo_urls,
            "location": location,
            "tool_events": tool_events,
            "created_issue_id": created_issue_id,
            "created_at": message.created_at,
        }

    def _safe_json_loads(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}




