import json
import time
from typing import List, Dict, Optional, Generator
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger
from .prompts import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_BUILD_PROMPT,
    OUTLINE_OPTIMIZE_PROMPT,
    VOLUME_GENERATION_PROMPT,
    CHAPTER_SUMMARY_PROMPT,
    CHAPTER_CONTENT_PROMPT,
    SELF_OPTIMIZE_PROMPT,
    TITLE_SUGGESTION_PROMPT,
    TITLE_REWRITE_PROMPT,
    DESCRIPTION_OPTIMIZE_PROMPT,
    VOLUME_OPTIMIZE_PROMPT,
    CHAPTER_OPTIMIZE_PROMPT,
    CHAPTER_VERIFY_PROMPT,
    CHAPTER_SPLIT_PROMPT,
    CHAPTER_CONTINUE_PROMPT,
    CHAPTER_OPTIMIZE_CONTENT_PROMPT,
    PROJECT_INFO_GENERATION_PROMPT
)

MAX_HISTORY_MESSAGES = 10

def log_token_usage(task_type: str, prompt_tokens: int, completion_tokens: int, user=None, project=None):
    '''记录Token使用日志'''
    try:
        from apps.core.models import TokenUsageLog
        TokenUsageLog.objects.create(
            user=user,
            project=project,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cache_hit=False
        )
    except Exception as e:
        logger.error(f"记录Token使用失败: {e}")

