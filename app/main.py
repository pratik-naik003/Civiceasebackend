from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.db import base  # noqa: F401
from app.db.session import engine

app = FastAPI(title="CivicEase Backend", version="0.1.0")
app.include_router(v1_router)


@app.on_event("startup")
def create_tables_on_startup() -> None:
    # Creates missing tables only; existing schema changes are not auto-migrated.
    base.Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
