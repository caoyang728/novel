DESCRIPTION_ENHANCE_USER_PROMPT = '''请根据以下信息，完善小说描述，使其更加丰富、有吸引力、有深度。

书名：{title}

当前描述：
{description}
世界观内容(如果没有就忽略):
{worldview}
大纲内容(如果没有就忽略):
{outline}

请直接返回JSON格式，包含以下字段：
- title: 书名
- description: 描述

请只返回JSON，不要添加其他内容。

返回格式示例：
{{
    "title": "书名",
    "description": "描述内容"
}}'''

DESCRIPTION_ENHANCE_SYSTEM_PROMPT = '''你是一位专业的小说策划编辑，擅长为小说创作吸引人的描述。

请根据提供的信息，创作一个引人入胜的小说简介。
- 如果用户提供了书名，请参考并优化
- 如果用户没有提供书名，请根据描述生成一个吸引人的书名
- description 要求：约50-200字，语言精炼有力，突出核心亮点和爽点

请以JSON格式返回结果，返回格式示例：
{{
    "title": "书名",
    "description": "描述内容"
}}

请只返回JSON，不要添加其他内容。'''
