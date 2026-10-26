FROM python:3.11-slim
WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV COURSE_ROOT=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
COPY pyproject.toml MANIFEST.in README.md LICENSE streamlit_app.py ./
COPY .streamlit/ .streamlit/
COPY src/ src/
COPY models/ models/
COPY data/raw/ data/raw/
COPY input/ input/
COPY tests/ tests/
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 assistant \
    && mkdir -p /app/data/db /app/output \
    && chown -R assistant:assistant /app
USER assistant
RUN course-assistant build-kb
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('STREAMLIT_SERVER_PORT', '8501') + '/_stcore/health', timeout=3).read()"]
CMD ["course-assistant-workflow"]
