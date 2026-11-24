from fastapi import FastAPI

from dental_agent.api import router
from dental_agent.tracing import setup_tracing

setup_tracing()
app = FastAPI(title="Dental Agent")

app.include_router(router)
