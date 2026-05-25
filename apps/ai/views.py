"""
AI views - 通用 AI 功能视图
"""
import json
import time
from typing import Optional
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion
from apps.user.models import TokenUsageLog
from apps.ai.llm import get_llm
from apps.ai.prompts import (
    PROJECT_INFO_GENERATION_PROMPT,
    TITLE_SUGGESTION_PROMPT,
    TITLE_REWRITE_PROMPT,
    DESCRIPTION_OPTIMIZE_PROMPT,
)


def log_token_usage(task_type: str, prompt_tokens: int, completion_tokens: int, user=None, project=None):
    try:
        TokenUsageLog.objects.create(
            user=user,
            project=project,
            model_name=settings.LLM_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    except Exception as e:
        logger.error(f"记录Token使用失败: {e}")


def _call_with_retry(messages, stream=False, timeout=None, user=None, scene="default"):
    max_retries = settings.LLM_RETRY
    retry_interval = settings.LLM_RETRY_INTERVAL

    llm = get_llm(user=user, scene=scene, timeout=timeout)

    prompt_messages = []
    for msg in messages:
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

    for retry_count in range(max_retries):
        try:
            if stream:
                def gen():
                    for chunk in chain.stream({}):
                        if hasattr(chunk, 'content'):
                            yield chunk.content
                        else:
                            yield str(chunk)
                return gen()
            else:
                result = chain.invoke({})
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


def generate_project_info(outline: str, user=None, project=None) -> Optional[dict]:
    prompt = PROJECT_INFO_GENERATION_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说创作吸引人的书名和简介。请严格按照JSON格式返回。"),
        HumanMessage(content=prompt)
    ]

    response = _call_with_retry(messages, user=user, scene="default")

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.error(f"解析项目信息生成响应失败: {response}")
        return None


def suggest_title(outline: str, user=None, project=None) -> str:
    prompt = TITLE_SUGGESTION_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。"),
        HumanMessage(content=prompt)
    ]

    return _call_with_retry(messages, user=user, scene="default")


def rewrite_title(original_title: str, user=None, project=None) -> list:
    prompt = TITLE_REWRITE_PROMPT.format(original_title=original_title)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。请以JSON数组格式返回5个建议的书名。"),
        HumanMessage(content=prompt)
    ]

    response = _call_with_retry(messages, user=user, scene="default")

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get('titles', [])
        return []
    except json.JSONDecodeError:
        logger.error(f"解析重写标题响应失败: {response}")
        return []


def optimize_description(description: str, user=None, project=None) -> str:
    if not description or description.strip() == "":
        return "请输入小说简介"

    prompt = DESCRIPTION_OPTIMIZE_PROMPT.format(description=description)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长优化和润色小说简介。"),
        HumanMessage(content=prompt)
    ]

    return _call_with_retry(messages, user=user, scene="default")


class GenerateProjectInfoView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        
        finalized_outline = project.outline_versions.filter(is_deleted=False, is_finalized=True).order_by('-version_number').first()
        
        if not finalized_outline:
            latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
            if not latest_outline:
                return JsonResponse({'success': False, 'message': '暂无大纲，无法生成项目名和简介'})
            outline_content = latest_outline.content
        else:
            outline_content = finalized_outline.content
        
        if not outline_content or outline_content.strip() == "":
            return JsonResponse({'success': False, 'message': '大纲内容为空，无法生成项目名和简介'})
        
        result = generate_project_info(outline_content, user=request.user, project=project)
        
        if result:
            titles = []
            if 'titles' in result and isinstance(result['titles'], list):
                titles = result['titles']
            elif 'title' in result:
                titles = [result['title']]
            
            if titles and 'description' in result:
                return JsonResponse({
                    'success': True,
                    'titles': titles,
                    'description': result['description']
                })
        
        return JsonResponse({'success': False, 'message': '生成失败，请重试'})


class SuggestTitleView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        outline_version_id = request.data.get('outline_version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project__user=request.user)
        
        suggestions = suggest_title(outline_version.content)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class RewriteTitleView(View):
    def post(self, request):
        original_title = request.POST.get('original_title')
        
        suggestions = rewrite_title(original_title)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class OptimizeDescriptionView(View):
    def post(self, request):
        description = request.POST.get('description')
        
        optimized = optimize_description(description)
        
        return JsonResponse({'success': True, 'optimized': optimized})