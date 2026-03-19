from fastapi import FastAPI

from middlewares.auth import auth_middleware


def setup_middlewares(app: FastAPI) -> None:
    app.middleware("http")(auth_middleware)
