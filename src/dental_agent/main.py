from fastapi import FastAPI

from dental_agent.api import router

app = FastAPI(title="Dental Agent")

app.include_router(router)