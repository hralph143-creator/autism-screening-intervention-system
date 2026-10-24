import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api import auth, children, dashboard, health, system
from .core.config import settings
from .core.database import initialize_database

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database(); logger.info("服务已启动，运行模式：%s", settings.environment)
    yield
    logger.info("服务已停止")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.frontend_origins), allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(children.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    message = exc.errors()[0].get("msg", "请求参数不正确") if exc.errors() else "请求参数不正确"
    return JSONResponse(status_code=422, content={"detail": message.replace("Value error, ", "")})


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, exc: Exception):
    logger.exception("未处理的服务异常：%s", exc)
    return JSONResponse(status_code=500, content={"detail": "服务器处理请求时发生错误"})
