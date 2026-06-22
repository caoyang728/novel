/**
 * 世界观聊天构建页面脚本
 * 聊天记录仅在前端内存缓存(messages[])，不持久化
 * 依赖: common.js (api, showSuccess, showError, showLoading, hideLoading, escapeHtml, getCookie, safeMarkdownParse)
 */

let messages = [];
let currentWorldview = '';
let isSelectionMode = false;
let selectedMessages = new Set();
let isGenerating = false;
let worldviewId = '';
const projectId = getProjectIdFromUrl() || '';

// 供 common.js 回调：选择模式变化时重渲染聊天
function onSelectionModeChanged() {
    renderChatHistory();
}

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', async function() {
    // 立即显示 loading，避免页面空白等待
    if (projectId) showLoading('加载世界观数据...');

    const authOk = await checkAuth();
    if (!authOk) {
        hideLoading();
        return;
    }
    if (!projectId) {
        hideLoading();
        return;
    }

    // 使用 common.js 的 initBackToProjectButton 初始化返回按钮
    initBackToProjectButton('#backBtn', 'worldview.html');

    const sendBtn = document.getElementById('send-btn');
    const chatInput = document.getElementById('chat-input');

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (chatInput) {
        initChatInput(chatInput, { onSend: () => { if (!isGenerating) sendMessage(); }, maxHeight: 160 });
    }

    try {
        await loadProjectInfo(projectId);
        // 并行发起两个请求：Markdown 快速渲染，LLM 引导问题异步更新气泡
        fetchWorldviewMarkdown();
        fetchInitQuestions();
    } catch(e) {
        console.error('初始化失败:', e);
        hideLoading();
    }
});

// ==================== 导航 ====================
// 使用 common.js 的 initBackToProjectButton，无需自定义 goBack()


// ==================== 世界观 Markdown 加载（快速，毫秒级）====================
async function fetchWorldviewMarkdown() {
    if (!projectId) {
        hideLoading();
        return;
    }
    try {
        await _loadAndRenderMarkdown();
    } catch(e) {
        console.error('加载世界观Markdown失败:', e);
    } finally {
        hideLoading();
    }
}

async function refreshWorldviewMarkdown() {
    if (!projectId) return;
    try {
        await _loadAndRenderMarkdown();
    } catch(e) {
        console.error('刷新世界观Markdown失败:', e);
    }
}

async function _loadAndRenderMarkdown() {
    const d = await api.get(`/api/projects/${projectId}/worldviews/export/markdown/`);
    if (!d || !d.success || !d.data) return;
    worldviewId = d.data.worldview_id;
    const markdown = d.data.markdown || '';
    if (markdown && markdown.trim()) {
        currentWorldview = markdown;
        renderWorldview(markdown);
    } else {
        renderWorldviewEmptyHint();
    }
}

// ==================== LLM 引导问题（慢速，AI 调用 ~17秒）====================
async function fetchInitQuestions() {
    if (!projectId) return;
    isGenerating = true;
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.classList.add('generating');
    }
    showWelcomeLoading();
    try {
        const d = await api.post(`/api/projects/${projectId}/worldviews/chat/open/`, {});
        if (!d || !d.success || !d.data) {
            showWelcomeDefault();
            return;
        }

        // 如果 markdown 请求还没返回 worldviewId，这里兜底
        if (!worldviewId && d.data.worldview_id) {
            worldviewId = d.data.worldview_id;
        }

        const hasContent = d.data.has_content !== false;
        if (hasContent) {
            const { question, options } = d.data;
            if (question && worldviewId) {
                updateWelcomeBubble(question, options);
            } else {
                showWelcomeDefault();
            }
        } else {
            showWelcomeDefault();
        }
    } catch(e) {
        console.error('加载引导问题失败:', e);
        showWelcomeDefault();
    } finally {
        isGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.classList.remove('generating');
        }
    }
}

function showWelcomeLoading() {
    const bubble = _getWelcomeBubble();
    if (!bubble) return;
    bubble.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在分析世界观空缺，生成引导问题...';
}

