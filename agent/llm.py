"""
统一的 LLM 调用封装
支持流式/非流式调用，可动态配置参数
"""
import json
import time
from typing import List, Dict, Optional, Generator, Any, Union
from django.http import StreamingHttpResponse
from django.conf import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from django.conf import settings
from loguru import logger
from apps.user.models import TokenUsageLog
from apps.user.models import LLMConfig as UserLLMBaseConfig
from apps.user.models import UserLLMConfig
from .llm_scenes import get_scene_config


class LLMConfig:
    """LLM 配置类"""
    def __init__(
        self,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        top_p: float = None,
        frequency_penalty: float = None,
        presence_penalty: float = None,
        timeout: int = None,
        stream: bool = True,
        **kwargs
    ):
        self.model = model or getattr(settings, 'LLM_MODEL', 'gpt-4o')
        self.temperature = temperature if temperature is not None else getattr(settings, 'LLM_TEMPERATURE', 0.7)
        self.max_tokens = max_tokens or getattr(settings, 'LLM_MAX_TOKENS', 4096)
        self.top_p = top_p or getattr(settings, 'LLM_TOP_P', None)
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.timeout = timeout or getattr(settings, 'LLM_TIMEOUT', 120)
        self.stream = stream
        self.extra = kwargs

    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'timeout': self.timeout,
        }
        if self.top_p is not None:
            result['top_p'] = self.top_p
        if self.frequency_penalty is not None:
            result['frequency_penalty'] = self.frequency_penalty
        if self.presence_penalty is not None:
            result['presence_penalty'] = self.presence_penalty
        result.update(self.extra)
        return result


