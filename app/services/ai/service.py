import json
from dataclasses import dataclass

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:  # Backward compatibility for older LangChain releases
    from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, ValidationError

from app.services.ai.cerebras_client import CerebrasClient


class RouteOutput(BaseModel):
    department_name: str
    reason: str
    confidence: float = Field(ge=0, le=1)


class PriorityOutput(BaseModel):
    score: float = Field(ge=0, le=1)
    reason: str


@dataclass
class AIRouteResult:
    department_name: str
    reason: str
    confidence: float
    model: str


@dataclass
class AIPriorityResult:
    score: float
    level: str
    reason: str
    model: str


class AIService:
    def __init__(self) -> None:
        self.client = CerebrasClient()

        self.route_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You route municipal civic issues. Use only issue description text. Return strict JSON: department_name, reason, confidence."),
                (
                    "human",
                    "Issue description: {description}\nDepartments: {departments}",
                ),
            ]
        )
        self.priority_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You score civic issue urgency. Return strict JSON: score (0..1), reason."),
                ("human", "Issue description: {description}"),
            ]
        )

    def _priority_level(self, score: float) -> str:
        if score >= 0.85:
            return "p0"
        if score >= 0.65:
            return "p1"
        if score >= 0.4:
            return "p2"
        return "p3"

    def route_department(self, description: str, departments: list[dict]) -> AIRouteResult:
        if not departments:
            return AIRouteResult(department_name="", reason="No departments available", confidence=0.0, model="fallback")

        if not self.client.enabled:
            return AIRouteResult(
                department_name=departments[0]["name"],
                reason="Fallback route: first active department",
                confidence=0.35,
                model="fallback",
            )

        prompt_value = self.route_prompt.format_prompt(description=description, departments=json.dumps(departments)).to_messages()
        result = self.client.chat(system_prompt=prompt_value[0].content, user_prompt=prompt_value[1].content)
        try:
            parsed = RouteOutput.model_validate_json(result.content)
            return AIRouteResult(
                department_name=parsed.department_name,
                reason=parsed.reason,
                confidence=parsed.confidence,
                model=result.model,
            )
        except ValidationError:
            return AIRouteResult(
                department_name=departments[0]["name"],
                reason="Fallback route: malformed model response",
                confidence=0.3,
                model=result.model,
            )

    def score_priority(self, description: str) -> AIPriorityResult:
        fallback_score = 0.5
        if not self.client.enabled:
            level = self._priority_level(fallback_score)
            return AIPriorityResult(score=fallback_score, level=level, reason="Fallback priority", model="fallback")

        prompt_value = self.priority_prompt.format_prompt(description=description).to_messages()
        result = self.client.chat(system_prompt=prompt_value[0].content, user_prompt=prompt_value[1].content)

        try:
            parsed = PriorityOutput.model_validate_json(result.content)
            return AIPriorityResult(
                score=parsed.score,
                level=self._priority_level(parsed.score),
                reason=parsed.reason,
                model=result.model,
            )
        except ValidationError:
            level = self._priority_level(fallback_score)
            return AIPriorityResult(
                score=fallback_score,
                level=level,
                reason="Fallback priority: malformed model response",
                model=result.model,
            )
