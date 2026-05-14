from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, experiments, health, projects, retrieve, runtime
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="RAG Lab API",
        version="0.1.0",
        description="Experiment workbench API for reproducible RAG testing.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(projects.router, prefix="/v1", tags=["projects"])
    app.include_router(runtime.router, prefix="/v1", tags=["runtime"])
    app.include_router(retrieve.router, prefix="/v1", tags=["retrieve"])
    app.include_router(ask.router, prefix="/v1", tags=["ask"])
    app.include_router(experiments.router, prefix="/v1", tags=["experiments"])

    return app


app = create_app()