class LLMService:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )
    
    def _call_with_retry(self, messages: List, stream: bool = False):
        retry_count = 0
        while retry_count < settings.LLM_RETRY:
            try:
                if stream:
                    return self.llm.stream(messages)
                else:
                    return self.llm.invoke(messages)
            except Exception as e:
                logger.error(f"LLM调用失败: {e}, 重试 {retry_count + 1}/{settings.LLM_RETRY}")
                retry_count += 1
                time.sleep(settings.LLM_RETRY_INTERVAL)
        raise Exception(f"LLM调用失败，已重试 {settings.LLM_RETRY} 次")
    
    def _compress_messages(self, messages: List[Dict]) -> List[Dict]:
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return messages
        
        compressed = []
        user_messages = [m for m in messages if m['role'] == 'user']
        assistant_messages = [m for m in messages if m['role'] == 'assistant']
        
        if len(user_messages) > 5:
            user_messages = user_messages[-5:]
        if len(assistant_messages) > 5:
            assistant_messages = assistant_messages[-5:]
        
        for i in range(max(len(user_messages), len(assistant_messages))):
            if i < len(user_messages):
                compressed.append(user_messages[i])
            if i < len(assistant_messages):
                compressed.append(assistant_messages[i])
        
        return compressed
    
    def build_outline(self, user_input: str, current_outline: str = "", messages: Optional[List[Dict]] = None, user=None, project=None) -> str:
        formatted_messages = [SystemMessage(content=OUTLINE_SYSTEM_PROMPT)]
        
        if messages:
            compressed_messages = self._compress_messages(messages)
            for msg in compressed_messages:
                if msg['role'] == 'user':
                    formatted_messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    formatted_messages.append(AIMessage(content=msg['content']))
        
        if not current_outline or current_outline.strip() == "":
            prompt = OUTLINE_BUILD_PROMPT.format(user_input=user_input)
        else:
            prompt = OUTLINE_OPTIMIZE_PROMPT.format(
                current_outline=current_outline,
                user_feedback=user_input
            )
        
        formatted_messages.append(HumanMessage(content=prompt))
        response = self._call_with_retry(formatted_messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('outline', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content
    
    def build_outline_stream(self, user_input: str, current_outline: str = "", messages: Optional[List[Dict]] = None, user=None, project=None) -> Generator[str, None, None]:
        formatted_messages = [SystemMessage(content=OUTLINE_SYSTEM_PROMPT)]
        
        if messages:
            compressed_messages = self._compress_messages(messages)
            for msg in compressed_messages:
                if msg['role'] == 'user':
                    formatted_messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    formatted_messages.append(AIMessage(content=msg['content']))
        
        if not current_outline or current_outline.strip() == "":
            prompt = OUTLINE_BUILD_PROMPT.format(user_input=user_input)
        else:
            prompt = OUTLINE_OPTIMIZE_PROMPT.format(
                current_outline=current_outline,
                user_feedback=user_input
            )
        
        formatted_messages.append(HumanMessage(content=prompt))
        
        total_output_tokens = 0
        for chunk in self._call_with_retry(formatted_messages, stream=True):
            if chunk.content:
                total_output_tokens += len(chunk.content) // 4
                yield chunk.content
        
        log_token_usage('outline', len(prompt) // 4, total_output_tokens, user, project)
    
    def generate_volumes(self, outline: str, user=None, project=None) -> List[Dict]:
        prompt = VOLUME_GENERATION_PROMPT.format(outline=outline)
        
        messages = [
            SystemMessage(content="你是一位专业的小说结构设计助手，请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('volume', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            result = json.loads(response.content)
            return result.get('volumes', [])
        except json.JSONDecodeError:
            logger.error(f"解析卷生成响应失败: {response.content}")
            return []
    
    def optimize_volumes(self, outline: str, current_volumes: str, user_feedback: str, user=None, project=None) -> List[Dict]:
        prompt = VOLUME_OPTIMIZE_PROMPT.format(
            current_volumes=current_volumes,
            outline=outline,
            user_feedback=user_feedback
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说结构设计助手，请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('volume', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            result = json.loads(response.content)
            return result.get('volumes', [])
        except json.JSONDecodeError:
            logger.error(f"解析卷优化响应失败: {response.content}")
            return []
    
    def generate_chapter_summaries(self, outline: str, volume_number: int, volume_title: str, volume_summary: str, user=None, project=None) -> List[Dict]:
        prompt = CHAPTER_SUMMARY_PROMPT.format(
            outline=outline,
            volume_number=volume_number,
            volume_title=volume_title,
            volume_summary=volume_summary
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说章节设计助手，请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('chapter', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            result = json.loads(response.content)
            return result.get('chapters', [])
        except json.JSONDecodeError:
            logger.error(f"解析章节概要响应失败: {response.content}")
            return []
    
    def generate_chapter_summaries_stream(self, outline: str, volume_number: int, volume_title: str, volume_summary: str, user=None, project=None) -> Generator[str, None, None]:
        prompt = CHAPTER_SUMMARY_PROMPT.format(
            outline=outline,
            volume_number=volume_number,
            volume_title=volume_title,
            volume_summary=volume_summary
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说章节设计助手，请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        total_output_tokens = 0
        for chunk in self._call_with_retry(messages, stream=True):
            if chunk.content:
                total_output_tokens += len(chunk.content) // 4
                yield chunk.content
        
        log_token_usage('chapter', len(prompt) // 4, total_output_tokens, user, project)
    
    def optimize_chapter_summaries(self, volume_title: str, volume_summary: str, current_chapters: str, user_feedback: str, user=None, project=None) -> List[Dict]:
        prompt = CHAPTER_OPTIMIZE_PROMPT.format(
            current_chapters=current_chapters,
            volume_title=volume_title,
            volume_summary=volume_summary,
            user_feedback=user_feedback
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说章节设计助手，请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('chapter', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            result = json.loads(response.content)
            return result.get('chapters', [])
        except json.JSONDecodeError:
            logger.error(f"解析章节优化响应失败: {response.content}")
            return []
    
    def generate_chapter_content(self, outline: str, volume_title: str, volume_summary: str, 
                                 chapter_number: int, chapter_title: str, chapter_summary: str,
                                 reference_content: Optional[str] = None, user=None, project=None) -> str:
        reference_context = ""
        if reference_content:
            reference_context = f"上一章节的内容（作为写作参考，保持风格和情节连续性）:\n{reference_content}\n\n"
        
        prompt = CHAPTER_CONTENT_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            reference_context=reference_context
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说创作家，擅长写精彩的小说章节。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('content', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content
    
    def generate_chapter_content_stream(self, outline: str, volume_title: str, volume_summary: str,
                                        chapter_number: int, chapter_title: str, chapter_summary: str,
                                        reference_content: Optional[str] = None, user=None, project=None) -> Generator[str, None, None]:
        reference_context = ""
        if reference_content:
            reference_context = f"上一章节的内容（作为写作参考，保持风格和情节连续性）:\n{reference_content}\n\n"
        
        prompt = CHAPTER_CONTENT_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            reference_context=reference_context
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说创作家，擅长写精彩的小说章节。"),
            HumanMessage(content=prompt)
        ]
        
        total_output_tokens = 0
        for chunk in self._call_with_retry(messages, stream=True):
            if chunk.content:
                total_output_tokens += len(chunk.content) // 4
                yield chunk.content
        
        log_token_usage('content', len(prompt) // 4, total_output_tokens, user, project)
    
    def suggest_title(self, outline: str, user=None, project=None) -> str:
        prompt = TITLE_SUGGESTION_PROMPT.format(outline=outline)
        
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('other', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content
    
    def rewrite_title(self, original_title: str, user=None, project=None) -> List[str]:
        prompt = TITLE_REWRITE_PROMPT.format(original_title=original_title)
        
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。请以JSON数组格式返回5个建议的书名。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('other', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            result = json.loads(response.content)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return result.get('titles', [])
            return []
        except json.JSONDecodeError:
            logger.error(f"解析重写标题响应失败: {response.content}")
            return []
    
    def optimize_description(self, description: str, user=None, project=None) -> str:
        if not description or description.strip() == "":
            return "请输入小说简介"
        
        prompt = DESCRIPTION_OPTIMIZE_PROMPT.format(description=description)
        
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长优化和润色小说简介。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('other', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content
    
    def self_optimize(self, content: str, user=None, project=None) -> str:
        prompt = SELF_OPTIMIZE_PROMPT.format(content=content)
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长优化和润色小说内容。"),
            HumanMessage(content=prompt)
        ]
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('other', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content

    def verify_chapter_flow(self, outline: str, volume_title: str, volume_summary: str,
                            chapter_number: int, chapter_title: str, chapter_content: str,
                            prev_chapter_content: str = "", user=None, project=None) -> str:
        prompt = CHAPTER_VERIFY_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            prev_chapter_content=prev_chapter_content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_content=chapter_content
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说审核编辑，擅长校验小说内容的连贯性和逻辑性。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('content', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content

    def split_chapter(self, outline: str, volume_title: str, volume_summary: str,
                      chapter_number: int, chapter_title: str, chapter_content: str,
                      user=None, project=None) -> Optional[Dict]:
        prompt = CHAPTER_SPLIT_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_content=chapter_content
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说编辑，擅长合理地拆分过长的章节。请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('content', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"解析章节拆分响应失败: {response.content}")
            return None

    def continue_chapter(self, outline: str, volume_title: str, volume_summary: str,
                        chapter_number: int, chapter_title: str, kept_content: str,
                        next_chapter_number: int, user=None, project=None) -> Optional[Dict]:
        prompt = CHAPTER_CONTINUE_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            kept_content=kept_content,
            next_chapter_number=next_chapter_number
        )
        
        messages = [
            SystemMessage(content="你是一位专业的小说创作家，擅长续写和延伸章节内容。请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('content', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"解析章节延续响应失败: {response.content}")
            return None

    def optimize_chapter_content(self, outline: str, volume_title: str, volume_summary: str,
                                  chapter_number: int, chapter_title: str, chapter_content: str,
                                  user=None, project=None) -> str:
        prompt = CHAPTER_OPTIMIZE_CONTENT_PROMPT.format(
            outline=outline,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_content=chapter_content
        )
        
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长优化和润色小说章节内容。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('content', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        return response.content

    def generate_project_info(self, outline: str, user=None, project=None) -> Optional[Dict]:
        prompt = PROJECT_INFO_GENERATION_PROMPT.format(outline=outline)
        
        messages = [
            SystemMessage(content="你是一位专业的文学编辑，擅长为小说创作吸引人的书名和简介。请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ]
        
        response = self._call_with_retry(messages)
        
        if hasattr(response, 'usage_metadata'):
            log_token_usage('other', 
                          response.usage_metadata.get('input_tokens', 0),
                          response.usage_metadata.get('output_tokens', 0),
                          user, project)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"解析项目信息生成响应失败: {response.content}")
            return None
