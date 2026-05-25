let projectId = null;
let events = [];
let messages = [];
let selectedEvent = null;
let isGenerating = false;
let previewTimelines = [];
let originalTimelines = [];
let selectedPreviewIndex = 0;
let isPreviewProcessing = false;
let isPreviewEditing = false;
let savedItemIds = new Set(); // 追踪已保存的项目

function showLoadingModal() {
    document.getElementById('loading-modal').classList.add('show');
}

function hideLoadingModal() {
    document.getElementById('loading-modal').classList.remove('show');
}

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    
    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');
    
    if (!projectId) {
        showToast('项目ID参数缺失', 'error');
        setTimeout(() => window.location.href = '/index.html', 2000);
        return;
    }

    loadEvents();
    loadChatHistory();

    document.getElementById('send-message').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    const chatInput = document.getElementById('chat-input');
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 160) + 'px';
    });
});

async function checkAuth() {
    if (!api.isAuthenticated()) {
        window.location.href = 'login.html';
        return;
    }
    try {
        const data = await api.get('/api/auth/user/');
        if (!data.success) {
            api.logout();
        }
    } catch (error) {
        api.logout();
    }
}

function goBack() {
    window.location.href = `project.html?project_id=${projectId}`;
}

async function loadEvents() {
    try {
        const data = await api.get(`/api/projects/${projectId}/timeline/events/`);
        if (data) {
            events = data.sort((a, b) => {
                if (a.start_chapter !== b.start_chapter) {
                    return a.start_chapter - b.start_chapter;
                }
                return a.end_chapter - b.end_chapter;
            });
            originalTimelines = [...events];
            renderEvents();
        }
    } catch (error) {
        console.error('加载时间线事件失败:', error);
    }
}

function renderEvents() {
    const container = document.getElementById('timeline-list');
    
    if (!events || events.length === 0) {
        container.innerHTML = `
            <div class="timeline-empty">
                <i class="fas fa-clock"></i>
                <p>暂无时间线事件</p>
                <p class="mt-2" style="font-size: 0.8rem;">点击上方AI生成时间线，或手动添加事件</p>
            </div>
        `;
        document.getElementById('event-count').textContent = '0 个事件';
        return;
    }

    let html = '';
    events.forEach((event, index) => {
        const isSelected = selectedEvent && selectedEvent.id === event.id;
        html += `
            <div class="timeline-item ${isSelected ? 'active' : ''}" data-id="${event.id}" onclick="selectEvent(${event.id})">
                <div class="timeline-item-header">
                    <span class="timeline-item-title">${escapeHtml(event.title)}</span>
                    <span class="timeline-item-chapters">
                        ${event.start_chapter}-${event.end_chapter}章
                    </span>
                </div>
                ${event.description ? `<div class="timeline-item-description">${escapeHtml(event.description)}</div>` : ''}
            </div>
        `;
    });
    
    container.innerHTML = html;
    document.getElementById('event-count').textContent = `${events.length} 个事件`;
}

function selectEvent(eventId) {
    selectedEvent = events.find(e => e.id === eventId);
    
    renderEvents();
    
    if (selectedEvent) {
        renderEventDetail();
        document.getElementById('detail-actions').style.display = 'flex';
    }
}

