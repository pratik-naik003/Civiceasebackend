from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.v1.router import router as v1_router
from app.db import base  # noqa: F401
from app.db.session import engine

app = FastAPI(title="CivicEase Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.on_event("startup")
def create_tables_on_startup() -> None:
    # Creates missing tables only; existing schema changes are not auto-migrated.
    base.Base.metadata.create_all(bind=engine)
    _ensure_issue_assignment_columns()


def _ensure_issue_assignment_columns() -> None:
    inspector = inspect(engine)
    column_names = {column["name"] for column in inspector.get_columns("issues")}
    with engine.begin() as conn:
        if "assigned_person_id" not in column_names:
            conn.execute(text("ALTER TABLE issues ADD COLUMN assigned_person_id INTEGER"))
        if "assigned_person_name" not in column_names:
            conn.execute(text("ALTER TABLE issues ADD COLUMN assigned_person_name VARCHAR(120)"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