function showWelcomeDefault() {
    const bubble = _getWelcomeBubble();
    if (!bubble) return;
    bubble.innerHTML = '你好！我是你的世界观构建助手。<br><br>告诉我你想创作什么类型的故事（玄幻、科幻、都市、末世、古风等），以及大致的世界背景构想，我会一步步帮你搭建完整的世界观体系。';
}

function _getWelcomeBubble() {
    const firstMsg = document.querySelector('#chat-messages .chat-message.assistant');
    return firstMsg ? firstMsg.querySelector('.chat-bubble-assistant') : null;
}

function updateWelcomeBubble(question, options) {
    const firstMsg = document.querySelector('#chat-messages .chat-message.assistant');
    if (!firstMsg) return;
    const bubble = firstMsg.querySelector('.chat-bubble-assistant');
    if (!bubble) return;

    let html = escapeHtml(question).replace(/\n/g, '<br>');
    if (options && options.length > 0) {
        html += '<div class="init-options">';
        options.forEach((opt, idx) => {
            html += `<button class="init-option-btn" data-init-idx="${idx}">${escapeHtml(opt)}</button>`;
        });
        html += '</div>';
        // 存储选项供点击时使用
        bubble._initOptions = options;
    }
    bubble.innerHTML = html;

    // 使用事件委托绑定点击，避免 inline onclick 的 XSS 风险
    bubble.querySelectorAll('.init-option-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const idx = parseInt(this.dataset.initIdx);
            const opts = bubble._initOptions;
            if (opts && opts[idx]) {
                selectInitOption(opts[idx]);
            }
        });
    });
}

function renderWorldviewEmptyHint() {
    const preview = document.getElementById('wv-preview');
    if (!preview) return;
    preview.innerHTML = `
        <div class="worldview-empty">
            <i class="fas fa-lightbulb"></i>
            <p>还没有世界观数据</p>
            <p class="empty-hint">在右侧对话框向AI描述你想要的<br>题材、风格、基本设定，开始构建吧</p>
        </div>
    `;
    preview.classList.remove('d-none');
}

function selectInitOption(text) {
    const input = document.getElementById('chat-input');
    if (input) {
        input.value = text;
        input.dispatchEvent(new Event('input'));
        sendMessage();
    }
}

