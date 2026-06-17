let projectId = null;
let messages = [];
let currentVersionId = null;
let currentVersionNumber = 0;
let streamVersionId = null; // 流式响应期间锁定的版本ID，防止竞态
let isVersionLocked = false; // 版本是否被锁定
const selectedMessages = new Set();
let isSelectionMode = false;
const MAX_INPUT_LENGTH = 5000;
const MAX_OUTLINE_LENGTH = 200000;

// 大纲基线：与数据库一致的内容，用于 diff 对比和未保存检测
let savedOutlineBaseline = '';

function getBaselineKey() {
    return projectId ? `outline_baseline_${projectId}_${currentVersionId || 'new'}` : '';
}

function saveBaseline(content) {
    savedOutlineBaseline = content;
    const key = getBaselineKey();
    if (key) {
        localStorage.setItem(key, content);
    }
}

function hasUnsavedChanges() {
    const currentContent = document.getElementById('outline-content').value;
    return currentContent !== savedOutlineBaseline;
}

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    projectId = getProjectIdFromUrl();
    const urlParams = new URLSearchParams(window.location.search);
    currentVersionId = urlParams.get('version_id');

    // 校验 projectId 为有效正整数，防止模板变量未渲染等异常
    if (projectId && /^\d+$/.test(projectId)) {
        showLoading('加载中...');
        Promise.all([loadProjectInfo(projectId), loadOutlineVersions()]).finally(() => hideLoading());
    } else {
        projectId = null;
        showModal('参数错误', '项目ID参数无效，请从项目列表进入。', function() {
            window.location.href = '/project.html';
        });
    }

    const savedContextCount = localStorage.getItem('outline_context_count');
    if (savedContextCount) {
        document.getElementById('context-count-dropdown').value = savedContextCount;
    }

    document.getElementById('context-count-dropdown').addEventListener('change', function() {
        localStorage.setItem('outline_context_count', this.value);
    });

    document.getElementById('outline-content').addEventListener('input', function() {
        updateButtons();
    });

    // 点击大纲编辑区时停止打字机效果
    document.getElementById('outline-content').addEventListener('click', function() {
        if (isTyping) {
            stopTyping();
        }
    });

    document.getElementById('send-message').addEventListener('click', sendMessage);
    initChatInput('#chat-input', { onSend: sendMessage, maxHeight: 160 });

    initBackToProjectButton('.back-btn');

    // 页面离开前检测未保存修改
    window.addEventListener('beforeunload', function(e) {
        if (hasUnsavedChanges()) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // 返回按钮拦截未保存修改
    const backBtn = document.querySelector('.back-btn');
    if (backBtn) {
        const originalOnclick = backBtn.onclick;
        backBtn.onclick = function(e) {
            if (hasUnsavedChanges()) {
                e.preventDefault();
                showModal('未保存的修改', '当前大纲有未保存的修改，离开页面将丢失这些修改。确定要离开吗？', function() {
                    saveBaseline(document.getElementById('outline-content').value); // 标记为已保存以避免二次弹窗
                    if (originalOnclick) {
                        originalOnclick.call(backBtn);
                    } else {
                        window.history.back();
                    }
                });
            } else if (originalOnclick) {
                originalOnclick.call(backBtn);
            }
        };
    }

    const versionSelect = document.getElementById('version-select');
    let ignoreNextBlur = false;

    versionSelect.addEventListener('focus', function() {
        Array.from(this.options).forEach(option => {
            if (option.dataset.originalText) {
                option.text = option.dataset.originalText;
            }
        });
    });

    versionSelect.addEventListener('change', function() {
        const versionId = this.value;
        if (versionId) {
            if (hasUnsavedChanges()) {
                showModal('未保存的修改', '当前大纲有未保存的修改，切换版本将丢失这些修改。确定要切换吗？', function() {
                    loadOutlineVersion(versionId);
                });
                // 重置下拉框回到当前版本
                this.value = currentVersionId || '';
            } else {
                loadOutlineVersion(versionId);
            }
            ignoreNextBlur = true;
        }
    });

    versionSelect.addEventListener('blur', function() {
        if (ignoreNextBlur) {
            ignoreNextBlur = false;
            return;
        }
        const selectedOption = this.options[this.selectedIndex];
        if (selectedOption && selectedOption.dataset.originalText) {
            selectedOption.text = `当前版本 ${selectedOption.dataset.originalText}`;
        }
    });
});

