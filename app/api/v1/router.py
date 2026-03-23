from fastapi import APIRouter

from app.api.v1.routes import agent, clusters, community, departments, issues, resources

router = APIRouter(prefix="/v1")
router.include_router(issues.router, tags=["issues"])
router.include_router(departments.router, tags=["departments"])
router.include_router(clusters.router, tags=["clusters"])
router.include_router(community.router, tags=["community"])
router.include_router(resources.router, tags=["resources"])
router.include_router(agent.router, tags=["agent"])
