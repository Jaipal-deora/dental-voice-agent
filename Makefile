run:
    uv sync
	uv run alembic upgrade head 
	uv run python -m dental_agent.seed 
	uv run uvicorn dental_agent.main:app --reload
test:
    uv run pytest --cov=dental_agent --cov-fail-under=80