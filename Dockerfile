FROM node:22-alpine AS frontend
WORKDIR /web
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --fetch-timeout=60000 --fetch-retries=2
COPY Frontend/ ./
ENV VITE_API_URL=
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    ENVIRONMENT=production \
    FRONTEND_DIST=/app/Frontend/dist

COPY Backend/requirements.txt /app/Backend/requirements.txt
RUN pip install --no-cache-dir -r /app/Backend/requirements.txt

COPY Backend/app /app/Backend/app
COPY --from=frontend /web/dist /app/Frontend/dist

WORKDIR /app/Backend
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health' % os.environ.get('PORT','8080'))"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
