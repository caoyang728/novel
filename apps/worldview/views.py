import re
import json
import copy
import traceback
from loguru import logger

from django.http import JsonResponse, StreamingHttpResponse
from django.db import close_old_connections
from apps.project.base import BaseAPIView
from apps.project.models import ProjectList as Project
from agent.llm import get_llm
from agent.memory import compress_history

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .models import WorldView
from .prompts import (
    WORLDVIEW_STRUCTURE,
    WORLDVIEW_GAP_DETECTION_SYSTEM_PROMPT,
    WORLDVIEW_GAP_DETECTION_USER_PROMPT,
    WORLDVIEW_GAP_DETECTION_INTEGRATE_SYSTEM_PROMPT,
    WORLDVIEW_GAP_DETECTION_INTEGRATE_USER_PROMPT,
    WORLDVIEW_MACRO_CONSISTENCY_SYSTEM_PROMPT,
    WORLDVIEW_MACRO_CONSISTENCY_USER_PROMPT,
    WORLDVIEW_BUILD_SYSTEM_PROMPT,
    WORLDVIEW_BUILD_USER_PROMPT,
    WORLDVIEW_CHAT_SYSTEM_PROMPT,
    WORLDVIEW_CHAT_USER_PROMPT,
    WORLDVIEW_MACRO_CONSISTENCY_FIX_SYSTEM_PROMPT,
    WORLDVIEW_MACRO_CONSISTENCY_FIX_USER_PROMPT,
    WORLDVIEW_INIT_QUESTION_SYSTEM_PROMPT,
    WORLDVIEW_INIT_QUESTION_USER_PROMPT,
    get_layer_info,
    get_layers,
    get_field_cn_name,
)
from .serializers import (
    clean_worldview_layer,
    clean_worldview_data,
    prepare_worldview_for_llm,
)


class BaseWorldAPIView(BaseAPIView):

    def get_worldview(self, user, pk=None, project_id=None, worldview_id=None):
        try:
            if pk:
                return WorldView.objects.get(pk=pk, project__user=user)
            elif project_id:
                return WorldView.objects.get(project_id=project_id, project__user=user)
            elif worldview_id:
                return WorldView.objects.get(id=worldview_id, project__user=user)
        except WorldView.DoesNotExist:
            # pk 和 worldview_id 不存在时直接抛出异常，不自动创建
            if pk or worldview_id:
                raise
            # 只有 project_id 才自动创建
            worldview = WorldView.objects.create(project_id=project_id, **self.get_default_worldview_data())
            return worldview
        except Project.DoesNotExist:
            raise Exception('项目不存在')
        
    # ========== 辅助方法 =========
    def get_worldview_setting(self, worldview):
        """获取 世界观 基础设定"""
        if worldview.setting is None:
            return self.get_default_worldview_data()['setting']
        return worldview.setting

    def get_worldview_foundation(self, worldview):
        """获取 世界观 世界基础"""
        if worldview.foundation is None:
            return self.get_default_worldview_data()['foundation']
        return worldview.foundation

    def get_worldview_power(self, worldview):
        """获取 世界观 力量体系"""
        if worldview.power is None:
            return self.get_default_worldview_data()['power']
        return worldview.power

    def get_worldview_races(self, worldview):
        """获取 世界观 种族设定"""
        if worldview.races is None:
            return self.get_default_worldview_data()['races']
        return worldview.races

    def get_worldview_society(self, worldview):
        """获取 世界观 社会结构"""
        if worldview.society is None:
            return self.get_default_worldview_data()['society']
        return worldview.society

    def get_worldview_culture(self, worldview):
        """获取 世界观 文化/设定"""
        if worldview.culture is None:
            return self.get_default_worldview_data()['culture']
        return worldview.culture

    def get_worldview_history(self, worldview):
        """获取 世界观 历史设定"""
        if worldview.history is None:
            return self.get_default_worldview_data()['history']
        return worldview.history

    def get_worldview_special(self, worldview):
        """获取 世界观 特殊规则设定"""
        if worldview.special is None:
            return self.get_default_worldview_data().get('special', {})
        return worldview.special
    
    def error_response(self, message, status=400):
        return JsonResponse({'success': False, 'message': message}, status=status)

    def success_response(self, data=None, message='操作成功'):
        response = {'success': True}
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        return JsonResponse(response)

    def parse_request_data(self, request):
        try:
            return json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return None

    def get_default_worldview_data(self):
        """获取默认世界观数据"""
        return {
            'setting': {
                'identity': {'world_name': '', 'genre': ''},
                'position': {'identity': '', 'tone': ''},
                'overview': '',
                'conflict': ''
            },
            'foundation': {
                'geography': {'continent_distribution': '', 'special_terrain': ''},
                'calendar': {'era': '', 'days_per_year': '', 'seasons': '', 'festivals': ''},
                'rules': {'natural_laws': '', 'boundaries': '', 'axioms': []},
                'balance': ''
            },
            'power': {
                "energy": {"types": "", "distribution": "", "properties": ""},
                "level": "",
                "martial": {"categories": "", "inheritance": ""},
                "treasure": {"categories": "", "pills": ""},
                "beast": {"levels": "", "mythical": ""}
            },
            'races': {
                "category": "",
                "value": "",
                "trait": {"lifespan": "", "reproduction": "", "physique": ""},
                "relation": ""
            },
            'society': {
                "court": {"political_system": "", "bureaucracy": ""},
                "sect": {"levels": "", "relationships": ""},
                "martial": {"factions": "", "alliances": ""},
                "external": "",
                "strata": {"social_classes": "", "mobility": ""},
                "currency": {"types": "", "rules": ""},
                "resource": ""
            },
            'culture': {
                "custom": {"festivals": "", "rituals": ""},
                "language": {"languages": "", "writing_system": ""},
                "daily": {"clothing": "", "cuisine": "", "architecture": "", "transportation": ""},
                "religion": {"deities": "", "organization": "", "faith_differences": ""}
            },
            'history': {"ancient": "", "modern": "", "crisis": "", "destiny": "", "future": ""},
            'special': {
                "taboo": "", "secret": "",
                "fate": {"fortune_rules": "", "destiny_types": ""},
                "reincarnation": {"soul_rules": "", "mechanics": ""},
                "transmigration": "", "system": "", "rules": ""
            }
        }




