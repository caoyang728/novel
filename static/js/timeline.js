let projectId = null;
let events = [];
let selectedEvent = null;
let previewTimelines = [];
let originalTimelines = [];
let selectedPreviewIndex = 0;
let isPreviewProcessing = false;
let isPreviewEditing = false;
let savedItemIds = new Set();
let deletedItemIds = [];
let printingTimerIds = [];

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();

    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');

    if (!projectId || !/^\d+$/.test(projectId)) {
        showToast('项目ID参数缺失或无效', 'error');
        setTimeout(() => window.location.href = '/index.html', 2000);
        return;
    }

    loadEvents();

    // 初始化返回项目按钮
    initBackToProjectButton('.btn-back');

    // ESC键统一关闭所有弹窗并恢复overflow
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.show').forEach(modal => {
                modal.classList.remove('show');
            });
            // 清理预览弹窗的打印定时器
            clearAllPrintingTimers();
            isPreviewEditing = false;
            // 恢复 body 滚动
            document.body.style.overflow = '';
        }
    });
});

async function loadEvents() {
    showLoading('加载中...', 0.6);
    try {
        const data = await api.get(`/api/projects/${projectId}/timeline/events/`);
        if (data) {
            events = (data.events || data).sort((a, b) => a.start_year - b.start_year || a.start_month - b.start_month || a.end_year - b.end_year || a.end_month - b.end_month);
            originalTimelines = [...events];
            updateTimeFilterOptions();
            renderEvents();
            renderWorldviewInfo(data.worldview_info);

            // 显示/隐藏状态
            if (events.length === 0) {
                document.getElementById('timeline-list').style.display = 'none';
                document.getElementById('emptyState').style.display = 'flex';
            } else {
                document.getElementById('timeline-list').style.display = 'grid';
                document.getElementById('emptyState').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('加载时间线事件失败:', error);
    } finally {
        hideLoading();
    }
}

function renderWorldviewInfo(worldviewInfo) {
    const container = document.getElementById('worldview-info');
    if (!container) return;
    if (worldviewInfo) {
        container.innerHTML = `
            <div style="font-size: 0.85rem;">
                <p class="mb-1"><strong>世界观已构建</strong> <i class="fa-solid fa-check-circle text-success"></i></p>
                ${worldviewInfo.world_name ? `<p class="mb-1 text-muted">世界名称：${escapeHtml(worldviewInfo.world_name)}</p>` : ''}
                ${worldviewInfo.genre ? `<p class="mb-1 text-muted">题材类型：${escapeHtml(worldviewInfo.genre)}</p>` : ''}
                ${worldviewInfo.overview ? `<p class="mb-0 text-muted" style="font-size: 0.8rem;">${escapeHtml(worldviewInfo.overview)}</p>` : ''}
            </div>
        `;
    } else {
        container.innerHTML = `
            <div style="font-size: 0.85rem;">
                <p class="mb-0 text-warning"><i class="fa-solid fa-exclamation-triangle"></i> 尚未构建世界观，建议先完善世界观设定</p>
            </div>
        `;
    }
}

function extractTimeYear(event) {
    const eraUnit = event.era_unit || '';
    const year = event.start_year;
    if (year === 0 || year === undefined || year === null) {
        return eraUnit ? `${eraUnit}元年` : '元年';
    } else if (year < 0) {
        return eraUnit ? `${eraUnit}前${Math.abs(year)}年` : `前${Math.abs(year)}年`;
    } else {
        return eraUnit ? `${eraUnit}${year}年` : `${year}年`;
    }
}

function updateTimeFilterOptions() {
    const select = document.getElementById('time-filter');
    if (!select) return;

    // 构建 yearLabel -> minStartYear 映射，避免 O(n²) 查找
    const yearMap = new Map();
    events.forEach((event) => {
        const yearLabel = extractTimeYear(event);
        if (!yearMap.has(yearLabel) || event.start_year < yearMap.get(yearLabel)) {
            yearMap.set(yearLabel, event.start_year);
        }
    });

    // 按 start_year 排序
    const sortedYears = [...yearMap.entries()]
        .sort((a, b) => a[1] - b[1])
        .map(entry => entry[0]);

    // 保留当前选择
    const currentValue = select.value;

    select.innerHTML = '<option value="">全部时间</option>';
    sortedYears.forEach((year) => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        select.appendChild(option);
    });

    // 恢复选择
    if (currentValue && sortedYears.includes(currentValue)) {
        select.value = currentValue;
    }
}

function renderEventList(eventList) {
    const container = document.getElementById('timeline-list');

    if (!eventList || eventList.length === 0) {
        container.style.display = 'none';
        const emptyState = document.getElementById('emptyState');
        // 有搜索/筛选条件时显示"没有找到匹配的事件"，否则显示默认文案
        const searchTerm = document.getElementById('search-input')?.value?.trim();
        const timeFilter = document.getElementById('time-filter')?.value;
        if (searchTerm || timeFilter) {
            emptyState.querySelector('h3').textContent = '没有找到匹配的事件';
        } else {
            emptyState.querySelector('h3').textContent = '暂无时间线事件';
        }
        emptyState.style.display = 'flex';
        return;
    }

    container.style.display = 'grid';
    document.getElementById('emptyState').style.display = 'none';

    // Group events by year
    const groups = {};
    const groupMinYear = {};
    eventList.forEach((event) => {
        const yearLabel = extractTimeYear(event);
        if (!groups[yearLabel]) {
            groups[yearLabel] = [];
            groupMinYear[yearLabel] = event.start_year;
        }
        groups[yearLabel].push(event);
        if (event.start_year < groupMinYear[yearLabel]) {
            groupMinYear[yearLabel] = event.start_year;
        }
    });

    // Sort groups by minimum start_year
    const sortedGroupNames = Object.keys(groups).sort((a, b) => groupMinYear[a] - groupMinYear[b]);

    const htmlParts = [];
    sortedGroupNames.forEach((groupName) => {
        const groupEvents = groups[groupName].sort((a, b) => a.start_year - b.start_year || a.start_month - b.start_month || a.end_year - b.end_year || a.end_month - b.end_month);
        htmlParts.push(`
            <div class="timeline-time-group">
                <div class="timeline-time-group-header">
                    <i class="fa-solid fa-clock"></i>
                    ${escapeHtml(groupName)}
                </div>
            </div>
        `);
        groupEvents.forEach((event) => {
            const timeLabel = formatTimeLabel(event);
            htmlParts.push(`
                <div class="event-card" data-event-id="${event.id}">
                    <div class="event-card-header">
                        <div class="event-card-icon">
                            <i class="fa-solid fa-clock-rotate-left"></i>
                        </div>
                        <div class="event-card-info">
                            <div class="event-card-title" title="${escapeHtml(event.title)}">${escapeHtml(event.title)}</div>
                            <span class="event-card-time">${escapeHtml(timeLabel)}</span>
                        </div>
                    </div>
                    ${event.description ? `<div class="event-card-description">${escapeHtml(event.description)}</div>` : ''}
                </div>
            `);
        });
    });

    container.innerHTML = htmlParts.join('');

    // 事件委托：点击事件卡片
    container.querySelectorAll('.event-card[data-event-id]').forEach(card => {
        card.addEventListener('click', function() {
            const eventId = parseInt(this.dataset.eventId);
            if (eventId) selectEvent(eventId);
        });
    });
}

function renderEvents() {
    renderEventList(events);
}

function formatTimePoint(eraUnit, year, month) {
    if (!year && !month && year !== 0) return '';
    let result = eraUnit || '';
    if (year === 0) {
        result += '元年';
    } else if (year !== undefined && year !== null) {
        if (year < 0 && eraUnit) {
            result += `前${Math.abs(year)}年`;
        } else {
            result += `${year}年`;
        }
    }
    if (month && month !== 0) result += `${month}月`;
    return result;
}

function formatTimeFromFields(event) {
    const start = formatTimePoint(event.era_unit, event.start_year, event.start_month);
    const end = formatTimePoint(event.era_unit, event.end_year, event.end_month);
    if (start && end) return `${start} - ${end}`;
    return start || end || '';
}

function formatTimeLabel(event) {
    if (event.time_range) return event.time_range;
    return formatTimeFromFields(event);
}

function selectEvent(eventId) {
    selectedEvent = events.find(e => e.id === eventId);
    if (selectedEvent) {
        openEditModal();
    }
}

function filterEvents() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
    const timeFilter = document.getElementById('time-filter').value;

    if (!searchTerm && !timeFilter) {
        renderEventList(events);
        return;
    }

    const filteredEvents = events.filter(event => {
        // Time filter: match against year label
        if (timeFilter) {
            const yearLabel = extractTimeYear(event);
            if (yearLabel !== timeFilter) return false;
        }

        // Search text filter
        if (searchTerm) {
            const timeRange = `${event.era_unit || ''}${String(event.start_year)}${String(event.start_month)}${String(event.end_year)}${String(event.end_month)}`.toLowerCase();
            const title = (event.title || '').toLowerCase();
            const description = (event.description || '').toLowerCase();

            if (!timeRange.includes(searchTerm) && !title.includes(searchTerm) && !description.includes(searchTerm)) {
                return false;
            }
        }

        return true;
    });

    renderEventList(filteredEvents);
}

