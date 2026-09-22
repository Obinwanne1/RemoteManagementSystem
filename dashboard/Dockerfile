FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user. app.py and utils/styles.py write generated CSS to
# ./static at runtime, so that directory (and Streamlit's own config/cache
# dirs, which live under $HOME) must be owned by this user.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/static \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)"

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
