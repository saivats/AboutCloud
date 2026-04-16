import uuid
import time
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.core.config import get_settings
from backend.core.database import init_db, close_db
from backend.api.routes.auth import router as auth_router
from backend.api.routes.metrics import router as metrics_router
from backend.api.routes.anomalies import router as anomalies_router
from backend.api.routes.health import router as health_router
from backend.api.routes.admin import router as admin_router
from backend.api.routes.ws import router as ws_router

logger = structlog.get_logger("aboutcloud.api")

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])


@asynccontextmanager
async def lifespan(application: FastAPI):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_config().get("min_level", 0)
        ),
    )
    await logger.ainfo("starting_aboutcloud", version=settings.VERSION)
    try:
        await init_db()
        await logger.ainfo("database_initialized")
    except Exception as exc:
        await logger.aerror("database_init_failed", error=str(exc))
    yield
    await close_db()
    await logger.ainfo("aboutcloud_shutdown")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Multi-tenant cloud anomaly analytics platform",
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()

        response: Response = await call_next(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Latency-Ms"] = str(latency_ms)

        structlog.get_logger("aboutcloud.access").info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )

        return response

    application.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
    application.include_router(metrics_router, prefix=f"{settings.API_V1_PREFIX}/metrics", tags=["metrics"])
    application.include_router(anomalies_router, prefix=f"{settings.API_V1_PREFIX}/anomalies", tags=["anomalies"])
    application.include_router(health_router, prefix=f"{settings.API_V1_PREFIX}/health", tags=["health"])
    application.include_router(admin_router, prefix=f"{settings.API_V1_PREFIX}/admin", tags=["admin"])
    application.include_router(ws_router, prefix=f"{settings.API_V1_PREFIX}/ws", tags=["websocket"])

    @application.get("/", include_in_schema=False)
    async def root():
        return {"service": settings.PROJECT_NAME, "version": settings.VERSION, "status": "running"}

    return application


app = create_app()
