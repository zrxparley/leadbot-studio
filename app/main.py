from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.studio_routes import router as studio_router
from app.core.config import get_settings
from app.core.scheduler import scheduler_service
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    """FastAPI 应用生命周期管理函数
    
    该函数用于管理 FastAPI 应用的启动和关闭过程，主要执行以下操作：
    1. 初始化数据库连接
    2. 获取应用配置设置
    3. 根据配置启动调度器服务（如果启用）
    4. 应用运行期间保持活动状态
    5. 应用关闭时停止调度器服务
    
    Args:
        _: FastAPI 实例（未使用，仅作为函数签名要求）
    
    Yields:
        None: 生成控制流，分隔启动和关闭逻辑
    """
    # 初始化数据库
    init_db()
    
    # 获取应用配置
    settings = get_settings()
    
    # 如果启用了调度器，启动调度器服务
    if settings.enable_scheduler:
        scheduler_service.start()
    
    # 生成控制流，应用开始运行
    yield
    
    # 应用关闭时，停止调度器服务
    scheduler_service.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.include_router(router)
    application.include_router(studio_router)
    application.mount("/static", StaticFiles(directory="app/static"), name="static")
    return application


app = create_app()
