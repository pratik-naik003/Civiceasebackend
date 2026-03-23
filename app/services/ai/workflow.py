from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cluster import ClusterMember, IssueCluster
from app.models.department import Department
from app.models.issue import Issue
from app.services.ai.service import AIService
from app.services.ai.similarity import haversine_meters, text_similarity


class AIState(TypedDict):
    issue_id: int
    description: str
    latitude: float
    longitude: float
    routed_department_id: int | None
    routing_reason: str | None
    routing_confidence: float | None
    priority_score: float
    priority_level: str
    priority_reason: str
    cluster_id: int | None
    cluster_similarity: float
    model: str


class AIWorkflow:
    def __init__(self, db: Session, ai_service: AIService | None = None) -> None:
        self.db = db
        self.ai_service = ai_service or AIService()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AIState)
        graph.add_node("route_department", self._route_department)
        graph.add_node("score_priority", self._score_priority)
        graph.add_node("cluster_match", self._cluster_match)

        graph.set_entry_point("route_department")
        graph.add_edge("route_department", "score_priority")
        graph.add_edge("score_priority", "cluster_match")
        graph.add_edge("cluster_match", END)
        return graph.compile()

    def run(self, issue: Issue) -> AIState:
        initial: AIState = {
            "issue_id": issue.id,
            "description": issue.description,
            "latitude": issue.latitude,
            "longitude": issue.longitude,
            "routed_department_id": None,
            "routing_reason": None,
            "routing_confidence": None,
            "priority_score": 0.5,
            "priority_level": "p2",
            "priority_reason": "",
            "cluster_id": None,
            "cluster_similarity": 0.0,
            "model": "fallback",
        }
        return self.graph.invoke(initial)

    def _route_department(self, state: AIState) -> AIState:
        departments = self.db.scalars(select(Department).where(Department.is_active.is_(True))).all()
        payload = [{"id": d.id, "name": d.name, "description": d.description} for d in departments]
        route = self.ai_service.route_department(state["description"], payload)

        matched = next((d for d in departments if d.name.lower() == route.department_name.lower()), None)
        if not matched and departments:
            matched = departments[0]

        state["routed_department_id"] = matched.id if matched else None
        state["routing_reason"] = route.reason
        state["routing_confidence"] = route.confidence
        state["model"] = route.model
        return state

    def _score_priority(self, state: AIState) -> AIState:
        priority = self.ai_service.score_priority(state["description"])
        state["priority_score"] = priority.score
        state["priority_level"] = priority.level
        state["priority_reason"] = priority.reason
        state["model"] = priority.model
        return state

    def _cluster_match(self, state: AIState) -> AIState:
        issue_id = state["issue_id"]
        lat = state["latitude"]
        lng = state["longitude"]
        description = state["description"]

        candidates = self.db.scalars(select(IssueCluster)).all()
        best_cluster = None
        best_similarity = 0.0

        for cluster in candidates:
            geo_distance = haversine_meters(lat, lng, cluster.centroid_latitude, cluster.centroid_longitude)
            if geo_distance > settings.cluster_geo_threshold_meters:
                continue

            similarity = text_similarity(description, cluster.representative_text)
            if similarity >= settings.cluster_text_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster

        if best_cluster:
            best_cluster.affected_count += 1
            issue = self.db.get(Issue, issue_id)
            issue.cluster_id = best_cluster.id
            self.db.add(ClusterMember(cluster_id=best_cluster.id, issue_id=issue_id, similarity_score=best_similarity))
            self.db.add(best_cluster)
            state["cluster_id"] = best_cluster.id
            state["cluster_similarity"] = best_similarity
            return state

        new_cluster = IssueCluster(
            centroid_latitude=lat,
            centroid_longitude=lng,
            representative_text=description,
            affected_count=1,
        )
        self.db.add(new_cluster)
        self.db.flush()

        issue = self.db.get(Issue, issue_id)
        issue.cluster_id = new_cluster.id
        self.db.add(ClusterMember(cluster_id=new_cluster.id, issue_id=issue_id, similarity_score=1.0))

        state["cluster_id"] = new_cluster.id
        state["cluster_similarity"] = 1.0
        return state
