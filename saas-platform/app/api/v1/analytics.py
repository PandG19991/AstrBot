"""
数据分析API端点

提供多维度数据分析功能：
- 会话统计分析
- 消息统计分析  
- 实时监控数据
- 趋势分析
- 自定义报表
- 数据导出
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db
from app.core.permissions import CommonPermissions
from app.models.tenant import Tenant
from app.schemas.analytics import (
    AnalyticsFilter,
    SessionStatsResponse,
    MessageStatsResponse,
    RealtimeMetrics,
    TrendAnalysis,
    CustomReportRequest,
    CustomReportResponse,
    DashboardOverview,
    ExportRequest,
    ExportResponse
)
from app.schemas.common import StandardResponse
from app.services.analytics_service import AnalyticsService

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()


@router.get(
    "/sessions/stats",
    response_model=StandardResponse[SessionStatsResponse],
    summary="获取会话统计",
    description="获取会话相关的统计数据，支持时间范围和状态过滤"
)
async def get_session_stats(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    status: Optional[str] = Query(None, description="会话状态过滤，多个状态用逗号分隔"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_view_analytics)
) -> StandardResponse[SessionStatsResponse]:
    """
    获取会话统计数据
    
    Args:
        start_date: 开始时间
        end_date: 结束时间  
        status: 会话状态过滤
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        会话统计响应
    """
    try:
        # 默认时间范围（最近30天）
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # 解析状态过滤
        status_list = status.split(',') if status else None
        
        # 构建过滤条件
        filters = AnalyticsFilter(
            start_date=start_date,
            end_date=end_date,
            status=status_list
        )
        
        # 获取统计数据
        analytics_service = AnalyticsService(db)
        stats = await analytics_service.get_session_stats(tenant.id, filters)
        
        logger.info(
            "session_stats_retrieved",
            tenant_id=str(tenant.id),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_sessions=stats.total_sessions
        )
        
        return StandardResponse(
            success=True,
            data=stats,
            message="会话统计数据获取成功"
        )
        
    except Exception as e:
        logger.error(
            "session_stats_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="获取会话统计失败"
        )


@router.get(
    "/messages/stats",
    response_model=StandardResponse[MessageStatsResponse],
    summary="获取消息统计",
    description="获取消息相关的统计数据，包括类型分布和响应时间"
)
async def get_message_stats(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    message_types: Optional[str] = Query(None, description="消息类型过滤，多个类型用逗号分隔"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_view_analytics)
) -> StandardResponse[MessageStatsResponse]:
    """
    获取消息统计数据
    
    Args:
        start_date: 开始时间
        end_date: 结束时间
        message_types: 消息类型过滤
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        消息统计响应
    """
    try:
        # 默认时间范围（最近30天）
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # 解析消息类型过滤
        types_list = message_types.split(',') if message_types else None
        
        # 构建过滤条件
        filters = AnalyticsFilter(
            start_date=start_date,
            end_date=end_date,
            message_types=types_list
        )
        
        # 获取统计数据
        analytics_service = AnalyticsService(db)
        stats = await analytics_service.get_message_stats(tenant.id, filters)
        
        logger.info(
            "message_stats_retrieved",
            tenant_id=str(tenant.id),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_messages=stats.total_messages
        )
        
        return StandardResponse(
            success=True,
            data=stats,
            message="消息统计数据获取成功"
        )
        
    except Exception as e:
        logger.error(
            "message_stats_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="获取消息统计失败"
        )


@router.get(
    "/realtime",
    response_model=StandardResponse[RealtimeMetrics],
    summary="获取实时监控指标",
    description="获取当前实时的系统监控指标"
)
async def get_realtime_metrics(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_view_analytics)
) -> StandardResponse[RealtimeMetrics]:
    """
    获取实时监控指标
    
    Args:
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        实时监控指标
    """
    try:
        analytics_service = AnalyticsService(db)
        metrics = await analytics_service.get_realtime_metrics(tenant.id)
        
        logger.info(
            "realtime_metrics_retrieved",
            tenant_id=str(tenant.id),
            active_sessions=metrics.active_sessions
        )
        
        return StandardResponse(
            success=True,
            data=metrics,
            message="实时监控指标获取成功"
        )
        
    except Exception as e:
        logger.error(
            "realtime_metrics_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="获取实时监控指标失败"
        )


@router.get(
    "/trends",
    response_model=StandardResponse[TrendAnalysis],
    summary="获取趋势分析",
    description="获取指定周期的趋势分析数据"
)
async def get_trend_analysis(
    days: int = Query(7, description="分析天数", ge=1, le=365),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_view_analytics)
) -> StandardResponse[TrendAnalysis]:
    """
    获取趋势分析数据
    
    Args:
        days: 分析天数
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        趋势分析结果
    """
    try:
        analytics_service = AnalyticsService(db)
        analysis = await analytics_service.get_trend_analysis(tenant.id, days)
        
        logger.info(
            "trend_analysis_retrieved",
            tenant_id=str(tenant.id),
            days=days,
            sessions_change=analysis.sessions_change_percent
        )
        
        return StandardResponse(
            success=True,
            data=analysis,
            message="趋势分析数据获取成功"
        )
        
    except Exception as e:
        logger.error(
            "trend_analysis_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="获取趋势分析失败"
        )


@router.get(
    "/dashboard",
    response_model=StandardResponse[DashboardOverview],
    summary="获取仪表板概览",
    description="获取仪表板所需的完整概览数据"
)
async def get_dashboard_overview(
    days: int = Query(30, description="统计天数", ge=1, le=365),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_view_analytics)
) -> StandardResponse[DashboardOverview]:
    """
    获取仪表板概览数据
    
    Args:
        days: 统计天数
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        仪表板概览数据
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 构建过滤条件
        filters = AnalyticsFilter(
            start_date=start_date,
            end_date=end_date
        )
        
        analytics_service = AnalyticsService(db)
        
        # 并行获取各类统计数据
        session_stats = await analytics_service.get_session_stats(tenant.id, filters)
        message_stats = await analytics_service.get_message_stats(tenant.id, filters)
        realtime_metrics = await analytics_service.get_realtime_metrics(tenant.id)
        trend_analysis = await analytics_service.get_trend_analysis(tenant.id, days)
        
        # 构建仪表板概览
        overview = DashboardOverview(
            tenant_id=tenant.id,
            period_start=start_date,
            period_end=end_date,
            # 核心指标
            total_sessions=session_stats.total_sessions,
            total_messages=message_stats.total_messages,
            active_sessions=realtime_metrics.active_sessions,
            avg_response_time=message_stats.avg_response_time_seconds,
            # 趋势数据
            sessions_trend=session_stats.time_series,
            messages_trend=message_stats.time_series,
            # 分布统计
            session_status_distribution=session_stats.status_distribution,
            message_type_distribution=message_stats.type_distribution,
            hourly_activity=trend_analysis.hourly_activity_distribution,
            # 性能指标
            peak_concurrent_sessions=realtime_metrics.active_sessions,  # 简化处理
            resolution_rate=85.0,  # 占位值，实际需要更复杂计算
            customer_satisfaction=None  # 需要额外的满意度数据
        )
        
        logger.info(
            "dashboard_overview_retrieved",
            tenant_id=str(tenant.id),
            days=days,
            total_sessions=overview.total_sessions,
            total_messages=overview.total_messages
        )
        
        return StandardResponse(
            success=True,
            data=overview,
            message="仪表板概览数据获取成功"
        )
        
    except Exception as e:
        logger.error(
            "dashboard_overview_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="获取仪表板概览失败"
        )


