set -a
[ -f .env ] && . ./.env
set +a
exec python -m uvicorn app_final:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}"
