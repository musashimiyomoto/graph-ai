FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG UID=1000 \
    GID=1000

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    gcc \
    libpq-dev \
    python3-dev \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd -g "${GID}" -r web \
    && useradd -d '/app' -g web -l -r -u "${UID}" web \
    && chown web:web -R '/app'

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY --chown=web:web . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

COPY entrypoint.sh /docker-entrypoint.sh
RUN chmod +x '/docker-entrypoint.sh' \
    && sed -i 's/\r$//g' '/docker-entrypoint.sh'

ENTRYPOINT []

RUN mkdir -p /tmp/fastembed_cache && chown web:web /tmp/fastembed_cache

USER web
