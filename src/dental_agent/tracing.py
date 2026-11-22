from opentelemetry import trace

from dental_agent.config import settings

tracer = trace.get_tracer("dental_agent")


def setup_tracing() -> None:
    if not settings.phoenix_endpoint:
        return
    from phoenix.otel import register

    register(
        project_name="dental-agent",
        endpoint=settings.phoenix_endpoint,
        auto_instrument=True,
    )
