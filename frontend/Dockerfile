FROM node:24-alpine

ARG UID=1000 \
    GID=1000

ENV NODE_ENV=development \
    HOME=/home/app \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false

SHELL ["/bin/sh", "-eo", "pipefail", "-c"]

WORKDIR /app

RUN mkdir -p "${HOME}/.npm" /app \
    && chown -R "${UID}:${GID}" "${HOME}" /app

USER ${UID}:${GID}

COPY --chown=${UID}:${GID} package.json package-lock.json ./

RUN --mount=type=cache,target=/home/app/.npm,uid=${UID},gid=${GID} \
    npm ci

COPY --chown=${UID}:${GID} . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
