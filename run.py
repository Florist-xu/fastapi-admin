
import uvicorn


def load_uvicorn_settings() -> dict:
    settings = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True,
        "reload_dirs": ["./apis", "./models", "./utils", "./middlewares", "./fields"]
    }
    return settings


if __name__ == "__main__":
    uvicorn.run(**load_uvicorn_settings())