class ApiWorldviewDataView(BaseWorldAPIView):
    """世界观数据API 通过项目ID或世界观ID获取"""
    # pk 来自 URL <int:pk> 路由；project_id 来自 URL <int:project_id> 路由

    def get(self, request, project_id=None, pk=None):
        try:
            if pk:
                worldview = self.get_worldview(request.user, pk=pk)
            else:
                worldview = self.get_worldview(request.user, project_id=project_id)
            
            return self.success_response({
                'worldview_id': worldview.id,
                'project_id': worldview.project.id,
                'setting': clean_worldview_layer('setting', self.get_worldview_setting(worldview)),
                'foundation': clean_worldview_layer('foundation', self.get_worldview_foundation(worldview)),
                'power': clean_worldview_layer('power', self.get_worldview_power(worldview)),
                'races': clean_worldview_layer('races', self.get_worldview_races(worldview)),
                'society': clean_worldview_layer('society', self.get_worldview_society(worldview)),
                'culture': clean_worldview_layer('culture', self.get_worldview_culture(worldview)),
                'history': clean_worldview_layer('history', self.get_worldview_history(worldview)),
                'special': clean_worldview_layer('special', self.get_worldview_special(worldview)),
                'created_at': worldview.created_at.isoformat(),
                'updated_at': worldview.updated_at.isoformat()
            })


        except WorldView.DoesNotExist:
            return self.error_response('世界观不存在', status=404)
        except Project.DoesNotExist:
            return self.error_response('项目不存在', status=404)
        except Exception as e:
            logger.error(f"获取世界观失败 {e}", exc_info=True)
            return self.error_response('服务器内部错误', status=500)

    def put(self, request, project_id, pk):
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        # 更新 WorldView 字段
        if 'setting' in data:
            worldview.setting = data['setting']
        if 'foundation' in data:
            worldview.foundation = data['foundation']
        if 'power' in data:
            worldview.power = data['power']
        if 'races' in data:
            worldview.races = data['races']
        if 'society' in data:
            worldview.society = data['society']
        if 'culture' in data:
            worldview.culture = data['culture']
        if 'history' in data:
            worldview.history = data['history']
        if 'special' in data:
            worldview.special = data['special']

        worldview.save()

        return self.success_response({
            'setting': worldview.setting,
            'foundation': worldview.foundation,
            'power': worldview.power,
            'races': worldview.races,
            'society': worldview.society,
            'culture': worldview.culture,
            'history': worldview.history,
            'special': worldview.special,
        })

    def delete(self, request, project_id, pk):
        """删除世界观"""
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        worldview.delete()
        return self.success_response(message='删除成功')



class ApiWorldviewDeepeningQuestionsView(BaseWorldAPIView):
    """生成深化问题API"""

    def post(self, request, project_id, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        try:
            # 获取完整 WorldView 数据
            worldview_detail = WorldView.objects.get(project=worldview.project)
            
            worldview_json = prepare_worldview_for_llm(worldview_detail)

            # 构建 LCEL 提示词
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_GAP_DETECTION_SYSTEM_PROMPT),
                ("user", WORLDVIEW_GAP_DETECTION_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_deepen")

            # 使用 LCEL 链式调用（不包含 JsonOutputParser，以便获取 usage_metadata）
            llm_chain = prompt | llm
            llm_result = llm_chain.invoke({
                "worldview": worldview_json,
            })
            self.log_token_usage('worldview_deepen', result=llm_result, user=request.user, project=worldview.project)

            # 手动解析 JSON
            try:
                parser = JsonOutputParser()
                result = parser.parse(llm_result.content)
            except Exception:
                result = llm_result.content

            # 验证结果格式
            if isinstance(result, list):
                questions = result
            else:
                return self.error_response('AI返回格式错误，请重试')
        except WorldView.DoesNotExist:
            return self.error_response('世界观详情不存在，请先生成世界观')
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self.error_response('AI调用失败，请重试')
        # logger.debug(questions)
        return self.success_response(questions)


class ApiWorldviewDeepeningSubmitView(BaseWorldAPIView):
    """提交深化问答答案API，并返回修改建议"""

    def post(self, request, project_id, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')
        
        qa_list = data.get('qaList', [])
        
        if not qa_list:
            return self.success_response(data=[], message='没有需要分析的问答内容')
        
        try:
            # 直接使用前端传递的问题和答案进行分析
            suggestions = self.analyze_answers(request.user, worldview, qa_list)
            return self.success_response(data=suggestions, message='提交成功')
        except Exception as e:
            logger.error(f"提交并分析失败 {e}")
            return self.error_response(f'分析失败: {str(e)}')

    def analyze_answers(self, user, worldview, qa_list):
        """分析用户回答，生成世界观修改建议"""
        try:
            # logger.info(f"开始分析回答，qa_list: {json.dumps(qa_list, ensure_ascii=False)}")
            
            # worldview 已经存在 WorldView 对象，直接使用           
            # 构建问答记录字符数            
            qa_records = ""
            for idx, qa in enumerate(qa_list):
                if isinstance(qa, dict):
                    answer = qa.get('answer', '').strip()
                    question = qa.get('question', '').strip()
                    if answer and question:
                        qa_records += f"Q{idx+1}: {question}\nA{idx+1}: {answer}\n\n"
            
            # logger.info(f"构建的问答记录 {repr(qa_records)}")
            
            if not qa_records.strip():
                logger.info("没有有效的问答内容")
                return []
            
            worldview_json = prepare_worldview_for_llm(worldview)

            # logger.info(f"世界观数据长 {len(worldview_json)} 字符")
            
            prompt_vars = {
                "worldview": worldview_json,
                "qa_records": qa_records.strip(),
            }
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_GAP_DETECTION_INTEGRATE_SYSTEM_PROMPT),
                ("user", WORLDVIEW_GAP_DETECTION_INTEGRATE_USER_PROMPT)
            ])
            
            # logger.info("正在调用 LLM...")
            llm = get_llm(user=user, scene="worldview_deepen")
            llm_chain = prompt | llm
            llm_result = llm_chain.invoke(prompt_vars)
            self.log_token_usage('worldview_deepen_integrate', result=llm_result, user=user, project=worldview.project)

            # 手动解析 JSON
            try:
                parser = JsonOutputParser()
                result = parser.parse(llm_result.content)
            except Exception:
                result = llm_result.content
            
            # logger.info(f"LLM 返回结果类型: {type(result)}")
            # logger.info(f"LLM 返回结果: {json.dumps(result, ensure_ascii=False) if result else 'None'}")
            
            if isinstance(result, list):
                # logger.info(f"返回 {len(result)} 条修改建议")
                return result
            else:
                # logger.info("返回结果不是列表，返回空数组")
                return []
        except WorldView.DoesNotExist:
            logger.error("WorldView 不存在")
            raise Exception('no worldview')
        except Exception as e:
            logger.error(f"分析回答失败: {e}", exc_info=True)
            raise Exception('internal server error')


