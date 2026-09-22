FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user. Runtime write paths (screenshots, reports, backups — see
# routes/agents.py, tasks/report_tasks.py, tasks/backup_tasks.py) must be
# owned by this user; BACKUP_DIR is pinned to /app/backups in docker-compose.yml
# so the default "../backups" (which would resolve outside /app) is never used.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/screenshots /app/reports /app/backups \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health', timeout=3)"

CMD ["python", "app.py"]
