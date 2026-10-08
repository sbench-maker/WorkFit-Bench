from fastapi import FastAPI
from rosterly.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Rosterly API")
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
