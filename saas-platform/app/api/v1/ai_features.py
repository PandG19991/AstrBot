"""
智能功能API端点

提供自动回复、会话总结、客服话术推荐等AI智能功能的RESTful接口
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_tenant
from app.models.tenant import Tenant
from app.services.auto_reply_service import AutoReplyService
from app.services.session_summary_service import SessionSummaryService
from app.services.agent_suggestion_service import AgentSuggestionService
from app.schemas.common import StandardResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()


# 请求/响应模型
class AutoReplyRequest(BaseModel):
    """自动回复请求"""
    session_id: UUID = Field(..., description="会话ID")
    user_message: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")
    llm_config: Optional[Dict[str, Any]] = Field(None, description="LLM配置参数")
    system_prompt: Optional[str] = Field(None, max_length=1000, description="系统提示词")
    auto_save: bool = Field(True, description="是否自动保存消息到数据库")


class AutoReplyResponse(BaseModel):
    """自动回复响应"""
    reply_content: str = Field(..., description="生成的回复内容")
    session_id: UUID = Field(..., description="会话ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据信息")


class SessionSummaryRequest(BaseModel):
    """会话总结请求模型"""
    session_id: UUID = Field(..., description="会话ID")
    summary_type: str = Field("detailed", pattern="^(brief|detailed|analysis)$", description="总结类型")
    include_sentiment: bool = Field(True, description="是否包含情感分析")
    language: str = Field("zh", description="总结语言")


class ReplySuggestionsRequest(BaseModel):
    """回复建议请求"""
    session_id: UUID = Field(..., description="会话ID")
    user_message: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")
    suggestion_count: int = Field(3, ge=1, le=10, description="建议数量")
    suggestion_type: str = Field("general", pattern="^(general|professional|empathetic|solution)$", description="建议类型")


class SentimentAnalysisRequest(BaseModel):
    # This class is mentioned in the original file but not defined in the new file
    # It's assumed to exist as it's called in the code block
    pass


# API端点实现

@router.post("/auto-reply", response_model=StandardResponse[AutoReplyResponse])
async def generate_auto_reply(
    request: AutoReplyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    生成自动回复
    
    基于用户消息和会话上下文，使用LLM生成智能回复
    
    - **session_id**: 会话ID，确保租户隔离
    - **user_message**: 用户消息内容
    - **llm_config**: 可选的LLM配置参数
    - **system_prompt**: 可选的系统提示词
    - **auto_save**: 是否自动保存消息到数据库
    """
    try:
        # 初始化自动回复服务
        auto_reply_service = AutoReplyService(db)
        
        # 生成自动回复
        reply_content = await auto_reply_service.generate_reply(
            session_id=request.session_id,
            tenant_id=tenant.id,
            user_message=request.user_message,
            llm_config=request.llm_config,
            system_prompt=request.system_prompt,
            auto_save=request.auto_save
        )
        
        # 构建响应
        response_data = AutoReplyResponse(
            reply_content=reply_content,
            session_id=request.session_id,
            metadata={
                "tenant_id": str(tenant.id),
                "auto_save": request.auto_save,
                "llm_config": request.llm_config is not None
            }
        )
        
        return StandardResponse(
            success=True,
            data=response_data,
            message="自动回复生成成功"
        )
        
    except ValueError as e:
        logger.warning("auto_reply_validation_error", 
                      tenant_id=tenant.id,
                      session_id=request.session_id,
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("auto_reply_generation_error", 
                    tenant_id=tenant.id,
                    session_id=request.session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="自动回复生成失败")


@router.post("/auto-reply/stream")
async def generate_auto_reply_stream(
    request: AutoReplyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    生成流式自动回复
    
    基于用户消息生成流式AI回复，适用于实时对话场景
    """
    try:
        # 初始化自动回复服务
        auto_reply_service = AutoReplyService(db)
        
        # 生成流式回复
        async def generate_stream():
            try:
                async for chunk in auto_reply_service.generate_stream_reply(
                    session_id=request.session_id,
                    tenant_id=tenant.id,
                    user_message=request.user_message,
                    llm_config=request.llm_config,
                    system_prompt=request.system_prompt
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("stream_reply_error", 
                           tenant_id=tenant.id,
                           error=str(e))
                yield f"data: [ERROR] {str(e)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except ValueError as e:
        logger.warning("stream_reply_validation_error", 
                      tenant_id=tenant.id,
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("stream_reply_setup_error", 
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="流式回复初始化失败")


@router.post("/sessions/{session_id}/summary", response_model=StandardResponse[Dict[str, Any]])
async def generate_session_summary(
    session_id: UUID,
    request: SessionSummaryRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    生成会话总结
    
    分析会话对话内容，生成智能总结报告，包括用户行为分析和服务质量评估
    
    - **session_id**: 会话ID
    - **summary_type**: 总结类型
        - brief: 简要总结（50字以内）
        - detailed: 详细总结（结构化分析）
        - analysis: 深度分析（包含改进建议）
    """
    try:
        # 验证session_id一致性
        if session_id != request.session_id:
            raise HTTPException(status_code=400, detail="URL中的session_id与请求体不一致")
        
        # 初始化会话总结服务
        summary_service = SessionSummaryService(db)
        
        # 生成会话总结
        summary_report = await summary_service.generate_session_summary(
            session_id=session_id,
            tenant_id=tenant.id,
            summary_type=request.summary_type
        )
        
        # 后台任务：可以用于统计分析或通知
        background_tasks.add_task(
            _log_summary_generation,
            tenant_id=tenant.id,
            session_id=session_id,
            summary_type=request.summary_type
        )
        
        return StandardResponse(
            success=True,
            data=summary_report,
            message=f"会话{request.summary_type}总结生成成功"
        )
        
    except ValueError as e:
        logger.warning("session_summary_validation_error", 
                      tenant_id=tenant.id,
                      session_id=session_id,
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("session_summary_generation_error", 
                    tenant_id=tenant.id,
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="会话总结生成失败")


@router.post("/reply-suggestions", response_model=StandardResponse[Dict[str, Any]])
async def get_reply_suggestions(
    request: ReplySuggestionsRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    获取回复建议
    
    基于用户消息和会话上下文，为客服人员提供专业的回复建议和处理提示
    
    - **session_id**: 会话ID
    - **user_message**: 用户消息内容
    - **suggestion_count**: 建议数量（1-10个）
    - **suggestion_type**: 建议类型
        - general: 通用专业回复
        - professional: 正式专业语调
        - empathetic: 同理心回复（适合投诉）
        - solution: 解决方案导向
    """
    try:
        # 初始化客服建议服务
        suggestion_service = AgentSuggestionService(db)
        
        # 获取回复建议
        suggestions = await suggestion_service.get_reply_suggestions(
            session_id=request.session_id,
            tenant_id=tenant.id,
            user_message=request.user_message,
            suggestion_count=request.suggestion_count,
            suggestion_type=request.suggestion_type
        )
        
        return StandardResponse(
            success=True,
            data=suggestions,
            message="回复建议生成成功"
        )
        
    except ValueError as e:
        logger.warning("reply_suggestions_validation_error", 
                      tenant_id=tenant.id,
                      session_id=request.session_id,
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("reply_suggestions_generation_error", 
                    tenant_id=tenant.id,
                    session_id=request.session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="回复建议生成失败")


@router.get("/sessions/{session_id}/auto-reply/status", response_model=StandardResponse[Dict[str, bool]])
async def check_auto_reply_status(
    session_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    检查会话自动回复状态
    
    确认指定会话是否启用了自动回复功能
    """
    try:
        # 初始化自动回复服务
        auto_reply_service = AutoReplyService(db)
        
        # 检查自动回复状态
        is_enabled = await auto_reply_service.is_auto_reply_enabled(
            session_id=session_id,
            tenant_id=tenant.id
        )
        
        return StandardResponse(
            success=True,
            data={"auto_reply_enabled": is_enabled},
            message="自动回复状态查询成功"
        )
        
    except Exception as e:
        logger.error("auto_reply_status_check_error", 
                    tenant_id=tenant.id,
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="自动回复状态查询失败")


@router.get("/health", response_model=StandardResponse[Dict[str, str]])
async def ai_features_health_check():
    """
    AI功能健康检查
    
    验证AI服务组件的可用性
    """
    try:
        # 这里可以添加AI服务的健康检查逻辑
        # 例如检查LLM提供商的连接状态
        
        return StandardResponse(
            success=True,
            data={
                "status": "healthy",
                "services": "auto_reply,session_summary,agent_suggestions",
                "version": "1.0.0"
            },
            message="AI功能服务正常"
        )
        
    except Exception as e:
        logger.error("ai_features_health_check_error", error=str(e))
        raise HTTPException(status_code=500, detail="AI功能健康检查失败")


# 背景任务函数

async def _log_summary_generation(
    tenant_id: UUID, 
    session_id: UUID, 
    summary_type: str
):
    """
    记录总结生成日志（后台任务）
    
    Args:
        tenant_id: 租户ID
        session_id: 会话ID
        summary_type: 总结类型
    """
    try:
        logger.info("session_summary_background_log",
                   tenant_id=tenant_id,
                   session_id=session_id,
                   summary_type=summary_type,
                   timestamp=__import__('datetime').datetime.utcnow().isoformat())
        
        # 这里可以添加更多的后台处理逻辑
        # 例如：统计分析、通知推送、数据同步等
        
    except Exception as e:
        logger.error("background_task_error", 
                    task="log_summary_generation",
                    error=str(e)) 