class ApiWorldviewDeepeningApplyView(BaseWorldAPIView):
    """应用深化问答修改建议API"""

    def post(self, request, project_id, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')
        
        changes = data.get('changes', [])
        
        # logger.info(f"接收到 changes 数据: {changes}")
        
        if not changes:
            return self.error_response('没有要应用的修改')
        
        try:
            # 获取 WorldView 对象
            worldview_detail = WorldView.objects.get(project=worldview.project)
            
            # logger.info(f"接收 {len(changes)} 个修改请求")
            # logger.info(f"WorldView ID: {worldview_detail.id}, project_id: {worldview_detail.project_id}")
            
            # 记录修改结果
            applied_changes = []
            skipped_changes = []
            
            for idx, change in enumerate(changes):
                # 提取修改数据
                target_layer = change.get('targetLayer')  # 例如: "history"
                target_field = change.get('targetField')  # 例如: "history.future"
                new_value = change.get('newValue')        # 例如: "xxxxx"
                
                # logger.info(f"处理修改 {idx+1}: layer={target_layer}, field={target_field}, value={new_value}")
                
                # 检查必要字段是否存在
                if not target_layer or not target_field or new_value is None:
                    logger.warning(f"修改 {idx+1} 缺少必要字段")
                    skipped_changes.append({'index': idx, 'reason': '缺少必要字段'})
                    continue
                
                # 检查目标层级是否存在于模型中
                if not hasattr(worldview_detail, target_layer):
                    logger.warning(f"修改 {idx+1}: 目标层级 '{target_layer}' 不存在")
                    skipped_changes.append({'index': idx, 'reason': f"目标层级 '{target_layer}' 不存在"})
                    continue
                
                # 获取当前层级的完整数据（你的思路：先查询）
                current_layer_data = getattr(worldview_detail, target_layer, None)
                if current_layer_data is None:
                    layer_data = {}
                elif isinstance(current_layer_data, dict):
                    layer_data = current_layer_data.copy()  # 复制一份进行修改
                else:
                    layer_data = {}
                
                # logger.info(f"当前 {target_layer} 数据: {layer_data}")
                
                # 解析目标字段路径（支持嵌套）
                field_parts = target_field.split('.')
                
                # 关键修复：如果 targetField 开头是 targetLayer（例如 "history.future" 中 "history" 是层级名），则跳过第一个
                if field_parts[0] == target_layer:
                    field_parts = field_parts[1:]
                
                # 检查字段路径是否为空（当 targetField 只有一层且等于 targetLayer 时会发生）
                if not field_parts:
                    logger.warning(f"修改 {idx+1}: 字段路径为空，跳过（target_field='{target_field}', target_layer='{target_layer}'）")
                    skipped_changes.append({'index': idx, 'reason': '字段路径为空'})
                    continue
                
                # 导航到目标字段的父级
                current_dict = layer_data
                final_field_name = field_parts[-1]  # 最后一个是字段名
                
                # 遍历路径（除了最后一个）
                for part in field_parts[:-1]:
                    if part not in current_dict:
                        current_dict[part] = {}
                        logger.info(f"创建嵌套路径: {part}")
                    current_dict = current_dict[part]
                
                # 保存旧值用于日志
                old_value = current_dict.get(final_field_name)
                
                # 修改字段值（你的思路：修改future）
                current_dict[final_field_name] = new_value
                logger.info(f"修改 {target_field}: {old_value} -> {new_value}")
                
                # 将修改后的数据存回去（你的思路：将history存进去）
                setattr(worldview_detail, target_layer, layer_data)
                logger.info(f"保存修改后的 {target_layer}: {layer_data}")
                
                applied_changes.append({'index': idx, 'layer': target_layer, 'field': target_field})
            
            # 保存到数据库
            worldview_detail.save()
            logger.info(f"WorldView 保存成功，应用了 {len(applied_changes)} 个修改")
            
            return self.success_response({
                'applied': applied_changes,
                'skipped': skipped_changes
            }, message='修改已应用')

        except WorldView.DoesNotExist:
                return self.error_response('世界观详情不存在，请先生成世界观')
        except Exception as e:
            logger.error(f"应用修改失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.error_response(f'应用修改失败: {str(e)}')


class ApiWorldviewConsistencyView(BaseWorldAPIView):
    """一致性检查API"""

    def post(self, request, project_id, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        issues = []
        try:
            worldview_data = clean_worldview_data({
                'setting': self.get_worldview_setting(worldview),
                'foundation': self.get_worldview_foundation(worldview),
                'power': self.get_worldview_power(worldview),
                'races': self.get_worldview_races(worldview),
                'society': self.get_worldview_society(worldview),
                'culture': self.get_worldview_culture(worldview),
                'history': self.get_worldview_history(worldview),
                'special': self.get_worldview_special(worldview)
            })
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_MACRO_CONSISTENCY_SYSTEM_PROMPT),
                ("user", WORLDVIEW_MACRO_CONSISTENCY_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_consistency")

            llm_chain = prompt | llm
            llm_result = llm_chain.invoke({
                "worldview": json.dumps(worldview_data, ensure_ascii=False),
            })
            self.log_token_usage('worldview_consistency', result=llm_result, user=request.user, project=worldview.project)

            # 手动解析 JSON
            try:
                parser = JsonOutputParser()
                result = parser.parse(llm_result.content)
            except Exception:
                result = llm_result.content
            
            issues = result if isinstance(result, list) else []
            
            # 保存问题到临时存储，供后续修复使用
            self.request.session['consistency_issues'] = issues
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            issues = []

        return self.success_response({
            'issues': issues,
            'hasIssues': len(issues) > 0
        })


class ApiWorldviewConsistencyFixView(BaseWorldAPIView):
    """一致性修复API"""

    def post(self, request, project_id, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)

        # 获取AI发现的问题（从session）和用户手动补充的问题（从请求体）
        ai_issues = self.request.session.get('consistency_issues', [])
        manual_issues_text = (data or {}).get('manual_issues', '').strip()

        # 将手动输入的文本转为问题对象
        manual_issues = []
        if manual_issues_text:
            for line in manual_issues_text.split('\n'):
                line = line.strip()
                if line:
                    manual_issues.append({
                        'severity': 'manual',
                        'message': '用户手动补充',
                        'detail': line
                    })

        all_issues = ai_issues + manual_issues

        if not all_issues:
            return self.error_response('没有发现一致性问题，无需修复')

        try:
            # 构造完整的世界观数据结构
            worldview_data = {
                'setting': self.get_worldview_setting(worldview),
                'foundation': self.get_worldview_foundation(worldview),
                'power': self.get_worldview_power(worldview),
                'races': self.get_worldview_races(worldview),
                'society': self.get_worldview_society(worldview),
                'culture': self.get_worldview_culture(worldview),
                'history': self.get_worldview_history(worldview),
                'special': self.get_worldview_special(worldview)
            }
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_MACRO_CONSISTENCY_FIX_SYSTEM_PROMPT),
                ("user", WORLDVIEW_MACRO_CONSISTENCY_FIX_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_consistency")

            llm_chain = prompt | llm
            llm_result = llm_chain.invoke({
                "worldview_data": json.dumps(worldview_data, ensure_ascii=False),
                "consistency_issues": json.dumps(all_issues, ensure_ascii=False)
            })
            self.log_token_usage('worldview_consistency_fix', result=llm_result, user=request.user, project=worldview.project)

            # 手动解析 JSON
            try:
                parser = JsonOutputParser()
                result = parser.parse(llm_result.content)
            except Exception:
                result = llm_result.content
            
            suggestions = result if isinstance(result, list) else []
            
        except Exception as e:
            logger.error(f"生成修复建议失败: {e}")
            return self.error_response('生成修复建议失败')

        return self.success_response(suggestions)



class ApiWorldviewOptimizeView(BaseWorldAPIView):
    """世界观分层AI优化（通用）- 流式返回

    支持两种模式:
    - polish: 前端只传用户修改过的 dirty 字段，LLM 只润色这些字段
    - fill: 前端传空字段列表，LLM 只填充空白字段

    后端从 DB 读取当前层完整数据，用前端传的字段覆盖后发给 LLM。
    LLM 返回完整层 JSON，前端直接渲染。
    """

    def post(self, request, project_id, pk, layer):
        """AI优化指定层 — 字段级自动判断（有内容→润色，空白→填充）"""
        valid_layers = ('setting', 'foundation', 'power', 'races', 'society', 'culture', 'history', 'special')
        if layer not in valid_layers:
            return self.error_response('无效的层级参数', status=400)

        # 查询世界观数据
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        # 解析请求数据
        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        # 提取题材分类、层数据、需要处理的字段
        genre = data.get('genre', '')
        layer_flat_data = data.get('layer_data', {})
        changed_keys = data.get('changed_keys', [])  # 前端标记的字段 flat key 列表

        # 1. 从 DB 读取当前层的完整数据作为基础（而非空模板）
        db_layer_data = getattr(self, f'get_worldview_{layer}')(worldview)
        target_data = copy.deepcopy(db_layer_data)

        # 确保子字典存在
        config = LAYER_SAVE_CONFIG[layer]
        for sub in config['sub_dicts']:
            target_data.setdefault(sub, {})

        # 2. 将 frontend 传来的字段覆盖到 target_data 上
        special_fields = config.get('special_fields', {})
        for flat_key, nested_path in config['mappings']:
            if flat_key in layer_flat_data:
                value = layer_flat_data[flat_key]
                if flat_key in special_fields:
                    value = special_fields[flat_key](value)
                _set_nested(target_data, nested_path, value)

        # 3. 序列化器校验 + 清洗 target_data
        target_data = clean_worldview_layer(layer, target_data)

        # 4. 获取全量世界观（序列化清洗后），剔除当前层 → reference_worldview
        full_worldview = clean_worldview_data({
            'setting': self.get_worldview_setting(worldview),
            'foundation': self.get_worldview_foundation(worldview),
            'power': self.get_worldview_power(worldview),
            'races': self.get_worldview_races(worldview),
            'society': self.get_worldview_society(worldview),
            'culture': self.get_worldview_culture(worldview),
            'history': self.get_worldview_history(worldview),
            'special': self.get_worldview_special(worldview),
        })
        full_worldview.pop(layer, None)  # 剔除目标层，LLM 只用 reference 做跨层一致性参考

        # 5. 构建 polish_instruction — 告诉 LLM 哪些字段需要处理
        polish_instruction = self._build_polish_instruction(layer, changed_keys)

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_BUILD_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_BUILD_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")
                chain = prompt | llm

                full_content = ''
                last_chunk = None
                usage_chunk = None
                layer_name_cn, layer_structure = get_layer_info(layer)

                reference_json = json.dumps(full_worldview, ensure_ascii=False, indent=2)
                target_json = json.dumps(target_data, ensure_ascii=False, indent=2)

                stream_response = chain.stream({
                    "layer_name_cn": layer_name_cn,
                    "layer_structure": layer_structure,
                    "genre": genre,
                    "reference_worldview": reference_json,
                    "target_data": target_json,
                    "polish_instruction": polish_instruction,
                })

                for chunk in stream_response:
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    chunk_data = json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)
                    yield f"data: {chunk_data}\n\n"

                close_old_connections()
                self.log_token_usage(f'worldview_{layer}_field', result=last_chunk, usage_result=usage_chunk, user=request.user, project=worldview.project)

                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    json.loads(full_content)
                    complete_data = json.dumps({'type': 'complete', 'data': full_content}, ensure_ascii=False)
                    yield f"data: {complete_data}\n\n"
                except json.JSONDecodeError:
                    error_data = json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)
                    yield f"data: {error_data}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                error_data = json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def _build_polish_instruction(self, layer, changed_keys):
        """构建 LLM 润色字段指令。

        列出需要润色的字段中文名，LLM 仅润色这些字段中有内容的部分，
        空白字段和占位符字段原样不动。
        """
        if not changed_keys:
            return "无需润色任何字段。请直接原样返回输入数据，不做任何修改。"

        # 将 flat key 映射为中文字段名
        config = LAYER_SAVE_CONFIG.get(layer, {})
        mappings_dict = dict(config.get('mappings', []))
        field_names = []
        for flat_key in changed_keys:
            nested_path = mappings_dict.get(flat_key, flat_key)
            cn_name = get_field_cn_name(layer, nested_path)
            field_names.append(cn_name)

        fields_str = '、'.join(field_names)

        return (
            '请仅润色以下字段（只处理其中有内容的部分，空白字段和占位符字段保留原样）：'
            + fields_str +
            '。未列出的字段严格保持原样，一字不改。'
        )


def _set_nested(data, path, value):
    """Set nested dict value, creating intermediate dicts as needed."""
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


LAYER_SAVE_CONFIG = {
    'setting': {
        'sub_dicts': ['identity', 'position'],
        'mappings': [
            ('overview', 'overview'),
            ('conflict', 'conflict'),
            ('genre', 'identity.genre'),
            ('world_name', 'identity.world_name'),
            ('tone', 'position.tone'),
            ('identity', 'position.identity'),
        ],
    },
    'foundation': {
        'sub_dicts': ['geography', 'calendar', 'rules'],
        'mappings': [
            ('continent', 'geography.continent_distribution'),
            ('terrain', 'geography.special_terrain'),
            ('era', 'calendar.era'),
            ('days', 'calendar.days_per_year'),
            ('seasons', 'calendar.seasons'),
            ('festivals', 'calendar.festivals'),
            ('laws', 'rules.natural_laws'),
            ('boundary', 'rules.boundaries'),
            ('axioms', 'rules.axioms'),
            ('balance', 'balance'),
        ],
        'special_fields': {
            'axioms': lambda v: [a.strip() for a in v.split('\n') if a.strip()] if isinstance(v, str) else v,
        },
    },
    'power': {
        'sub_dicts': ['energy', 'martial', 'treasure', 'beast'],
        'mappings': [
            ('energy_types', 'energy.types'),
            ('energy_distribution', 'energy.distribution'),
            ('energy_properties', 'energy.properties'),
            ('level', 'level'),
            ('martial_categories', 'martial.categories'),
            ('martial_inheritance', 'martial.inheritance'),
            ('treasure_categories', 'treasure.categories'),
            ('treasure_pills', 'treasure.pills'),
            ('beast_levels', 'beast.levels'),
            ('beast_mythical', 'beast.mythical'),
        ],
    },
    'races': {
        'sub_dicts': ['trait'],
        'mappings': [
            ('category', 'category'),
            ('value', 'value'),
            ('lifespan', 'trait.lifespan'),
            ('reproduction', 'trait.reproduction'),
            ('physique', 'trait.physique'),
            ('relation', 'relation'),
        ],
    },
    'society': {
        'sub_dicts': ['court', 'sect', 'martial', 'strata', 'currency'],
        'mappings': [
            ('government', 'court.political_system'),
            ('bureaucracy', 'court.bureaucracy'),
            ('sect_level', 'sect.levels'),
            ('sect_heritage', 'sect.relationships'),
            ('martial_faction', 'martial.factions'),
            ('martial_guild', 'martial.alliances'),
            ('external', 'external'),
            ('class_level', 'strata.social_classes'),
            ('class_mobility', 'strata.mobility'),
            ('currency_type', 'currency.types'),
            ('currency_rule', 'currency.rules'),
            ('resource', 'resource'),
        ],
    },
    'culture': {
        'sub_dicts': ['custom', 'language', 'daily', 'religion'],
        'mappings': [
            ('festival', 'custom.festivals'),
            ('ritual', 'custom.rituals'),
            ('language', 'language.languages'),
            ('script', 'language.writing_system'),
            ('clothing', 'daily.clothing'),
            ('architecture', 'daily.architecture'),
            ('transport', 'daily.transportation'),
            # 饮食: 兼容旧字段名 food
            ('food', 'daily.cuisine'),
            ('cuisine', 'daily.cuisine'),
            # 信仰: 兼容旧字段名 deity / faith_diff
            ('deity', 'religion.deities'),
            ('deities', 'religion.deities'),
            ('religion_org', 'religion.organization'),
            ('faith_diff', 'religion.faith_differences'),
            ('faith_differences', 'religion.faith_differences'),
        ],
    },
    'history': {
        'sub_dicts': [],
        'mappings': [
            ('ancient', 'ancient'),
            ('modern', 'modern'),
            ('crisis', 'crisis'),
            ('destiny', 'destiny'),
            ('future', 'future'),
        ],
    },
    'special': {
        'sub_dicts': ['fate', 'reincarnation'],
        'mappings': [
            ('taboo', 'taboo'),
            ('secret', 'secret'),
            ('fortune', 'fate.fortune_rules'),
            ('destiny', 'fate.destiny_types'),
            ('soul', 'reincarnation.soul_rules'),
            ('reincarnation', 'reincarnation.mechanics'),
            ('transmigration', 'transmigration'),
            ('system', 'system'),
            ('rules', 'rules'),
        ],
    },
}


class ApiWorldviewLayerView(BaseWorldAPIView):
    """世界观分层CRUD（通用）- 支持 GET/PUT"""

    valid_layers = ('setting', 'foundation', 'power', 'races', 'society', 'culture', 'history', 'special')

    def get(self, request, project_id, pk, layer):
        if layer not in self.valid_layers:
            return self.error_response('无效的层级参数', status=400)

        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        helper = getattr(self, f'get_worldview_{layer}')
        return self.success_response({layer: clean_worldview_layer(layer, helper(worldview))})

    def put(self, request, project_id, pk, layer):
        if layer not in self.valid_layers:
            return self.error_response('无效的层级参数', status=400)

        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        # 从默认数据开始（而非 DB 现有数据），确保覆盖保存
        layer_data = self.get_default_worldview_data().get(layer, {})

        config = LAYER_SAVE_CONFIG[layer]
        for sub in config['sub_dicts']:
            layer_data.setdefault(sub, {})

        special_fields = config.get('special_fields', {})
        for flat_key, nested_path in config['mappings']:
            if flat_key in data:
                value = data[flat_key]
                if flat_key in special_fields:
                    value = special_fields[flat_key](value)
                _set_nested(layer_data, nested_path, value)

        # 序列化器校验 + 清洗，只保留结构内定义的字段
        layer_data = clean_worldview_layer(layer, layer_data)

        setattr(worldview, layer, layer_data)
        worldview.save()

        return self.success_response({layer: clean_worldview_layer(layer, layer_data)})


class ApiWorldviewExportMarkdownView(BaseWorldAPIView):
    """将世界观导出为Markdown格式"""
    
    def get(self, request, project_id):
        worldview = self.get_worldview(request.user, project_id=project_id)
        if not worldview:
            return self.error_response('世界观不存在')

        md_parts = []
        setting = worldview.setting or {}
        identity = setting.get('identity', {})
        position = setting.get('position', {})

        # 标题
        world_name = identity.get('world_name', '') or '未命名世界观'
        md_parts.append(f'# {world_name}\n')
        if identity.get('genre'):
            md_parts.append(f'\n**类型**：{identity["genre"]}\n')

        # 简介
        overview = setting.get('overview', '')
        md_parts.append(f'\n## 世界简介\n\n{overview if overview else "暂无简介"}\n')

        # 核心冲突
        conflict = setting.get('conflict', '')
        if conflict:
            md_parts.append(f'\n## 背景设定\n\n{conflict}\n')

        # 身份/调性
        if position.get('identity') or position.get('tone'):
            md_parts.append('\n## 世界概要\n')
            if position.get('identity'):
                md_parts.append(f'- **世界身份**：{position["identity"]}\n')
            if position.get('tone'):
                md_parts.append(f'- **整体调性**：{position["tone"]}\n')

        layers = get_layers()
        md_parts.append('\n## 分层构建\n')
        for field_name, layer_name in layers:
            layer_data = getattr(worldview, field_name, None) or {}
            if layer_data and not self._is_empty_dict(layer_data):
                md_parts.append(f'\n### {layer_name}\n')
                md_parts.append(self._render_json_field(layer_data))

        return self.success_response({'markdown': ''.join(md_parts)})

    def _is_empty_dict(self, data):
        """检查 JSON 数据是否为空（所有值均为空字符串或空列表）"""
        if not data:
            return True
        for v in data.values():
            if isinstance(v, dict):
                if not self._is_empty_dict(v):
                    return False
            elif isinstance(v, list):
                if any(v):
                    return False
            elif v:
                return False
        return True

    def _render_json_field(self, data, indent_level=0):
        """递归渲染 JSONField 为 Markdown 列表"""
        lines = []
        prefix = '  ' * indent_level
        if isinstance(data, dict):
            for k, v in data.items():
                label = _get_chinese_label(k)
                if isinstance(v, dict):
                    lines.append(f'{prefix}- **{label}**：')
                    lines.append(self._render_json_field(v, indent_level + 1))
                elif isinstance(v, list):
                    if v:
                        lines.append(f'{prefix}- **{label}**：')
                        for item in v:
                            lines.append(f'{prefix}  - {item}')
                elif v:
                    lines.append(f'{prefix}- **{label}**：{v}')
        return '\n'.join(lines)


class ApiWorldviewChatOpenView(BaseWorldAPIView):
    """聊天页初始数据 — 返回 Markdown + 空缺分析引导问题"""

    def post(self, request, project_id):
        worldview = self.get_worldview(request.user, project_id=project_id)
        if not worldview:
            return self.error_response('世界观不存在')

        # 生成 Markdown（复用导出逻辑）
        markdown = _build_worldview_markdown_instance(worldview)

        # 检查世界观是否为空（没有任何字段被填写过）
        has_content = not (
            _is_json_empty(worldview.setting or {}) and
            _is_json_empty(worldview.foundation or {}) and
            _is_json_empty(worldview.power or {}) and
            _is_json_empty(worldview.races or {}) and
            _is_json_empty(worldview.society or {}) and
            _is_json_empty(worldview.culture or {}) and
            _is_json_empty(worldview.history or {}) and
            _is_json_empty(worldview.special or {})
        )

        # LLM 分析空缺字段，生成引导问题（仅在有数据时才调用 LLM）
        question = ''
        options = []
        if has_content:
            try:
                current_worldview = prepare_worldview_for_llm(worldview)

                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_INIT_QUESTION_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_INIT_QUESTION_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="default")
                llm_chain = prompt | llm
                llm_result = llm_chain.invoke({"current_worldview": current_worldview})
                self.log_token_usage('worldview_init_question', result=llm_result, user=request.user, project=worldview.project)

                # 手动解析 JSON
                try:
                    parser = JsonOutputParser()
                    result = parser.parse(llm_result.content)
                except Exception:
                    result = llm_result.content
                question = result.get('question', '') if isinstance(result, dict) else ''
                options = result.get('options', []) if isinstance(result, dict) else []
            except Exception as e:
                logger.error(f'初始问题生成异常 {e}')

        return self.success_response({
            'worldview_id': worldview.id,
            'markdown': markdown,
            'question': question,
            'options': options,
            'has_content': has_content,
        })