function filterEvents() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
    
    if (!searchTerm) {
        renderEvents();
        return;
    }
    
    const filteredEvents = events.filter(event => {
        const chapterRange = `${event.start_chapter}-${event.end_chapter}`;
        const title = (event.title || '').toLowerCase();
        const description = (event.description || '').toLowerCase();
        
        const chapterMatch = chapterRange.includes(searchTerm) || 
                            event.start_chapter.toString() === searchTerm ||
                            event.end_chapter.toString() === searchTerm;
        
        const textMatch = title.includes(searchTerm) || description.includes(searchTerm);
        
        return chapterMatch || textMatch;
    });
    
    const container = document.getElementById('timeline-list');
    
    if (filteredEvents.length === 0) {
        container.innerHTML = `
            <div class="timeline-empty">
                <i class="fa-solid fa-search"></i>
                <p>没有找到匹配的事件</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    filteredEvents.forEach((event) => {
        const isSelected = selectedEvent && selectedEvent.id === event.id;
        html += `
            <div class="timeline-item ${isSelected ? 'active' : ''}" data-id="${event.id}" onclick="selectEvent(${event.id})">
                <div class="timeline-item-header">
                    <span class="timeline-item-title">${escapeHtml(event.title)}</span>
                    <span class="timeline-item-chapters">
                        ${event.start_chapter}-${event.end_chapter}章
                    </span>
                </div>
                ${event.description ? `<div class="timeline-item-description">${escapeHtml(event.description)}</div>` : ''}
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function renderEventDetail() {
    if (!selectedEvent) return;
    
    const detailContainer = document.getElementById('timeline-detail');
    detailContainer.innerHTML = `
        <div class="detail-content">
            <div class="detail-header-row">
                <div class="detail-title">${escapeHtml(selectedEvent.title)}</div>
                <div class="detail-chapters">第 ${selectedEvent.start_chapter} - ${selectedEvent.end_chapter} 章</div>
            </div>
            <div class="detail-description">${selectedEvent.description ? escapeHtml(selectedEvent.description) : '<span style="color: #94a3b8;">暂无内容概述</span>'}</div>
        </div>
    `;
}

function showGenerateModal() {
    document.getElementById('estimate-chapters').value = 100;
    document.getElementById('generate-prompt').value = '';
    document.getElementById('generate-modal').classList.add('show');
}

function closeGenerateModal() {
    document.getElementById('generate-modal').classList.remove('show');
}

function openAddModal() {
    const modal = document.getElementById('add-modal');
    document.getElementById('add-id').value = '';
    document.getElementById('add-title').value = '';
    document.getElementById('add-start-chapter').value = 1;
    document.getElementById('add-end-chapter').value = 10;
    document.getElementById('add-description').value = '';
    modal.classList.add('show');
}

function closeAddModal() {
    document.getElementById('add-modal').classList.remove('show');
}

async function saveAddEvent() {
    const title = document.getElementById('add-title').value.trim();
    const startChapter = parseInt(document.getElementById('add-start-chapter').value);
    const endChapter = parseInt(document.getElementById('add-end-chapter').value);
    const description = document.getElementById('add-description').value.trim();

    if (!title) {
        showToast('请输入事件标题', 'error');
        return;
    }

    if (isNaN(startChapter) || isNaN(endChapter)) {
        showToast('章节号必须是数字', 'error');
        return;
    }

    if (startChapter > endChapter) {
        showToast('起始章节不能大于结束章节', 'error');
        return;
    }

    const data = {
        title: title,
        start_chapter: startChapter,
        end_chapter: endChapter,
        description: description,
        event_order: events.length
    };

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/events/`, data);

        if (response.success || response.id) {
            showToast('创建成功', 'success');
            closeAddModal();
            loadEvents();
            if (response.id) {
                selectEvent(response.id);
            }
        } else {
            showToast(response.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('保存事件失败:', error);
        showToast('保存失败', 'error');
    }
}

function openEditModal() {
    if (!selectedEvent) return;
    
    const modal = document.getElementById('edit-modal');
    document.getElementById('edit-id').value = selectedEvent.id;
    document.getElementById('edit-title').value = selectedEvent.title;
    document.getElementById('edit-start-chapter').value = selectedEvent.start_chapter;
    document.getElementById('edit-end-chapter').value = selectedEvent.end_chapter;
    document.getElementById('edit-description').value = selectedEvent.description || '';
    modal.classList.add('show');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('show');
}

async function saveEditEvent() {
    const id = document.getElementById('edit-id').value;
    const title = document.getElementById('edit-title').value.trim();
    const startChapter = parseInt(document.getElementById('edit-start-chapter').value);
    const endChapter = parseInt(document.getElementById('edit-end-chapter').value);
    const description = document.getElementById('edit-description').value.trim();

    if (!title) {
        showToast('请输入事件标题', 'error');
        return;
    }

    if (isNaN(startChapter) || isNaN(endChapter)) {
        showToast('章节号必须是数字', 'error');
        return;
    }

    if (startChapter > endChapter) {
        showToast('起始章节不能大于结束章节', 'error');
        return;
    }

    const data = {
        title: title,
        start_chapter: startChapter,
        end_chapter: endChapter,
        description: description,
        event_order: events.length
    };

    try {
        const response = await api.request(`/api/projects/${projectId}/timeline/events/${id}/`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });

        if (response.success || response.id) {
            showToast('更新成功', 'success');
            closeEditModal();
            loadEvents();
            if (id) {
                selectEvent(parseInt(id));
            }
        } else {
            showToast(response.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('保存事件失败:', error);
        showToast('保存失败', 'error');
    }
}

async function deleteEvent(eventId = null) {
    const id = eventId || (selectedEvent ? selectedEvent.id : null);
    if (!id || !confirm('确定要删除这个时间线事件吗？')) return;

    try {
        const response = await api.request(`/api/projects/${projectId}/timeline/events/${id}/`, {
            method: 'DELETE'
        });

        if (response.success) {
            showToast('删除成功', 'success');
            loadEvents();
            if (selectedEvent && selectedEvent.id === id) {
                selectedEvent = null;
                document.getElementById('timeline-detail').innerHTML = `
                    <div class="detail-empty">
                        <i class="fas fa-search"></i>
                        <p>请从左侧选择一个时间线事件</p>
                    </div>
                `;
                document.getElementById('detail-actions').style.display = 'none';
            }
        } else {
            showToast(response.message || '删除失败', 'error');
        }
    } catch (error) {
        console.error('删除事件失败:', error);
        showToast('删除失败', 'error');
    }
}

function openMergeModal() {
    const checkboxesContainer = document.getElementById('merge-checkboxes');
    checkboxesContainer.innerHTML = '';
    
    events.forEach(event => {
        const isSelected = selectedEvent && selectedEvent.id === event.id;
        checkboxesContainer.innerHTML += `
            <div class="merge-checkboxes-item">
                <input type="checkbox" id="merge-${event.id}" ${isSelected ? 'checked' : ''}>
                <label for="merge-${event.id}" class="title">${escapeHtml(event.title)}</label>
                <span class="chapters">${event.start_chapter}-${event.end_chapter}章</span>
            </div>
        `;
    });
    
    document.getElementById('merge-modal').classList.add('show');
}

function closeMergeModal() {
    document.getElementById('merge-modal').classList.remove('show');
}

async function mergeTimelines() {
    const selectedIds = [];
    events.forEach(event => {
        const checkbox = document.getElementById(`merge-${event.id}`);
        if (checkbox && checkbox.checked) {
            selectedIds.push(event.id);
        }
    });

    const title = document.getElementById('merge-title').value.trim();
    const description = document.getElementById('merge-description').value.trim();

    if (selectedIds.length < 2) {
        showToast('请至少选择2个时间线进行合并', 'error');
        return;
    }

    if (!title) {
        showToast('请输入合并后的标题', 'error');
        return;
    }

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/merge/`, {
            event_ids: selectedIds,
            title: title,
            description: description
        });

        if (response.success) {
            showToast('合并成功', 'success');
            closeMergeModal();
            loadEvents();
            if (response.event) {
                selectEvent(response.event.id);
            }
        } else {
            showToast(response.message || '合并失败', 'error');
        }
    } catch (error) {
        console.error('合并失败:', error);
        showToast('合并失败', 'error');
    }
}

