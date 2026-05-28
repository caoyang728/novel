import re
import json
import traceback
from loguru import logger

from django.http import JsonResponse, StreamingHttpResponse
from django.db import close_old_connections
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from novel_agent.authentication import JWTAuthentication
from apps.project.models import ProjectList as Project
from apps.ai.llm import get_llm
from .models import WorldView, WorldViewChatHistory
from .prompts import (
    LAYER_NAMES,
    WORLDVIEW_DEEPENING_SYSTEM_PROMPT,
    WORLDVIEW_DEEPENING_USER_PROMPT,
    WORLDVIEW_DEEPENING_INTEGRATE_SYSTEM_PROMPT,
    WORLDVIEW_DEEPENING_INTEGRATE_USER_PROMPT,
    WORLDVIEW_FALLBACK_QUESTIONS,
    WORLDVIEW_CONSISTENCY_SYSTEM_PROMPT,
    WORLDVIEW_CONSISTENCY_USER_PROMPT,
    FACTION_GENERATE_SYSTEM_PROMPT,
    FACTION_GENERATE_USER_PROMPT,
    LOCATION_GENERATE_SYSTEM_PROMPT,
    LOCATION_GENERATE_USER_PROMPT,
    RELATION_GENERATE_SYSTEM_PROMPT,
    RELATION_GENERATE_USER_PROMPT,
    WORLDVIEW_BASIC_SETTINGS_SYSTEM_PROMPT,
    WORLDVIEW_BASIC_SETTINGS_USER_PROMPT,
    WORLDVIEW_STREAM_SYSTEM_PROMPT,
    WORLDVIEW_STREAM_USER_PROMPT,
    WORLDVIEW_FOUNDATION_SYSTEM_PROMPT,
    WORLDVIEW_FOUNDATION_USER_PROMPT,
    WORLDVIEW_POWER_SYSTEM_PROMPT,
    WORLDVIEW_POWER_USER_PROMPT,
    WORLDVIEW_RACES_SYSTEM_PROMPT,
    WORLDVIEW_RACES_USER_PROMPT,
    WORLDVIEW_SOCIETY_SYSTEM_PROMPT,
    WORLDVIEW_SOCIETY_USER_PROMPT,
    WORLDVIEW_CULTURE_SYSTEM_PROMPT,
    WORLDVIEW_CULTURE_USER_PROMPT,
    WORLDVIEW_HISTORY_SYSTEM_PROMPT,
    WORLDVIEW_HISTORY_USER_PROMPT,
    WORLDVIEW_SPECIAL_SYSTEM_PROMPT,
    WORLDVIEW_SPECIAL_USER_PROMPT,
    WORLDVIEW_CONSISTENCY_FIX_SYSTEM_PROMPT,
    WORLDVIEW_CONSISTENCY_FIX_USER_PROMPT,
)


class BaseWorldAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
                "class": {"social_classes": "", "mobility": ""},
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
    # pk 来自 URL <int:pk> 路由；project_id / worldview_id 来自查询参数

    def get(self, request, pk=None):
        try:
            if pk:
                worldview = self.get_worldview(request.user, pk=pk)
            else:
                project_id = request.query_params.get('project_id')
                worldview_id = request.query_params.get('worldview_id')

                if project_id:
                    worldview = self.get_worldview(request.user, project_id=project_id)
                elif worldview_id:
                    worldview = self.get_worldview(request.user, worldview_id=worldview_id)
                else:
                    return self.error_response('缺少project_id或worldview_id参数')
            
            return self.success_response({
                'worldview_id': worldview.id,
                'project_id': worldview.project.id,
                'setting': self.get_worldview_setting(worldview),
                'foundation': self.get_worldview_foundation(worldview),
                'power': self.get_worldview_power(worldview),
                'races': self.get_worldview_races(worldview),
                'society': self.get_worldview_society(worldview),
                'culture': self.get_worldview_culture(worldview),
                'history': self.get_worldview_history(worldview),
                'special': self.get_worldview_special(worldview),
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

    def put(self, request, pk):
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



class ApiWorldviewDeleteView(BaseWorldAPIView):
    """删除世界观"""

    def delete(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        worldview.delete()
        return self.success_response(message='删除成功')


class ApiWorldviewDeepeningQuestionsView(BaseWorldAPIView):
    """生成深化问题API"""

    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        try:
            # 获取完整 WorldView 数据
            worldview_detail = WorldView.objects.get(project=worldview.project)
            
            # 将整个 WorldView 序列化为 JSON
            worldview_full_data = {
                'setting': worldview_detail.setting or {},
                'foundation': worldview_detail.foundation or {},
                'power': worldview_detail.power or {},
                'races': worldview_detail.races or {},
                'society': worldview_detail.society or {},
                'culture': worldview_detail.culture or {},
                'history': worldview_detail.history or {},
                'special': worldview_detail.special or {},
            }
            worldview_json = json.dumps(worldview_full_data, ensure_ascii=False, indent=2)
            
            # 构建 LCEL 提示词
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_DEEPENING_SYSTEM_PROMPT),
                ("user", WORLDVIEW_DEEPENING_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_deepen")
            
            # 使用 LCEL 链式调用
            chain = prompt | llm | JsonOutputParser()
            
            result = chain.invoke({
                "worldview": worldview_json,
            })
            
            # 验证结果格式
            if isinstance(result, list):
                questions = result
            else:
                questions = list(WORLDVIEW_FALLBACK_QUESTIONS)
        except WorldView.DoesNotExist:
            return self.error_response('世界观详情不存在，请先生成世界观')
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            questions = list(WORLDVIEW_FALLBACK_QUESTIONS)
        # logger.debug(questions)
        return self.success_response(questions)


class ApiWorldviewDeepeningSubmitView(BaseWorldAPIView):
    """提交深化问答答案API，并返回修改建议"""

    def post(self, request, pk):
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
            logger.info(f"开始分析回答，qa_list: {json.dumps(qa_list, ensure_ascii=False)}")
            
            # worldview 已经存在 WorldView 对象，直接使用           
            # 构建问答记录字符数            
            qa_records = ""
            for idx, qa in enumerate(qa_list):
                if isinstance(qa, dict):
                    answer = qa.get('answer', '').strip()
                    question = qa.get('question', '').strip()
                    if answer and question:
                        qa_records += f"Q{idx+1}: {question}\nA{idx+1}: {answer}\n\n"
            
            logger.info(f"构建的问答记录 {repr(qa_records)}")
            
            if not qa_records.strip():
                logger.info("没有有效的问答内容")
                return []
            
            # 直接 将整个 WorldView 序列化为 JSON，让 LLM 自己解析
            worldview_full_data = {
                'setting': worldview.setting,
                'foundation': worldview.foundation,
                'power': worldview.power,
                'races': worldview.races,
                'society': worldview.society,
                'culture': worldview.culture,
                'history': worldview.history,
                'special': worldview.special,
            }
            worldview_json = json.dumps(worldview_full_data, ensure_ascii=False, indent=2)
            
            logger.info(f"世界观数据长 {len(worldview_json)} 字符")
            
            prompt_vars = {
                "worldview": worldview_json,
                "qa_records": qa_records.strip(),
            }
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", WORLDVIEW_DEEPENING_INTEGRATE_SYSTEM_PROMPT),
                ("user", WORLDVIEW_DEEPENING_INTEGRATE_USER_PROMPT)
            ])
            
            logger.info("正在调用 LLM...")
            llm = get_llm(user=user, scene="worldview_deepen_integrate")
            chain = prompt | llm | JsonOutputParser()
            result = chain.invoke(prompt_vars)
            
            logger.info(f"LLM 返回结果类型: {type(result)}")
            logger.info(f"LLM 返回结果: {json.dumps(result, ensure_ascii=False) if result else 'None'}")
            
            if isinstance(result, list):
                logger.info(f"返回 {len(result)} 条修改建议")
                return result
            else:
                logger.info("返回结果不是列表，返回空数组")
                return []
        except WorldView.DoesNotExist:
            logger.error("WorldView 不存在")
            raise Exception('no worldview')
        except Exception as e:
            logger.error(f"分析回答失败: {e}", exc_info=True)
            raise Exception('internal server error')


class ApiWorldviewDeepeningApplyView(BaseWorldAPIView):
    """应用深化问答修改建议API"""

    def post(self, request, pk):
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

    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        issues = []
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
                ("system", WORLDVIEW_CONSISTENCY_SYSTEM_PROMPT),
                ("user", WORLDVIEW_CONSISTENCY_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_consistency")
            
            chain = prompt | llm | JsonOutputParser()
            
            result = chain.invoke({
                "worldview": json.dumps(worldview_data, ensure_ascii=False),
            })
            
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

    def post(self, request, pk):
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
                ("system", WORLDVIEW_CONSISTENCY_FIX_SYSTEM_PROMPT),
                ("user", WORLDVIEW_CONSISTENCY_FIX_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="worldview_consistency_fix")
            
            chain = prompt | llm | JsonOutputParser()
            
            result = chain.invoke({
                "worldview_data": json.dumps(worldview_data, ensure_ascii=False),
                "consistency_issues": json.dumps(all_issues, ensure_ascii=False)
            })
            
            suggestions = result if isinstance(result, list) else []
            
        except Exception as e:
            logger.error(f"生成修复建议失败: {e}")
            return self.error_response('生成修复建议失败')

        return self.success_response(suggestions)


class ApiFactionGenerateView(BaseWorldAPIView):
    """AI生成阵营"""

    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        doctrine = data.get('doctrine', '')
        name = data.get('name', '')
        position = data.get('position', '')
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", FACTION_GENERATE_SYSTEM_PROMPT),
                ("user", FACTION_GENERATE_USER_PROMPT)
            ])

            llm = get_llm(user=request.user, scene="faction_design")
            
            chain = prompt | llm | JsonOutputParser()
            
            result = chain.invoke({
                "separator": '-' * 40,
                "name": name if name else '（请根据以下信息生成合适的名称)',
                "position": position if position else '（请根据以下理念确定合适的立场)',
                "doctrine": doctrine if doctrine else '（请根据阵营性质生成合适的理念)',
            })
            
            if isinstance(result, dict):
                generated_name = result.get('name', name)
                generated_position = result.get('position', position)
                generated_doctrine = result.get('doctrine', doctrine)
            else:
                generated_name = name
                generated_position = position
                generated_doctrine = str(result) if result else doctrine
                
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            generated_name = name
            generated_position = position
            generated_doctrine = f'基于「{doctrine}」的扩展阵营理念...' if doctrine else ''

        return self.success_response({
            'name': generated_name,
            'position': generated_position,
            'doctrine': generated_doctrine
        })