class ApiWorldviewChatStreamView(BaseWorldAPIView):
    """世界观聊天流式生成API — LLM 返回结构化 JSON，增量更新模型后生成 Markdown 流式返回"""

    def post(self, request, project_id):
        data = request.data
        user_input = data.get('message', '')
        history_messages = data.get('messages', [])

        if not user_input:
            return self.error_response('消息不能为空')

        worldview = self.get_worldview(request.user, project_id=project_id)
        if not worldview:
            return self.error_response('世界观不存在')

        close_old_connections()

        def generate():
            try:
                # 1. 构建完整世界观 JSON 字符串发送给 LLM
                current_worldview = prepare_worldview_for_llm(worldview)

                # 滚动压缩历史消息（使用 LLM 摘要旧消息）
                llm = get_llm(user=request.user, scene="default")
                history_text = compress_history(history_messages, llm)

                # 从 worldview 获取题材分类
                setting_data = worldview.setting or {}
                identity = setting_data.get('identity', {})
                genre = identity.get('genre', '') if isinstance(identity, dict) else ''

                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_CHAT_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_CHAT_USER_PROMPT)
                ])

                # 先流式接收 LLM 原始输出（避免非流式 invoke 导致的请求超时）
                chain = prompt | llm
                full_content = ''
                last_chunk = None
                usage_chunk = None
                for chunk in chain.stream({
                    "genre": genre,
                    "current_worldview": current_worldview,
                    "user_input": user_input,
                    "history_messages": history_text,
                }):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                # 记录 token 使用量
                self.log_token_usage('worldview_chat', result=last_chunk, usage_result=usage_chunk, user=request.user, project=worldview.project)

                # 解析 JSON 结果
                parser = JsonOutputParser()
                try:
                    result = parser.parse(full_content)
                except Exception:
                    json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', full_content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(1))
                    else:
                        result = json.loads(full_content)

                changes = result.get('changes', {}) if isinstance(result, dict) else {}
                reply = result.get('reply', '') if isinstance(result, dict) else ''
                options = result.get('options', []) if isinstance(result, dict) else []

                # 3. 增量更新 worldview 模型
                for field_name, field_changes in changes.items():
                    if hasattr(worldview, field_name) and isinstance(field_changes, dict):
                        field_changes.pop(field_name, None)  # 剔除 LLM 误嵌套的层名键
                        _normalize_list_fields(field_changes, WORLDVIEW_STRUCTURE.get(field_name, {}))
                        current = getattr(worldview, field_name) or {}
                        _deep_merge(current, field_changes)
                        setattr(worldview, field_name, current)

                # 刷新 DB 连接（LLM 流式处理可能耗时数分钟，连接可能已超时断开）
                close_old_connections()
                worldview.save()

                # 4. 生成更新后的 Markdown
                markdown = self._build_worldview_markdown(worldview)

                # 5. 流式发送 Markdown 分块
                chunk_size = 50
                for i in range(0, len(markdown), chunk_size):
                    chunk = markdown[i:i + chunk_size]
                    yield f'data: {json.dumps({"type": "chunk", "chunk": chunk}, ensure_ascii=False)}\n\n'

                # 6. 发送完成信号（含助手回复）
                yield f'data: {json.dumps({"type": "complete", "markdown": markdown, "reply": reply, "options": options}, ensure_ascii=False)}\n\n'

            except Exception as e:
                logger.error(f'世界观流式生成异常 {e}')
                logger.error(traceback.format_exc())
                yield f'data: {json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}\n\n'

        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def _build_worldview_markdown(self, worldview):
        return _build_worldview_markdown_instance(worldview)


