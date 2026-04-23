#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
APP_ENV="$SCRIPT_DIR/app.env"

ensure_env_file() {
  target=$1
  example=$2
  if [ ! -f "$target" ]; then
    cp "$example" "$target"
    echo "Generated $(basename "$target"). Update passwords before public deployment."
  fi
}

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found. Please install Docker first." >&2
  exit 1
fi

ensure_env_file "$APP_ENV" "$SCRIPT_DIR/app.env.example"

cd "$PROJECT_ROOT"

case "${1:-up}" in
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f app
    ;;
  up)
    docker compose up -d --build
    echo "App docs: http://127.0.0.1:8000/docs"
    ;;
  *)
    echo "Usage: ./docker/deploy.sh [up|down|logs]" >&2
    exit 1
    ;;
esac
