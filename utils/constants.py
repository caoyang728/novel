"""
项目级公共常量定义

集中管理所有业务常量，便于统一维护和跨模块引用。
"""

# ========== 章节字段长度限制 ==========

# 章节内容最大长度（10万字）
MAX_CONTENT_LENGTH = 100000

# 章节标题最大长度
MAX_TITLE_LENGTH = 255

# 章节摘要最大长度
MAX_SUMMARY_LENGTH = 5000

# ========== 章节生成参数 ==========

# 章节延续时保留的原章节字数
CONTINUE_KEPT_LENGTH = 3100

# 获取上一章末尾上下文时截取的字数
PREV_CHAPTER_TAIL_LENGTH = 500

# ========== 聊天对话参数 ==========

# 聊天消息最大长度
MAX_CHAT_MESSAGE_LENGTH = 2000

# 聊天历史最大条数
MAX_CHAT_HISTORY_LENGTH = 20