@router.post(
    "/reports/custom",
    response_model=StandardResponse[CustomReportResponse],
    summary="生成自定义报表",
    description="根据指定条件生成自定义报表"
)
async def generate_custom_report(
    request: CustomReportRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_create_analytics)
) -> StandardResponse[CustomReportResponse]:
    """
    生成自定义报表
    
    Args:
        request: 报表请求参数
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        自定义报表响应
    """
    try:
        analytics_service = AnalyticsService(db)
        
        # 这里是一个简化的实现，实际需要根据metrics和dimensions动态构建查询
        # 目前返回基础统计数据作为示例
        session_stats = await analytics_service.get_session_stats(tenant.id, request.filters)
        message_stats = await analytics_service.get_message_stats(tenant.id, request.filters)
        
        # 构建报表数据
        report_data = [
            {
                "metric": "total_sessions",
                "value": session_stats.total_sessions,
                "period": f"{request.filters.start_date} to {request.filters.end_date}"
            },
            {
                "metric": "total_messages", 
                "value": message_stats.total_messages,
                "period": f"{request.filters.start_date} to {request.filters.end_date}"
            }
        ]
        
        response = CustomReportResponse(
            report_name=request.report_name,
            generated_at=datetime.utcnow(),
            data=report_data,
            summary={
                "total_sessions": session_stats.total_sessions,
                "total_messages": message_stats.total_messages,
                "avg_response_time": message_stats.avg_response_time_seconds
            },
            metadata={
                "tenant_id": str(tenant.id),
                "filters": request.filters.dict(),
                "metrics": request.metrics,
                "dimensions": request.dimensions
            }
        )
        
        logger.info(
            "custom_report_generated",
            tenant_id=str(tenant.id),
            report_name=request.report_name,
            data_points=len(report_data)
        )
        
        return StandardResponse(
            success=True,
            data=response,
            message="自定义报表生成成功"
        )
        
    except Exception as e:
        logger.error(
            "custom_report_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="生成自定义报表失败"
        )


@router.post(
    "/export",
    response_model=StandardResponse[ExportResponse],
    summary="导出数据",
    description="导出分析数据到指定格式"
)
async def export_data(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.can_export_analytics)
) -> StandardResponse[ExportResponse]:
    """
    导出分析数据
    
    Args:
        request: 导出请求参数
        background_tasks: 后台任务
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        导出响应
    """
    try:
        # 生成导出任务ID
        export_id = UUID('12345678-1234-5678-9abc-123456789abc')  # 实际应该生成随机UUID
        
        # 添加后台任务处理导出
        # background_tasks.add_task(process_export_task, export_id, request, tenant.id)
        
        response = ExportResponse(
            export_id=export_id,
            status="processing",
            download_url=None,
            file_size=None,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow()
        )
        
        logger.info(
            "export_task_created",
            tenant_id=str(tenant.id),
            export_id=str(export_id),
            export_type=request.export_type,
            data_type=request.data_type
        )
        
        return StandardResponse(
            success=True,
            data=response,
            message="导出任务已创建，正在处理中"
        )
        
    except Exception as e:
        logger.error(
            "export_task_failed",
            tenant_id=str(tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="创建导出任务失败"
        ) 