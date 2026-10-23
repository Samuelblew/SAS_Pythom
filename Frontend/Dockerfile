FROM node:22-alpine AS build
WORKDIR /web
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --fetch-timeout=60000 --fetch-retries=2
COPY Frontend/ ./
ENV VITE_API_URL=
RUN npm run build

FROM nginx:stable-alpine
COPY Frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
