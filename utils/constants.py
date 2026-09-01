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

# ========== 章节批次生成参数 ==========

# 每批次生成的章节数（可配置）
BATCH_SIZE = 2

# 批次生成时，取前N章摘要作为上下文
BATCH_PREV_CHAPTERS_COUNT = 3

# 批次生成时，取后M章概述作为上下文
BATCH_NEXT_CHAPTERS_COUNT = 3

# 上一批次摘要上下文（取末尾N字）
PREV_BATCH_SUMMARY_TAIL_LENGTH = 1500

# 一致性修复最大循环次数
MAX_VERIFY_FIX_LOOPS = 2

# 评分达标阈值（0-100分）
SCORING_PASS_THRESHOLD = 75

# 评分不达标时最大重写次数
MAX_REWRITE_LOOPS = 1

# 章节内容末尾截取字数（用于批次间衔接）
CHAPTER_TAIL_CONTEXT_LENGTH = 500

# ========== Redis 缓存键前缀 ==========

# 基石上下文缓存键
REDIS_KEY_CORNERSTONE_CTX = "cornerstone_ctx"

# 卷大纲编辑锁键
REDIS_KEY_VOLUME_LOCK = "volume_lock"

# ========== 聊天对话参数 ==========

# 聊天消息最大长度
MAX_CHAT_MESSAGE_LENGTH = 2000

# 聊天历史最大条数
MAX_CHAT_HISTORY_LENGTH = 20
