if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|\#*) continue ;; esac
        key=${line%%=*}
        if [ -z "$(printenv "$key")" ]; then
            eval "export $line"
        fi
    done < .env
fi
exec python -m uvicorn app_final:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}"
