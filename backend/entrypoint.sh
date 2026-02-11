#!/bin/sh

set -eu

entrypoint_mode="${ENTRYPOINT_MODE:-backend}"

if [ "${entrypoint_mode}" = "ollama" ]; then
  model_name="${OLLAMA_BOOT_MODEL:-qwen2.5:1.5b}"

  ollama serve &
  ollama_pid="$!"

  cleanup() {
    kill "${ollama_pid}" >/dev/null 2>&1 || true
  }

  trap cleanup EXIT INT TERM

  is_ready=false
  for _ in $(seq 1 60); do
    if ollama list >/dev/null 2>&1; then
      is_ready=true
      break
    fi
    sleep 1
  done

  if [ "${is_ready}" != "true" ]; then
    echo "Ollama API is not ready after 60 seconds."
    exit 1
  fi

  echo "Pulling boot model: ${model_name}"
  ollama pull "${model_name}"
  wait "${ollama_pid}"
  exit 0
fi

alembic upgrade head

exec "$@"