// ==================== 聊天消息渲染 ====================
function renderChatHistory() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    chatMessages.innerHTML = '';

    for (let index = 0; index < messages.length; index++) {
        const msg = messages[index];
        const div = document.createElement('div');
        div.className = `chat-message ${msg.role}${selectedMessages.has(index) ? ' selected' : ''}`;
        div.dataset.messageIndex = index;

        if (msg.role === 'user') {
            div.innerHTML = `
                ${isSelectionMode ? `<input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${index})" ${selectedMessages.has(index) ? 'checked' : ''}>` : ''}
                <div class="chat-message-content">
                    <div class="chat-bubble chat-bubble-user">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>
                    <div class="chat-message-avatar avatar-me ms-2">我</div>
                </div>
            `;
        } else {
            div.innerHTML = `
                ${isSelectionMode ? `<input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${index})" ${selectedMessages.has(index) ? 'checked' : ''}>` : ''}
                <div class="chat-message-content">
                    <div class="chat-message-avatar avatar-wv me-2">WV</div>
                    <div class="chat-bubble chat-bubble-assistant">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>
                </div>
            `;
        }
        chatMessages.appendChild(div);
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderWorldview(content) {
    const preview = document.getElementById('wv-preview');
    if (!preview) return;
    if (content && content.trim()) {
        preview.innerHTML = safeMarkdownParse(content);
        preview.classList.remove('d-none');
    } else {
        renderWorldviewEmptyHint();
    }
}

// ==================== 编辑/预览切换 ====================
function showEditMode() {
    const textarea = document.getElementById('wv-textarea');
    const preview = document.getElementById('wv-preview');
    const btnEdit = document.getElementById('btn-edit');
    const btnPreview = document.getElementById('btn-preview');

    if (textarea) textarea.classList.remove('d-none');
    if (preview) preview.classList.add('d-none');
    if (btnEdit) btnEdit.classList.add('active');
    if (btnPreview) btnPreview.classList.remove('active');
    if (textarea) {
        textarea.value = currentWorldview;
        textarea.focus();
    }
}

function showPreviewMode() {
    const textarea = document.getElementById('wv-textarea');
    const preview = document.getElementById('wv-preview');
    const btnEdit = document.getElementById('btn-edit');
    const btnPreview = document.getElementById('btn-preview');

    if (textarea) currentWorldview = textarea.value;
    if (preview) preview.innerHTML = safeMarkdownParse(currentWorldview || '');
    if (textarea) textarea.classList.add('d-none');
    if (preview) preview.classList.remove('d-none');
    if (btnPreview) btnPreview.classList.add('active');
    if (btnEdit) btnEdit.classList.remove('active');
}

// ==================== 分类更新 ====================
function updateCategoryBadge(category) {
    const badge = document.getElementById('current-category');
    if (!badge) return;
    const labels = {
        worldview:'世界地理',
        setting:'力量体系',
        history:'起源历史',
        culture:'社会文化',
        location:'地理环境',
        rule:'规则设定',
        plot_foreshadow:'伏笔秘密',
        base:'整体基调',
        economy:'经济资源',
        faction:'势力格局',
        race:'种族生物',
        other:'其他'
    };
    badge.textContent = labels[category] || category;
    badge.className = 'category-badge cat-' + category;
}

// ==================== 发送消息 ====================
async function sendMessage() {
    if (isGenerating) return;
    if (!projectId) return;
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    isGenerating = true;
    // 每次发送前重置流式状态变量
    let isComplete = false;
    let finalMarkdown = '';
    let finalReply = '';
    let finalOptions = [];

    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.classList.add('generating');
    }

    const chatMessages = document.getElementById('chat-messages');
    // 用户消息
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    userDiv.innerHTML = `
        <div class="chat-message-content">
            <div class="chat-bubble chat-bubble-user">${escapeHtml(message).replace(/\n/g,'<br>')}</div>
            <div class="chat-message-avatar avatar-me ms-2">我</div>
        </div>
    `;
    chatMessages.appendChild(userDiv);

    // 思考状态
    const thinkDiv = document.createElement('div');
    thinkDiv.className = 'chat-message assistant';
    const thinkAvatar = document.createElement('div');
    thinkAvatar.className = 'chat-message-avatar avatar-wv me-2';
    thinkAvatar.textContent = 'WV';
    const thinkBubble = document.createElement('div');
    thinkBubble.className = 'chat-bubble chat-bubble-assistant';
    thinkBubble.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 思考中...`;
    const thinkContent = document.createElement('div');
    thinkContent.className = 'chat-message-content';
    thinkContent.appendChild(thinkAvatar);
    thinkContent.appendChild(thinkBubble);
    thinkDiv.appendChild(thinkContent);
    chatMessages.appendChild(thinkDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    messages.push({ role: 'user', content: message });
    input.value = '';
    input.style.height = 'auto';

    // 根据上下文数量截取消息
    const ctxDropdown = document.getElementById('context-count-dropdown');
    const ctxCount = ctxDropdown ? parseInt(ctxDropdown.value) || 10 : 10;
    const contextMessages = ctxCount >= messages.length ? messages : messages.slice(messages.length - ctxCount * 2);

    try {
        await api.streamRequestRaw(`/api/projects/${projectId}/worldviews/chat/stream/`, {
            body: JSON.stringify({
                message: message,
                messages: contextMessages
            })
        }, (chunk) => {
            if (chunk.done) return;
            const parsed = chunk.data;
            if (parsed && parsed.type === 'error') {
                thinkBubble.innerHTML = `<i class="fas fa-exclamation-circle" style="color:#ef4444;"></i> ${escapeHtml(parsed.message || '')}`;
                chatMessages.scrollTop = chatMessages.scrollHeight;
                return;
            }
            if (parsed && parsed.type === 'chunk' && parsed.chunk) {
                currentWorldview += parsed.chunk;
                renderWorldview(currentWorldview);
            } else if (parsed && parsed.type === 'complete') {
                isComplete = true;
                finalMarkdown = parsed.markdown || '';
                finalReply = parsed.reply || '';
                finalOptions = parsed.options || [];
                if (finalMarkdown) {
                    currentWorldview = finalMarkdown;
                    renderWorldview(currentWorldview);
                }
            }
        });

        // 完成 — 显示助手回复
        thinkDiv.remove();
        if (isComplete) {
            if (finalReply) {
                const replyDiv = document.createElement('div');
                replyDiv.className = 'chat-message assistant';
                const replyAvatar = document.createElement('div');
                replyAvatar.className = 'chat-message-avatar avatar-wv me-2';
                replyAvatar.textContent = 'WV';
                const replyBubble = document.createElement('div');
                replyBubble.className = 'chat-bubble chat-bubble-assistant';
                const replyContent = document.createElement('div');
                replyContent.className = 'chat-message-content';
                replyContent.appendChild(replyAvatar);
                replyContent.appendChild(replyBubble);
                replyDiv.appendChild(replyContent);
                chatMessages.appendChild(replyDiv);

                await typeText(replyBubble, finalReply, () => {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }, 15);
                // 添加推荐选项按钮
                if (finalOptions && finalOptions.length > 0) {
                    const optionsDiv = document.createElement('div');
                    optionsDiv.className = 'init-options';
                    finalOptions.forEach(opt => {
                        const btn = document.createElement('button');
                        btn.className = 'init-option-btn';
                        btn.textContent = opt;
                        btn.addEventListener('click', () => selectInitOption(opt));
                        optionsDiv.appendChild(btn);
                    });
                    replyBubble.appendChild(optionsDiv);
                }
                messages.push({ role: 'assistant', content: finalReply });
            } else {
                // 没有 reply 时显示简要确认
                const doneDiv = document.createElement('div');
                doneDiv.className = 'chat-message assistant';
                doneDiv.innerHTML = `
                    <div class="chat-message-content">
                        <div class="chat-message-avatar avatar-wv me-2">WV</div>
                        <div class="chat-bubble chat-bubble-assistant">世界观内容已更新，请查看左侧预览区</div>
                    </div>
                `;
                chatMessages.appendChild(doneDiv);
                messages.push({ role: 'assistant', content: '世界观内容已更新' });
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        } else {
            const failDiv = document.createElement('div');
            failDiv.className = 'chat-message assistant';
            failDiv.innerHTML = `
                <div class="chat-message-content">
                    <div class="chat-message-avatar avatar-wv me-2">WV</div>
                    <div class="chat-bubble chat-bubble-assistant" style="color:#ef4444;"><i class="fas fa-exclamation-circle"></i> 抱歉，生成失败，请重试。</div>
                </div>
            `;
            chatMessages.appendChild(failDiv);
        }

        // 从后端重新获取最终 Markdown（比流式拼装更可靠）
        await refreshWorldviewMarkdown();

    } catch(error) {
        console.error(error);
        thinkDiv.remove();
        const errDiv = document.createElement('div');
        errDiv.className = 'chat-message assistant';
        errDiv.innerHTML = `
            <div class="chat-message-content">
                <div class="chat-message-avatar avatar-wv me-2">WV</div>
                <div class="chat-bubble chat-bubble-assistant" style="color:#ef4444;"><i class="fas fa-exclamation-circle"></i> 发生错误，请重试。</div>
            </div>
        `;
        chatMessages.appendChild(errDiv);
    } finally {
        isGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.classList.remove('generating');
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// 打字机效果
async function typeText(element, text, callback, speed) {
    element.innerHTML = '';
    for (let i = 0; i < text.length; i++) {
        const char = text.charAt(i);
        if (char === '\n') {
            element.appendChild(document.createElement('br'));
        } else {
            element.appendChild(document.createTextNode(char));
        }
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(r => setTimeout(r, speed || 15));
    }
    if (callback) callback();
}
