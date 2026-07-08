from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.data_flow.websocket import router as dashboard_ws_router
from app.data_flow.zmq_listener import zmq_dashboard_listener


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DATA_SOURCE == "zmq":
        zmq_dashboard_listener.start()
    try:
        yield
    finally:
        if settings.DATA_SOURCE == "zmq":
            await zmq_dashboard_listener.stop()


app = FastAPI(
    title="Track Simulation API",
    description="Power / vehicle / track / signal simulation backend API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(dashboard_ws_router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "data_source": settings.DATA_SOURCE}