class LLM:
    """统一的 LLM 调用类"""

    # 预定义配置模板
    CONFIG_CREATIVE = LLMConfig(temperature=0.8, max_tokens=2000, stream=False)
    CONFIG_BALANCED = LLMConfig(temperature=0.7, max_tokens=1500, stream=False)
    CONFIG_REASONING = LLMConfig(temperature=0.3, max_tokens=1500, stream=False)
    CONFIG_STREAM = LLMConfig(temperature=0.7, max_tokens=2000, stream=True)
    CONFIG_DETAILED = LLMConfig(temperature=0.7, max_tokens=4000, stream=False)

    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        self._client = None

    @property
    def client(self) -> ChatOpenAI:
        """获取或创建 LLM 客户端"""
        if self._client is None:
            params = self.config.to_dict()
            self._client = ChatOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                **params
            )
        return self._client
    
    def as_runnable(self) -> ChatOpenAI:
        """
        返回原生的 ChatOpenAI 实例，支持 LCEL (LangChain Expression Language)
        
        使用示例：
            llm = LLM(LLMConfig(model='gpt-4o', temperature=0.7))
            chain = prompt | llm.as_runnable() | JsonOutputParser()
            result = chain.invoke({"input": "..."})
        
        Returns:
            ChatOpenAI: 原生的 LangChain ChatOpenAI 实例，支持 LCEL 链式调用
        """
        return self.client
    
    @classmethod
    def creative(cls) -> 'LLM':
        """创建创意生成配置的 LLM 实例（高温、大token）"""
        return cls(cls.CONFIG_CREATIVE)
    
    @classmethod
    def balanced(cls) -> 'LLM':
        """创建平衡配置的 LLM 实例（中等温度）"""
        return cls(cls.CONFIG_BALANCED)
    
    @classmethod
    def reasoning(cls) -> 'LLM':
        """创建推理配置的 LLM 实例（低温、精准）"""
        return cls(cls.CONFIG_REASONING)
    
    @classmethod
    def stream(cls) -> 'LLM':
        """创建流式输出配置的 LLM 实例"""
        return cls(cls.CONFIG_STREAM)
    
    @classmethod
    def detailed(cls) -> 'LLM':
        """创建详细输出配置的 LLM 实例（大token）"""
        return cls(cls.CONFIG_DETAILED)
    
    @classmethod
    def with_params(cls, **kwargs) -> 'LLM':
        """
        使用指定参数创建 LLM 实例
        
        使用示例：
            llm = LLM.with_params(temperature=0.7, max_tokens=1200, stream=False)
        
        Args:
            **kwargs: LLMConfig 支持的参数
        
        Returns:
            LLM: 配置好的 LLM 实例
        """
        return cls(LLMConfig(**kwargs))

    def _create_client(self, config: LLMConfig) -> ChatOpenAI:
        """
        根据配置创建 ChatOpenAI 客户端
        
        Args:
            config: LLM 配置
        
        Returns:
            ChatOpenAI: 配置好的客户端实例
        """
        params = config.to_dict()
        client_params = {k: v for k, v in params.items() if k != 'stream'}
        return ChatOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            **client_params
        )

    def _merge_config(self, config: Optional[LLMConfig], stream: Optional[bool]) -> LLMConfig:
        """
        合并配置
        
        Args:
            config: 可选的配置
            stream: 可选的流式标志
        
        Returns:
            LLMConfig: 合并后的配置
        """
        if config:
            merged_config = LLMConfig(
                **{**self.config.to_dict(), **config.to_dict()}
            )
        else:
            merged_config = self.config
        
        if stream is not None:
            merged_config = LLMConfig(**{**merged_config.to_dict(), 'stream': stream})
        
        return merged_config

    def invoke(
        self,
        messages: List[BaseMessage],
        config: LLMConfig = None,
        stream: bool = None
    ) -> Union[Any, Generator[str, None, None]]:
        """
        调用 LLM

        Args:
            messages: 消息列表
            config: 可选的配置，会合并到默认配置
            stream: 是否流式返回，默认使用 self.config.stream

        Returns:
            非流式: 返回完整响应对象
            流式: 返回生成器，逐块产出字符串
        """
        merged_config = self._merge_config(config, stream)
        client = self._create_client(merged_config)

        if merged_config.stream:
            return self._stream_invoke(client, messages)
        else:
            return client.invoke(messages)

    def _stream_invoke(
        self,
        client: ChatOpenAI,
        messages: List[BaseMessage]
    ) -> Generator[str, None, None]:
        """流式调用"""
        try:
            response = client.stream(messages)
            for chunk in response:
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"流式调用异常: {e}")
            raise

    def invoke_with_retry(
        self,
        messages: List[BaseMessage],
        config: LLMConfig = None,
        stream: bool = None,
        max_retries: int = None,
        retry_interval: int = None
    ) -> Union[Any, Generator[str, None, None]]:
        """
        带重试的 LLM 调用

        Args:
            messages: 消息列表
            config: 可选的配置
            stream: 是否流式
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）

        Returns:
            非流式: 返回完整响应对象
            流式: 返回生成器，逐块产出字符串
        """
        max_retries = max_retries or getattr(settings, 'LLM_RETRY', 3)
        retry_interval = retry_interval or getattr(settings, 'LLM_RETRY_INTERVAL', 2)

        last_error = None
        for attempt in range(max_retries):
            try:
                result = self.invoke(messages, config, stream)
                return result
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"LLM调用失败: {error_msg}, 重试 {attempt + 1}/{max_retries}")

                # 超时错误增加等待时间
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    retry_interval *= 2

                if attempt < max_retries - 1:
                    time.sleep(retry_interval)

        raise Exception(f"LLM调用失败，已重试 {max_retries} 次: {last_error}")





