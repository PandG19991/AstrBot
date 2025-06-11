"""
会话总结服务

在会话结束时生成智能总结，提供用户行为分析和会话质量评估
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base_provider import (
    BaseLLMProvider, 
    LLMConfig, 
    LLMMessage, 
    LLMProviderError
)
from app.services.llm.openai_provider import OpenAIProvider
from app.services.context_manager import ContextManager
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.schemas.message import MessageRead

# 配置日志
logger = logging.getLogger(__name__)


class SessionSummaryService:
    """会话总结服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化会话总结服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.context_manager = ContextManager(db)
        self.message_service = MessageService(db)
        self.session_service = SessionService(db)
        
        # LLM提供商缓存
        self._providers: Dict[str, BaseLLMProvider] = {}
    
    async def generate_session_summary(
        self,
        session_id: UUID,
        tenant_id: UUID,
        summary_type: str = "detailed"
    ) -> Dict[str, Any]:
        """
        生成会话总结
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            summary_type: 总结类型 ("brief", "detailed", "analysis")
            
        Returns:
            Dict[str, Any]: 会话总结信息
            
        Raises:
            ValueError: 参数无效
            LLMProviderError: LLM调用失败
        """
        try:
            # 获取会话信息
            session = await self.session_service.get_session(session_id, tenant_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # 获取会话消息
            messages = await self._get_session_messages(session_id, tenant_id)
            if not messages:
                return self._create_empty_summary(session, "无对话内容")
            
            # 生成基础统计信息
            basic_stats = self._calculate_basic_stats(messages, session)
            
            # 根据总结类型生成不同详细程度的总结
            if summary_type == "brief":
                summary_content = await self._generate_brief_summary(messages, tenant_id)
            elif summary_type == "detailed":
                summary_content = await self._generate_detailed_summary(messages, tenant_id)
            elif summary_type == "analysis":
                summary_content = await self._generate_analysis_summary(messages, tenant_id)
            else:
                raise ValueError(f"Unsupported summary type: {summary_type}")
            
            # 生成用户行为分析
            behavior_analysis = await self._analyze_user_behavior(messages, tenant_id)
            
            # 生成服务质量评估
            quality_assessment = await self._assess_service_quality(messages, tenant_id)
            
            # 构建完整的总结报告
            summary_report = {
                "session_id": str(session_id),
                "tenant_id": str(tenant_id),
                "summary_type": summary_type,
                "generated_at": datetime.utcnow().isoformat(),
                "basic_stats": basic_stats,
                "summary_content": summary_content,
                "behavior_analysis": behavior_analysis,
                "quality_assessment": quality_assessment,
                "session_info": {
                    "start_time": session.created_at.isoformat(),
                    "end_time": session.updated_at.isoformat() if session.updated_at else None,
                    "user_id": session.user_id,
                    "status": session.status
                }
            }
            
            logger.info("session_summary_generated", 
                       session_id=session_id,
                       tenant_id=tenant_id,
                       summary_type=summary_type,
                       message_count=len(messages))
            
            return summary_report
            
        except Exception as e:
            logger.error("session_summary_generation_error", 
                        session_id=session_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_session_messages(
        self,
        session_id: UUID,
        tenant_id: UUID
    ) -> List[MessageRead]:
        """
        获取会话所有消息
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            
        Returns:
            List[MessageRead]: 消息列表
        """
        # 获取所有消息（不分页）
        messages_result = await self.message_service.get_session_messages(
            session_id=session_id,
            tenant_id=tenant_id,
            page=1,
            page_size=1000,  # 假设单个会话不会超过1000条消息
            message_type=None
        )
        
        # 按时间正序排序
        return sorted(messages_result.items, key=lambda x: x.created_at)
    
    def _calculate_basic_stats(
        self, 
        messages: List[MessageRead], 
        session: Any
    ) -> Dict[str, Any]:
        """
        计算基础统计信息
        
        Args:
            messages: 消息列表
            session: 会话对象
            
        Returns:
            Dict[str, Any]: 基础统计信息
        """
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        agent_messages = [msg for msg in messages if msg.message_type == "agent"]
        
        # 计算时长
        duration_minutes = 0
        if messages:
            start_time = messages[0].created_at
            end_time = messages[-1].created_at
            duration_minutes = (end_time - start_time).total_seconds() / 60
        
        # 计算平均响应时间
        avg_response_time = self._calculate_avg_response_time(messages)
        
        return {
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "agent_messages": len(agent_messages),
            "duration_minutes": round(duration_minutes, 2),
            "avg_response_time_seconds": avg_response_time,
            "total_characters": sum(len(msg.content) for msg in messages),
            "user_characters": sum(len(msg.content) for msg in user_messages),
            "agent_characters": sum(len(msg.content) for msg in agent_messages)
        }
    
    def _calculate_avg_response_time(self, messages: List[MessageRead]) -> float:
        """
        计算平均响应时间
        
        Args:
            messages: 消息列表
            
        Returns:
            float: 平均响应时间（秒）
        """
        response_times = []
        
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]
            
            # 如果当前是用户消息，下一条是客服消息，计算响应时间
            if (current_msg.message_type == "user" and 
                next_msg.message_type == "agent"):
                response_time = (next_msg.created_at - current_msg.created_at).total_seconds()
                response_times.append(response_time)
        
        return sum(response_times) / len(response_times) if response_times else 0
    
    async def _generate_brief_summary(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID
    ) -> str:
        """
        生成简要总结
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            
        Returns:
            str: 简要总结
        """
        try:
            provider = await self._get_llm_provider(tenant_id)
            
            # 构建消息内容
            conversation_text = self._format_messages_for_summary(messages, max_length=1000)
            
            prompt = f"""请为以下客服对话生成一个简要总结（50字以内）：

{conversation_text}

总结要点：
- 用户主要问题
- 解决方案
- 最终结果"""
            
            context = [LLMMessage(
                role="system", 
                content="你是一个专业的客服对话分析师，擅长提取对话要点。"
            )]
            context.append(LLMMessage(role="user", content=prompt))
            
            response = await provider.generate_response(context)
            return response.content.strip()
            
        except Exception as e:
            logger.error("generate_brief_summary_error", error=str(e))
            return "总结生成失败"
    
    async def _generate_detailed_summary(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID
    ) -> str:
        """
        生成详细总结
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            
        Returns:
            str: 详细总结
        """
        try:
            provider = await self._get_llm_provider(tenant_id)
            
            conversation_text = self._format_messages_for_summary(messages, max_length=2000)
            
            prompt = f"""请为以下客服对话生成详细总结：

{conversation_text}

请按以下结构总结：
1. 用户咨询背景
2. 主要问题和需求
3. 客服处理过程
4. 解决方案
5. 最终结果
6. 用户满意度预估"""
            
            context = [LLMMessage(
                role="system", 
                content="你是一个专业的客服对话分析师，需要提供结构化的详细分析。"
            )]
            context.append(LLMMessage(role="user", content=prompt))
            
            response = await provider.generate_response(context)
            return response.content.strip()
            
        except Exception as e:
            logger.error("generate_detailed_summary_error", error=str(e))
            return "详细总结生成失败"
    
    async def _generate_analysis_summary(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID
    ) -> str:
        """
        生成分析型总结
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            
        Returns:
            str: 分析型总结
        """
        try:
            provider = await self._get_llm_provider(tenant_id)
            
            conversation_text = self._format_messages_for_summary(messages, max_length=2500)
            
            prompt = f"""请对以下客服对话进行深度分析：

{conversation_text}

分析维度：
1. 用户情绪变化趋势
2. 问题复杂程度评估
3. 客服专业度表现
4. 沟通效率分析
5. 改进建议
6. 风险点识别"""
            
            context = [LLMMessage(
                role="system", 
                content="你是一个资深的客服质量分析专家，擅长深度分析客服对话。"
            )]
            context.append(LLMMessage(role="user", content=prompt))
            
            response = await provider.generate_response(context)
            return response.content.strip()
            
        except Exception as e:
            logger.error("generate_analysis_summary_error", error=str(e))
            return "分析总结生成失败"
    
    async def _analyze_user_behavior(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        分析用户行为
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 用户行为分析
        """
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        
        if not user_messages:
            return {"status": "no_user_messages"}
        
        # 基础行为指标
        analysis = {
            "message_frequency": len(user_messages),
            "avg_message_length": sum(len(msg.content) for msg in user_messages) / len(user_messages),
            "response_pattern": self._analyze_response_pattern(messages),
            "emotion_indicators": await self._detect_emotion_indicators(user_messages, tenant_id),
            "urgency_level": self._assess_urgency_level(user_messages),
            "interaction_style": self._determine_interaction_style(user_messages)
        }
        
        return analysis
    
    def _analyze_response_pattern(self, messages: List[MessageRead]) -> str:
        """
        分析用户响应模式
        
        Args:
            messages: 消息列表
            
        Returns:
            str: 响应模式描述
        """
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        
        if len(user_messages) <= 1:
            return "single_message"
        elif len(user_messages) <= 3:
            return "brief_conversation"
        elif len(user_messages) <= 10:
            return "normal_conversation"
        else:
            return "extended_conversation"
    
    async def _detect_emotion_indicators(
        self, 
        user_messages: List[MessageRead], 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        检测用户情绪指标
        
        Args:
            user_messages: 用户消息列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 情绪指标
        """
        # 简单的情绪检测（可以后续集成专业的情感分析API）
        text_content = " ".join(msg.content for msg in user_messages)
        
        # 基础情绪关键词
        positive_keywords = ["谢谢", "感谢", "满意", "很好", "不错"]
        negative_keywords = ["投诉", "不满", "生气", "失望", "问题"]
        urgent_keywords = ["紧急", "急", "马上", "立即", "快"]
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in text_content)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text_content)
        urgent_count = sum(1 for keyword in urgent_keywords if keyword in text_content)
        
        return {
            "positive_indicators": positive_count,
            "negative_indicators": negative_count,
            "urgent_indicators": urgent_count,
            "overall_tone": self._determine_overall_tone(positive_count, negative_count)
        }
    
    def _determine_overall_tone(self, positive_count: int, negative_count: int) -> str:
        """
        确定整体语调
        
        Args:
            positive_count: 积极指标数量
            negative_count: 消极指标数量
            
        Returns:
            str: 整体语调
        """
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _assess_urgency_level(self, user_messages: List[MessageRead]) -> str:
        """
        评估紧急程度
        
        Args:
            user_messages: 用户消息列表
            
        Returns:
            str: 紧急程度
        """
        # 基于消息频率和内容特征评估
        if len(user_messages) >= 10:
            return "high"
        elif len(user_messages) >= 5:
            return "medium"
        else:
            return "low"
    
    def _determine_interaction_style(self, user_messages: List[MessageRead]) -> str:
        """
        确定互动风格
        
        Args:
            user_messages: 用户消息列表
            
        Returns:
            str: 互动风格
        """
        avg_length = sum(len(msg.content) for msg in user_messages) / len(user_messages)
        
        if avg_length > 100:
            return "detailed"
        elif avg_length > 30:
            return "moderate"
        else:
            return "concise"
    
    async def _assess_service_quality(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        评估服务质量
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 服务质量评估
        """
        agent_messages = [msg for msg in messages if msg.message_type == "agent"]
        
        if not agent_messages:
            return {"status": "no_agent_messages"}
        
        # 计算基础质量指标
        avg_response_time = self._calculate_avg_response_time(messages)
        
        assessment = {
            "response_timeliness": self._rate_response_timeliness(avg_response_time),
            "response_completeness": self._assess_response_completeness(agent_messages),
            "professional_tone": await self._assess_professional_tone(agent_messages, tenant_id),
            "problem_resolution": self._assess_problem_resolution(messages),
            "overall_rating": 0  # 将在最后计算
        }
        
        # 计算综合评分
        assessment["overall_rating"] = self._calculate_overall_rating(assessment)
        
        return assessment
    
    def _rate_response_timeliness(self, avg_response_time: float) -> Dict[str, Any]:
        """
        评估响应及时性
        
        Args:
            avg_response_time: 平均响应时间（秒）
            
        Returns:
            Dict[str, Any]: 及时性评估
        """
        if avg_response_time <= 30:
            return {"score": 5, "level": "excellent"}
        elif avg_response_time <= 60:
            return {"score": 4, "level": "good"}
        elif avg_response_time <= 120:
            return {"score": 3, "level": "fair"}
        elif avg_response_time <= 300:
            return {"score": 2, "level": "poor"}
        else:
            return {"score": 1, "level": "very_poor"}
    
    def _assess_response_completeness(self, agent_messages: List[MessageRead]) -> Dict[str, Any]:
        """
        评估回复完整性
        
        Args:
            agent_messages: 客服消息列表
            
        Returns:
            Dict[str, Any]: 完整性评估
        """
        avg_length = sum(len(msg.content) for msg in agent_messages) / len(agent_messages)
        
        if avg_length >= 50:
            return {"score": 5, "level": "comprehensive"}
        elif avg_length >= 30:
            return {"score": 4, "level": "adequate"}
        elif avg_length >= 15:
            return {"score": 3, "level": "basic"}
        else:
            return {"score": 2, "level": "insufficient"}
    
    async def _assess_professional_tone(
        self, 
        agent_messages: List[MessageRead], 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        评估专业语调
        
        Args:
            agent_messages: 客服消息列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 专业性评估
        """
        # 简单的专业性评估（可以后续集成更复杂的NLP分析）
        professional_indicators = ["您好", "请问", "为您", "感谢", "如果"]
        
        text_content = " ".join(msg.content for msg in agent_messages)
        professional_count = sum(1 for indicator in professional_indicators if indicator in text_content)
        
        score = min(5, professional_count)
        levels = {5: "excellent", 4: "good", 3: "fair", 2: "poor", 1: "very_poor", 0: "very_poor"}
        
        return {"score": score, "level": levels[score]}
    
    def _assess_problem_resolution(self, messages: List[MessageRead]) -> Dict[str, Any]:
        """
        评估问题解决程度
        
        Args:
            messages: 所有消息列表
            
        Returns:
            Dict[str, Any]: 问题解决评估
        """
        # 基于对话结束方式判断解决程度
        if not messages:
            return {"score": 1, "level": "unresolved"}
        
        last_messages = messages[-3:] if len(messages) >= 3 else messages
        last_content = " ".join(msg.content for msg in last_messages)
        
        resolution_indicators = ["解决了", "明白了", "谢谢", "满意", "可以了"]
        if any(indicator in last_content for indicator in resolution_indicators):
            return {"score": 5, "level": "fully_resolved"}
        else:
            return {"score": 3, "level": "partially_resolved"}
    
    def _calculate_overall_rating(self, assessment: Dict[str, Any]) -> float:
        """
        计算综合评分
        
        Args:
            assessment: 评估结果
            
        Returns:
            float: 综合评分（1-5分）
        """
        scores = []
        
        if "response_timeliness" in assessment:
            scores.append(assessment["response_timeliness"]["score"])
        if "response_completeness" in assessment:
            scores.append(assessment["response_completeness"]["score"])
        if "professional_tone" in assessment:
            scores.append(assessment["professional_tone"]["score"])
        if "problem_resolution" in assessment:
            scores.append(assessment["problem_resolution"]["score"])
        
        return sum(scores) / len(scores) if scores else 0
    
    def _format_messages_for_summary(
        self, 
        messages: List[MessageRead], 
        max_length: int = 2000
    ) -> str:
        """
        格式化消息用于总结
        
        Args:
            messages: 消息列表
            max_length: 最大长度
            
        Returns:
            str: 格式化的对话文本
        """
        formatted_lines = []
        current_length = 0
        
        for msg in messages:
            role = "用户" if msg.message_type == "user" else "客服"
            line = f"{role}: {msg.content}"
            
            if current_length + len(line) > max_length:
                break
            
            formatted_lines.append(line)
            current_length += len(line)
        
        return "\n".join(formatted_lines)
    
    def _create_empty_summary(self, session: Any, reason: str) -> Dict[str, Any]:
        """
        创建空总结
        
        Args:
            session: 会话对象
            reason: 空总结原因
            
        Returns:
            Dict[str, Any]: 空总结报告
        """
        return {
            "session_id": str(session.id),
            "generated_at": datetime.utcnow().isoformat(),
            "summary_type": "empty",
            "reason": reason,
            "basic_stats": {
                "total_messages": 0,
                "duration_minutes": 0
            },
            "session_info": {
                "start_time": session.created_at.isoformat(),
                "user_id": session.user_id,
                "status": session.status
            }
        }
    
    async def _get_llm_provider(self, tenant_id: UUID) -> BaseLLMProvider:
        """
        获取LLM提供商
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            BaseLLMProvider: LLM提供商实例
        """
        cache_key = f"summary_{tenant_id}"
        
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # 使用OpenAI作为总结服务的默认提供商
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0.3,  # 较低的温度确保总结的一致性
            max_tokens=1000
        )
        
        provider = OpenAIProvider(
            config=config,
            api_key="your-api-key",  # 应该从配置中获取
            base_url="https://api.openai.com/v1"
        )
        
        self._providers[cache_key] = provider
        return provider 