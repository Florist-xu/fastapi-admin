# fastapi-admin

## Docker 一键部署

Docker 打包和一键部署说明见 [docker/README.md](docker/README.md)。

一个基于 FastAPI + Tortoise ORM + MySQL 的后台服务示例，包含用户、角色、权限与登录鉴权能力。

## 环境要求

- Python 3.10+
- MySQL 8.x

## 安装依赖

```bash
pip install -r requirements.txt
```

## 数据库配置

数据库连接在 [config.py](e:/test/fastapi/fastapi-admin/config.py) 的 `TORTOISE_ORM` 中配置：

- `host`
- `port`
- `user`
- `password`
- `database`

请按你的本地环境修改后再启动。

## 启动项目

```bash
uvicorn main:app --reload
```

启动后可访问：

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 主要接口

- `POST /auth/login` 登录
- `POST /auth/refresh` 刷新 token
- `GET /auth/info` 获取当前用户信息（含角色和按钮权限）
- `GET /user/list` 用户列表
- `POST /user/add` 新增用户
- `POST /user/update` 修改用户
- `POST /user/delete` 删除用户
- `GET /role/list` 角色列表

## 权限说明（当前实现）

`/auth/info` 返回模板保持固定，`buttons` 联动数据库计算：

1. 根据登录用户查 `system_user_role`
2. 根据角色 ID 查 `system_role.role_code`
3. 根据角色编码查 `casbin_rule`（`ptype='p'` 且 `v2='button'`）
4. 使用 `v1` 匹配 `system_permission`（`id/path/api_path`）
5. 提取按钮码（优先 `authMark`），去重后返回 `buttons`