def _build_worldview_markdown_instance(worldview):
        """从 worldview 模型生成 Markdown 文本，复用导出逻辑"""
        md_parts = []
        setting = worldview.setting or {}
        identity = setting.get('identity', {})
        position = setting.get('position', {})

        world_name = identity.get('world_name', '') or '未命名世界观'
        md_parts.append(f'# {world_name}\n')
        if identity.get('genre'):
            md_parts.append(f'\n**类型**：{identity["genre"]}\n')

        overview = setting.get('overview', '')
        md_parts.append(f'\n## 世界简介\n\n{overview if overview else "暂无"}\n')

        conflict = setting.get('conflict', '')
        if conflict:
            md_parts.append(f'\n## 核心冲突\n\n{conflict}\n')

        if position.get('identity') or position.get('tone'):
            md_parts.append('\n## 世界概要\n')
            if position.get('identity'):
                md_parts.append(f'- **世界身份**：{position["identity"]}\n')
            if position.get('tone'):
                md_parts.append(f'- **整体调性**：{position["tone"]}\n')

        layers = get_layers()
        md_parts.append('\n## 分层构建\n')
        for field_name, layer_name in layers:
            if field_name == 'setting':
                continue  # setting 已在上方单独渲染
            layer_data = getattr(worldview, field_name, None) or {}
            md_parts.append(f'\n### {layer_name}\n')
            if layer_data and not _is_json_empty(layer_data):
                md_parts.append(_render_json_to_md(layer_data))
            else:
                md_parts.append('暂无\n')

        return ''.join(md_parts)