def get_llm(user=None, scene=None, **kwargs) -> ChatOpenAI:
    """
    根据用户和场景获取 LLM 实例
    
    配置优先级（从高到低）：
    1. kwargs 参数（临时覆盖）
    2. 用户场景配置（UserLLMConfig）
    3. 用户默认配置（LLMConfig）
    4. 场景默认配置（LLM_SCENES）
    5. 系统默认配置（settings）
    
    Args:
        user: 用户对象
        scene: 场景标识（如 "worldview_build"）
        **kwargs: 临时覆盖参数
    
    Returns:
        ChatOpenAI: 配置好的客户端实例
    """
    
    
    # 1. 系统默认配置
    config = {
        "api_key": settings.LLM_API_KEY,
        "base_url": settings.LLM_BASE_URL,
        "model": getattr(settings, "LLM_MODEL", "gpt-4o"),
        "temperature": getattr(settings, "LLM_TEMPERATURE", 0.7),
        "max_tokens": getattr(settings, "LLM_MAX_TOKENS", 4096),
        "timeout": getattr(settings, "LLM_TIMEOUT", 120),
    }
    
    # 2. 场景默认配置
    if scene:
        scene_config = get_scene_config(scene)
        config["temperature"] = scene_config.get("default_temperature", config["temperature"])
        config["max_tokens"] = scene_config.get("default_max_tokens", config["max_tokens"])
    
    # 3. 用户默认配置（LLMConfig）
    user_default_config = None
    if user:
        try:
            
            user_default_config = UserLLMBaseConfig.objects.filter(
                user=user,
                is_default=True,
                is_active=True
            ).first()
            if user_default_config:
                config["api_key"] = user_default_config.get_api_key() or config["api_key"]
                if user_default_config.base_url:
                    config["base_url"] = user_default_config.base_url
                config["model"] = user_default_config.model_name
                config["temperature"] = user_default_config.temperature
                config["max_tokens"] = user_default_config.max_tokens
        except Exception as e:
            pass  # 无用户配置，保持现有配置
    
    # 4. 用户场景配置（UserLLMConfig）
    if user and scene:
        try:
            user_scene_config = UserLLMConfig.objects.filter(
                user=user,
                task_type=scene
            ).first()
            if user_scene_config:
                # 使用用户场景配置关联的 LLM 配置
                if user_scene_config.llm_config and user_scene_config.llm_config.is_active:
                    config["api_key"] = user_scene_config.llm_config.get_api_key() or config["api_key"]
                    if user_scene_config.llm_config.base_url:
                        config["base_url"] = user_scene_config.llm_config.base_url
                    config["model"] = user_scene_config.llm_config.model_name
                # 覆盖用户场景的温度和 token 数
                config["temperature"] = user_scene_config.temperature
                config["max_tokens"] = user_scene_config.max_tokens
        except Exception as e:
            pass  # 无场景配置，保持现有配置
    
    # 5. kwargs 最终覆盖
    config.update(kwargs)
    
    # 构建参数（移除 None 值）
    final_params = {k: v for k, v in config.items() if v is not None}
    
    return ChatOpenAI(**final_params)


def create_llm(config: LLMConfig = None) -> LLM:
    """创建新的 LLM 实例"""
    return LLM(config)


# ========== Token 日志 ==========

def log_token_usage(task_type: str, result=None, prompt_tokens: int = 0, completion_tokens: int = 0, user=None, project=None):
    """记录Token使用量

    支持两种调用方式：
    1. 传入 result 对象，自动从 usage_metadata 提取 token 数：
       log_token_usage('content', result=result, user=user, project=project)
    2. 手动传入 token 数（流式等无法获取 usage_metadata 的场景）：
       log_token_usage('content', prompt_tokens=100, completion_tokens=200, user=user, project=project)
    """
    # 优先从 result 对象提取
    if result is not None and hasattr(result, 'usage_metadata') and result.usage_metadata:
        prompt_tokens = result.usage_metadata.get('input_tokens', 0)
        completion_tokens = result.usage_metadata.get('output_tokens', 0)

    if prompt_tokens == 0 and completion_tokens == 0:
        return

    try:
        TokenUsageLog.objects.create(
            user=user,
            project=project,
            model_name='',
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    except Exception as e:
        logger.error(f"记录Token使用失败: {e}")


# ========== LLM 调用 + 重试 ==========

def call_llm_with_retry(chain_or_messages, input_vars=None, stream=False, timeout=None, user=None, scene="default", project=None, task_type=None):
    """
    统一的LLM调用+重试方法，兼容三种调用风格：

    风格1（LCEL chain模式）：传入 ChatPromptTemplate | llm 构建的 chain + input_vars
        prompt = ChatPromptTemplate.from_messages([("system", ...), ("human", ...)])
        chain = prompt | llm
        call_llm_with_retry(chain, input_vars={...})

    风格2（messages模式）：传入消息列表（dict），自动构建 chain
        call_llm_with_retry(messages, timeout=60)

    风格3（BaseMessage模式）：传入 BaseMessage 对象列表，直接调用 LLM（避免 ChatPromptTemplate 解析问题）
        call_llm_with_retry([SystemMessage(...), HumanMessage(...)], scene="content_generate")

    Args:
        project: 项目对象，用于 token 日志记录
        task_type: 任务类型标识，用于 token 日志记录（默认使用 scene）
    """
    max_retries = settings.LLM_RETRY
    retry_interval = settings.LLM_RETRY_INTERVAL

    # 风格3: BaseMessage 对象列表，直接调用 LLM（避免 ChatPromptTemplate 解析问题）
    if input_vars is None and isinstance(chain_or_messages, list) and chain_or_messages and isinstance(chain_or_messages[0], BaseMessage):
        llm = get_llm(user=user, scene=scene, timeout=timeout)
        messages = chain_or_messages
        for retry_count in range(max_retries):
            try:
                if stream:
                    def gen():
                        for chunk in llm.stream(messages):
                            if hasattr(chunk, 'content'):
                                yield chunk.content
                            else:
                                yield str(chunk)
                    return gen()
                else:
                    result = llm.invoke(messages)
                    log_task = task_type or scene
                    log_token_usage(log_task, result=result, user=user, project=project)
                    if hasattr(result, 'content'):
                        return result.content
                    return str(result)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"LLM调用失败: {error_msg}, 重试 {retry_count + 1}/{max_retries}")
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    retry_interval *= 2
                if retry_count < max_retries - 1:
                    time.sleep(retry_interval)
        raise Exception(f"LLM调用失败，已重试 {max_retries} 次")

    # 判断调用风格（风格1或风格2）
    if input_vars is not None:
        # 风格1: chain + input_vars（chapter 应用使用）
        chain = chain_or_messages
    else:
        # 风格2: messages 列表（project/ai/note 应用使用）
        llm = get_llm(user=user, scene=scene, timeout=timeout)
        prompt_messages = []
        for msg in chain_or_messages:
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt_messages.append((role, content))
            else:
                if hasattr(msg, 'content'):
                    if hasattr(msg, 'role'):
                        prompt_messages.append((msg.role, msg.content))
                    elif isinstance(msg, SystemMessage):
                        prompt_messages.append(('system', msg.content))
                    elif isinstance(msg, HumanMessage):
                        prompt_messages.append(('user', msg.content))
        prompt = ChatPromptTemplate.from_messages(prompt_messages)
        chain = prompt | llm
        input_vars = {}

    for retry_count in range(max_retries):
        try:
            if stream:
                def gen():
                    for chunk in chain.stream(input_vars):
                        if hasattr(chunk, 'content'):
                            yield chunk.content
                        else:
                            yield str(chunk)
                return gen()
            else:
                result = chain.invoke(input_vars)
                # 记录 token 使用量
                log_task = task_type or scene
                log_token_usage(log_task, result=result, user=user, project=project)
                if hasattr(result, 'content'):
                    return result.content
                return str(result)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM调用失败: {error_msg}, 重试 {retry_count + 1}/{max_retries}")
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                retry_interval *= 2
            if retry_count < max_retries - 1:
                time.sleep(retry_interval)

    raise Exception(f"LLM调用失败，已重试 {max_retries} 次")