async function loadOutlineVersions() {
    try {
        // console.log('Loading outline versions for project:', projectId);
        const data = await api.get(`/api/projects/${projectId}/outline/versions/`);
        // console.log('Loaded outline versions data:', data);

        if (data.success) {
            const select = document.getElementById('version-select');
            select.innerHTML = '<option value="">选择版本...</option>';

            let finalizedVersion = null;
            let latestVersion = null;

            data.versions.forEach(version => {
                const option = document.createElement('option');
                option.value = version.id;
                const text = `v${version.version_number}${version.is_finalized ? ' (锁定)' : ''}`;
                option.textContent = text;
                option.dataset.originalText = text;
                select.appendChild(option);

                if (version.is_finalized) {
                    finalizedVersion = version;
                }
                if (!latestVersion || version.version_number > latestVersion.version_number) {
                    latestVersion = version;
                }
            });

            // console.log('Finalized version:', finalizedVersion);
            // console.log('Latest version:', latestVersion);

            if (currentVersionId) {
                select.value = currentVersionId;
                const option = select.querySelector(`option[value="${currentVersionId}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                loadOutlineVersion(currentVersionId);
            } else if (latestVersion) {
                select.value = latestVersion.id;
                const option = select.querySelector(`option[value="${latestVersion.id}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                // console.log('Loading from latestVersion:', latestVersion.id);
                loadOutlineVersion(latestVersion.id);
            } else if (finalizedVersion) {
                select.value = finalizedVersion.id;
                const option = select.querySelector(`option[value="${finalizedVersion.id}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                loadOutlineVersion(finalizedVersion.id);
            }
        }
    } catch (error) {
        console.error('Failed to load outline versions:', error);
    }
}

async function loadOutlineVersion(versionId) {
    currentVersionId = versionId;
    // console.log('Loading outline version:', versionId);

    // 淡出预览区
    const previewEl = document.getElementById('outline-preview');
    previewEl.classList.add('fade-out');

    try {
        const data = await api.get(`/api/projects/${projectId}/outline/versions/${versionId}/`);
        // console.log('Loaded outline version data:', data);

        if (data.success) {
            const content = data.content || '';

            document.getElementById('outline-content').value = content;
            previewEl.innerHTML = content ? safeMarkdownParse(content) : '<div class="outline-empty"><i class="fas fa-file-text"></i><p>暂无大纲内容</p></div>';

            // 存储基线（与数据库一致的内容）
            saveBaseline(content);

            if (data.version_number !== undefined) {
                document.getElementById('outline-version').textContent = `v${data.version_number}`;
                currentVersionNumber = data.version_number;
            }

            const select = document.getElementById('version-select');
            const selectedOption = select.querySelector(`option[value="${versionId}"]`);
            if (selectedOption) {
                selectedOption.text = `当前版本 v${data.version_number}${data.is_finalized ? ' (锁定)' : ''}`;
            }

            // 更新锁定状态
            isVersionLocked = data.is_finalized || false;
            
            // 聊天记录仅在前端维护，切换版本时清空
            messages = [];
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="chat-message assistant">
                        <div class="chat-message-avatar avatar-ai me-2">AI</div>
                        <div class="chat-bubble chat-bubble-assistant">
                            您好！我是您的大纲助手，可以为您提供大纲的生成和优化服务。
                        </div>
                    </div>
                `;
            }

            updateButtons();
            // 淡入预览区
            previewEl.classList.remove('fade-out');
        } else {
            // console.log('API response not successful:', data);
            previewEl.innerHTML = '<div class="outline-empty"><i class="fas fa-file-text"></i><p>暂无大纲内容</p></div>';
            previewEl.classList.remove('fade-out');
        }
    } catch (error) {
        console.error('Failed to load outline version:', error);
        previewEl.classList.remove('fade-out');
    }
}

function renderChatHistory() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    if (messages.length === 0) {
        chatMessages.innerHTML = `
            <div class="chat-message assistant">
                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                <div class="chat-bubble chat-bubble-assistant">
                    您好！我是您的大纲助手，可以为您提供大纲的生成和优化服务。
                </div>
            </div>
        `;
        return;
    }

    chatMessages.innerHTML = '';
    messages.forEach((msg, index) => {
        const div = document.createElement('div');
        div.className = `chat-message ${msg.role === 'user' ? 'user' : 'assistant'}`;
        div.dataset.messageIndex = index;

        const cleanedContent = msg.content
            .replace(/════CONTENT_START════/g, '')
            .replace(/════CONTENT_END════/g, '')
            .replace(/════QUESTION_START════/g, '')
            .replace(/════QUESTION_END════/g, '');

        if (msg.role === 'user') {
            div.innerHTML = `
                <input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${index})" ${selectedMessages.has(index) ? 'checked' : ''}>
                <div class="chat-bubble chat-bubble-user">${escapeHtml(cleanedContent).replace(/\n/g, '<br>')}</div>
                <div class="chat-message-avatar avatar-me ms-2">我</div>
            `;
        } else {
            div.innerHTML = `
                <input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${index})" ${selectedMessages.has(index) ? 'checked' : ''}>
                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                <div class="chat-bubble chat-bubble-assistant markdown-content">${safeMarkdownParse(cleanedContent)}</div>
            `;
        }

        if (selectedMessages.has(index)) {
            div.classList.add('selected');
        }

        chatMessages.appendChild(div);
    });
    chatMessages.scrollTop = chatMessages.scrollHeight;
    updateDeleteButton();
}

// 供 common.js 回调：选择模式变化时重渲染聊天
function onSelectionModeChanged() {
    renderChatHistory();
    updateDeleteButton();
}

function updateDeleteButton() {
    const deleteBtn = document.getElementById('delete-selected-btn');
    if (deleteBtn) {
        deleteBtn.disabled = selectedMessages.size === 0;
        deleteBtn.innerHTML = `<i class="fas fa-trash"></i> 删除选中`;
    }
}

function updateButtons() {
    const content = document.getElementById('outline-content').value;
    const hasContent = content.trim() !== '';
    document.getElementById('save-btn').disabled = !hasContent || isVersionLocked;
    document.getElementById('save-as-btn').disabled = !hasContent;
    document.getElementById('lock-btn').disabled = !hasContent || isVersionLocked;
    document.getElementById('delete-version-btn').disabled = !currentVersionId || isVersionLocked;
    
    // 更新字数统计
    const wordCount = content.length;
    document.getElementById('outline-word-count').textContent = `${wordCount} 字`;
}

function showEditMode() {
    document.getElementById('outline-content').classList.remove('d-none');
    document.getElementById('outline-preview').classList.add('d-none');
    document.getElementById('btn-edit').classList.add('active');
    document.getElementById('btn-preview').classList.remove('active');
}

function showPreviewMode() {
    const content = document.getElementById('outline-content').value;
    // 对比基线，有差异时高亮显示
    if (hasUnsavedChanges()) {
        document.getElementById('outline-preview').innerHTML = diffHighlight(savedOutlineBaseline, content);
    } else {
        document.getElementById('outline-preview').innerHTML = content ? safeMarkdownParse(content) : '<div class="outline-empty"><i class="fas fa-file-text"></i><p>暂无大纲内容</p></div>';
    }
    document.getElementById('outline-content').classList.add('d-none');
    document.getElementById('outline-preview').classList.remove('d-none');
    document.getElementById('btn-preview').classList.add('active');
    document.getElementById('btn-edit').classList.remove('active');
}

function diffHighlight(oldContent, newContent) {
    // 在 HTML 层面做 diff，避免 markdown 标记冲突
    const oldHtml = oldContent.trim() ? safeMarkdownParse(oldContent) : '';
    const newHtml = newContent.trim() ? safeMarkdownParse(newContent) : '';

    if (!oldHtml.trim()) {
        return newHtml;
    }

    const oldLines = oldHtml.split('\n');
    const newLines = newHtml.split('\n');
    let result = '';
    let lineIndex = 0;

    while (lineIndex < newLines.length) {
        const newLine = newLines[lineIndex];
        const oldLine = oldLines[lineIndex];

        if (oldLine === newLine) {
            result += newLine + '\n';
        } else if (!oldLine) {
            // 新增行
            result += `<div class="diff-change">${newLine}</div>\n`;
        } else {
            // 修改行：对行内内容做词级 diff
            const oldWords = oldLine.split(/(<[^>]+>)/);
            const newWords = newLine.split(/(<[^>]+>)/);
            // 简化处理：整行标记为变更
            result += `<div class="diff-change">${newLine}</div>\n`;
        }
        lineIndex++;
    }
    return result.trim();
}

let isSending = false;
let isTyping = false;
let currentTypingTimeout = null;

async function sendMessage() {
    if (isSending) return;
    
    // 停止正在进行的打字机效果
    stopTyping();
    
    // 检查版本是否被锁定
    if (isVersionLocked) {
        showError('当前版本已被锁定，无法进行修改');
        return;
    }
    
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    if (message.length > MAX_INPUT_LENGTH) {
        showError(`消息内容不能超过${MAX_INPUT_LENGTH}字符`);
        return;
    }

    isSending = true;
    // 锁定当前版本ID，防止流式响应期间切换版本导致竞态
    streamVersionId = currentVersionId;

    input.disabled = true;
    document.getElementById('send-message').disabled = true;

    const chatMessages = document.getElementById('chat-messages');
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    userDiv.innerHTML = `
        <div class="chat-bubble chat-bubble-user">${escapeHtml(message).replace(/\n/g, '<br>')}</div>
        <div class="chat-message-avatar avatar-me ms-2">我</div>
    `;
    chatMessages.appendChild(userDiv);

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-message assistant';
    loadingDiv.innerHTML = `
        <div class="chat-message-avatar avatar-ai me-2">AI</div>
        <div class="chat-bubble chat-bubble-assistant">
            <i class="fas fa-spinner fa-spin"></i> 思考中...
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    messages.push({ role: 'user', content: message });
    input.value = '';
    input.style.height = 'auto';

    showLoading('AI 正在思考...', 0.3);

    const contextCount = document.getElementById('context-count-dropdown').value;
    let historyMessages = messages.slice(0, -1);

    if (contextCount !== 'all') {
        historyMessages = historyMessages.slice(-parseInt(contextCount) * 2);
    }

    try {
        const CONTENT_START = '════CONTENT_START════';
        const CONTENT_END = '════CONTENT_END════';
        const QUESTION_START = '════QUESTION_START════';
        const QUESTION_END = '════QUESTION_END════';

        let rawTextBuffer = '';
        let parsedOutline = '';
        let parsedQuestion = '';

        let inOutlineSection = false;
        let inQuestionSection = false;
        let contentFinished = false;
        let loadingHidden = false;

        function hideLoadingOnce() {
            if (!loadingHidden) {
                hideLoading();
                loadingHidden = true;
            }
        }

        function initChatTyping() {
            const chatTypingDiv = document.createElement('div');
            chatTypingDiv.className = 'chat-bubble chat-bubble-assistant';
            chatTypingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 输出中...';
            loadingDiv.innerHTML = `<div class="chat-message-avatar avatar-ai me-2">AI</div>`;
            loadingDiv.appendChild(chatTypingDiv);
            return chatTypingDiv;
        }

        function streamToChat(chatTypingDiv, text) {
            if (!chatTypingDiv) return;
            chatTypingDiv.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        let chatTypingDiv = null;

        function processStream(buffer) {
            if (buffer.includes(CONTENT_START) && !inOutlineSection && !contentFinished) {
                inOutlineSection = true;
                // 收到大纲内容开始标记，隐藏loading，切换到编辑模式实时显示
                hideLoadingOnce();
                showEditMode();
            }

            if (inOutlineSection && !contentFinished) {
                const csIdx = buffer.indexOf(CONTENT_START);
                const ceIdx = buffer.indexOf(CONTENT_END);
                const qsIdx = buffer.indexOf(QUESTION_START);

                if (csIdx !== -1) {
                    let contentEndIdx = buffer.length;

                    if (ceIdx !== -1 && ceIdx > csIdx) {
                        contentEndIdx = ceIdx;
                    } else if (qsIdx !== -1 && qsIdx > csIdx) {
                        contentEndIdx = qsIdx;
                    }

                    const contentStartIdx = csIdx + CONTENT_START.length;
                    const outlineContent = buffer.substring(contentStartIdx, contentEndIdx);

                    const outlineTextarea = document.getElementById('outline-content');
                    outlineTextarea.value = outlineContent;
                    updateButtons();

                    outlineTextarea.scrollTop = outlineTextarea.scrollHeight;

                    if (ceIdx !== -1 && ceIdx > csIdx) {
                        inOutlineSection = false;
                        contentFinished = true;
                        parsedOutline = outlineContent.trim();

                        // 大纲输出结束，使用打字机效果展示
                        const outlineTextarea = document.getElementById('outline-content');
                        outlineTextarea.value = '';
                        showEditMode();
                        typeWriter(outlineTextarea, parsedOutline, () => {
                            document.getElementById('outline-preview').innerHTML = diffHighlight(savedOutlineBaseline, parsedOutline);
                            showPreviewMode();
                            outlineTextarea.value = parsedOutline;
                            updateButtons();
                        });
                    }
                }
            }

            if (buffer.includes(QUESTION_START) && !inQuestionSection) {
                inQuestionSection = true;
                // 收到问题开始标记，隐藏loading（如果还没隐藏的话）
                hideLoadingOnce();
                if (!chatTypingDiv) {
                    chatTypingDiv = initChatTyping();
                }
            }

            if (inQuestionSection) {
                const qsIdx = buffer.indexOf(QUESTION_START);
                const qeIdx = buffer.indexOf(QUESTION_END);

                if (qsIdx !== -1) {
                    const qStartIdx = qsIdx + QUESTION_START.length;
                    let qEndIdx = buffer.length;

                    if (qeIdx !== -1 && qeIdx > qsIdx) {
                        qEndIdx = qeIdx;
                    }

                    const questionContent = buffer.substring(qStartIdx, qEndIdx);

                    streamToChat(chatTypingDiv, questionContent);

                    if (qeIdx !== -1 && qeIdx > qsIdx) {
                        inQuestionSection = false;
                        parsedQuestion = questionContent.trim();
                    }
                }
            }
        }

        await api.streamRequestRaw(`/api/projects/${projectId}/outline/chat/`, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `version_number=${currentVersionNumber || 0}&message=${encodeURIComponent(message)}&current_outline=${encodeURIComponent(document.getElementById('outline-content').value)}&messages=${encodeURIComponent(JSON.stringify(historyMessages))}`,
            onError: (error) => {
                hideLoadingOnce();
                showError('网络错误，请重试');
                if (loadingDiv.parentNode) {
                    loadingDiv.innerHTML = `
                        <div class="chat-message-avatar avatar-ai me-2">AI</div>
                        <div class="chat-bubble chat-bubble-assistant" style="color: #ef4444;">网络错误，请重试</div>
                    `;
                }
            }
        }, (chunk) => {
            if (chunk.done) return;

            const parsed = chunk.data;
            if (parsed && parsed.type === 'error') {
                hideLoadingOnce();
                showError(parsed.message || '大纲生成失败');
                if (loadingDiv.parentNode) {
                    loadingDiv.innerHTML = `
                        <div class="chat-message-avatar avatar-ai me-2">AI</div>
                        <div class="chat-bubble chat-bubble-assistant" style="color: #ef4444;">${escapeHtml(parsed.message || '生成失败')}</div>
                    `;
                }
                return;
            }

            if (chunk.content) {
                rawTextBuffer += chunk.content;

                if (!chatTypingDiv && !inOutlineSection) {
                    initChatTyping();
                }

                processStream(rawTextBuffer);
            }
        });

        // 确保loading最终被隐藏
        hideLoadingOnce();

        if (parsedQuestion) {
            messages.push({ role: 'assistant', content: parsedQuestion });
        }

        // 竞态保护：如果流式响应期间用户切换了版本，不更新大纲内容
        const versionChanged = streamVersionId !== currentVersionId;

        // 清理 loadingDiv：用最终内容替换
        if (loadingDiv.parentNode) {
            if (parsedQuestion) {
                loadingDiv.innerHTML = `
                    <div class="chat-message-avatar avatar-ai me-2">AI</div>
                    <div class="chat-bubble chat-bubble-assistant markdown-content">${safeMarkdownParse(parsedQuestion)}</div>
                `;
            } else {
                loadingDiv.remove();
            }
        }

        if (parsedOutline && !versionChanged) {
            document.getElementById('outline-content').value = parsedOutline;
            updateButtons();

            // 更新预览区内容（使用diff高亮）
            document.getElementById('outline-preview').innerHTML = diffHighlight(savedOutlineBaseline, parsedOutline);
            showPreviewMode();
            showSuccess('大纲生成完成');
        } else if (versionChanged) {
            // 版本已切换，不更新内容，避免覆盖新版本数据
        }

    } catch (error) {
        console.error('Error:', error);
        hideLoading();
        showError('网络错误，请重试');
    }

    input.disabled = false;
    document.getElementById('send-message').disabled = false;
    isSending = false;
    streamVersionId = null;
}

// 打字机效果：逐字显示大纲内容到 textarea
function typeWriter(element, text, callback) {
    stopTyping();
    isTyping = true;
    let index = 0;
    element.value = '';

    function type() {
        if (!isTyping) return;
        if (index < text.length) {
            element.value += text.charAt(index);
            index++;
            currentTypingTimeout = setTimeout(type, 15);
        } else {
            isTyping = false;
            currentTypingTimeout = null;
            if (callback) callback();
        }
    }
    type();
}

function stopTyping() {
    isTyping = false;
    if (currentTypingTimeout) {
        clearTimeout(currentTypingTimeout);
        currentTypingTimeout = null;
    }
}

function saveVersion(isNewVersion) {
    const content = document.getElementById('outline-content').value;
    if (!content.trim()) {
        showError('请先输入大纲内容');
        return;
    }

    const label = isNewVersion ? '另存新版本' : '保存当前版本';
    const msg = isNewVersion
        ? '将当前内容保存为新的版本，现有版本不受影响。'
        : '将覆盖当前版本的内容。';

    showModal(label, msg, function() {
        doSaveVersion(isNewVersion);
    });
}

async function doSaveVersion(isNewVersion) {
    const content = document.getElementById('outline-content').value;

    if (content.length > MAX_OUTLINE_LENGTH) {
        showError(`大纲内容不能超过${MAX_OUTLINE_LENGTH}字符`);
        return;
    }

    try {
        const data = await api.post(`/api/projects/${projectId}/outline/versions/save/`, `content=${encodeURIComponent(content)}${currentVersionId ? `&version_id=${currentVersionId}` : ''}` + (isNewVersion ? '&new_version=true' : ''), { contentType: 'application/x-www-form-urlencoded' });
        if (data.success) {
            closeModal();
            // 保存成功后更新基线，与数据库保持一致
            saveBaseline(content);
            showSuccess(`保存成功！版本号：v${data.version_number}`);
            loadOutlineVersions();
        } else {
            closeModal();
            showError(data.message || '保存失败');
        }
    } catch (error) {
        closeModal();
        showError('网络错误，请重试');
    }
}

function confirmLock() {
    showModal('锁定版本', '确定要锁定这个大纲版本吗？锁定后将无法修改、删除', function() {
        lockOutline();
    });
}

async function lockOutline() {
    try {
        const data = await api.post(`/api/projects/${projectId}/outline/lock/`, `version_id=${currentVersionId}`, { contentType: 'application/x-www-form-urlencoded' });
        if (data.success) {
            closeModal();
            showSuccess('版本已锁定！');
            loadOutlineVersions();
        } else {
            closeModal();
            showError(data.message || '锁定失败');
        }
    } catch (error) {
        closeModal();
        showError('网络错误，请重试');
    }
}

function confirmDeleteVersion() {
    if (!currentVersionId) {
        showError('请先选择要删除的版本');
        return;
    }
    const versionSelect = document.getElementById('version-select');
    const selectedOption = versionSelect.options[versionSelect.selectedIndex];
    const versionLabel = selectedOption ? selectedOption.textContent : '该版本';
    showModal('删除版本', `确定要删除${versionLabel}吗？锁定版本不能删除。此操作不可恢复。`, function() {
        doDeleteVersion();
    });
}

async function doDeleteVersion() {
    try {
        const data = await api.post(`/api/projects/${projectId}/outline/delete/`, `version_id=${currentVersionId}`, { contentType: 'application/x-www-form-urlencoded' });
        if (data.success) {
            closeModal();
            currentVersionId = null;
            showSuccess('版本已删除');
            loadOutlineVersions();
        } else {
            closeModal();
            showError(data.message || data.error || '删除失败');
        }
    } catch (error) {
        closeModal();
        showError('网络错误，请重试');
    }
}
