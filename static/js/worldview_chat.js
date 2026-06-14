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
const urlParams = new URLSearchParams(window.location.search);
const projectId = urlParams.get('project_id') || '';

// 供 common.js 回调：选择模式变化时重渲染聊天
function onSelectionModeChanged() {
    renderChatHistory();
}

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', async function() {
    // 立即显示 loading，避免页面空白等待
    if (projectId) showLoading('加载世界观数据...');

    checkAuth();
    if (!projectId) return;

    const sendBtn = document.getElementById('send-btn');
    const chatInput = document.getElementById('chat-input');

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (chatInput) {
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!isGenerating) sendMessage(); }
        });
        chatInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 160) + 'px';
        });
    }

    await loadExistingWorldview();
    if (worldviewId) {
        await initChatQuestion();
    }
    hideLoading();
});

// ==================== 导航 ====================
function goBack() {
    if (projectId) {
        window.location.href = `/worldview.html?project_id=${projectId}`;
    } else {
        window.location.href = '/index.html';
    }
}

// ==================== 认证 ====================
async function checkAuth() {
    if (!api.isAuthenticated()) {
        window.location.href = '/login.html';
        return;
    }
    try {
        const d = await api.get('/api/auth/user/');
        if (!d || !d.success) api.forceReLogin();
    } catch(e) {
        api.forceReLogin();
    }
}

// ==================== 世界观加载（仅内容，不含聊天记录）====================
async function loadExistingWorldview() {
    if (!projectId) return;
    try {
        const d = await api.get(`/api/worldview/?project_id=${projectId}`);
        if (d.success && d.data) {
            worldviewId = d.data.worldview_id;
        }
    } catch(e) {
        console.error('加载世界观失败:', e);
    }
}

// ==================== 初始引导（合并：Markdown + 空缺分析引导问题）====================
async function initChatQuestion() {
    if (!worldviewId) return;
    try {
        const d = await api.post(`/api/worldview/${worldviewId}/chat/open/`, {});
        if (!d.success || !d.data) return;

        // 渲染 Markdown
        const markdown = d.data.markdown || '';
        const hasContent = d.data.has_content !== false;

        if (hasContent && markdown) {
            // 有数据：渲染 Markdown
            currentWorldview = markdown;
            renderWorldview(markdown);

            // 渲染 LLM 生成的问题
            const { question, options } = d.data;
            if (question) updateWelcomeBubble(question, options);
        } else {
            // 无数据：显示引导提示，保留欢迎消息
            renderWorldviewEmptyHint();
        }
    } catch(e) {
        console.error('初始化数据加载失败:', e);
    }
}

function updateWelcomeBubble(question, options) {
    const firstMsg = document.querySelector('#chat-messages .chat-message.assistant');
    if (!firstMsg) return;
    const bubble = firstMsg.querySelector('.chat-bubble-assistant');
    if (!bubble) return;

    let html = escapeHtml(question).replace(/\n/g, '<br>');
    if (options && options.length > 0) {
        html += '<div class="init-options">';
        options.forEach(opt => {
            html += `<button class="init-option-btn" onclick="selectInitOption('${escapeHtml(opt).replace(/'/g, "\\'")}')">${escapeHtml(opt)}</button>`;
        });
        html += '</div>';
    }
    bubble.innerHTML = html;
}

