FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
# build-only skips vue-tsc. Images are built only from commits whose
# frontend-verify job in ci.yml already type-checked them: the channel
# images wait for it, and a release builds the merge commit of a release
# branch that had to contain main, so its tree is the one CI checked.
RUN npm run build-only

FROM nginx:stable-alpine@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
# The image's entrypoint runs every executable in /docker-entrypoint.d before
# nginx starts; this one writes the trusted proxy list nginx.conf includes.
# The empty file keeps nginx -t working without the entrypoint.
COPY --chmod=0755 docker/trusted-proxies.sh /docker-entrypoint.d/40-glados-trusted-proxies.sh
RUN mkdir -p /etc/nginx/glados && touch /etc/nginx/glados/trusted-proxies.conf
EXPOSE 80