class ApiLocationGenerateView(BaseWorldAPIView):
    """AI生成地点"""

    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        summary = data.get('summary', '')
        name = data.get('name', '')
        terrain = data.get('terrain', '')
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", LOCATION_GENERATE_SYSTEM_PROMPT),
                ("user", LOCATION_GENERATE_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="location_design")
            
            chain = prompt | llm | JsonOutputParser()
            
            result = chain.invoke({
                "separator": '-' * 40,
                "name": name if name else '（请根据以下信息生成合适的名称)',
                "terrain": terrain if terrain else '（请根据概述确定合适的地形)',
                "summary": summary if summary else '（请生成一个合适的地点概述)',
            })
            
            if isinstance(result, dict):
                generated_name = result.get('name', name)
                generated_terrain = result.get('terrain', terrain)
                generated_summary = result.get('summary', summary)
            else:
                generated_name = name
                generated_terrain = terrain
                generated_summary = str(result) if result else summary
                
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            generated_name = name
            generated_terrain = terrain
            generated_summary = f'基于「{summary}」的扩展地点描述...' if summary else ''

        return self.success_response({
            'name': generated_name,
            'terrain': generated_terrain,
            'summary': generated_summary
        })


class ApiRelationGenerateView(BaseWorldAPIView):
    """AI生成关系"""

    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        source = data.get('source', '')
        target = data.get('target', '')
        relation_type = data.get('type', '')
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", RELATION_GENERATE_SYSTEM_PROMPT),
                ("user", RELATION_GENERATE_USER_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="default")
            
            chain = prompt | llm
            
            response = chain.invoke({
                "source": source,
                "target": target,
                "relation_type": relation_type,
            })
            
            generated_description = response.content if hasattr(response, 'content') else str(response)
                
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            generated_description = f'{source}与{target}之间的{relation_type}关系描述...'

        return self.success_response({
            'source': source,
            'target': target,
            'type': relation_type,
            'description': generated_description
        })