function openSplitModal() {
    if (!selectedEvent) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    document.getElementById('current-timeline-info').innerHTML = `
        <strong>${escapeHtml(selectedEvent.title)}</strong><br>
        <span style="color: #64748b;">章节范围：第 ${selectedEvent.start_chapter} - ${selectedEvent.end_chapter} 章</span>
    `;
    document.getElementById('split-points').value = '';
    document.getElementById('split-modal').classList.add('show');
}

function closeSplitModal() {
    document.getElementById('split-modal').classList.remove('show');
}

async function splitTimeline() {
    if (!selectedEvent) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const splitPointsInput = document.getElementById('split-points').value.trim();
    if (!splitPointsInput) {
        showToast('请输入拆分点', 'error');
        return;
    }

    const splitPoints = splitPointsInput.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p));
    
    if (splitPoints.length === 0) {
        showToast('拆分点必须是数字', 'error');
        return;
    }

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/split/`, {
            event_id: selectedEvent.id,
            split_points: splitPoints
        });

        if (response.success) {
            showToast('拆分成功', 'success');
            closeSplitModal();
            loadEvents();
            selectedEvent = null;
            document.getElementById('timeline-detail').innerHTML = `
                <div class="detail-empty">
                    <i class="fas fa-search"></i>
                    <p>请从左侧选择一个时间线事件</p>
                </div>
            `;
            document.getElementById('detail-actions').style.display = 'none';
        } else {
            showToast(response.message || '拆分失败', 'error');
        }
    } catch (error) {
        console.error('拆分失败:', error);
        showToast('拆分失败', 'error');
    }
}

async function loadChatHistory() {
    try {
        const data = await api.get(`/api/projects/${projectId}/timeline/chat/`);
        if (data.success && data.messages) {
            messages = data.messages;
            renderChatHistory();
        }
    } catch (error) {
        console.error('加载聊天记录失败:', error);
    }
}

function renderChatHistory() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';

    messages.forEach(msg => {
        const div = document.createElement('div');
        div.className = `chat-message ${msg.role}`;

        if (msg.role === 'user') {
            div.innerHTML = `
                <div class="chat-bubble chat-bubble-user">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>
                <div class="chat-message-avatar avatar-me ms-2">我</div>
            `;
        } else {
            div.innerHTML = `
                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                <div class="chat-bubble chat-bubble-assistant">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>
            `;
        }
        
        chatMessages.appendChild(div);
    });
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

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

    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'chat-message assistant';
    thinkingDiv.innerHTML = `
        <div class="chat-message-avatar avatar-ai me-2">AI</div>
        <div class="chat-bubble chat-bubble-assistant">
            <span class="typing-indicator"><i class="fas fa-circle"></i><i class="fas fa-circle"></i><i class="fas fa-circle"></i></span> 思考中...
        </div>
    `;
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    messages.push({ role: 'user', content: message });
    input.value = '';
    input.style.height = 'auto';

    await api.post(`/api/projects/${projectId}/timeline/chat/`, { content: message });

    try {
        await streamGenerateTimeline(messages);
    } catch (error) {
        console.error('发送消息失败:', error);
        thinkingDiv.innerHTML = `
            <div class="chat-message-avatar avatar-ai me-2">AI</div>
            <div class="chat-bubble chat-bubble-assistant">
                <span style="color: #ef4444;">生成失败，请重试</span>
            </div>
        `;
    }

    input.disabled = false;
    document.getElementById('send-message').disabled = false;
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function generateTimelineWithEstimate() {
    const estimateChapters = parseInt(document.getElementById('estimate-chapters').value);
    const extraPrompt = document.getElementById('generate-prompt').value.trim();

    if (isNaN(estimateChapters) || estimateChapters < 10) {
        showToast('预估章节数至少为10章', 'error');
        return;
    }

    closeGenerateModal();
    isGenerating = true;
    document.getElementById('loading-modal').classList.add('show');
    previewTimelines = [];
    selectedPreviewIndex = 0;

    try {
        const requestMessages = [{ 
            role: 'user', 
            content: `根据大纲生成时间线，共${estimateChapters}章，每10章为一个时间线事件。${extraPrompt}`
        }];
        
        await streamGenerateTimeline(requestMessages);
    } catch (error) {
        console.error('生成时间线失败:', error);
        showToast('生成失败，请重试', 'error');
    }

    isGenerating = false;
}

async function streamGenerateTimeline(requestMessages) {
    document.getElementById('loading-modal').classList.add('show');
    isPreviewProcessing = true;
    previewTimelines = [];
    savedItemIds.clear(); // 重置已保存标记
    let firstItemReceived = false;

    const currentTimeline = previewTimelines.map(item => {
        return `════ITEM_START════\n${JSON.stringify({
            start_chapter: item.start_chapter,
            end_chapter: item.end_chapter,
            title: item.title,
            content: item.completeContent || item.printedContent || ''
        })}\n════ITEM_END════`;
    }).join('\n');

    try {
        const response = await fetch(`/api/projects/${projectId}/timeline/generate/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${api.getToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                messages: requestMessages,
                current_timeline: currentTimeline
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        const ITEM_START = '════ITEM_START════';
        const ITEM_END = '════ITEM_END════';
        const QUESTION_START = '════QUESTION_START════';
        const QUESTION_END = '════QUESTION_END════';

        let rawTextBuffer = '';
        let currentItemBuffer = '';
        let inItemSection = false;
        let inQuestionSection = false;
        let currentQuestionText = '';

        let processingItems = [];
        let currentPrintingIndex = -1;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'chunk') {
                            rawTextBuffer += data.data || '';

                            // 处理流内容
                            while (true) {
                                if (!inItemSection && !inQuestionSection) {
                                    const itemStartIdx = rawTextBuffer.indexOf(ITEM_START);
                                    const questionStartIdx = rawTextBuffer.indexOf(QUESTION_START);

                                    if (itemStartIdx !== -1 && (questionStartIdx === -1 || itemStartIdx < questionStartIdx)) {
                                        console.log('检测到 ITEM_START，开始解析时间线项');
                                        inItemSection = true;
                                        currentItemBuffer = '';
                                        rawTextBuffer = rawTextBuffer.substring(itemStartIdx + ITEM_START.length);
                                    } else if (questionStartIdx !== -1 && (itemStartIdx === -1 || questionStartIdx < itemStartIdx)) {
                                        console.log('检测到 QUESTION_START');
                                        inQuestionSection = true;
                                        currentQuestionText = '';
                                        rawTextBuffer = rawTextBuffer.substring(questionStartIdx + QUESTION_START.length);
                                    } else {
                                        break;
                                    }
                                } else if (inItemSection) {
                                    const itemEndIdx = rawTextBuffer.indexOf(ITEM_END);
                                    if (itemEndIdx !== -1) {
                                        currentItemBuffer += rawTextBuffer.substring(0, itemEndIdx);
                                        inItemSection = false;
                                        rawTextBuffer = rawTextBuffer.substring(itemEndIdx + ITEM_END.length);
                                        
                                        console.log('检测到 ITEM_END，内容:', currentItemBuffer);
                                        
                                        try {
                                            const jsonStr = currentItemBuffer.trim();
                                            const parsed = safeJsonParse(jsonStr);
                                            if (parsed) {
                                                processingItems.push({
                                                    ...parsed,
                                                    printedContent: '',
                                                    completeContent: parsed.content || ''
                                                });
                                                
                                                if (!firstItemReceived) {
                                                    firstItemReceived = true;
                                                    previewTimelines = [...processingItems];
                                                    console.log('第一个时间线项解析成功，打开预览弹窗');
                                                    document.getElementById('loading-modal').classList.remove('show');
                                                    document.getElementById('preview-modal').classList.add('show');
                                                    renderPreview();
                                                    currentPrintingIndex = 0;
                                                    startPrintingItems(processingItems);
                                                } else {
                                                    previewTimelines = [...processingItems];
                                                    renderPreviewList();
                                                }
                                            } else {
                                                console.log('JSON解析失败，跳过此项');
                                            }
                                        } catch (e) {
                                            console.error('解析时间线失败:', e);
                                        }
                                    } else {
                                        break;
                                    }
                                } else if (inQuestionSection) {
                                    const questionEndIdx = rawTextBuffer.indexOf(QUESTION_END);
                                    if (questionEndIdx !== -1) {
                                        currentQuestionText += rawTextBuffer.substring(0, questionEndIdx);
                                        inQuestionSection = false;
                                        rawTextBuffer = rawTextBuffer.substring(questionEndIdx + QUESTION_END.length);
                                        
                                        if (currentQuestionText.trim()) {
                                            const chatMessages = document.getElementById('chat-messages');
                                            const aiMessageDiv = document.createElement('div');
                                            aiMessageDiv.className = 'chat-message assistant';
                                            aiMessageDiv.innerHTML = `
                                                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                                                <div class="chat-bubble chat-bubble-assistant">${escapeHtml(currentQuestionText.trim()).replace(/\n/g, '<br>')}</div>
                                            `;
                                            chatMessages.appendChild(aiMessageDiv);
                                            chatMessages.scrollTop = chatMessages.scrollHeight;
                                            
                                            messages.push({ role: 'assistant', content: currentQuestionText.trim() });
                                            // 异步保存聊天记录，不阻塞流式处理
                                            saveChatMessage(currentQuestionText.trim());
                                        }
                                    } else {
                                        break;
                                    }
                                }
                            }
                        } else if (data.type === 'stream_complete') {
                            // 流式结束
                            isPreviewProcessing = false;
                        }
                    } catch (e) {
                        // JSON解析失败，忽略
                    }
                }
            }
        }

        // 处理完成
        isPreviewProcessing = false;

    } catch (error) {
        console.error('流式生成失败:', error);
        document.getElementById('loading-modal').classList.remove('show');
        throw error;
    }
}

