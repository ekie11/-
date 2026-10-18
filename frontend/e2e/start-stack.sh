#!/usr/bin/env bash
# Поднимает API + RQ-воркер + Redis для сквозных тестов; при выходе всё убирает.
set -euo pipefail

PYTHON="${PYTHON:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
PIDS=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 143' INT TERM

REDIS_PORT="$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"

# Фиктивный soffice: последний аргумент — DOCX, рядом кладём минимальный PDF.
cat > "$TMP/soffice" <<'SOFFICE'
#!/usr/bin/env bash
out=""; prev=""; src=""
for a in "$@"; do
  [ "$prev" = "--outdir" ] && out="$a"
  prev="$a"; src="$a"
done
stem="$(basename "${src%.*}")"
printf '%%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%%%EOF\n' > "$out/$stem.pdf"
SOFFICE
chmod +x "$TMP/soffice"

export DATABASE_URL="sqlite:///$TMP/e2e.db"
export REDIS_URL="redis://127.0.0.1:$REDIS_PORT/0"
export STORAGE_DIR="$TMP/storage"
export COOKIE_SECURE=false
export SOFFICE_PATH="$TMP/soffice"
export JOB_TIMEOUT_S=60

# Заглушка модели для извлечения требований из методички.
LLM_PORT="$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
"$PYTHON" "$ROOT/frontend/e2e/fake_llm.py" "$LLM_PORT" &
PIDS+=("$!")
export LLM_BASE_URL="http://127.0.0.1:$LLM_PORT"
export LLM_API_KEY="e2e-dummy-key"
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

redis-server --port "$REDIS_PORT" --bind 127.0.0.1 --save "" --appendonly no --dir "$TMP" >"$TMP/redis.log" 2>&1 &
REDIS_PID=$!
PIDS+=("$REDIS_PID")

ready=0
for _ in $(seq 1 100); do
  kill -0 "$REDIS_PID" 2>/dev/null || break
  if "$PYTHON" -c 'import socket,sys; socket.create_connection(("127.0.0.1", int(sys.argv[1])), 0.2).close()' "$REDIS_PORT" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 0.1
done
if [ "$ready" != 1 ]; then
  echo "Redis не запустился на порту $REDIS_PORT:" >&2
  cat "$TMP/redis.log" >&2
  exit 1
fi

cd "$ROOT/backend"
"$PYTHON" -m gostdoc_api migrate
"$PYTHON" -m gostdoc_api serve --host 127.0.0.1 --port 8000 &
PIDS+=("$!")
"$PYTHON" -m gostdoc_api worker &
PIDS+=("$!")

# Выходим, как только любой из процессов умер (cleanup уберёт остальные).
wait -n || true
echo "Один из процессов стека завершился, останавливаем всё" >&2
cat "$TMP/redis.log" >&2 || true
exit 1
