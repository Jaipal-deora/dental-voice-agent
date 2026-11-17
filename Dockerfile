FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project 
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic 
RUN uv sync --frozen --no-dev 

FROM python:3.13-slim 
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && python -m dental_agent.seed && uvicorn dental_agent.main:app --host 0.0.0.0 --port 8000"]