function safeJsonParse(str) {
    try {
        const cleaned = str.replace(/^[^{]*|[^}]*$/g, '');
        if (!cleaned) {
            console.log('safeJsonParse: 清理后为空', str);
            return null;
        }
        const result = JSON.parse(cleaned);
        console.log('safeJsonParse: 解析成功', result);
        return result;
    } catch (e) {
        console.error('safeJsonParse: 解析失败', str, e);
        return null;
    }
}

function startPrintingItems(items) {
    let index = 0;

    function printNext() {
        if (index >= items.length) return;
        
        const item = items[index];
        let contentIndex = 0;
        
        function printContent() {
            if (contentIndex <= item.completeContent.length) {
                item.printedContent = item.completeContent.substring(0, contentIndex);
                previewTimelines = [...items];
                renderPreviewContent(index);
                contentIndex++;
                setTimeout(printContent, 20);
            } else {
                index++;
                if (index < items.length) {
                    selectedPreviewIndex = index;
                    renderPreviewList();
                    printNext();
                } else {
                    // 全部打印完成
                    isPreviewProcessing = false;
                    showToast('生成完成！', 'success');
                }
            }
        }
        
        printContent();
    }
    
    printNext();
}

function renderPreview() {
    renderPreviewList();
    renderPreviewContent(selectedPreviewIndex);
}

