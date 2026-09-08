# --- Build stage ----------------------------------------------------------
# Node version tracks .nvmrc at the repository root.
FROM node:24-alpine AS build

WORKDIR /build

# npm ci needs both files and nothing else, so a dependency install is cached
# independently of every source change.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public

RUN npm run build

# --- Runtime stage --------------------------------------------------------
# The unprivileged image runs as uid 101 and defaults to port 8080, which is
# what Cloud Run expects. The runtime carries no Node, no sources and no
# secrets: only the compiled bundle and this config.
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime

# Substituted into nginx.conf at container start. Restricting the filter to
# the API_ prefix is what keeps nginx's own $variables — $uri, $host,
# $request_uri — from being eaten by envsubst.
ENV NGINX_ENVSUBST_FILTER='^API_'
# Docker's embedded DNS. A deployment on another platform overrides it; see the
# comment in nginx.conf for why a resolver is required at all.
ENV API_DNS_RESOLVER=127.0.0.11

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 8080