function showGenerateModal() {
    document.getElementById('generate-prompt').value = '';
    document.getElementById('generate-modal').classList.add('show');
}

function closeGenerateModal() {
    document.getElementById('generate-modal').classList.remove('show');
    document.body.style.overflow = '';
}

function openAddModal() {
    const modal = document.getElementById('edit-modal');
    document.getElementById('edit-id').value = '';
    document.getElementById('edit-title').value = '';
    document.getElementById('edit-era-unit').value = '';
    document.getElementById('edit-start-year').value = '0';
    document.getElementById('edit-start-month').value = '0';
    document.getElementById('edit-end-year').value = '0';
    document.getElementById('edit-end-month').value = '0';
    document.getElementById('edit-description').value = '';

    // 新增模式：切换标题和隐藏编辑专属按钮
    document.getElementById('edit-modal-title').innerHTML = '<i class="fa-solid fa-calendar-plus me-2"></i>新增事件';
    document.getElementById('btn-delete-event').style.display = 'none';
    document.getElementById('btn-merge-event').style.display = 'none';
    document.getElementById('btn-split-event').style.display = 'none';
    document.getElementById('btn-ai-generate').style.display = '';
    document.getElementById('btn-optimize-description').style.display = 'none';

    modal.classList.add('show');
}

function openEditModal() {
    if (!selectedEvent) return;

    const modal = document.getElementById('edit-modal');
    document.getElementById('edit-id').value = selectedEvent.id;
    document.getElementById('edit-title').value = selectedEvent.title;
    document.getElementById('edit-era-unit').value = selectedEvent.era_unit || '';
    document.getElementById('edit-start-year').value = selectedEvent.start_year || 0;
    document.getElementById('edit-start-month').value = selectedEvent.start_month || 0;
    document.getElementById('edit-end-year').value = selectedEvent.end_year || 0;
    document.getElementById('edit-end-month').value = selectedEvent.end_month || 0;
    document.getElementById('edit-description').value = selectedEvent.description || '';

    // 编辑模式：切换标题和显示编辑专属按钮
    document.getElementById('edit-modal-title').innerHTML = '<i class="fa-solid fa-pencil me-2"></i>编辑事件';
    document.getElementById('btn-delete-event').style.display = '';
    document.getElementById('btn-merge-event').style.display = '';
    document.getElementById('btn-split-event').style.display = '';
    document.getElementById('btn-ai-generate').style.display = 'none';
    document.getElementById('btn-optimize-description').style.display = '';

    modal.classList.add('show');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('show');
    document.body.style.overflow = '';
}