function renderWorldviewEmptyHint() {
    const preview = document.getElementById('wv-preview');
    if (!preview) return;
    preview.innerHTML = `
        <div class="worldview-empty">
            <i class="fas fa-lightbulb"></i>
            <p>还没有世界观数据</p>
            <p style="font-size:0.85rem; color: var(--text-muted);">在右侧对话框向AI描述你想要的<br>题材、风格、基本设定，开始构建吧</p>
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
    if (content.trim()) {
        preview.innerHTML = safeMarkdownParse(content);
        preview.classList.remove('d-none');
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
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;
    if (!worldviewId) {
        showError('世界观未加载，请刷新页面');
        return;
    }

    isGenerating = true;
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.classList.add('generating');
    }

    const chatMessages = document.getElementById('chat-messages');
    // 用户消息
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    userDiv.innerHTML = `<div class="chat-bubble chat-bubble-user">${escapeHtml(message).replace(/\n/g,'<br>')}</div><div class="chat-message-avatar avatar-me ms-2">我</div>`;
    chatMessages.appendChild(userDiv);

    // 思考状态
    const thinkDiv = document.createElement('div');
    thinkDiv.className = 'chat-message assistant';
    const thinkBubble = document.createElement('div');
    thinkBubble.className = 'chat-bubble chat-bubble-assistant';
    thinkBubble.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 思考中...`;
    thinkDiv.innerHTML = `<div class="chat-message-avatar avatar-wv me-2">WV</div>`;
    thinkDiv.appendChild(thinkBubble);
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
        const response = await fetch(`/api/worldview/${worldviewId}/chat/stream/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${api.getToken()}`,
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                message: message,
                messages: contextMessages
            })
        });

        if (response.status === 401) {
            api.forceReLogin();
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `请求失败: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let streamingBuffer = '';
        let isComplete = false;
        let finalMarkdown = '';
        let finalReply = '';
        let finalOptions = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            streamingBuffer += chunk;

            const lines = streamingBuffer.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.type === 'chunk' && data.chunk) {
                            // 流式 Markdown 分块 → 实时渲染到左侧预览区
                            currentWorldview += data.chunk;
                            renderWorldview(currentWorldview);
                        } else if (data.type === 'complete') {
                            isComplete = true;
                            finalMarkdown = data.markdown || '';
                            finalReply = data.reply || '';
                            finalOptions = data.options || [];
                            if (finalMarkdown) {
                                currentWorldview = finalMarkdown;
                                renderWorldview(currentWorldview);
                            }
                        } else if (data.type === 'error') {
                            thinkBubble.innerHTML = `<i class="fas fa-exclamation-circle" style="color:#ef4444;"></i> ${escapeHtml(data.message || '')}`;
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                    } catch (e) {
                        // JSON 解析失败，忽略
                    }
                }
            }
        }

        // 完成 — 显示助手回复
        thinkDiv.innerHTML = '';
        if (isComplete) {
            if (finalReply) {
                const replyDiv = document.createElement('div');
                replyDiv.className = 'chat-message assistant';
                replyDiv.innerHTML = `<div class="chat-message-avatar avatar-wv me-2">WV</div>`;
                const replyBubble = document.createElement('div');
                replyBubble.className = 'chat-bubble chat-bubble-assistant';
                replyDiv.appendChild(replyBubble);
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
                        btn.onclick = () => selectInitOption(opt);
                        optionsDiv.appendChild(btn);
                    });
                    replyBubble.appendChild(optionsDiv);
                }
                messages.push({ role: 'assistant', content: finalReply });
            } else {
                // 没有 reply 时显示简要确认
                const doneDiv = document.createElement('div');
                doneDiv.className = 'chat-message assistant';
                doneDiv.innerHTML = `<div class="chat-message-avatar avatar-wv me-2">WV</div>
                    <div class="chat-bubble chat-bubble-assistant">世界观内容已更新，请查看左侧预览区</div>`;
                chatMessages.appendChild(doneDiv);
                messages.push({ role: 'assistant', content: '世界观内容已更新' });
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        } else {
            thinkDiv.innerHTML = `<div class="chat-message-avatar avatar-wv me-2">WV</div>
                <div class="chat-bubble chat-bubble-assistant" style="color:#ef4444;"><i class="fas fa-exclamation-circle"></i> 抱歉，生成失败，请重试。</div>`;
        }

        isGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.classList.remove('generating');
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch(error) {
        console.error(error);
        thinkDiv.innerHTML = `<div class="chat-message-avatar avatar-wv me-2">WV</div>
            <div class="chat-bubble chat-bubble-assistant" style="color:#ef4444;"><i class="fas fa-exclamation-circle"></i> 发生错误，请重试。</div>`;
        isGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.classList.remove('generating');
        }
    }
}

// 打字机效果
async function typeText(element, text, callback, speed) {
    element.innerHTML = '';
    for (let i = 0; i < text.length; i++) {
        element.innerHTML += escapeHtml(text.charAt(i)).replace(/\n/g, '<br>');
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(r => setTimeout(r, speed || 15));
    }
    if (callback) callback();
}
