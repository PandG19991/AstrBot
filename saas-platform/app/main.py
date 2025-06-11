"""
AstrBot SaaS Platform - FastAPI应用主入口

这是SaaS平台的FastAPI应用主入口文件，包含应用初始化和路由配置。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AstrBot多租户智能客服SaaS平台",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """根路径健康检查"""
    return {
        "message": "AstrBot SaaS Platform API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "astrbot-saas-platform"} 