def _is_json_empty(data):
    """检查 JSON 数据是否为空（所有值均为空字符串或空列表）"""
    if not data:
        return True
    for v in data.values():
        if isinstance(v, dict):
            if not _is_json_empty(v):
                return False
        elif isinstance(v, list):
            if any(v):
                return False
        elif v:
            return False
    return True


def _render_json_to_md(data, indent_level=0):
    """递归渲染 JSON 为 Markdown 缩进列表（中文字段名 + 空值显示'暂无'）"""
    lines = []
    prefix = '  ' * indent_level
    if isinstance(data, dict):
        for k, v in data.items():
            label = _get_chinese_label(k)
            if isinstance(v, dict):
                # 跳过全空的嵌套字典
                if _is_json_empty(v):
                    continue
                lines.append(f'{prefix}- **{label}**：')
                lines.append(_render_json_to_md(v, indent_level + 1))
            elif isinstance(v, list):
                if v:
                    lines.append(f'{prefix}- **{label}**：')
                    for item in v:
                        lines.append(f'{prefix}  - {item}')
                else:
                    lines.append(f'{prefix}- **{label}**：暂无')
            else:
                display = v if v else '暂无'
                lines.append(f'{prefix}- **{label}**：{display}')
    return '\n'.join(lines)


def _get_chinese_label(key):
    """英文字段名 → 中文标签映射"""
    _LABELS = {
        # setting 层
        'identity': '世界身份', 'world_name': '世界名称', 'genre': '题材类型',
        'position': '定位调性', 'tone': '整体调性',
        'overview': '世界概述', 'conflict': '核心冲突',
        # foundation 层
        'geography': '地理格局', 'continent_distribution': '大陆分布', 'special_terrain': '特殊地形',
        'calendar': '历法时间', 'era': '纪元', 'days_per_year': '每年天数', 'seasons': '季节', 'festivals': '节日庆典',
        'rules': '世界法则', 'natural_laws': '自然法则', 'boundaries': '边界规则', 'axioms': '基本公理',
        'balance': '平衡机制',
        # power 层
        'energy': '能量体系', 'types': '能量类型', 'distribution': '能量分布', 'properties': '能量特性',
        'level': '等级划分',
        'martial': '武学体系', 'categories': '武学类别', 'inheritance': '武学传承',
        'treasure': '宝物体系', 'pills': '丹药',
        'beast': '妖兽神兽', 'levels': '妖兽等级', 'mythical': '神话生物',
        # races 层
        'category': '种族分类', 'value': '种族价值观',
        'trait': '种族特征', 'lifespan': '寿命', 'reproduction': '繁衍方式', 'physique': '体质特征',
        'relation': '种族关系',
        # society 层
        'court': '朝廷官制', 'political_system': '政治体制', 'bureaucracy': '官僚体系',
        'sect': '宗门势力', 'levels': '宗门等级', 'relationships': '宗门关系',
        'factions': '武林势力', 'alliances': '武林联盟',
        'external': '外部势力',
        'strata': '社会阶层', 'social_classes': '阶层划分', 'mobility': '阶层流动',
        'currency': '货币经济', 'resource': '资源物产',
        # culture 层
        'custom': '风俗礼仪', 'rituals': '礼仪习俗',
        'language': '语言文字', 'languages': '语言种类', 'writing_system': '文字系统',
        'daily': '日常生活', 'clothing': '服饰', 'cuisine': '饮食', 'food': '饮食', 'architecture': '建筑', 'transportation': '交通出行',
        'religion': '宗教信仰', 'deity': '神祇', 'deities': '神祇', 'organization': '宗教组织', 'faith_differences': '信仰差异', 'faith_diff': '信仰差异',
        # history 层
        'ancient': '远古时期', 'modern': '近现代', 'crisis': '当前危机', 'destiny': '命运走向', 'future': '未来展望',
        # special 层
        'taboo': '禁忌', 'secret': '秘密',
        'fate': '命运规则', 'fortune_rules': '运势规则', 'destiny_types': '命运类型',
        'reincarnation': '转世轮回', 'soul_rules': '灵魂规则', 'mechanics': '转世机制',
        'transmigration': '穿越设定', 'system': '系统设定', 'rules': '特殊规则',
    }
    return _LABELS.get(key, key.replace('_', ' ').title())


def _deep_merge(base, incoming):
    """递归合并 incoming 到 base（原地修改 base）。
    
    - dict 字段：递归合并子字段
    - list 字段：扩展（不会覆盖已有项，只能追加）
    - 其他 字段：覆盖
    """
    for key, value in incoming.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        elif key in base and isinstance(base[key], list) and isinstance(value, list):
            base[key].extend(value)
        else:
            base[key] = value


def _normalize_list_fields(data, struct):
    """递归归一化 list 类型字段：LLM 经常返回 ['item1\nitem2\nitem3']，拆分为 ['item1', 'item2', 'item3']"""
    if not isinstance(data, dict) or not isinstance(struct, dict):
        return
    for key, value in data.items():
        node = struct.get(key)
        if isinstance(node, tuple) and len(node) >= 3 and node[2] == 'list':
            if isinstance(data[key], list):
                normalized = []
                for item in data[key]:
                    s = str(item).strip() if item else ''
                    if '\n' in s:
                        normalized.extend(line.strip() for line in s.split('\n') if line.strip())
                    elif s:
                        normalized.append(s)
                data[key] = normalized
        elif isinstance(node, dict) and isinstance(value, dict):
            _normalize_list_fields(value, node)
