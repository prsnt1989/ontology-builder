# Ontology Builder — Frontend (Vite build → nginx static + /api reverse proxy)
# Build context is the repo root:  docker build -f docker/frontend/Dockerfile .

# ── Stage 1: build the static assets ──────────────────────────────────────────
FROM --platform=linux/amd64 node:20-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: serve via nginx, proxying /api to the backend ─────────────────────
FROM --platform=linux/amd64 nginx:1.27-alpine

# nginx.conf is a TEMPLATE — backend host/port + the DNS resolver are substituted
# at container start so Azure Container Apps' rotating internal IPs re-resolve.
COPY docker/frontend/nginx.conf /etc/nginx/nginx.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# Defaults match docker-compose service DNS; overridden per-environment in deploy.sh.
ENV BACKEND_HOST=backend
ENV BACKEND_PORT=8005

EXPOSE 80

CMD ["/bin/sh", "-c", "export DNS_RESOLVER=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf) && envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${DNS_RESOLVER}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
