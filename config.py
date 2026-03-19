TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": "127.0.0.1",
                "port": 3306,
                "user": "root",
                "password": "heavin0422",
                "database": "fva",
                "maxsize": 10,
                "minsize": 1,
                "charset": "utf8mb4",
                "echo": True,
            },
        }
    },
    "apps": {
        "system": {
            "models": ["models"],
            "default_connection": "default",
        }
    },
    # 使用本地时间直接入库（不进行 UTC 转换）
    "use_tz": False,
    "timezone": "Asia/Shanghai",
}