function renderPreviewList() {
    const container = document.getElementById('preview-list');
    if (!previewTimelines || previewTimelines.length === 0) {
        container.innerHTML = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">等待生成...</div>';
        return;
    }

    let html = '';
    previewTimelines.forEach((item, index) => {
        const isSaved = savedItemIds.has(index);
        html += `
            <div class="timeline-preview-item ${index === selectedPreviewIndex ? 'active' : ''}" 
                 onclick="selectPreviewItem(${index})">
                <div class="chapters">${item.start_chapter}-${item.end_chapter}章</div>
                <div class="title">${escapeHtml(item.title || '')}</div>
                ${isSaved ? '<div class="saved-badge"><i class="fas fa-check-circle"></i> 已保存</div>' : ''}
            </div>
        `;
    });
    container.innerHTML = html;
}

function selectPreviewItem(index) {
    selectedPreviewIndex = index;
    renderPreviewList();
    renderPreviewContent(index);
}

function renderPreviewContent(index) {
    const originalContainer = document.getElementById('preview-original');
    const modifiedContainer = document.getElementById('preview-modified');

    if (!previewTimelines || !previewTimelines[index]) {
        originalContainer.innerHTML = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">请选择时间线</div>';
        modifiedContainer.innerHTML = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">请选择时间线</div>';
        return;
    }

    const item = previewTimelines[index];
    const originalItem = originalTimelines.find(ot => 
        ot.start_chapter === item.start_chapter || ot.end_chapter === item.end_chapter
    );

    // 原文
    let originalHtml = '';
    if (originalItem) {
        originalHtml = `
            <div class="preview-title">${escapeHtml(originalItem.title)}</div>
            <div class="preview-chapters">第 ${originalItem.start_chapter} - ${originalItem.end_chapter} 章</div>
            <div class="preview-text">${escapeHtml(originalItem.description || '')}</div>
        `;
    } else {
        originalHtml = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">无原文</div>';
    }
    originalContainer.innerHTML = originalHtml;

    // 修改后的内容，高亮差异
    let modifiedContentHtml = escapeHtml(item.printedContent || item.completeContent || '');
    if (originalItem && originalItem.description) {
        modifiedContentHtml = highlightDifferences(originalItem.description, item.completeContent || item.printedContent || '');
    }

    if (isPreviewEditing) {
        modifiedContainer.innerHTML = `
            <div class="preview-title">${escapeHtml(item.title || '')}</div>
            <div class="preview-chapters">第 ${item.start_chapter} - ${item.end_chapter} 章</div>
            <div class="preview-edit">
                <textarea id="preview-edit-content">${escapeHtml(item.completeContent || item.printedContent || '')}</textarea>
                <button class="btn-save-single" onclick="saveSingleTimeline(${index})">保存此项</button>
            </div>
        `;
    } else {
        modifiedContainer.innerHTML = `
            <div class="preview-title">${escapeHtml(item.title || '')}</div>
            <div class="preview-chapters">第 ${item.start_chapter} - ${item.end_chapter} 章</div>
            <div class="preview-text">${modifiedContentHtml}</div>
        `;
    }
}

