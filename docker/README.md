# Docker API Deployment

This setup only runs the FastAPI service in Docker.
MySQL stays on the host machine.

## Files

- `docker-compose.yml`: runs the API container only
- `Dockerfile`: builds the backend image
- `docker/app.env.example`: API environment template
- `docker/deploy.ps1`: one-click deploy for Windows
- `docker/deploy.sh`: one-click deploy for Linux/macOS

## First Run

Windows:

```powershell
.\docker\deploy.ps1
```

Linux / macOS:

```bash
chmod +x ./docker/deploy.sh
./docker/deploy.sh
```

The script creates:

- `docker/app.env`

Only `docker/app.env` is used now. Any old `docker/mysql.env` file can be removed.

## Database Settings

Default database host:

```env
DB_HOST=host.docker.internal
```

This lets the container connect to MySQL running on the host.

If the API still cannot connect, check these items on the host MySQL side:

- MySQL is listening on a reachable address, not only a blocked local socket setup
- The MySQL user has permission to connect from Docker
- Port `3306` is open locally and not blocked by firewall rules

## Common Commands

Windows:

```powershell
.\docker\deploy.ps1 -Logs
.\docker\deploy.ps1 -Down
```

Linux / macOS:

```bash
./docker/deploy.sh logs
./docker/deploy.sh down
```

## URL

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Persistent Data

These paths are persisted with Docker volumes:

- `uplode`
- `runtime_modules/packages`
- `runtime_modules/_uploads`