class ApiWorldviewFoundationView(BaseWorldAPIView):
    """世界基础API"""

    def put(self, request, pk):
        """保存世界基础"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        foundation = self.get_worldview_foundation(worldview)

        foundation.setdefault('geography', {})
        foundation.setdefault('calendar', {})
        foundation.setdefault('rules', {})

        # 逐字段更新，只更新传入的字段
        if 'continent' in data:
            foundation['geography']['continent_distribution'] = data['continent']
        if 'terrain' in data:
            foundation['geography']['special_terrain'] = data['terrain']
        if 'era' in data:
            foundation['calendar']['era'] = data['era']
        if 'days' in data:
            foundation['calendar']['days_per_year'] = data['days']
        if 'seasons' in data:
            foundation['calendar']['seasons'] = data['seasons']
        if 'festivals' in data:
            foundation['calendar']['festivals'] = data['festivals']
        if 'laws' in data:
            foundation['rules']['natural_laws'] = data['laws']
        if 'boundary' in data:
            foundation['rules']['boundaries'] = data['boundary']
        if 'axioms' in data:
            # axioms 可以是数组或换行分隔的字符串
            axioms_data = data['axioms']
            if isinstance(axioms_data, str):
                foundation['rules']['axioms'] = [a.strip() for a in axioms_data.split('\n') if a.strip()]
            else:
                foundation['rules']['axioms'] = axioms_data
        if 'balance' in data:
            foundation['balance'] = data['balance']

        worldview.foundation = foundation
        worldview.save()

        return self.success_response({
            'foundation': self.get_worldview_foundation(worldview),
        })

    def post(self, request, pk):
        """AI一键优化世界基础所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        continent = data.get('continent', '')
        terrain = data.get('terrain', '')
        era = data.get('era', '')
        days = data.get('days', '')
        seasons = data.get('seasons', '')
        festivals = data.get('festivals', '')
        laws = data.get('laws', '')
        boundary = data.get('boundary', '')
        axioms = data.get('axioms', '')
        balance = data.get('balance', '')

        def generate():
            try:
                logger.debug(1111)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_FOUNDATION_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_FOUNDATION_USER_PROMPT)
                ])
                logger.debug(2222)
                llm = get_llm(user=request.user, scene="worldview_build")
                logger.debug(3333)
                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "continent": continent,
                    "terrain": terrain,
                    "era": era,
                    "days": days,
                    "seasons": seasons,
                    "festivals": festivals,
                    "laws": laws,
                    "boundary": boundary,
                    "axioms": axioms,
                    "balance": balance,
                })

                for chunk in stream_response:
                    # chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    # full_content += chunk_content

                    # yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                # 查找JSON
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    foundation = json.loads(full_content)
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewPowerView(BaseWorldAPIView):
    """力量体系API"""

    def put(self, request, pk):
        """保存力量体系"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        power = self.get_worldview_power(worldview)
        power.setdefault('energy', {})
        power.setdefault('martial', {})
        power.setdefault('treasure', {})
        power.setdefault('beast', {})

        # 逐字段更新，只更新传入的字段
        if 'energy_types' in data:
            power['energy']['types'] = data['energy_types']
        if 'energy_distribution' in data:
            power['energy']['distribution'] = data['energy_distribution']
        if 'energy_properties' in data:
            power['energy']['properties'] = data['energy_properties']
        if 'level' in data:
            power['level'] = data['level']
        if 'martial_categories' in data:
            power['martial']['categories'] = data['martial_categories']
        if 'martial_inheritance' in data:
            power['martial']['inheritance'] = data['martial_inheritance']
        if 'treasure_categories' in data:
            power['treasure']['categories'] = data['treasure_categories']
        if 'treasure_pills' in data:
            power['treasure']['pills'] = data['treasure_pills']
        if 'beast_levels' in data:
            power['beast']['levels'] = data['beast_levels']
        if 'beast_mythical' in data:
            power['beast']['mythical'] = data['beast_mythical']

        worldview.power = power
        worldview.save()

        return self.success_response({
            'power': self.get_worldview_power(worldview),
        })

    def post(self, request, pk):
        """AI一键优化力量体系所有字段- 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        energy_types = data.get('energy_types', '')
        energy_distribution = data.get('energy_distribution', '')
        energy_properties = data.get('energy_properties', '')
        level = data.get('level', '')
        martial_categories = data.get('martial_categories', '')
        martial_inheritance = data.get('martial_inheritance', '')
        treasure_categories = data.get('treasure_categories', '')
        treasure_pills = data.get('treasure_pills', '')
        beast_levels = data.get('beast_levels', '')
        beast_mythical = data.get('beast_mythical', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_POWER_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_POWER_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                
                logger.info(f"Power AI expand params - genre: {genre[:50]}, energy_types: {energy_types[:50]}, level: {level[:50]}")
                
                stream_response = chain.stream({
                    "genre": genre,
                    "energy_types": energy_types,
                    "energy_distribution": energy_distribution,
                    "energy_properties": energy_properties,
                    "level": level,
                    "martial_categories": martial_categories,
                    "martial_inheritance": martial_inheritance,
                    "treasure_categories": treasure_categories,
                    "treasure_pills": treasure_pills,
                    "beast_levels": beast_levels,
                    "beast_mythical": beast_mythical,
                })

                chunk_count = 0
                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content
                    chunk_count += 1

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewRacesView(BaseWorldAPIView):
    """种族族群API - 单项修改"""

    def get(self, request, pk):
        """获取种族族群"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)
        
        return self.success_response({
            'races': self.get_worldview_races(worldview)
        })

    def put(self, request, pk):
        """保存种族族群 - 单项修改"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        races = self.get_worldview_races(worldview)
        races.setdefault('trait', {})

        # 逐字段更新，只更新传入的字段
        if 'category' in data:
            races['category'] = data['category']
        if 'value' in data:
            races['value'] = data['value']
        if 'lifespan' in data:
            races['trait']['lifespan'] = data['lifespan']
        if 'reproduction' in data:
            races['trait']['reproduction'] = data['reproduction']
        if 'physique' in data:
            races['trait']['physique'] = data['physique']
        if 'relation' in data:
            races['relation'] = data['relation']

        worldview.races = races
        worldview.save()

        return self.success_response({
            'races': self.get_worldview_races(worldview),
        })

    def post(self, request, pk):
        """AI一键优化种族族群所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        category = data.get('category', '')
        value = data.get('value', '')
        lifespan = data.get('lifespan', '')
        reproduction = data.get('reproduction', '')
        physique = data.get('physique', '')
        relation = data.get('relation', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_RACES_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_RACES_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "category": category,
                    "value": value,
                    "lifespan": lifespan,
                    "reproduction": reproduction,
                    "physique": physique,
                    "relation": relation,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    races = json.loads(full_content)
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewSocietyView(BaseWorldAPIView):
    """组织势力API - 单项修改"""

    def get(self, request, pk):
        """获取组织势力"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)
        
        return self.success_response({
            'society': self.get_worldview_society(worldview)
        })

    def put(self, request, pk):
        """保存组织势力 - 单项修改"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        society = self.get_worldview_society(worldview)
        society.setdefault('court', {})
        society.setdefault('sect', {})
        society.setdefault('martial', {})
        society.setdefault('class', {})
        society.setdefault('currency', {})

        # 逐字段更新，只更新传入的字段
        if 'government' in data:
            society['court']['political_system'] = data['government']
        if 'bureaucracy' in data:
            society['court']['bureaucracy'] = data['bureaucracy']
        if 'sect_level' in data:
            society['sect']['levels'] = data['sect_level']
        if 'sect_heritage' in data:
            society['sect']['relationships'] = data['sect_heritage']
        if 'martial_faction' in data:
            society['martial']['factions'] = data['martial_faction']
        if 'martial_guild' in data:
            society['martial']['alliances'] = data['martial_guild']
        if 'external' in data:
            society['external'] = data['external']
        if 'class_level' in data:
            society['class']['social_classes'] = data['class_level']
        if 'class_mobility' in data:
            society['class']['mobility'] = data['class_mobility']
        if 'currency_type' in data:
            society['currency']['types'] = data['currency_type']
        if 'currency_rule' in data:
            society['currency']['rules'] = data['currency_rule']
        if 'resource' in data:
            society['resource'] = data['resource']

        worldview.society = society
        worldview.save()

        return self.success_response({
            'society': self.get_worldview_society(worldview),
        })

    def post(self, request, pk):
        """AI一键优化组织势力所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        government = data.get('government', '')
        bureaucracy = data.get('bureaucracy', '')
        sect_level = data.get('sect_level', '')
        sect_heritage = data.get('sect_heritage', '')
        martial_faction = data.get('martial_faction', '')
        martial_guild = data.get('martial_guild', '')
        external = data.get('external', '')
        class_level = data.get('class_level', '')
        class_mobility = data.get('class_mobility', '')
        currency_type = data.get('currency_type', '')
        currency_rule = data.get('currency_rule', '')
        resource = data.get('resource', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_SOCIETY_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_SOCIETY_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "government": government,
                    "bureaucracy": bureaucracy,
                    "sect_level": sect_level,
                    "sect_heritage": sect_heritage,
                    "martial_faction": martial_faction,
                    "martial_guild": martial_guild,
                    "external": external,
                    "class_level": class_level,
                    "class_mobility": class_mobility,
                    "currency_type": currency_type,
                    "currency_rule": currency_rule,
                    "resource": resource,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content
                    
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    society = json.loads(full_content)
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        
        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewCultureView(BaseWorldAPIView):
    """文化习俗API - 单项修改"""

    def get(self, request, pk):
        """获取文化习俗"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)
        
        return self.success_response({
            'culture': self.get_worldview_culture(worldview)
        })

    def put(self, request, pk):
        """保存文化习俗 - 单项修改"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        culture = self.get_worldview_culture(worldview)
        culture.setdefault('custom', {})
        culture.setdefault('language', {})
        culture.setdefault('daily', {})
        culture.setdefault('religion', {})

        # 逐字段更新，只更新传入的字段
        if 'festival' in data:
            culture['custom']['festivals'] = data['festival']
        if 'ritual' in data:
            culture['custom']['rituals'] = data['ritual']
        if 'language' in data:
            culture['language']['languages'] = data['language']
        if 'script' in data:
            culture['language']['writing_system'] = data['script']
        if 'clothing' in data:
            culture['daily']['clothing'] = data['clothing']
        if 'food' in data:
            culture['daily']['food'] = data['food']
        if 'architecture' in data:
            culture['daily']['architecture'] = data['architecture']
        if 'transport' in data:
            culture['daily']['transportation'] = data['transport']
        if 'deity' in data:
            culture['religion']['deity'] = data['deity']
        if 'religion_org' in data:
            culture['religion']['organization'] = data['religion_org']
        if 'faith_diff' in data:
            culture['religion']['faith_diff'] = data['faith_diff']

        worldview.culture = culture
        worldview.save()

        return self.success_response({
            'culture': self.get_worldview_culture(worldview),
        })

    def post(self, request, pk):
        """AI一键优化文化习俗所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        festival = data.get('festival', '')
        ritual = data.get('ritual', '')
        language = data.get('language', '')
        script = data.get('script', '')
        clothing = data.get('clothing', '')
        food = data.get('food', '')
        architecture = data.get('architecture', '')
        transport = data.get('transport', '')
        deity = data.get('deity', '')
        religion_org = data.get('religion_org', '')
        faith_diff = data.get('faith_diff', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_CULTURE_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_CULTURE_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "festival": festival,
                    "ritual": ritual,
                    "language": language,
                    "script": script,
                    "clothing": clothing,
                    "food": food,
                    "architecture": architecture,
                    "transport": transport,
                    "deity": deity,
                    "religion_org": religion_org,
                    "faith_diff": faith_diff,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    culture_flat = json.loads(full_content)
                    # 转换为嵌套结构
                    culture = {
                        "custom": {
                            "festivals": culture_flat.get("festival", ""),
                            "rituals": culture_flat.get("ritual", "")
                        },
                        "language": {
                            "languages": culture_flat.get("language", ""),
                            "writing_system": culture_flat.get("script", "")
                        },
                        "daily": {
                            "clothing": culture_flat.get("clothing", ""),
                            "food": culture_flat.get("food", ""),
                            "architecture": culture_flat.get("architecture", ""),
                            "transportation": culture_flat.get("transport", "")
                        },
                        "religion": {
                            "deity": culture_flat.get("deity", ""),
                            "organization": culture_flat.get("religion_org", ""),
                            "faith_diff": culture_flat.get("faith_diff", "")
                        }
                    }
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewHistoryView(BaseWorldAPIView):
    """重要事件API - 单项修改"""

    def get(self, request, pk):
        """获取重要事件"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)
        
        return self.success_response({
            'history': self.get_worldview_history(worldview)
        })

    def put(self, request, pk):
        """保存重要事件 - 单项修改"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        history = self.get_worldview_history(worldview)

        # 逐字段更新，只更新传入的字段
        if 'ancient' in data:
            history['ancient'] = data['ancient']
        if 'modern' in data:
            history['modern'] = data['modern']
        if 'crisis' in data:
            history['crisis'] = data['crisis']
        if 'destiny' in data:
            history['destiny'] = data['destiny']
        if 'future' in data:
            history['future'] = data['future']

        worldview.history = history
        worldview.save()

        return self.success_response({
            'history': self.get_worldview_history(worldview),
        })

    def post(self, request, pk):
        """AI一键优化重要事件所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        ancient = data.get('ancient', '')
        modern = data.get('modern', '')
        crisis = data.get('crisis', '')
        destiny = data.get('destiny', '')
        future = data.get('future', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_HISTORY_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_HISTORY_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "ancient": ancient,
                    "modern": modern,
                    "crisis": crisis,
                    "destiny": destiny,
                    "future": future,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    history = json.loads(full_content)
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewSpecialView(BaseWorldAPIView):
    """特色地标API - 单项修改"""

    def get(self, request, pk):
        """获取特色地标"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)
        
        return self.success_response({
            'special': self.get_worldview_special(worldview)
        })

    def put(self, request, pk):
        """保存特色地标 - 单项修改"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        special = self.get_worldview_special(worldview)
        special.setdefault('fate', {})
        special.setdefault('reincarnation', {})

        # 逐字段更新，只更新传入的字段
        if 'taboo' in data:
            special['taboo'] = data['taboo']
        if 'secret' in data:
            special['secret'] = data['secret']
        if 'fortune' in data:
            special['fate']['fortune_rules'] = data['fortune']
        if 'destiny' in data:
            special['fate']['destiny_types'] = data['destiny']
        if 'soul' in data:
            special['reincarnation']['soul_rules'] = data['soul']
        if 'reincarnation' in data:
            special['reincarnation']['mechanics'] = data['reincarnation']
        if 'transmigration' in data:
            special['transmigration'] = data['transmigration']
        if 'system' in data:
            special['system'] = data['system']
        if 'rules' in data:
            special['rules'] = data['rules']

        worldview.special = special
        worldview.save()

        return self.success_response({
            'special': self.get_worldview_special(worldview),
        })

    def post(self, request, pk):
        """AI一键优化特色地标所有字段 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        genre = data.get('genre', '')
        taboo = data.get('taboo', '')
        secret = data.get('secret', '')
        fortune = data.get('fortune', '')
        destiny = data.get('destiny', '')
        soul = data.get('soul', '')
        reincarnation = data.get('reincarnation', '')
        transmigration = data.get('transmigration', '')
        system = data.get('system', '')
        rules = data.get('rules', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_SPECIAL_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_SPECIAL_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "taboo": taboo,
                    "secret": secret,
                    "fortune": fortune,
                    "destiny": destiny,
                    "soul": soul,
                    "reincarnation": reincarnation,
                    "transmigration": transmigration,
                    "system": system,
                    "rules": rules,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    special_flat = json.loads(full_content)
                    # 转换为嵌套结构
                    special = {
                        "taboo": special_flat.get("taboo", ""),
                        "secret": special_flat.get("secret", ""),
                        "fate": {
                            "fortune_rules": special_flat.get("fortune", ""),
                            "destiny_types": special_flat.get("destiny", "")
                        },
                        "reincarnation": {
                            "soul_rules": special_flat.get("soul", ""),
                            "mechanics": special_flat.get("reincarnation", "")
                        },
                        "transmigration": special_flat.get("transmigration", ""),
                        "system": special_flat.get("system", ""),
                        "rules": special_flat.get("rules", "")
                    }
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewSettingView(BaseWorldAPIView):
    """基础设定API - 使用 WorldView.setting JSONField 存储"""

    def put(self, request, pk):
        """保存基础设定 - WorldView.setting"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = request.data
        if data is None:
            return self.error_response('无效的请求数据')

        setting = self.get_worldview_setting(worldview)
        setting.setdefault('identity', {})
        setting.setdefault('position', {})

        if 'overview' in data:
            setting['overview'] = data['overview']
        if 'conflict' in data:
            setting['conflict'] = data['conflict']
        if 'genre' in data:
            setting['identity']['genre'] = data['genre']
        if 'world_name' in data:
            setting['identity']['world_name'] = data['world_name']
        if 'tone' in data:
            setting['position']['tone'] = data['tone']
        if 'identity' in data:
            setting['position']['identity'] = data['identity']

        worldview.setting = setting
        worldview.save()

        return self.success_response({
            'setting': self.get_worldview_setting(worldview),
        })

    def post(self, request, pk):
        """AI一键优化基础设定 - 流式返回"""
        try:
            worldview = self.get_worldview(request.user, pk=pk)
        except Exception:
            return self.error_response('世界观不存在', status=404)

        data = self.parse_request_data(request)
        if data is None:
            return self.error_response('无效的请求数据')

        world_name = data.get('world_name', '')
        genre = data.get('genre', '')
        identity = data.get('identity', '')
        tone = data.get('tone', '')
        overview = data.get('overview', '')
        conflict = data.get('conflict', '')

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_BASIC_SETTINGS_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_BASIC_SETTINGS_USER_PROMPT)
                ])

                llm = get_llm(user=request.user, scene="worldview_build")

                chain = prompt | llm

                full_content = ''
                stream_response = chain.stream({
                    "genre": genre,
                    "world_name": world_name,
                    "identity": identity,
                    "tone": tone,
                    "overview": overview,
                    "conflict": conflict,
                })

                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"

                # 尝试从返回内容中解析JSON
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)

                try:
                    yield f"data: {json.dumps({'type': 'complete', 'length': len(full_content)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI返回格式错误，请重试'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewExportMarkdownView(BaseWorldAPIView):
    """将世界观导出为Markdown格式"""
    
    def get(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        md_parts = []
        md_parts.append(f'# {self.get_world_name(worldview)}\n')
        if self.get_world_genre(worldview):
            md_parts.append(f'\n**类型**：{self.get_world_genre(worldview)}\n')
        md_parts.append(f'\n## 世界简介\n\n{self.get_world_summary(worldview) if self.get_world_summary(worldview) else "暂无简介"}\n')
        if self.get_world_conflict(worldview):
            md_parts.append(f'\n## 背景设定\n\n{self.get_world_conflict(worldview)}\n')
        
        # 分层内容
        all_layers = self.get_all_layers(worldview)
        if all_layers:
            md_parts.append(f'\n## 分层构建\n')
            layer_names = LAYER_NAMES
            for layer_key, layer_data in all_layers.items():
                layer_name = layer_names.get(layer_key, layer_key)
                content = layer_data.get('content', '') or layer_data.get('summary', '') or ''
                if content:
                    md_parts.append(f'\n### {layer_name}\n\n{content}\n')
        
        # 结构化设置
        if self.get_world_profile(worldview):
            # 世界概要
            profile = self.get_world_profile(worldview).get('profile', {})
            if profile:
                md_parts.append(f'\n## 世界概要\n')
                if profile.get('identity'):
                    md_parts.append(f'- **世界身份**：{profile.get("identity")}\n')
                if profile.get('tone'):
                    md_parts.append(f'- **整体调性**：{profile.get("tone")}\n')
                if profile.get('summary'):
                    md_parts.append(f'- **世界摘要**：{profile.get("summary")}\n')
                if profile.get('coreConflict') or profile.get('core_conflict'):
                    md_parts.append(f'- **核心冲突**：{profile.get("coreConflict", profile.get("core_conflict"))}\n')
            
            # 规则
            rules = self.get_world_profile(worldview).get('rules', {})
            if rules and rules.get('axioms'):
                md_parts.append(f'\n## 核心规则\n')
                for idx, rule in enumerate(rules.get('axioms', [])):
                    md_parts.append(f'\n### 规则 {idx + 1}\n')
                    if rule.get('name'):
                        md_parts.append(f'- **名称**：{rule.get("name")}\n')
                    if rule.get('summary'):
                        md_parts.append(f'- **说明**：{rule.get("summary")}\n')
                    if rule.get('cost'):
                        md_parts.append(f'- **代价**：{rule.get("cost")}\n')
            
            # 势力
            factions = self.get_world_profile(worldview).get('factions', [])
            if factions:
                md_parts.append(f'\n## 势力\n')
                for faction in factions:
                    md_parts.append(f'\n### {faction.get("name", "未命名势力")}\n')
                    if faction.get('position'):
                        md_parts.append(f'- **立场**：{faction.get("position")}\n')
                    if faction.get('doctrine'):
                        md_parts.append(f'- **理念**：{faction.get("doctrine")}\n')
            
            # 地点
            locations = self.get_world_profile(worldview).get('locations', [])
            if locations:
                md_parts.append(f'\n## 地点\n')
                for location in locations:
                    md_parts.append(f'\n### {location.get("name", "未命名地名")}\n')
                    if location.get('terrain'):
                        md_parts.append(f'- **地形**：{location.get("terrain")}\n')
                    if location.get('description'):
                        md_parts.append(f'- **描述**：{location.get("description")}\n')
            
            # 关系
            relations = self.get_world_profile(worldview).get('relations', [])
            if relations:
                md_parts.append(f'\n## 关系\n')
                for relation in relations:
                    md_parts.append(f'\n### {relation.get("source", "未知")} - {relation.get("target", "未知")}\n')
                    if relation.get('type'):
                        md_parts.append(f'- **类型**：{relation.get("type")}\n')
                    if relation.get('description'):
                        md_parts.append(f'- **描述**：{relation.get("description")}\n')
        
        return self.success_response({'markdown': ''.join(md_parts)})


class ApiWorldviewChatHistoryView(BaseWorldAPIView):
    """世界观聊天历史API"""
    
    def get(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        messages = worldview.chat_histories.filter(
            is_deleted=False
        ).order_by('created_at')
        
        return self.success_response({
            'messages': [{
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat()
            } for msg in messages]
        })
    
    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = request.data
        role = data.get('role', 'user')
        content = data.get('content', '')
        
        if not content:
            return self.error_response('消息内容不能为空')
        
        # 保存用户消息
        WorldViewChatHistory.objects.create(
            worldview=worldview,
            role=role,
            content=content
        )
        
        return self.success_response(message='消息保存成功')


class ApiWorldviewChatHistoryDeleteView(BaseWorldAPIView):
    """删除世界观聊天历史API"""
    
    def post(self, request, pk):
        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        data = request.data
        message_ids = data.get('message_ids', [])
        
        if not message_ids:
            return self.error_response('未提供要删除的消息ID')
        
        deleted_count = WorldViewChatHistory.objects.filter(
            world=worldview,
            id__in=message_ids
        ).update(is_deleted=True)
        
        return self.success_response({
            'deleted_count': deleted_count
        }, message=f'已删除{deleted_count} 条消息')


class ApiWorldviewChatStreamView(BaseWorldAPIView):
    """世界观聊天流式生成API"""
    
    def post(self, request, pk):
        data = request.data
        user_input = data.get('message', '')
        history_messages = data.get('messages', [])
        
        if not user_input:
            return self.error_response('消息不能为空')

        worldview = self.get_worldview(request.user, pk=pk)
        if not worldview:
            return self.error_response('世界观不存在')

        # 保存用户消息
        WorldViewChatHistory.objects.create(
            world=worldview,
            role='user',
            content=user_input
        )
        
        close_old_connections()
        
        def generate():
            try:
                # 构建当前世界观的内容
                current_worldview = ''
                current_worldview += f'世界观名称：{self.get_world_name(worldview)}\n'
                if self.get_world_genre(worldview):
                    current_worldview += f'小说类型：{self.get_world_genre(worldview)}\n'
                if self.get_world_summary(worldview):
                    current_worldview += f'世界观描述：{self.get_world_summary(worldview)}\n'
                if self.get_world_conflict(worldview):
                    current_worldview += f'背景设定：{self.get_world_conflict(worldview)}\n'
                
                # 构造历史对话               
                history_text = ''
                for msg in history_messages:
                    history_text += f'{msg.get("role", "user")}: {msg.get("content", "")}\n'
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_STREAM_SYSTEM_PROMPT),
                    ("user", WORLDVIEW_STREAM_USER_PROMPT)
                ])
                
                llm = get_llm(user=request.user, scene="default")
                
                chain = prompt | llm
                
                full_content = ''
                
                for content_chunk in chain.stream({
                    "current_worldview": current_worldview,
                    "user_input": user_input,
                    "history_messages": history_text
                }):
                    chunk_content = content_chunk.content if hasattr(content_chunk, 'content') else str(content_chunk)
                    if chunk_content:
                        full_content += chunk_content
                        yield f'data: {json.dumps({"type": "chunk", "chunk": chunk_content}, ensure_ascii=False)}\n\n'
                
                # 解析生成的内容
                content_start = '════CONTENT_START════'
                content_end = '════CONTENT_END════'
                question_start = '════QUESTION_START════'
                question_end = '════QUESTION_END════'
                
                content_pattern = re.compile(
                    re.escape(content_start) + r'(.*?)' + re.escape(content_end),
                    re.DOTALL
                )
                question_pattern = re.compile(
                    re.escape(question_start) + r'(.*?)' + re.escape(question_end),
                    re.DOTALL
                )
                
                content_match = content_pattern.search(full_content)
                question_match = question_pattern.search(full_content)
                
                final_content = content_match.group(1).strip() if content_match else ''
                final_question = question_match.group(1).strip() if question_match else ''
                
                # 更新世界观内容（如果有新的内容）
                if final_content and len(final_content) > 10:
                    # 这里可以根据需要更新世界观的某个字段
                    pass
                
                # 保存AI回复
                WorldViewChatHistory.objects.create(
                    worldview=worldview,
                    role='assistant',
                    content=final_question if final_question else '好的，我已经理解了'
                )
                
                yield f'data: {json.dumps({"complete": True, "content": final_content, "question": final_question}, ensure_ascii=False)}\n\n'
                
            except Exception as e:
                logger.error(f'世界观流式生成异常 {e}')
                logger.error(traceback.format_exc())
                yield f'data: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'
        
        response = StreamingHttpResponse(
            generate(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