function togglePreviewEdit() {
    isPreviewEditing = !isPreviewEditing;
    const btn = document.getElementById('btn-edit-preview');
    
    if (isPreviewEditing) {
        btn.innerHTML = '<i class="fas fa-eye"></i> 预览';
        btn.classList.add('editing');
    } else {
        btn.innerHTML = '<i class="fas fa-pencil"></i> 编辑';
        btn.classList.remove('editing');
    }
    
    renderPreviewContent(selectedPreviewIndex);
}

function highlightDifferences(oldText, newText) {
    // 简单的差异高亮
    if (!oldText) return escapeHtml(newText);
    if (!newText) return escapeHtml(oldText);

    const oldWords = oldText.split(/\s+/);
    const newWords = newText.split(/\s+/);

    let result = '';
    let i = 0, j = 0;

    while (i < oldWords.length || j < newWords.length) {
        if (i < oldWords.length && j < newWords.length && oldWords[i] === newWords[j]) {
            result += escapeHtml(oldWords[i]) + ' ';
            i++;
            j++;
        } else {
            if (j < newWords.length) {
                result += `<span class="modified">${escapeHtml(newWords[j])}</span> `;
                j++;
            } else {
                i++;
            }
        }
    }

    return result.trim();
}

async function saveSingleTimeline(index) {
    const item = previewTimelines[index];
    const content = document.getElementById('preview-edit-content').value;
    const saveBtn = event.target;

    // 显示loading状态
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/events/`, {
            id: item.id || null, // 如果有id就携带，用于更新
            title: item.title,
            start_chapter: item.start_chapter,
            end_chapter: item.end_chapter,
            description: content,
            event_order: index
        });

        if (response.success) {
            // 更新当前项的内容和id
            item.id = response.id; // 绑定后端返回的id
            item.completeContent = content;
            item.printedContent = content;
            
            // 标记为已保存
            savedItemIds.add(index);
            
            showToast(response.message || '保存成功', 'success');
            loadEvents();
            renderPreviewList();
            renderPreviewContent(index);
        } else {
            showToast(response.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('保存失败:', error);
        showToast('保存失败', 'error');
    } finally {
        // 恢复按钮状态
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }
}

async function saveAllTimelines() {
    const saveBtn = event.target;
    const originalText = saveBtn.innerHTML;
    
    // 显示loading状态
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        let successCount = 0;
        for (let i = 0; i < previewTimelines.length; i++) {
            const item = previewTimelines[i];
            const response = await api.post(`/api/projects/${projectId}/timeline/events/`, {
                id: item.id || null, // 如果有id就携带，用于更新
                title: item.title,
                start_chapter: item.start_chapter,
                end_chapter: item.end_chapter,
                description: item.completeContent || item.printedContent || '',
                event_order: i
            });

            if (response.success) {
                // 绑定返回的id
                item.id = response.id;
                savedItemIds.add(i);
                successCount++;
            }
        }

        if (successCount === previewTimelines.length) {
            showToast('全部保存成功', 'success');
        } else {
            showToast(`保存完成：${successCount}/${previewTimelines.length}项`, 'warning');
        }
        
        closePreviewModal();
        loadEvents();
    } catch (error) {
        console.error('保存失败:', error);
        showToast('保存失败', 'error');
    } finally {
        // 恢复按钮状态
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }
}

function closePreviewModal() {
    document.getElementById('preview-modal').classList.remove('show');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function saveChatMessage(content) {
    // 异步保存聊天记录，不阻塞主流程
    api.post(`/api/projects/${projectId}/timeline/chat/`, { content: content })
        .catch(error => console.error('保存聊天记录失败:', error));
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    
    const iconClass = type === 'success' ? 'fa-check-circle' : 
                      type === 'error' ? 'fa-exclamation-circle' : 
                      type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';
    
    toast.innerHTML = `<i class="fas ${iconClass}"></i>${message}`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function aiMergeTimelines() {
    const selectedIds = [];
    events.forEach(event => {
        const checkbox = document.getElementById(`merge-${event.id}`);
        if (checkbox && checkbox.checked) {
            selectedIds.push(event.id);
        }
    });

    if (selectedIds.length < 2) {
        showToast('请至少选择2个时间线进行合并', 'error');
        return;
    }

    closeMergeModal();
    showLoadingModal();

    try {
        const response = await fetch(`/api/projects/${projectId}/timeline/ai-merge/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${api.getToken()}`
            },
            body: JSON.stringify({
                event_ids: selectedIds
            })
        });

        await streamGenerateTimeline(response);
    } catch (error) {
        hideLoadingModal();
        console.error('AI合并失败:', error);
        showToast('AI合并失败', 'error');
    }
}

async function aiSplitTimeline() {
    if (!selectedEvent) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const splitPointsInput = document.getElementById('split-points').value.trim();
    const splitPoints = splitPointsInput ? splitPointsInput.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p)) : [];

    closeSplitModal();
    showLoadingModal();

    try {
        const response = await fetch(`/api/projects/${projectId}/timeline/ai-split/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${api.getToken()}`
            },
            body: JSON.stringify({
                event_id: selectedEvent.id,
                split_points: splitPoints
            })
        });

        await streamGenerateTimeline(response);
    } catch (error) {
        hideLoadingModal();
        console.error('AI拆分失败:', error);
        showToast('AI拆分失败', 'error');
    }
}

async function optimizeDescription() {
    const title = document.getElementById('edit-title').value.trim();
    const startChapter = parseInt(document.getElementById('edit-start-chapter').value);
    const endChapter = parseInt(document.getElementById('edit-end-chapter').value);
    const content = document.getElementById('edit-description').value.trim();
    const eventId = document.getElementById('edit-id').value;

    if (!eventId) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const descriptionArea = document.getElementById('edit-description');
    const originalContent = descriptionArea.value;
    descriptionArea.disabled = true;
    descriptionArea.placeholder = 'AI优化中...';

    try {
        const response = await fetch(`/api/projects/${projectId}/timeline/optimize-description/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${api.getToken()}`
            },
            body: JSON.stringify({
                event_id: eventId,
                title: title,
                start_chapter: startChapter,
                end_chapter: endChapter,
                content: content
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let optimizeResult = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'chunk') {
                            optimizeResult += data.data || '';
                            descriptionArea.value = optimizeResult;
                        } else if (data.type === 'error') {
                            showToast(data.message || '优化失败', 'error');
                            descriptionArea.value = originalContent;
                        }
                    } catch (e) {
                        // JSON解析失败，忽略
                    }
                }
            }
        }

        if (optimizeResult) {
            showToast('优化完成', 'success');
        }
    } catch (error) {
        console.error('AI优化失败:', error);
        showToast('AI优化失败', 'error');
        descriptionArea.value = originalContent;
    } finally {
        descriptionArea.disabled = false;
        descriptionArea.placeholder = '输入这部分章节需要写的小说内容概述...';
    }
}
