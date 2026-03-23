import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.enums import UserRoleEnum
from app.models.issue import Issue
from app.models.user import User
from app.services.ai.cerebras_client import CerebrasClient
from app.services.community_service import CommunityService
from app.services.issue_service import IssueService
from app.services.resource_service import ResourceService
from app.services.user_service import has_role


class AgentState(TypedDict):
    message: str
    tool_name: str | None
    tool_args: dict[str, Any]
    tool_result: Any
    reply: str


class AssistantAgent:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user
        self.cerebras = CerebrasClient()
        self.graph = self._build_graph()

    def run(self, message: str) -> dict[str, Any]:
        state: AgentState = {
            "message": message,
            "tool_name": None,
            "tool_args": {},
            "tool_result": None,
            "reply": "",
        }
        return self.graph.invoke(state)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan", self._plan)
        graph.add_node("execute", self._execute)
        graph.add_node("respond", self._respond)

        graph.set_entry_point("plan")
        graph.add_edge("plan", "execute")
        graph.add_edge("execute", "respond")
        graph.add_edge("respond", END)
        return graph.compile()

    def _plan(self, state: AgentState) -> AgentState:
        message = state["message"].strip()
        plan = self._plan_with_llm(message) if self.cerebras.enabled else None
        if not plan:
            plan = self._plan_with_rules(message)

        state["tool_name"] = plan.get("tool")
        state["tool_args"] = plan.get("args", {})
        if plan.get("tool") is None:
            state["reply"] = plan.get("answer", "I can help with resources, posts, comments, votes, and issues.")
        return state

    def _execute(self, state: AgentState) -> AgentState:
        tool_name = state.get("tool_name")
        if not tool_name:
            return state

        try:
            result = self._run_tool(tool_name, state.get("tool_args", {}))
            state["tool_result"] = result
        except Exception as exc:  # keep agent resilient
            state["tool_result"] = {"error": str(exc)}
        return state

    def _respond(self, state: AgentState) -> AgentState:
        if state.get("reply"):
            return state

        tool = state.get("tool_name")
        result = state.get("tool_result")

        if isinstance(result, dict) and "error" in result:
            state["reply"] = f"I couldn't complete `{tool}`: {result['error']}"
            return state

        state["reply"] = f"Done. I used `{tool}` successfully."
        return state

    def _plan_with_llm(self, message: str) -> dict[str, Any] | None:
        system_prompt = (
            "You are a civic platform assistant. Choose exactly one tool and return strict JSON with keys: "
            "tool, args, answer. If no tool is needed, tool must be null and provide answer. "
            "Available tools: list_resources, create_post, list_posts, create_comment, "
            "vote_post, vote_comment, create_issue, my_issues, create_resource, list_departments."
        )
        user_prompt = (
            f"User message: {message}\n"
            "For create_post use args {title, body, image_keys?}. "
            "For create_issue use {description, lat, lng, photo_key?}. "
            "For create_resource use {title, link_url, thumbnail_url?, department_id?}."
        )

        try:
            result = self.cerebras.chat(system_prompt=system_prompt, user_prompt=user_prompt)
            return json.loads(result.content)
        except Exception:
            return None

    def _plan_with_rules(self, message: str) -> dict[str, Any]:
        text = message.lower()

        if "list departments" in text or "show departments" in text:
            return {"tool": "list_departments", "args": {}}

        if "resource" in text and any(w in text for w in ["list", "show", "fetch"]):
            return {"tool": "list_resources", "args": {}}

        if "my issues" in text or "show my issues" in text:
            return {"tool": "my_issues", "args": {}}

        if "list posts" in text or "show posts" in text:
            return {"tool": "list_posts", "args": {"sort": "hot"}}

        post_match = re.search(r"create post\s+title:(.+?)\s+body:(.+)", message, re.IGNORECASE | re.DOTALL)
        if post_match:
            return {
                "tool": "create_post",
                "args": {"title": post_match.group(1).strip(), "body": post_match.group(2).strip(), "image_keys": []},
            }

        comment_match = re.search(r"comment\s+post_id:(\d+)\s+body:(.+)", message, re.IGNORECASE | re.DOTALL)
        if comment_match:
            return {
                "tool": "create_comment",
                "args": {"post_id": int(comment_match.group(1)), "body": comment_match.group(2).strip()},
            }

        issue_match = re.search(r"create issue\s+lat:([-\d.]+)\s+lng:([-\d.]+)\s+description:(.+)", message, re.IGNORECASE | re.DOTALL)
        if issue_match:
            return {
                "tool": "create_issue",
                "args": {
                    "lat": float(issue_match.group(1)),
                    "lng": float(issue_match.group(2)),
                    "description": issue_match.group(3).strip(),
                },
            }

        resource_match = re.search(r"create resource\s+title:(.+?)\s+link:(.+?)(?:\s+department_id:(\d+))?$", message, re.IGNORECASE)
        if resource_match:
            args: dict[str, Any] = {
                "title": resource_match.group(1).strip(),
                "link_url": resource_match.group(2).strip(),
            }
            if resource_match.group(3):
                args["department_id"] = int(resource_match.group(3))
            return {"tool": "create_resource", "args": args}

        return {
            "tool": None,
            "answer": (
                "I can do actions for you. Examples: "
                "`list resources`, `list posts`, `show my issues`, "
                "`create post title:... body:...`, "
                "`comment post_id:12 body:...`, "
                "`create issue lat:12.9 lng:77.5 description:...`, "
                "`create resource title:... link:... department_id:1`."
            ),
        }

    def _run_tool(self, tool: str, args: dict[str, Any]) -> Any:
        if tool == "list_resources":
            return self._tool_list_resources(args)
        if tool == "create_post":
            return self._tool_create_post(args)
        if tool == "list_posts":
            return self._tool_list_posts(args)
        if tool == "create_comment":
            return self._tool_create_comment(args)
        if tool == "vote_post":
            return self._tool_vote_post(args)
        if tool == "vote_comment":
            return self._tool_vote_comment(args)
        if tool == "create_issue":
            return self._tool_create_issue(args)
        if tool == "my_issues":
            return self._tool_my_issues()
        if tool == "create_resource":
            return self._tool_create_resource(args)
        if tool == "list_departments":
            return self._tool_list_departments()
        raise ValueError(f"Unknown tool: {tool}")

    def _tool_list_resources(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        service = ResourceService(self.db)
        department_id = args.get("department_id")
        resources = service.list_resources(department_id=department_id)
        return [
            {
                "id": r.id,
                "title": r.title,
                "link_url": r.link_url,
                "thumbnail_url": r.thumbnail_url,
                "department_id": r.department_id,
            }
            for r in resources[:20]
        ]

    def _tool_create_post(self, args: dict[str, Any]) -> dict[str, Any]:
        service = CommunityService(self.db)
        post = service.create_post(
            author_id=self.user.id,
            title=args["title"],
            body=args["body"],
            image_keys=args.get("image_keys", []),
        )
        return {"post_id": post.id, "title": post.title, "score": post.score}

    def _tool_list_posts(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        service = CommunityService(self.db)
        posts = service.list_posts(sort=args.get("sort", "hot"))
        return [{"id": p.id, "title": p.title, "score": p.score, "comment_count": p.comment_count} for p in posts[:20]]

    def _tool_create_comment(self, args: dict[str, Any]) -> dict[str, Any]:
        service = CommunityService(self.db)
        comment = service.create_comment(
            post_id=int(args["post_id"]),
            author_id=self.user.id,
            body=args["body"],
            parent_comment_id=args.get("parent_comment_id"),
        )
        return {"comment_id": comment.id, "post_id": comment.post_id}

    def _tool_vote_post(self, args: dict[str, Any]) -> dict[str, Any]:
        service = CommunityService(self.db)
        vote = service.vote_post(post_id=int(args["post_id"]), user_id=self.user.id, value=int(args["value"]))
        return {"score": vote.score, "user_vote": vote.user_vote}

    def _tool_vote_comment(self, args: dict[str, Any]) -> dict[str, Any]:
        service = CommunityService(self.db)
        vote = service.vote_comment(comment_id=int(args["comment_id"]), user_id=self.user.id, value=int(args["value"]))
        return {"score": vote.score, "user_vote": vote.user_vote}

    def _tool_create_issue(self, args: dict[str, Any]) -> dict[str, Any]:
        issue = IssueService(self.db).create_issue(
            reporter_id=self.user.id,
            description=args["description"],
            lat=float(args["lat"]),
            lng=float(args["lng"]),
            photo_key=args.get("photo_key"),
        )
        return {
            "issue_id": issue.id,
            "department_id": issue.department_id,
            "priority_level": issue.priority_level,
            "cluster_id": issue.cluster_id,
        }

    def _tool_my_issues(self) -> list[dict[str, Any]]:
        issues = IssueService(self.db).list_user_issues(self.user.id)
        return [
            {
                "id": i.id,
                "status": i.status,
                "priority_level": i.priority_level,
                "department_id": i.department_id,
                "created_at": i.created_at.isoformat(),
            }
            for i in issues[:20]
        ]

    def _tool_create_resource(self, args: dict[str, Any]) -> dict[str, Any]:
        is_main_admin = has_role(self.user, UserRoleEnum.MAIN_ADMIN)
        department_id = args.get("department_id")

        if is_main_admin:
            role = UserRoleEnum.MAIN_ADMIN.value
        else:
            if department_id is None:
                raise PermissionError("Department admin must provide department_id")
            if not has_role(self.user, UserRoleEnum.DEPARTMENT_ADMIN, department_id=int(department_id)):
                raise PermissionError("Not allowed to publish for this department")
            role = UserRoleEnum.DEPARTMENT_ADMIN.value

        resource = ResourceService(self.db).create_resource(
            title=args["title"],
            link_url=args["link_url"],
            thumbnail_url=args.get("thumbnail_url"),
            department_id=department_id,
            created_by_user_id=self.user.id,
            created_by_role=role,
        )
        return {"resource_id": resource.id, "title": resource.title}

    def _tool_list_departments(self) -> list[dict[str, Any]]:
        rows = self.db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name.asc())).all()
        return [{"id": d.id, "name": d.name, "description": d.description} for d in rows]