async function saveEditEvent() {
    const id = document.getElementById('edit-id').value;
    const title = document.getElementById('edit-title').value.trim();
    const eraUnit = document.getElementById('edit-era-unit').value.trim();
    const startYear = parseInt(document.getElementById('edit-start-year').value) || 0;
    const startMonth = parseInt(document.getElementById('edit-start-month').value) || 0;
    const endYear = parseInt(document.getElementById('edit-end-year').value) || 0;
    const endMonth = parseInt(document.getElementById('edit-end-month').value) || 0;
    const description = document.getElementById('edit-description').value.trim();

    if (!title) {
        showToast('请输入事件标题', 'error');
        return;
    }

    const data = {
        title: title,
        era_unit: eraUnit,
        start_year: startYear,
        start_month: startMonth,
        end_year: endYear,
        end_month: endMonth,
        description: description,
        is_active: true
    };

    try {
        let response;
        if (id) {
            // 编辑模式
            response = await api.put(`/api/projects/${projectId}/timeline/events/${id}/`, data);
        } else {
            // 新增模式
            response = await api.post(`/api/projects/${projectId}/timeline/events/`, data);
        }

        if (response.success || response.id) {
            showToast(id ? '更新成功' : '创建成功', 'success');
            closeEditModal();
            selectedEvent = null;
            loadEvents();
        } else {
            showToast(response.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('保存事件失败:', error);
        showToast('保存失败', 'error');
    }
}

function confirmDeleteEvent() {
    const id = selectedEvent ? selectedEvent.id : null;
    if (!id) return;
    showModal('确认删除', '确定要删除这个时间线事件吗？此操作不可撤销。', () => deleteEvent(id));
}

async function deleteEvent(eventId) {
    if (!eventId) return;

    try {
        const response = await api.delete(`/api/projects/${projectId}/timeline/events/${eventId}/`);

        if (response.success) {
            showToast('删除成功', 'success');
            closeModal();
            closeEditModal();
            loadEvents();
            if (selectedEvent && selectedEvent.id === eventId) {
                selectedEvent = null;
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
        const timeLabel = formatTimeLabel(event);

        const div = document.createElement('div');
        div.className = 'merge-checkboxes-item';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = 'merge-' + event.id;
        checkbox.checked = isSelected;

        const label = document.createElement('label');
        label.htmlFor = 'merge-' + event.id;
        label.className = 'title';
        label.textContent = event.title;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'time';
        timeSpan.textContent = timeLabel;

        div.appendChild(checkbox);
        div.appendChild(label);
        div.appendChild(timeSpan);
        checkboxesContainer.appendChild(div);
    });

    document.getElementById('merge-modal').classList.add('show');
}

function closeMergeModal() {
    document.getElementById('merge-modal').classList.remove('show');
    document.body.style.overflow = '';
}

function openSplitModal() {
    if (!selectedEvent) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const timeLabel = formatTimeLabel(selectedEvent);
    document.getElementById('current-timeline-info').innerHTML = `
        <strong>${escapeHtml(selectedEvent.title)}</strong><br>
        <span style="color: #64748b;">时间范围：${escapeHtml(timeLabel)}</span>
    `;
    document.getElementById('split-era-unit').value = selectedEvent.era_unit || '';
    document.getElementById('split-points').value = '';
    document.getElementById('split-modal').classList.add('show');
}

function closeSplitModal() {
    document.getElementById('split-modal').classList.remove('show');
    document.body.style.overflow = '';
}

async function splitTimeline() {
    if (!selectedEvent) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const splitPointsInput = document.getElementById('split-points').value.trim();
    const splitEraUnit = document.getElementById('split-era-unit').value.trim();
    if (!splitPointsInput) {
        showToast('请输入拆分点', 'error');
        return;
    }

    // 解析拆分点：格式为 "年:月, 年:月" 或 "年, 年"
    const splitPoints = splitPointsInput.split(',').map(p => {
        const parts = p.trim().split(':');
        const year = parseInt(parts[0]) || 0;
        const month = parts.length > 1 ? (parseInt(parts[1]) || 0) : 0;
        return { year, month };
    }).filter(p => p.year !== 0 || p.month !== 0);

    if (splitPoints.length === 0) {
        showToast('拆分点不能为空', 'error');
        return;
    }

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/split/`, {
            event_id: selectedEvent.id,
            era_unit: splitEraUnit,
            split_points: splitPoints
        });

        if (response.success) {
            showToast('拆分成功', 'success');
            closeSplitModal();
            loadEvents();
            selectedEvent = null;
        } else {
            showToast(response.message || '拆分失败', 'error');
        }
    } catch (error) {
        console.error('拆分失败:', error);
        showToast('拆分失败', 'error');
    }
}

async function generateTimelineWithEstimate() {
    const extraPrompt = document.getElementById('generate-prompt').value.trim();

    closeGenerateModal();
    showLoading('思考中...', 0.3);
    previewTimelines = [];
    selectedPreviewIndex = 0;

    try {
        const requestMessages = [{
            role: 'user',
            content: `根据世界观生成完整时间线。${extraPrompt}`
        }];

        await streamGenerateTimeline(requestMessages, { extraPrompt: extraPrompt });
    } catch (error) {
        console.error('生成时间线失败:', error);
        showToast('生成失败，请重试', 'error');
        hideLoading();
    }
}

async function streamGenerateTimeline(requestMessages, options = {}) {
    isPreviewProcessing = true;
    previewTimelines = [];
    savedItemIds.clear();
    deletedItemIds = [];
    let firstItemReceived = false;

    // 保存当前时间线用于后续匹配ID
    const existingTimelines = [...(previewTimelines.length > 0 ? previewTimelines : events)];

    const apiUrl = `/api/projects/${projectId}/timeline/generate/`;
    const requestBody = {
        messages: requestMessages,
        extra_prompt: options.extraPrompt || ''
    };

    const ITEM_START = '════ITEM_START════';
    const ITEM_END = '════ITEM_END════';

    let rawTextBuffer = '';
    let currentItemBuffer = '';
    let inItemSection = false;

    let processingItems = [];

    try {
        await api.streamRequestRaw(apiUrl, { body: requestBody }, (chunk) => {
            if (chunk.done) return;

            const data = chunk.data;
            if (!data) return;

            if (data.type === 'chunk') {
                rawTextBuffer += data.data || '';

                while (true) {
                    if (!inItemSection) {
                        const itemStartIdx = rawTextBuffer.indexOf(ITEM_START);

                        if (itemStartIdx !== -1) {
                            inItemSection = true;
                            currentItemBuffer = '';
                            rawTextBuffer = rawTextBuffer.substring(itemStartIdx + ITEM_START.length);
                        } else {
                            break;
                        }
                    } else if (inItemSection) {
                        const itemEndIdx = rawTextBuffer.indexOf(ITEM_END);
                        if (itemEndIdx !== -1) {
                            currentItemBuffer += rawTextBuffer.substring(0, itemEndIdx);
                            inItemSection = false;
                            rawTextBuffer = rawTextBuffer.substring(itemEndIdx + ITEM_END.length);

                            try {
                                const jsonStr = currentItemBuffer.trim();
                                const parsed = safeJsonParse(jsonStr);
                                if (parsed) {
                                    const matchedItem = existingTimelines.find(item =>
                                        (item.title && parsed.title && item.title === parsed.title) ||
                                        (item.era_unit === parsed.era_unit && item.start_year === parsed.start_year && item.start_month === parsed.start_month && item.end_year === parsed.end_year && item.end_month === parsed.end_month)
                                    );
                                    const itemId = matchedItem ? matchedItem.id : null;

                                    processingItems.push({
                                        ...parsed,
                                        id: itemId,
                                        printedContent: '',
                                        completeContent: parsed.content || ''
                                    });

                                    if (!firstItemReceived) {
                                        firstItemReceived = true;
                                        originalTimelines = [...existingTimelines];
                                        showLoading('生成中...', 0.3);
                                        document.getElementById('preview-modal').classList.add('show');
                                        previewTimelines = [...processingItems];
                                        renderPreview();
                                        startPrintingItems(processingItems);
                                    } else {
                                        previewTimelines = [...processingItems];
                                        renderPreviewList();
                                    }
                                }
                            } catch (e) {
                                console.error('解析时间线失败:', e);
                            }
                        } else {
                            break;
                        }
                    }
                }
            } else if (data.type === 'stream_complete') {
                isPreviewProcessing = false;
            }
        });
    } catch (error) {
        if (error.message === 'no_worldview') {
            throw error;
        }
        console.error('流式生成失败:', error);
        hideLoading();
        throw error;
    }

    isPreviewProcessing = false;

    if (!firstItemReceived) {
        hideLoading();
    } else {
        hideLoading();
        showToast('生成完成！', 'success');
    }
}

function safeJsonParse(str) {
    if (!str) return null;
    try {
        // 第0步：剥离 ITEM 标记
        let rawStr = str.trim();
        const ITEM_START = '════ITEM_START════';
        const ITEM_END = '════ITEM_END════';
        if (rawStr.includes(ITEM_START)) {
            const startIdx = rawStr.indexOf(ITEM_START);
            const endIdx = rawStr.indexOf(ITEM_END, startIdx);
            if (endIdx !== -1) {
                rawStr = rawStr.substring(startIdx + ITEM_START.length, endIdx).trim();
            } else {
                rawStr = rawStr.substring(startIdx + ITEM_START.length).trim();
            }
        }

        // 第1步：直接解析
        try { return cleanParsed(JSON.parse(rawStr)); } catch(e) {}

        // 第2步：替换中文引号 + 修复未转义双引号 + 修复未转义换行 + 修复无效转义 + 清理控制字符
        let cleaned = rawStr;
        // 替换中文引号为单引号（避免与JSON结构引号冲突）
        cleaned = cleaned.replace(/[\u201c\u201d]/g, "'");
        cleaned = cleaned.replace(/[\u2018\u2019]/g, "'");

        // 逐字符扫描：修复字符串值内的未转义双引号、换行符、无效转义序列和控制字符
        let result = '';
        let inString = false;
        let escape = false;
        for (let i = 0; i < cleaned.length; i++) {
            const ch = cleaned[i];
            if (escape) {
                // 检查是否是合法的JSON转义字符
                if (!'"\\\/bfnrtu'.includes(ch)) {
                    // 无效转义序列：将反斜杠转义，保留原字符
                    result = result.slice(0, -1) + '\\\\' + ch;
                } else {
                    result += ch;
                }
                escape = false;
                continue;
            }
            if (ch === '\\' && inString) {
                result += ch;
                escape = true;
                continue;
            }
            if (ch === '"') {
                if (!inString) {
                    // 开始字符串
                    inString = true;
                    result += ch;
                } else {
                    // 可能是字符串结束——检查后面是否是合法JSON结构字符
                    let j = i + 1;
                    while (j < cleaned.length && cleaned[j] === ' ') j++;
                    if (j >= cleaned.length || ':,}]'.includes(cleaned[j])) {
                        // 合法的字符串结束
                        inString = false;
                        result += ch;
                    } else {
                        // 字符串值内的未转义双引号，转义它
                        result += '\\"';
                    }
                }
                continue;
            }
            if (inString && (ch === '\n' || ch === '\r')) {
                result += '\\n';
                continue;
            }
            if (inString && ch === '\t') {
                result += '\\t';
                continue;
            }
            // 清理字符串内的其他控制字符（0x00-0x1F，除已处理的换行/制表符）
            if (inString && ch.charCodeAt(0) < 0x20) {
                result += ' ';
                continue;
            }
            result += ch;
        }
        cleaned = result;

        try { return cleanParsed(JSON.parse(cleaned)); } catch(e) {}

        // 第3步：提取第一个 { 到最后一个 } 之间的内容
        const firstBrace = cleaned.indexOf('{');
        const lastBrace = cleaned.lastIndexOf('}');
        if (firstBrace !== -1 && lastBrace > firstBrace) {
            try { return cleanParsed(JSON.parse(cleaned.substring(firstBrace, lastBrace + 1))); } catch(e) {}
        }

        // 第4步：逐层剥离外层，尝试解析内部 JSON
        // 处理 LLM 在 JSON 外包裹多余字符的情况
        let inner = cleaned;
        for (let attempt = 0; attempt < 3; attempt++) {
            inner = inner.trim();
            // 去掉首尾非 JSON 字符
            if (inner[0] !== '{' && inner[0] !== '[') {
                const idx = inner.indexOf('{');
                if (idx === -1) break;
                inner = inner.substring(idx);
            }
            if (inner[inner.length - 1] !== '}' && inner[inner.length - 1] !== ']') {
                const idx = inner.lastIndexOf('}');
                if (idx === -1) break;
                inner = inner.substring(0, idx + 1);
            }
            try { return cleanParsed(JSON.parse(inner)); } catch(e) {}
            // 尝试去掉首尾各一个字符
            if (inner.length > 2) {
                inner = inner.substring(1, inner.length - 1);
            } else {
                break;
            }
        }

        console.error('safeJsonParse: 所有尝试均失败', str);
        return null;
    } catch (e) {
        console.error('safeJsonParse: 异常', str, e);
        return null;
    }
}

function cleanParsed(parsed) {
    if (!parsed) return parsed;
    // 清理 era_unit 中的"元年"/"年"后缀
    if (parsed.era_unit && typeof parsed.era_unit === 'string') {
        parsed.era_unit = parsed.era_unit.replace(/元年$|年$/, '');
    }
    return parsed;
}

function mergeIncrementalChanges(baseEvents, changes) {
    let result = [];

    for (const change of changes) {
        if (change.operation === 'add') {
            const existingMatch = baseEvents.find(t =>
                (t.title || '').trim() === (change.title || '').trim()
            );
            if (existingMatch) {
                continue;
            }
            result.push({
                ...change,
                id: null,
                printedContent: change.content || '',
                completeContent: change.content || '',
                _operation: 'add'
            });
        } else if (change.operation === 'modify') {
            const matchTitle = (change.match_title || '').trim();
            const original = baseEvents.find(t => (t.title || '').trim() === matchTitle);
            if (original) {
                const hasTimeChange = change.start_year !== undefined || change.start_month !== undefined ||
                    change.end_year !== undefined || change.end_month !== undefined || change.era_unit !== undefined;
                const mergedItem = {
                    ...original,
                    title: change.title || original.title,
                    era_unit: change.era_unit !== undefined ? change.era_unit : original.era_unit,
                    start_year: change.start_year !== undefined ? change.start_year : original.start_year,
                    start_month: change.start_month !== undefined ? change.start_month : original.start_month,
                    end_year: change.end_year !== undefined ? change.end_year : original.end_year,
                    end_month: change.end_month !== undefined ? change.end_month : original.end_month,
                    completeContent: change.content || original.description || '',
                    printedContent: change.content || original.description || '',
                    _operation: 'modify',
                    _originalTitle: matchTitle
                };
                if (hasTimeChange) {
                    delete mergedItem.time_range;
                }
                result.push(mergedItem);
            } else {
                result.push({
                    ...change,
                    id: null,
                    operation: 'add',
                    printedContent: change.content || '',
                    completeContent: change.content || '',
                    _operation: 'add'
                });
            }
        } else if (change.operation === 'delete') {
            const matchTitle = (change.match_title || '').trim();
            const original = baseEvents.find(t => (t.title || '').trim() === matchTitle);
            if (original) {
                if (original.id) {
                    deletedItemIds.push(original.id);
                }
                result.push({
                    ...original,
                    completeContent: original.description || '',
                    printedContent: original.description || '',
                    _operation: 'delete',
                    _originalTitle: matchTitle
                });
            }
        }
    }

    return result;
}

function clearAllPrintingTimers() {
    printingTimerIds.forEach(id => clearTimeout(id));
    printingTimerIds = [];
}

function startPrintingItems(items) {
    clearAllPrintingTimers();
    let index = 0;
    let currentTimerId = null;

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
                currentTimerId = setTimeout(printContent, 20);
                printingTimerIds.push(currentTimerId);
            } else {
                index++;
                if (index < items.length) {
                    selectedPreviewIndex = index;
                    renderPreviewList();
                    printNext();
                } else {
                    isPreviewProcessing = false;
                    hideLoading();
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
        const timeLabel = formatTimeLabel(item);
        let statusBadge = '';
        if (item._operation === 'add') {
            statusBadge = '<span class="preview-status-badge badge-add">新增</span>';
        } else if (item._operation === 'modify') {
            statusBadge = '<span class="preview-status-badge badge-modify">修改</span>';
        } else if (item._operation === 'delete') {
            statusBadge = '<span class="preview-status-badge badge-delete">删除</span>';
        }
        html += `
            <div class="timeline-preview-item ${index === selectedPreviewIndex ? 'active' : ''}" 
                 onclick="selectPreviewItem(${index})">
                <div class="time">${escapeHtml(timeLabel)}</div>
                <div class="title">${escapeHtml(item.title || '')}</div>
                ${statusBadge}
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

    if (item._operation === 'delete') {
        const originalItem = originalTimelines.find(ot =>
            (item.id && ot.id === item.id) ||
            ot.title === item.title ||
            (item._originalTitle && ot.title === item._originalTitle)
        );
        const origTimeLabel = originalItem ? formatTimeLabel(originalItem) : formatTimeLabel(item);
        originalContainer.innerHTML = `
            <div class="preview-title">${escapeHtml(originalItem ? originalItem.title : item.title)}</div>
            <div class="preview-time">${escapeHtml(origTimeLabel)}</div>
            <div class="preview-text">${escapeHtml(originalItem ? originalItem.description : item.completeContent)}</div>
        `;
        modifiedContainer.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: #ef4444;">
                <i class="fas fa-trash-alt" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                <p>此事件将被删除</p>
            </div>
        `;
        return;
    }

    let originalItem = null;
    if (item._operation !== 'add') {
        originalItem = originalTimelines.find(ot =>
            (item.id && ot.id === item.id) ||
            ot.title === item.title ||
            (item._originalTitle && ot.title === item._originalTitle)
        );
    }

    const timeLabel = formatTimeLabel(item);

    let originalHtml = '';
    if (originalItem) {
        const origTimeLabel = formatTimeLabel(originalItem);
        originalHtml = `
            <div class="preview-title">${escapeHtml(originalItem.title)}</div>
            <div class="preview-time">${escapeHtml(origTimeLabel)}</div>
            <div class="preview-text">${escapeHtml(originalItem.description || '')}</div>
        `;
    } else {
        originalHtml = '<div style="padding: 2rem; text-align: center; color: #94a3b8;">无原文</div>';
    }
    originalContainer.innerHTML = originalHtml;

    let modifiedTitleHtml = escapeHtml(item.title || '');
    if (originalItem && originalItem.title && originalItem.title !== item.title) {
        modifiedTitleHtml = highlightDifferences(originalItem.title, item.title || '');
    }

    let modifiedTimeHtml = escapeHtml(timeLabel);
    if (originalItem) {
        const origTimeLabel = formatTimeLabel(originalItem);
        if (origTimeLabel !== timeLabel) {
            modifiedTimeHtml = highlightTimeDifferences(origTimeLabel, timeLabel);
        }
    }

    let modifiedContentHtml = escapeHtml(item.printedContent || item.completeContent || item.description || '');
    if (originalItem && originalItem.description) {
        modifiedContentHtml = highlightDifferences(originalItem.description, item.completeContent || item.printedContent || item.description || '');
    }

    if (isPreviewEditing) {
        modifiedContainer.innerHTML = `
            <div class="preview-title">${escapeHtml(item.title || '')}</div>
            <div class="preview-edit-time">
                <div class="preview-edit-time-row">
                    <label class="preview-edit-time-label">纪元单位</label>
                    <input type="text" class="form-control preview-edit-time-input" id="preview-edit-era-unit" value="${escapeHtml(item.era_unit || '')}" placeholder="如：公元、洪武、贞观">
                </div>
                <div class="preview-edit-time-row">
                    <label class="preview-edit-time-label">开始年</label>
                    <input type="number" class="form-control preview-edit-time-input" id="preview-edit-start-year" value="${item.start_year || 0}" placeholder="0">
                </div>
                <div class="preview-edit-time-row">
                    <label class="preview-edit-time-label">开始月</label>
                    <input type="number" class="form-control preview-edit-time-input" id="preview-edit-start-month" value="${item.start_month || 0}" min="0" placeholder="0+">
                </div>
                <div class="preview-edit-time-row">
                    <label class="preview-edit-time-label">结束年</label>
                    <input type="number" class="form-control preview-edit-time-input" id="preview-edit-end-year" value="${item.end_year || 0}" placeholder="0">
                </div>
                <div class="preview-edit-time-row">
                    <label class="preview-edit-time-label">结束月</label>
                    <input type="number" class="form-control preview-edit-time-input" id="preview-edit-end-month" value="${item.end_month || 0}" min="0" placeholder="0+">
                </div>
            </div>
            <div class="preview-edit">
                <textarea id="preview-edit-content">${escapeHtml(item.completeContent || item.printedContent || '')}</textarea>
                <div class="preview-edit-actions">
                    <button class="btn-ai-optimize-single" onclick="aiOptimizeSingleItem(${index})" id="btn-ai-optimize-single">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> AI优化
                    </button>
                    <button class="btn-save-single" onclick="saveSingleTimeline(${index}, this)">保存此项</button>
                </div>
            </div>
        `;
    } else {
        modifiedContainer.innerHTML = `
            <div class="preview-title">${modifiedTitleHtml}</div>
            <div class="preview-time">${modifiedTimeHtml}</div>
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

function highlightTimeDifferences(oldText, newText) {
    if (!oldText) return escapeHtml(newText);
    if (!newText) return escapeHtml(oldText);
    if (oldText === newText) return escapeHtml(newText);

    function parseTimePoint(text) {
        const segs = { era: '', year: '', month: '' };
        if (!text) return segs;

        let eraMatch = text.match(/^([\u4e00-\u9fa5]+?)(?:(?:元|\d+)年|(?:\d+)月|$)/);
        if (eraMatch && eraMatch[1]) {
            segs.era = eraMatch[1];
        }

        let yearMatch = text.match(/(元|\d+)年/);
        if (yearMatch) {
            segs.year = yearMatch[1] + '年';
        }

        let monthMatch = text.match(/(\d+)月/);
        if (monthMatch) {
            segs.month = monthMatch[1] + '月';
        }

        return segs;
    }

    function formatSeg(oldVal, newVal) {
        if (oldVal === newVal) {
            return escapeHtml(newVal);
        } else if (newVal) {
            return '<span class="modified">' + escapeHtml(newVal) + '</span>';
        }
        return '';
    }

    const oldRanges = oldText.split(/\s*-\s*/);
    const newRanges = newText.split(/\s*-\s*/);
    const maxLen = Math.max(oldRanges.length, newRanges.length);

    let result = '';
    for (let i = 0; i < maxLen; i++) {
        if (i > 0) result += ' - ';

        const oldSegs = parseTimePoint(oldRanges[i] || '');
        const newSegs = parseTimePoint(newRanges[i] || '');

        result += formatSeg(oldSegs.era, newSegs.era);
        result += formatSeg(oldSegs.year, newSegs.year);
        result += formatSeg(oldSegs.month, newSegs.month);
    }

    return result;
}

function tokenize(text) {
    const tokens = [];
    let i = 0;
    while (i < text.length) {
        const ch = text[i];
        if (/[0-9]/.test(ch)) {
            let num = '';
            while (i < text.length && /[0-9]/.test(text[i])) {
                num += text[i];
                i++;
            }
            tokens.push(num);
        } else {
            tokens.push(ch);
            i++;
        }
    }
    return tokens;
}

function highlightDifferences(oldText, newText) {
    if (!oldText) return escapeHtml(newText);
    if (!newText) return escapeHtml(oldText);
    if (oldText === newText) return escapeHtml(newText);

    const oldTokens = tokenize(oldText);
    const newTokens = tokenize(newText);
    const m = oldTokens.length;
    const n = newTokens.length;

    // 滚动数组优化空间：仅保留前一行和当前行
    let prev = new Array(n + 1).fill(0);
    let curr = new Array(n + 1).fill(0);

    // 同时记录方向用于回溯（使用完整 dp 表仅用于方向）
    // 对于大文本，使用 Hirschberg 算法或简化策略
    // 这里保留完整 dp 表用于回溯，但限制最大 token 数
    const MAX_TOKENS = 500;
    if (m > MAX_TOKENS || n > MAX_TOKENS) {
        // 超长文本降级为逐行比较
        return escapeHtml(newText);
    }

    const dp = [];
    for (let i = 0; i <= m; i++) {
        dp[i] = [];
        for (let j = 0; j <= n; j++) {
            if (i === 0 || j === 0) {
                dp[i][j] = 0;
            } else if (oldTokens[i - 1] === newTokens[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
                dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
        }
    }

    const ops = [];
    let i = m, j = n;
    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 && oldTokens[i - 1] === newTokens[j - 1]) {
            ops.unshift({ type: 'equal', token: oldTokens[i - 1] });
            i--;
            j--;
        } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
            ops.unshift({ type: 'insert', token: newTokens[j - 1] });
            j--;
        } else {
            ops.unshift({ type: 'delete', token: oldTokens[i - 1] });
            i--;
        }
    }

    let result = '';
    let inModified = false;
    for (const op of ops) {
        if (op.type === 'equal') {
            if (inModified) {
                result += '</span>';
                inModified = false;
            }
            result += escapeHtml(op.token);
        } else if (op.type === 'insert') {
            if (!inModified) {
                result += '<span class="modified">';
                inModified = true;
            }
            result += escapeHtml(op.token);
        }
    }
    if (inModified) {
        result += '</span>';
    }

    return result;
}

async function saveSingleTimeline(index, btn) {
    const item = previewTimelines[index];
    const content = document.getElementById('preview-edit-content').value;
    const eraUnitInput = document.getElementById('preview-edit-era-unit');
    const startYearInput = document.getElementById('preview-edit-start-year');
    const startMonthInput = document.getElementById('preview-edit-start-month');
    const endYearInput = document.getElementById('preview-edit-end-year');
    const endMonthInput = document.getElementById('preview-edit-end-month');
    const eraUnit = eraUnitInput ? eraUnitInput.value.trim() : (item.era_unit || '');
    const startYear = startYearInput ? (parseInt(startYearInput.value) || 0) : (item.start_year || 0);
    const startMonth = startMonthInput ? (parseInt(startMonthInput.value) || 0) : (item.start_month || 0);
    const endYear = endYearInput ? (parseInt(endYearInput.value) || 0) : (item.end_year || 0);
    const endMonth = endMonthInput ? (parseInt(endMonthInput.value) || 0) : (item.end_month || 0);
    const saveBtn = btn;

    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        let response;
        if (item.id) {
            // 更新模式：使用 PUT 到 detail 端点，避免 IDOR
            response = await api.put(`/api/projects/${projectId}/timeline/events/${item.id}/`, {
                title: item.title,
                era_unit: eraUnit,
                start_year: startYear,
                start_month: startMonth,
                end_year: endYear,
                end_month: endMonth,
                description: content || item.description || '',
                is_active: item.is_active !== false
            });
        } else {
            // 新增模式
            response = await api.post(`/api/projects/${projectId}/timeline/events/`, {
                title: item.title,
                era_unit: eraUnit,
                start_year: startYear,
                start_month: startMonth,
                end_year: endYear,
                end_month: endMonth,
                description: content || item.description || '',
                is_active: item.is_active !== false
            });
        }

        if (response.success || response.id) {
            if (response.id) item.id = response.id;
            item.era_unit = eraUnit;
            item.start_year = startYear;
            item.start_month = startMonth;
            item.end_year = endYear;
            item.end_month = endMonth;
            item.completeContent = content;
            item.printedContent = content;

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
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }
}

async function saveAllTimelines() {
    const saveBtn = document.getElementById('btn-save-all');
    const originalText = saveBtn.innerHTML;

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        // 批量保存所有非删除事件，限制并发数为5
        const itemsToSave = previewTimelines
            .map((item, i) => ({ item, index: i }))
            .filter(({ item, index }) => item._operation !== 'delete' && !savedItemIds.has(index));

        const CONCURRENCY = 5;
        let successCount = 0;

        for (let batchStart = 0; batchStart < itemsToSave.length; batchStart += CONCURRENCY) {
            const batch = itemsToSave.slice(batchStart, batchStart + CONCURRENCY);
            const batchResults = await Promise.allSettled(batch.map(({ item, index }) => {
                const eventData = {
                    title: item.title,
                    era_unit: item.era_unit || '',
                    start_year: item.start_year || 0,
                    start_month: item.start_month || 0,
                    end_year: item.end_year || 0,
                    end_month: item.end_month || 0,
                    description: item.completeContent || item.printedContent || item.description || '',
                    is_active: item.is_active !== false
                };

                if (item.id) {
                    return api.put(`/api/projects/${projectId}/timeline/events/${item.id}/`, eventData);
                } else {
                    return api.post(`/api/projects/${projectId}/timeline/events/`, eventData);
                }
            }));

            batchResults.forEach((result, i) => {
                const { index } = batch[i];
                if (result.status === 'fulfilled') {
                    const response = result.value;
                    if (response.success || response.id) {
                        if (response.id) previewTimelines[index].id = response.id;
                        savedItemIds.add(index);
                        successCount++;
                    }
                }
            });
        }

        // 并发删除事件
        const deletePromises = deletedItemIds.map(id =>
            api.delete(`/api/projects/${projectId}/timeline/events/${id}/`).catch(e => {
                console.error('删除事件失败:', id, e);
            })
        );
        await Promise.allSettled(deletePromises);
        deletedItemIds = [];

        const saveableCount = previewTimelines.filter(i => i._operation !== 'delete').length;
        if (successCount === saveableCount) {
            showToast('全部保存成功', 'success');
        } else {
            showToast(`保存完成：${successCount}/${saveableCount}项`, 'warning');
        }

        closePreviewModal();
        loadEvents();
    } catch (error) {
        console.error('保存失败:', error);
        showToast('保存失败', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }
}

function closePreviewModal() {
    clearAllPrintingTimers();
    document.getElementById('preview-modal').classList.remove('show');
    document.body.style.overflow = '';
}

async function mergeTimelines() {
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
    showLoading('合并中...');

    try {
        const response = await api.post(`/api/projects/${projectId}/timeline/merge/`, {
            event_ids: selectedIds
        });

        hideLoading();

        if (response.success) {
            showToast('合并成功', 'success');
            loadEvents();
            selectedEvent = null;
        } else {
            showToast(response.message || '合并失败', 'error');
        }
    } catch (error) {
        hideLoading();
        console.error('合并失败:', error);
        showToast('合并失败', 'error');
    }
}

async function callOptimizeSingle(params, onResult) {
    let rawTextBuffer = '';

    await api.streamRequestRaw(`/api/projects/${projectId}/timeline/optimize-single/`, {
        body: params
    }, (chunk) => {
        if (chunk.done) return;
        const data = chunk.data;
        if (!data) return;
        if (data.type === 'chunk') {
            rawTextBuffer += data.data || '';
        } else if (data.type === 'error') {
            console.error('SSE error:', data.message);
            showToast(data.message || '优化失败', 'error');
        }
    });

    const parsed = safeJsonParse(rawTextBuffer);
    if (parsed) {
        onResult(parsed);
        showToast('AI优化完成', 'success');
    } else {
        console.error('AI返回内容无法解析为JSON:', rawTextBuffer);
        showToast('AI返回内容解析失败，未返回有效JSON', 'error');
    }
}

async function aiGenerateFields() {
    const description = document.getElementById('edit-description').value.trim();
    if (!description) {
        showToast('请先输入事件描述', 'error');
        return;
    }

    const btn = document.getElementById('btn-ai-generate');
    const titleInput = document.getElementById('edit-title');
    const eraUnitInput = document.getElementById('edit-era-unit');
    const startYearInput = document.getElementById('edit-start-year');
    const startMonthInput = document.getElementById('edit-start-month');
    const endYearInput = document.getElementById('edit-end-year');
    const endMonthInput = document.getElementById('edit-end-month');
    const descriptionArea = document.getElementById('edit-description');
    const originalBtnHtml = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    const inputs = [titleInput, eraUnitInput, startYearInput, startMonthInput, endYearInput, endMonthInput, descriptionArea];
    inputs.forEach(el => { if (el) el.disabled = true; });
    showLoading('AI生成中...', 0.3);

    // 获取相邻事件上下文（基于当前事件列表的排序位置）
    let prevItem = null;
    let nextItem = null;
    if (events.length > 0) {
        const lastEvent = events[events.length - 1];
        prevItem = {
            title: lastEvent.title || '',
            era_unit: lastEvent.era_unit || '',
            start_year: lastEvent.start_year || 0,
            start_month: lastEvent.start_month || 0,
            end_year: lastEvent.end_year || 0,
            end_month: lastEvent.end_month || 0,
            description: lastEvent.description || ''
        };
    }

    try {
        let rawTextBuffer = '';
        await api.streamRequestRaw(`/api/projects/${projectId}/timeline/generate-fields/`, {
            body: {
                description: description,
                prev_item: prevItem,
                next_item: nextItem
            }
        }, (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;
            if (data.type === 'chunk') {
                rawTextBuffer += data.data || '';
            } else if (data.type === 'error') {
                console.error('SSE error:', data.message);
                showToast(data.message || '生成失败', 'error');
            }
        });

        const parsed = safeJsonParse(rawTextBuffer);
        if (parsed) {
            if (parsed.title && titleInput) titleInput.value = parsed.title;
            if (parsed.era_unit !== undefined && eraUnitInput) eraUnitInput.value = parsed.era_unit;
            if (parsed.start_year !== undefined && startYearInput) startYearInput.value = parsed.start_year;
            if (parsed.start_month !== undefined && startMonthInput) startMonthInput.value = parsed.start_month;
            if (parsed.end_year !== undefined && endYearInput) endYearInput.value = parsed.end_year;
            if (parsed.end_month !== undefined && endMonthInput) endMonthInput.value = parsed.end_month;
            if (parsed.content && descriptionArea) descriptionArea.value = parsed.content;
            showToast('AI生成完成', 'success');
        } else {
            console.error('AI返回内容无法解析为JSON:', rawTextBuffer);
            showToast('AI返回内容解析失败，未返回有效JSON', 'error');
        }
    } catch (error) {
        console.error('AI生成失败:', error);
        showToast('AI生成失败', 'error');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
        inputs.forEach(el => { if (el) el.disabled = false; });
    }
}

async function optimizeEditEvent() {
    const title = document.getElementById('edit-title').value.trim();
    const eraUnit = document.getElementById('edit-era-unit').value.trim();
    const startYear = parseInt(document.getElementById('edit-start-year').value) || 0;
    const startMonth = parseInt(document.getElementById('edit-start-month').value) || 0;
    const endYear = parseInt(document.getElementById('edit-end-year').value) || 0;
    const endMonth = parseInt(document.getElementById('edit-end-month').value) || 0;
    const content = document.getElementById('edit-description').value.trim();
    const eventId = document.getElementById('edit-id').value;

    if (!eventId) {
        showToast('请先选择一个时间线事件', 'error');
        return;
    }

    const btn = document.getElementById('btn-optimize-description');
    const titleInput = document.getElementById('edit-title');
    const eraUnitInput = document.getElementById('edit-era-unit');
    const startYearInput = document.getElementById('edit-start-year');
    const startMonthInput = document.getElementById('edit-start-month');
    const endYearInput = document.getElementById('edit-end-year');
    const endMonthInput = document.getElementById('edit-end-month');
    const descriptionArea = document.getElementById('edit-description');
    const originalBtnHtml = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中...';
    const inputs = [titleInput, eraUnitInput, startYearInput, startMonthInput, endYearInput, endMonthInput, descriptionArea];
    inputs.forEach(el => { if (el) el.disabled = true; });
    showLoading('AI优化中...', 0.3);

    // 获取相邻事件上下文
    const eventIndex = events.findIndex(e => e.id === parseInt(eventId));
    let prevItem = null;
    let nextItem = null;
    if (eventIndex > 0) {
        const p = events[eventIndex - 1];
        prevItem = {
            title: p.title || '',
            era_unit: p.era_unit || '',
            start_year: p.start_year || 0,
            start_month: p.start_month || 0,
            end_year: p.end_year || 0,
            end_month: p.end_month || 0,
            description: p.description || ''
        };
    }
    if (eventIndex < events.length - 1) {
        const n = events[eventIndex + 1];
        nextItem = {
            title: n.title || '',
            era_unit: n.era_unit || '',
            start_year: n.start_year || 0,
            start_month: n.start_month || 0,
            end_year: n.end_year || 0,
            end_month: n.end_month || 0,
            description: n.description || ''
        };
    }

    try {
        await callOptimizeSingle({
            title: title,
            era_unit: eraUnit,
            start_year: startYear,
            start_month: startMonth,
            end_year: endYear,
            end_month: endMonth,
            content: content,
            prev_item: prevItem,
            next_item: nextItem
        }, (parsed) => {
            if (parsed.title && titleInput) titleInput.value = parsed.title;
            if (parsed.era_unit !== undefined && eraUnitInput) eraUnitInput.value = parsed.era_unit;
            if (parsed.start_year !== undefined && startYearInput) startYearInput.value = parsed.start_year;
            if (parsed.start_month !== undefined && startMonthInput) startMonthInput.value = parsed.start_month;
            if (parsed.end_year !== undefined && endYearInput) endYearInput.value = parsed.end_year;
            if (parsed.end_month !== undefined && endMonthInput) endMonthInput.value = parsed.end_month;
            if (parsed.content && descriptionArea) descriptionArea.value = parsed.content;
        });
    } catch (error) {
        console.error('AI优化失败:', error);
        showToast('AI优化失败', 'error');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
        inputs.forEach(el => { if (el) el.disabled = false; });
    }
}

async function aiOptimizeSingleItem(index) {
    const item = previewTimelines[index];
    if (!item) {
        showToast('未选择时间线事件', 'error');
        return;
    }

    const btn = document.getElementById('btn-ai-optimize-single');
    const textarea = document.getElementById('preview-edit-content');
    const eraUnitInput = document.getElementById('preview-edit-era-unit');
    const startYearInput = document.getElementById('preview-edit-start-year');
    const startMonthInput = document.getElementById('preview-edit-start-month');
    const endYearInput = document.getElementById('preview-edit-end-year');
    const endMonthInput = document.getElementById('preview-edit-end-month');

    if (!btn || !textarea) return;

    const originalBtnHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中...';
    textarea.disabled = true;
    if (eraUnitInput) eraUnitInput.disabled = true;
    if (startYearInput) startYearInput.disabled = true;
    if (startMonthInput) startMonthInput.disabled = true;
    if (endYearInput) endYearInput.disabled = true;
    if (endMonthInput) endMonthInput.disabled = true;
    showLoading('AI优化中...');

    const currentTitle = item.title || '';
    const currentEraUnit = eraUnitInput ? eraUnitInput.value.trim() : (item.era_unit || '');
    const currentStartYear = startYearInput ? (parseInt(startYearInput.value) || 0) : (item.start_year || 0);
    const currentStartMonth = startMonthInput ? (parseInt(startMonthInput.value) || 0) : (item.start_month || 0);
    const currentEndYear = endYearInput ? (parseInt(endYearInput.value) || 0) : (item.end_year || 0);
    const currentEndMonth = endMonthInput ? (parseInt(endMonthInput.value) || 0) : (item.end_month || 0);
    const currentContent = textarea.value.trim();

    let prevItem = null;
    let nextItem = null;
    if (index > 0 && previewTimelines[index - 1]) {
        const p = previewTimelines[index - 1];
        prevItem = {
            title: p.title || '',
            era_unit: p.era_unit || '',
            start_year: p.start_year || 0,
            start_month: p.start_month || 0,
            end_year: p.end_year || 0,
            end_month: p.end_month || 0,
            description: p.completeContent || p.printedContent || p.description || ''
        };
    }
    if (index < previewTimelines.length - 1 && previewTimelines[index + 1]) {
        const n = previewTimelines[index + 1];
        nextItem = {
            title: n.title || '',
            era_unit: n.era_unit || '',
            start_year: n.start_year || 0,
            start_month: n.start_month || 0,
            end_year: n.end_year || 0,
            end_month: n.end_month || 0,
            description: n.completeContent || n.printedContent || n.description || ''
        };
    }

    try {
        await callOptimizeSingle({
            title: currentTitle,
            era_unit: currentEraUnit,
            start_year: currentStartYear,
            start_month: currentStartMonth,
            end_year: currentEndYear,
            end_month: currentEndMonth,
            content: currentContent,
            prev_item: prevItem,
            next_item: nextItem
        }, (parsed) => {
            if (parsed.title) item.title = parsed.title;
            if (parsed.era_unit !== undefined) item.era_unit = parsed.era_unit;
            if (parsed.start_year !== undefined) item.start_year = parseInt(parsed.start_year) || 0;
            if (parsed.start_month !== undefined) item.start_month = parseInt(parsed.start_month) || 0;
            if (parsed.end_year !== undefined) item.end_year = parseInt(parsed.end_year) || 0;
            if (parsed.end_month !== undefined) item.end_month = parseInt(parsed.end_month) || 0;
            if (parsed.content) {
                item.completeContent = parsed.content;
                item.printedContent = parsed.content;
            }

            try {
                if (eraUnitInput && parsed.era_unit !== undefined) eraUnitInput.value = parsed.era_unit;
                if (startYearInput && parsed.start_year !== undefined) startYearInput.value = parsed.start_year;
                if (startMonthInput && parsed.start_month !== undefined) startMonthInput.value = parsed.start_month;
                if (endYearInput && parsed.end_year !== undefined) endYearInput.value = parsed.end_year;
                if (endMonthInput && parsed.end_month !== undefined) endMonthInput.value = parsed.end_month;
                if (parsed.content) textarea.value = parsed.content;

                const titleEl = document.querySelector('#preview-modified .preview-title');
                if (titleEl && parsed.title) titleEl.textContent = parsed.title;

                renderPreviewList();
            } catch (renderErr) {
                console.error('渲染优化结果失败:', renderErr);
            }
        });
    } catch (error) {
        console.error('AI优化失败:', error);
        showToast('AI优化失败', 'error');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
        textarea.disabled = false;
        if (eraUnitInput) eraUnitInput.disabled = false;
        if (startYearInput) startYearInput.disabled = false;
        if (startMonthInput) startMonthInput.disabled = false;
        if (endYearInput) endYearInput.disabled = false;
        if (endMonthInput) endMonthInput.disabled = false;
    }
}

async function checkTimeline() {
    const btn = document.getElementById('btn-check-timeline');
    if (!btn) {
        console.error('btn-check-timeline not found');
        return;
    }

    const originalBtnHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检查中...';
    showLoading('AI检查中...', 0.3);

    try {
        let rawTextBuffer = '';

        await api.streamRequestRaw(`/api/projects/${projectId}/timeline/check/`, {
            method: 'POST',
            body: {}
        }, (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;
            if (data.type === 'chunk') {
                rawTextBuffer += data.data || '';
            } else if (data.type === 'error') {
                hideLoading();
                showToast(data.message || '检查失败', 'error');
                return;
            }
        });

        hideLoading();

        const ITEM_START = '════ITEM_START════';
        const ITEM_END = '════ITEM_END════';
        const issues = [];

        let searchIdx = 0;
        while (true) {
            const startIdx = rawTextBuffer.indexOf(ITEM_START, searchIdx);
            if (startIdx === -1) break;
            const endIdx = rawTextBuffer.indexOf(ITEM_END, startIdx);
            if (endIdx === -1) break;

            const jsonStr = rawTextBuffer.substring(startIdx + ITEM_START.length, endIdx).trim();
            const parsed = safeJsonParse(jsonStr);
            if (parsed) {
                issues.push(parsed);
            }
            searchIdx = endIdx + ITEM_END.length;
        }

        renderCheckResult(issues);
    } catch (error) {
        console.error('AI检查失败:', error);
        hideLoading();
        showToast('AI检查失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
    }
}

let checkResultIssues = [];  // 存储检查结果

function renderCheckResult(issues) {
    const container = document.getElementById('check-issues-container');
    const emptyDiv = document.getElementById('check-empty');
    const optimizeBtn = document.getElementById('btn-check-optimize');
    const modal = document.getElementById('check-modal');

    container.innerHTML = '';

    if (!issues || issues.length === 0) {
        checkResultIssues = [];
        emptyDiv.style.display = 'block';
        optimizeBtn.style.display = 'none';
        modal.classList.add('show');
        return;
    }

    const passItem = issues.find(i => i.type === 'pass');
    if (passItem) {
        checkResultIssues = [];
        emptyDiv.innerHTML = `<i class="fa-solid fa-circle-check"></i><p>${escapeHtml(passItem.description || '时间线整体合理，未发现问题。')}</p>`;
        emptyDiv.style.display = 'block';
        optimizeBtn.style.display = 'none';
        modal.classList.add('show');
        return;
    }

    emptyDiv.style.display = 'none';
    optimizeBtn.style.display = 'inline-block';

    const typeMap = {
        duplicate: { label: '重复事件', cls: 'check-type-duplicate-badge' },
        conflict: { label: '时间冲突', cls: 'check-type-conflict-badge' },
        contradiction: { label: '逻辑矛盾', cls: 'check-type-contradiction-badge' },
        unreasonable: { label: '时间不合理', cls: 'check-type-unreasonable-badge' }
    };

    const seenPairs = new Set();
    const dedupedIssues = [];
    issues.forEach(issue => {
        const evts = issue.events || [];
        const ids = evts.map(e => typeof e === 'object' ? e.id : e).sort().join('|||');
        if (seenPairs.has(ids)) return;
        seenPairs.add(ids);
        dedupedIssues.push(issue);
    });

    // 存储去重后的 issues
    checkResultIssues = dedupedIssues;

    const htmlParts = [];
    dedupedIssues.forEach((issue, idx) => {
        const typeInfo = typeMap[issue.type] || { label: issue.type, cls: '' };
        const evts = issue.events || [];

        // 兼容两种格式：{id, title} 对象 或 纯标题字符串
        const event1Info = evts.length > 0 ? evts[0] : null;
        const event2Info = evts.length > 1 ? evts[1] : null;

        const event1Id = event1Info && typeof event1Info === 'object' ? event1Info.id : null;
        const event2Id = event2Info && typeof event2Info === 'object' ? event2Info.id : null;

        const event1Data = event1Id ? events.find(e => e.id == event1Id) : null;
        const event2Data = event2Id ? events.find(e => e.id == event2Id) : null;

        const event1Title = event1Data ? event1Data.title : (typeof event1Info === 'string' ? event1Info : (event1Info ? event1Info.title : ''));
        const event2Title = event2Data ? event2Data.title : (typeof event2Info === 'string' ? event2Info : (event2Info ? event2Info.title : ''));

        const event1Time = event1Data ? formatTimeLabel(event1Data) : '';
        const event2Time = event2Data ? formatTimeLabel(event2Data) : '';
        const event1Desc = event1Data ? event1Data.description || '' : '';
        const event2Desc = event2Data ? event2Data.description || '' : '';

        htmlParts.push(`
            <div class="check-issue" data-issue-idx="${idx}">
                <div class="check-issue-type-row">
                    <span class="check-issue-type-badge ${typeInfo.cls}">${typeInfo.label}</span>
                </div>
                <div class="check-issue-content-row">
                    <div class="check-issue-content-cell">
                        <div class="check-issue-content-title">${escapeHtml(event1Title || 'N/A')}</div>
                        ${event1Time ? `<div class="check-issue-content-time">${escapeHtml(event1Time)}</div>` : ''}
                        <div class="check-issue-content-desc">${escapeHtml(event1Desc) || '---'}</div>
                    </div>
                    ${event2Title ? `
                    <div class="check-issue-content-cell">
                        <div class="check-issue-content-title">${escapeHtml(event2Title)}</div>
                        ${event2Time ? `<div class="check-issue-content-time">${escapeHtml(event2Time)}</div>` : ''}
                        <div class="check-issue-content-desc">${escapeHtml(event2Desc) || '---'}</div>
                    </div>` : ''}
                </div>
                <div class="check-issue-reason-row">
                    <div class="check-issue-reason-cell">原因：${escapeHtml(issue.description || typeInfo.label)}</div>
                </div>
                <div class="check-issue-input-row">
                    <div class="check-issue-input-cell">
                        <textarea placeholder="输入解决方案（留空则AI自行判断）..."></textarea>
                    </div>
                </div>
            </div>
        `);
    });

    container.innerHTML = htmlParts.join('');

    modal.classList.add('show');
}

function closeCheckModal() {
    document.getElementById('check-modal').classList.remove('show');
    document.body.style.overflow = '';
}

async function optimizeCheckIssues() {
    const btn = document.getElementById('btn-check-optimize');
    const originalBtnHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> AI优化中...';
    showLoading('AI优化中...', 0.3);

    try {
        // 1. 从全局 checkResultIssues 和 DOM textarea 收集数据
        const issueCards = document.querySelectorAll('.check-issue');
        const solutions = [];
        issueCards.forEach((card, idx) => {
            const textarea = card.querySelector('.check-issue-input-cell textarea');
            solutions.push(textarea ? textarea.value.trim() : '');
        });

        // 2. 按 ID 分组事件，合并同一事件的原因
        const eventMap = new Map(); // key: eventId or title, value: { id, title, reasons: [], eventData }
        const typeLabels = {
            duplicate: '重复事件', conflict: '时间冲突',
            contradiction: '逻辑矛盾', unreasonable: '时间范围不合理', order: '时间顺序错误'
        };

        checkResultIssues.forEach((issue, idx) => {
            const evts = issue.events || [];
            const reason = `[${typeLabels[issue.type] || issue.type}] ${issue.description || ''}`;

            evts.forEach(evtInfo => {
                const isObj = evtInfo && typeof evtInfo === 'object';
                const evtId = isObj ? evtInfo.id : null;
                const evtTitle = isObj ? evtInfo.title : evtInfo;
                const key = evtId ? `id:${evtId}` : `title:${evtTitle}`;
                const eventData = evtId ? events.find(e => e.id == evtId) : (evtTitle ? events.find(e => e.title === evtTitle) : null);

                if (!eventMap.has(key)) {
                    eventMap.set(key, {
                        id: evtId || (eventData ? eventData.id : null),
                        title: eventData ? eventData.title : (evtTitle || ''),
                        reasons: [],
                        eventData: eventData
                    });
                }
                const entry = eventMap.get(key);
                if (!entry.reasons.includes(reason)) {
                    entry.reasons.push(reason);
                }
            });
        });

        // 3. 构建事件列表
        const eventList = Array.from(eventMap.values()).filter(e => e.title);
        if (eventList.length === 0) {
            showToast('未找到有效的事件信息', 'error');
            return;
        }

        // 4. 合并用户解决方案
        const userSolution = solutions.filter(s => s).join('\n');

        // 5. 发送请求
        const rawText = await api.streamRequest(
            `/api/projects/${projectId}/timeline/check/optimize/`,
            {
                method: 'POST',
                body: {
                    events: eventList.map(e => ({
                        id: e.id || '',
                        title: e.title,
                        reasons: e.reasons
                    })),
                    user_solution: userSolution
                }
            }
        );

        // 6. 解析返回结果
        const ITEM_START = '════ITEM_START════';
        const ITEM_END = '════ITEM_END════';
        const allChanges = [];
        let searchIdx = 0;

        while (true) {
            const startIdx = rawText.indexOf(ITEM_START, searchIdx);
            if (startIdx === -1) break;
            const endIdx = rawText.indexOf(ITEM_END, startIdx);
            if (endIdx === -1) break;

            const jsonStr = rawText.substring(startIdx + ITEM_START.length, endIdx).trim();
            const parsed = safeJsonParse(jsonStr);
            if (parsed) {
                // 查找对应的事件数据作为 fallback
                const findEventData = (title) => {
                    return eventList.find(e => e.title === title)?.eventData || null;
                };

                if (parsed.merge_with) {
                    const srcEvent = findEventData(parsed.match_title) || eventList[0]?.eventData;
                    allChanges.push({
                        operation: 'modify',
                        match_title: parsed.match_title,
                        title: parsed.title !== undefined ? parsed.title : srcEvent?.title,
                        era_unit: parsed.era_unit !== undefined ? parsed.era_unit : srcEvent?.era_unit,
                        start_year: parsed.start_year !== undefined ? parseInt(parsed.start_year) || 0 : (srcEvent?.start_year || 0),
                        start_month: parsed.start_month !== undefined ? parseInt(parsed.start_month) || 0 : (srcEvent?.start_month || 0),
                        end_year: parsed.end_year !== undefined ? parseInt(parsed.end_year) || 0 : (srcEvent?.end_year || 0),
                        end_month: parsed.end_month !== undefined ? parseInt(parsed.end_month) || 0 : (srcEvent?.end_month || 0),
                        content: parsed.description !== undefined ? parsed.description : srcEvent?.description
                    });
                    allChanges.push({
                        operation: 'delete',
                        match_title: parsed.merge_with
                    });
                } else if (parsed.match_title) {
                    const targetEvent = findEventData(parsed.match_title);
                    allChanges.push({
                        operation: 'modify',
                        match_title: parsed.match_title,
                        title: parsed.title !== undefined ? parsed.title : targetEvent?.title,
                        era_unit: parsed.era_unit !== undefined ? parsed.era_unit : targetEvent?.era_unit,
                        start_year: parsed.start_year !== undefined ? parseInt(parsed.start_year) || 0 : (targetEvent?.start_year || 0),
                        start_month: parsed.start_month !== undefined ? parseInt(parsed.start_month) || 0 : (targetEvent?.start_month || 0),
                        end_year: parsed.end_year !== undefined ? parseInt(parsed.end_year) || 0 : (targetEvent?.end_year || 0),
                        end_month: parsed.end_month !== undefined ? parseInt(parsed.end_month) || 0 : (targetEvent?.end_month || 0),
                        content: parsed.description !== undefined ? parsed.description : targetEvent?.description
                    });
                }
            }

            searchIdx = endIdx + ITEM_END.length;
        }

        if (allChanges.length === 0) {
            showToast('未生成任何调整方案，请输入解决方案', 'error');
            return;
        }

        originalTimelines = [...events];
        deletedItemIds = [];
        savedItemIds = new Set();
        selectedPreviewIndex = 0;

        previewTimelines = mergeIncrementalChanges(events, allChanges);

        const addCount = allChanges.filter(i => i.operation === 'add').length;
        const modifyCount = allChanges.filter(i => i.operation === 'modify').length;
        const deleteCount = allChanges.filter(i => i.operation === 'delete').length;
        const parts = [];
        if (modifyCount) parts.push(`修改${modifyCount}个`);
        if (addCount) parts.push(`新增${addCount}个`);
        if (deleteCount) parts.push(`删除${deleteCount}个`);

        closeCheckModal();
        document.getElementById('preview-modal').classList.add('show');
        renderPreview();

        if (parts.length > 0) {
            showToast(`已生成方案：${parts.join('，')}事件`, 'success');
        }
    } catch (error) {
        console.error('AI优化失败:', error);
        showToast('AI优化失败', 'error');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
    }
}