def stream_llm_response(system_prompt, user_prompt, prompt_vars, user, scene, timeout=None, error_msg='操作失败，请重试', post_process=None):
    """通用 LLM 流式调用，返回 StreamingHttpResponse

    使用 LCEL (LangChain Expression Language) 构建 chain，system/user 分开定义提示词，
    固定不变的上下文（世界观、人物等）放 system prompt 优先命中缓存，变化部分放 user prompt。

    Args:
        system_prompt: 系统提示词模板（固定部分，含 {worldview_context} 等变量）
        user_prompt: 用户提示词模板（变化部分，含 {current_outline} 等变量）
        prompt_vars: 提示词变量字典，同时用于 system 和 user prompt 的 format
        user: 当前用户
        scene: LLM 场景标识
        timeout: 超时时间（秒）
        error_msg: 错误提示信息
        post_process: 可选后处理函数，接收 full_content，返回最终 data 值

    Returns:
        StreamingHttpResponse: SSE 流式响应
    """
    

    max_retries = getattr(settings, 'LLM_RETRY', 3)
    retry_interval = getattr(settings, 'LLM_RETRY_INTERVAL', 2)

    def generate():
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", user_prompt),
            ])
            llm = get_llm(user=user, scene=scene, timeout=timeout)
            chain = prompt | llm

            full_content = ""
            for retry_count in range(max_retries):
                try:
                    for chunk in chain.stream(prompt_vars):
                        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        full_content += chunk_content
                        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                    break
                except Exception as e:
                    err = str(e)
                    logger.error(f"LLM调用失败(scene={scene}): {err}, 重试 {retry_count + 1}/{max_retries}")
                    if "timeout" in err.lower() or "timed out" in err.lower():
                        retry_interval_current = retry_interval * (2 ** retry_count)
                    else:
                        retry_interval_current = retry_interval
                    if retry_count < max_retries - 1:
                        time.sleep(retry_interval_current)
                    else:
                        raise Exception(f"LLM调用失败，已重试 {max_retries} 次")

            if post_process:
                data_value = post_process(full_content)
            else:
                data_value = full_content

            yield f"data: {json.dumps({'type': 'complete', 'data': data_value}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"LLM流式调用异常(scene={scene}): {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(generate(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
