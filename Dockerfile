FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml README.md ./
COPY src ./src
COPY apps ./apps
COPY config ./config
COPY fixtures ./fixtures
COPY scripts ./scripts
COPY docs ./docs
COPY contracts/src ./contracts/src
COPY agent-studio ./agent-studio
COPY evidence ./evidence
COPY deployments ./deployments
COPY submission ./submission
COPY templates ./templates
RUN pip install --no-cache-dir .
RUN mkdir -p /app/.data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
