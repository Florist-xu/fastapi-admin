import os

from dotenv import load_dotenv


load_dotenv()


TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": os.getenv("DB_HOST", "127.0.0.1"),
                "port": int(os.getenv("DB_PORT", "3306")),
                "user": os.getenv("DB_USER", "root"),
                "password": os.getenv("DB_PASSWORD", ""),
                "database": os.getenv("DB_NAME", "fva"),
                "maxsize": int(os.getenv("DB_MAXSIZE", "10")),
                "minsize": int(os.getenv("DB_MINSIZE", "1")),
                "charset": "utf8mb4",
                "echo": os.getenv("DB_ECHO", "true").lower() == "true",
            },
        }
    },
    "apps": {
        "system": {
            "models": ["models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "timezone": "Asia/Shanghai",
}
