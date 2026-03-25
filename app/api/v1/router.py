from fastapi import APIRouter

from app.api.v1.routes import agent, chatbot, clusters, community, departments, employee, issues, resources, users, voice

router = APIRouter(prefix="/v1")
router.include_router(issues.router, tags=["issues"])
router.include_router(departments.router, tags=["departments"])
router.include_router(employee.router, tags=["employee"])
router.include_router(chatbot.router, tags=["chatbot"])
router.include_router(clusters.router, tags=["clusters"])
router.include_router(community.router, tags=["community"])
router.include_router(resources.router, tags=["resources"])
router.include_router(agent.router, tags=["agent"])
router.include_router(users.router, tags=["users"])
router.include_router(voice.router, tags=["voice"])
