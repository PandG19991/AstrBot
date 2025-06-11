"""
客服话术推荐服务

实时分析用户问题，为客服人员推荐合适的回复话术和处理建议
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

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


class AgentSuggestionService:
    """客服话术推荐服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化客服话术推荐服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.context_manager = ContextManager(db)
        self.message_service = MessageService(db)
        self.session_service = SessionService(db)
        
        # LLM提供商缓存
        self._providers: Dict[str, BaseLLMProvider] = {}
        
        # 话术模板缓存
        self._templates_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    async def get_reply_suggestions(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str,
        suggestion_count: int = 3,
        suggestion_type: str = "general"
    ) -> Dict[str, Any]:
        """
        获取回复建议
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            user_message: 用户消息内容
            suggestion_count: 建议数量
            suggestion_type: 建议类型 ("general", "professional", "empathetic", "solution")
            
        Returns:
            Dict[str, Any]: 回复建议信息
            
        Raises:
            ValueError: 参数无效
            LLMProviderError: LLM调用失败
        """
        try:
            # 验证输入
            if not user_message.strip():
                raise ValueError("User message cannot be empty")
            
            # 获取会话上下文
            session_context = await self._get_session_context(session_id, tenant_id)
            
            # 分析用户消息
            message_analysis = await self._analyze_user_message(user_message, tenant_id)
            
            # 生成基于AI的建议
            ai_suggestions = await self._generate_ai_suggestions(
                user_message=user_message,
                session_context=session_context,
                message_analysis=message_analysis,
                suggestion_count=suggestion_count,
                suggestion_type=suggestion_type,
                tenant_id=tenant_id
            )
            
            # 获取模板化建议
            template_suggestions = await self._get_template_suggestions(
                message_analysis=message_analysis,
                tenant_id=tenant_id,
                suggestion_count=min(2, suggestion_count)
            )
            
            # 生成快速回复选项
            quick_replies = await self._generate_quick_replies(
                message_analysis=message_analysis,
                tenant_id=tenant_id
            )
            
            # 生成处理建议
            handling_tips = await self._generate_handling_tips(
                message_analysis=message_analysis,
                session_context=session_context,
                tenant_id=tenant_id
            )
            
            # 构建完整的建议响应
            suggestion_response = {
                "session_id": str(session_id),
                "tenant_id": str(tenant_id),
                "user_message": user_message,
                "generated_at": datetime.utcnow().isoformat(),
                "message_analysis": message_analysis,
                "ai_suggestions": ai_suggestions,
                "template_suggestions": template_suggestions,
                "quick_replies": quick_replies,
                "handling_tips": handling_tips,
                "suggestion_metadata": {
                    "suggestion_type": suggestion_type,
                    "suggestion_count": suggestion_count,
                    "context_length": len(session_context.get("recent_messages", []))
                }
            }
            
            logger.info("reply_suggestions_generated", 
                       session_id=session_id,
                       tenant_id=tenant_id,
                       suggestion_type=suggestion_type,
                       ai_count=len(ai_suggestions),
                       template_count=len(template_suggestions))
            
            return suggestion_response
            
        except Exception as e:
            logger.error("reply_suggestions_generation_error", 
                        session_id=session_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_session_context(
        self, 
        session_id: UUID, 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        获取会话上下文信息
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 会话上下文
        """
        try:
            # 获取会话基本信息
            session = await self.session_service.get_session(session_id, tenant_id)
            if not session:
                return {"error": "session_not_found"}
            
            # 获取最近的消息
            recent_messages_result = await self.message_service.get_session_messages(
                session_id=session_id,
                tenant_id=tenant_id,
                page=1,
                page_size=10,
                message_type=None
            )
            
            recent_messages = recent_messages_result.items
            
            # 计算会话统计信息
            user_message_count = len([msg for msg in recent_messages if msg.message_type == "user"])
            agent_message_count = len([msg for msg in recent_messages if msg.message_type == "agent"])
            
            # 计算会话时长
            session_duration = 0
            if recent_messages:
                start_time = session.created_at
                latest_time = max(msg.created_at for msg in recent_messages)
                session_duration = (latest_time - start_time).total_seconds() / 60
            
            return {
                "session_info": {
                    "id": str(session.id),
                    "user_id": session.user_id,
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "duration_minutes": round(session_duration, 2)
                },
                "message_stats": {
                    "total_messages": len(recent_messages),
                    "user_messages": user_message_count,
                    "agent_messages": agent_message_count
                },
                "recent_messages": [
                    {
                        "content": msg.content,
                        "type": msg.message_type,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in recent_messages
                ]
            }
            
        except Exception as e:
            logger.error("get_session_context_error", 
                        session_id=session_id,
                        error=str(e))
            return {"error": str(e)}
    
    async def _analyze_user_message(
        self, 
        user_message: str, 
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        分析用户消息
        
        Args:
            user_message: 用户消息内容
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 消息分析结果
        """
        try:
            provider = await self._get_llm_provider(tenant_id)
            
            # 构建分析提示词
            analysis_prompt = f"""请分析以下用户消息的特征：

用户消息：{user_message}

请分析：
1. 消息类型 (question, complaint, compliment, request, urgent, other)
2. 情绪状态 (positive, negative, neutral, frustrated, anxious)
3. 紧急程度 (low, medium, high, critical)
4. 主要关键词
5. 意图分类 (inquiry, support, complaint, purchase, refund, technical, other)

请简要回复分析结果。"""
            
            context = [LLMMessage(
                role="system", 
                content="你是专业的客服消息分析师。"
            )]
            context.append(LLMMessage(role="user", content=analysis_prompt))
            
            response = await provider.generate_response(context)
            
            # 简化的分析结果
            return {
                "message_type": "question",
                "emotion": "neutral",
                "urgency": "low",
                "keywords": user_message.split()[:3],
                "intent": "inquiry",
                "summary": response.content[:100] + "..." if len(response.content) > 100 else response.content
            }
            
        except Exception as e:
            logger.error("analyze_user_message_error", error=str(e))
            return {
                "message_type": "other",
                "emotion": "neutral",
                "urgency": "low",
                "keywords": [],
                "intent": "inquiry",
                "summary": "分析失败"
            }
    
    async def _generate_ai_suggestions(
        self,
        user_message: str,
        session_context: Dict[str, Any],
        message_analysis: Dict[str, Any],
        suggestion_count: int,
        suggestion_type: str,
        tenant_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        生成AI建议
        
        Args:
            user_message: 用户消息
            session_context: 会话上下文
            message_analysis: 消息分析
            suggestion_count: 建议数量
            suggestion_type: 建议类型
            tenant_id: 租户ID
            
        Returns:
            List[Dict[str, Any]]: AI建议列表
        """
        try:
            provider = await self._get_llm_provider(tenant_id)
            
            # 构建建议生成提示词
            suggestion_prompt = f"""基于以下用户消息，生成{suggestion_count}个专业的客服回复建议：

用户消息：{user_message}

请生成{suggestion_count}个不同风格的回复建议：
1. 正式专业的回复
2. 友好亲切的回复
3. 简洁直接的回复

每个建议要专业、友好、有帮助。"""
            
            context = [LLMMessage(
                role="system", 
                content="你是资深的客服培训师，为客服人员提供专业的回复建议。"
            )]
            context.append(LLMMessage(role="user", content=suggestion_prompt))
            
            response = await provider.generate_response(context)
            
            # 解析建议（简化版）
            suggestions_text = response.content.strip().split('\n')
            suggestions = []
            
            for i, text in enumerate(suggestions_text[:suggestion_count]):
                if text.strip():
                    suggestions.append({
                        "content": text.strip(),
                        "type": f"style_{i+1}",
                        "source": "ai_generated"
                    })
            
            # 确保至少有一个建议
            if not suggestions:
                suggestions = [{
                    "content": "感谢您的咨询，我会尽快为您处理。",
                    "type": "default",
                    "source": "fallback"
                }]
            
            return suggestions
            
        except Exception as e:
            logger.error("generate_ai_suggestions_error", error=str(e))
            return [{
                "content": "感谢您的咨询，我来为您处理。",
                "type": "default",
                "source": "fallback"
            }]
    
    async def _get_template_suggestions(
        self,
        message_analysis: Dict[str, Any],
        tenant_id: UUID,
        suggestion_count: int = 2
    ) -> List[Dict[str, Any]]:
        """
        获取模板化建议
        
        Args:
            message_analysis: 消息分析结果
            tenant_id: 租户ID
            suggestion_count: 建议数量
            
        Returns:
            List[Dict[str, Any]]: 模板建议列表
        """
        # 获取或创建模板库
        templates = await self._get_template_library(tenant_id)
        
        # 根据消息分析匹配合适的模板
        matched_templates = []
        
        message_type = message_analysis.get('message_type', 'other')
        emotion = message_analysis.get('emotion', 'neutral')
        intent = message_analysis.get('intent', 'inquiry')
        
        # 模板匹配逻辑
        for template in templates:
            template_types = template.get('applicable_types', [])
            template_emotions = template.get('applicable_emotions', [])
            template_intents = template.get('applicable_intents', [])
            
            score = 0
            if message_type in template_types:
                score += 3
            if emotion in template_emotions:
                score += 2
            if intent in template_intents:
                score += 1
            
            if score > 0:
                matched_templates.append((score, template))
        
        # 按匹配分数排序并返回前几个
        matched_templates.sort(key=lambda x: x[0], reverse=True)
        
        return [
            {
                "content": template[1]['content'],
                "scenario": template[1]['scenario'],
                "expected_effect": template[1]['effect'],
                "source": "template",
                "template_id": template[1]['id']
            }
            for template in matched_templates[:suggestion_count]
        ]
    
    async def _get_template_library(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """
        获取模板库
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            List[Dict[str, Any]]: 模板列表
        """
        cache_key = str(tenant_id)
        
        # 检查缓存
        if cache_key in self._templates_cache:
            return self._templates_cache[cache_key]
        
        # 这里应该从数据库加载租户的自定义模板
        # 暂时返回默认模板
        default_templates = [
            {
                "id": "greeting_1",
                "content": "您好！感谢您联系我们，我是您的专属客服，很高兴为您服务。请问有什么可以帮助您的吗？",
                "scenario": "初次接触",
                "effect": "建立友好的第一印象",
                "applicable_types": ["question", "other"],
                "applicable_emotions": ["neutral", "positive"],
                "applicable_intents": ["inquiry", "support"]
            },
            {
                "id": "complaint_1",
                "content": "非常抱歉给您带来了不便，我完全理解您的感受。让我立即为您查看具体情况并提供解决方案。",
                "scenario": "处理投诉",
                "effect": "表达同理心，缓解用户情绪",
                "applicable_types": ["complaint"],
                "applicable_emotions": ["negative", "frustrated"],
                "applicable_intents": ["complaint", "support"]
            },
            {
                "id": "technical_1",
                "content": "我来为您详细说明操作步骤。为了确保准确性，建议您可以截图或录屏，这样我能更好地为您指导。",
                "scenario": "技术支持",
                "effect": "提供专业技术协助",
                "applicable_types": ["question"],
                "applicable_emotions": ["neutral"],
                "applicable_intents": ["technical", "support"]
            }
        ]
        
        # 缓存模板
        self._templates_cache[cache_key] = default_templates
        
        return default_templates
    
    async def _generate_quick_replies(
        self,
        message_analysis: Dict[str, Any],
        tenant_id: UUID
    ) -> List[str]:
        """
        生成快速回复选项
        
        Args:
            message_analysis: 消息分析结果
            tenant_id: 租户ID
            
        Returns:
            List[str]: 快速回复选项
        """
        # 基于消息分析生成快速回复
        quick_replies = []
        
        message_type = message_analysis.get('message_type', 'other')
        emotion = message_analysis.get('emotion', 'neutral')
        urgency = message_analysis.get('urgency', 'low')
        
        # 根据不同情况生成快速回复
        if emotion == 'negative':
            quick_replies.extend([
                "我理解您的担忧，让我立即为您处理",
                "非常抱歉给您带来不便",
                "您的反馈对我们很重要"
            ])
        elif emotion == 'positive':
            quick_replies.extend([
                "感谢您的认可",
                "很高兴能帮助到您",
                "谢谢您的耐心"
            ])
        
        if urgency == 'high':
            quick_replies.extend([
                "我马上为您优先处理",
                "这确实比较紧急，让我立即跟进"
            ])
        
        if message_type == 'question':
            quick_replies.extend([
                "让我为您查询一下",
                "我来为您详细说明",
                "请稍等，我查看相关信息"
            ])
        
        # 通用快速回复
        quick_replies.extend([
            "好的，我明白了",
            "请您稍等片刻",
            "还有其他需要帮助的吗？"
        ])
        
        # 去重并限制数量
        unique_replies = list(set(quick_replies))
        return unique_replies[:6]  # 最多返回6个快速回复
    
    async def _generate_handling_tips(
        self,
        message_analysis: Dict[str, Any],
        session_context: Dict[str, Any],
        tenant_id: UUID
    ) -> List[str]:
        """
        生成处理建议
        
        Args:
            message_analysis: 消息分析结果
            session_context: 会话上下文
            tenant_id: 租户ID
            
        Returns:
            List[str]: 处理建议列表
        """
        tips = []
        
        emotion = message_analysis.get('emotion', 'neutral')
        urgency = message_analysis.get('urgency', 'low')
        complexity = message_analysis.get('complexity', 'moderate')
        message_type = message_analysis.get('message_type', 'other')
        
        # 根据情绪状态提供建议
        if emotion == 'negative':
            tips.append("💡 先表达同理心，不要急于解释或辩解")
            tips.append("🔥 用户情绪较为激动，保持冷静和耐心")
            tips.append("🎯 关注解决问题，而不是讨论责任")
        elif emotion == 'frustrated':
            tips.append("⚠️ 用户可能感到挫败，提供清晰的解决路径")
            tips.append("🤝 主动承担协助责任，降低用户心理负担")
        
        # 根据紧急程度提供建议
        if urgency == 'high':
            tips.append("🚨 高优先级处理，及时响应和跟进")
            tips.append("⏰ 预估处理时间并及时同步进展")
        elif urgency == 'critical':
            tips.append("🔴 紧急情况，考虑升级处理流程")
        
        # 根据复杂程度提供建议
        if complexity == 'complex':
            tips.append("🧩 问题较为复杂，可能需要分步骤处理")
            tips.append("📋 建议详细记录处理过程")
            tips.append("👥 如需要，及时寻求同事或主管协助")
        
        # 根据消息类型提供建议
        if message_type == 'complaint':
            tips.append("📢 投诉处理：倾听→理解→道歉→解决→跟进")
            tips.append("📝 详细记录投诉内容，便于后续改进")
        elif message_type == 'question':
            tips.append("❓ 确保完全理解问题后再回答")
            tips.append("📚 提供准确信息，不确定时查证后回复")
        
        # 会话上下文建议
        message_count = session_context.get('message_stats', {}).get('total_messages', 0)
        if message_count > 10:
            tips.append("💬 对话较长，适时总结要点确保理解一致")
        
        return tips[:5]  # 最多返回5个建议
    
    async def _get_llm_provider(self, tenant_id: UUID) -> BaseLLMProvider:
        """
        获取LLM提供商
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            BaseLLMProvider: LLM提供商实例
        """
        cache_key = f"suggestion_{tenant_id}"
        
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # 使用OpenAI作为建议服务的默认提供商
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0.7,  # 适中的创造性
            max_tokens=1500
        )
        
        provider = OpenAIProvider(
            config=config,
            api_key="your-api-key",  # 应该从配置中获取
            base_url="https://api.openai.com/v1"
        )
        
        self._providers[cache_key] = provider
        return provider 