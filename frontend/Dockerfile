# syntax=docker/dockerfile:1.7
ARG NODE_VERSION=22

# ---- build ----------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

# ---- runtime: static files + reverse proxy to the backend -----------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
ARG VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="agent-platform-frontend" \
      org.opencontainers.image.version="${VERSION}"
# nginx renders /etc/nginx/templates/*.template with envsubst at start-up.
ENV BACKEND_URL=http://backend:8000 \
    NGINX_ENVSUBST_FILTER=^BACKEND_URL$
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
