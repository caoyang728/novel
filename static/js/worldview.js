let worldviewId = null;
let axioms = [''];
let currentWorldview = null;
let currentStructure = null;

function getSelectedGenre() {
    return document.getElementById('genreSelect')?.value || '';
}

function setSelectedGenre(value) {
    const genreInput = document.getElementById('genreSelect');
    const genreLabel = document.getElementById('genreDropdownLabel');
    if (genreInput) {
        genreInput.value = value || '';
    }
    if (genreLabel) {
        genreLabel.textContent = value || '请选择小说类型';
    }
    document.querySelectorAll('.genre-dropdown .dropdown-item').forEach(item => {
        item.classList.toggle('active', item.dataset.value === value);
    });
    updateExpandBtn();
}

const genreData = [
    {
        group: '现代都市',
        items: ['现代都市', '都市生活', '都市职场', '都市校园', '都市竞技', '都市言情', '都市异能', '末世都市']
    },
    {
        group: '奇幻',
        items: ['玄幻', '科幻', '仙侠', '武侠', '东方玄幻', '东方科幻', '东方仙侠', '东方武侠', '西方魔幻', '西方科幻', '近未来科幻', '星际冒险', '末世科幻']
    },
    {
        group: '历史',
        items: ['历史架空', '历史穿越', '朝堂权谋', '王朝争霸']
    },
    {
        group: '悬疑惊悚',
        items: ['悬疑', '惊悚', '恐怖', '末世', '刑侦推理', '无限副本']
    }
];

function initGenreDropdown() {
    const dropdownMenu = document.getElementById('genreDropdownMenu');
    if (!dropdownMenu) return;

    let html = '<li><button class="dropdown-item" type="button" data-value="">请选择小说类型</button></li>';
    
    genreData.forEach(group => {
        html += `<li class="dropdown-group-label">${group.group}</li>`;
        group.items.forEach(item => {
            html += `<li><button class="dropdown-item" type="button" data-value="${item}">${item}</button></li>`;
        });
    });

    dropdownMenu.innerHTML = html;

    dropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', function() {
            setSelectedGenre(this.dataset.value || '');
        });
    });
}

function updateExpandBtn() {
    const name = document.getElementById('worldName').value.trim();
    const genre = getSelectedGenre();
    const identity = document.getElementById('worldIdentity').value.trim();
    const tone = document.getElementById('worldTone').value.trim();
    const overview = document.getElementById('worldOverview').value.trim();
    const conflict = document.getElementById('worldCoreConflict').value.trim();
}


function showLoading(message = '处理中...') {
    document.getElementById('loadingText').textContent = message;
    document.getElementById('loadingOverlay').classList.add('active');
    
    // 禁用 header-actions 中的按钮
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        const buttons = headerActions.querySelectorAll('button');
        buttons.forEach(btn => btn.disabled = true);
    }
    
    // 禁用 chatBuildBtn (链接)
    const chatBuildBtn = document.getElementById('chatBuildBtn');
    if (chatBuildBtn) {
        chatBuildBtn.style.pointerEvents = 'none';
        chatBuildBtn.style.opacity = '0.5';
    }
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
    
    // 启用 header-actions 中的按钮
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        const buttons = headerActions.querySelectorAll('button');
        buttons.forEach(btn => btn.disabled = false);
    }
    
    // 启用 chatBuildBtn (链接)
    const chatBuildBtn = document.getElementById('chatBuildBtn');
    if (chatBuildBtn) {
        chatBuildBtn.style.pointerEvents = '';
        chatBuildBtn.style.opacity = '';
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastSlideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

document.addEventListener('DOMContentLoaded', async function() {
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id');
    const projectName = urlParams.get('project_name');

    if (projectName) {
        const projectNameDisplay = document.getElementById('projectNameDisplay');
        if (projectNameDisplay) {
            projectNameDisplay.textContent = `> ${projectName}`;
        }
    }

    initGenreDropdown();
    initAutoResizeTextareas();
    initDeepeningState();

    if (projectId) {
        try {
            const data = await api.get(`/api/worldview/?project_id=${projectId}`);
            if (data.success && data.data) {
                worldviewId = data.data.worldview_id;
                currentWorldview = data.data;
                updateWorldviewUI(data.data);
            } else {
                showToast(data.message || '获取世界观失败', 'error');
            }
        } catch (error) {
            console.error('Failed to load world by project:', error);
            showToast('获取世界观失败', 'error');
        }
    } else if (worldviewId) {
        await loadWorldData(worldviewId);
    } else {
        showToast('无法加载世界观数据', 'error');
    }
});

function updateWorldviewUI(worldviewData) {
    // 解析 setting
    const setting = typeof worldviewData.setting === 'string' ? JSON.parse(worldviewData.setting || '{}') : (worldviewData.setting || {});
    const identity = setting.identity || {};
    const position = setting.position || {};
    
    // 更新页面标题显示的世界名称
    const worldNameDisplay = document.getElementById('worldNameDisplay');
    if (worldNameDisplay) {
        worldNameDisplay.textContent = identity.world_name || '世界观';
    }
    
    // 更新版本号
    const worldVersionDisplay = document.getElementById('worldVersionDisplay');
    if (worldVersionDisplay) {
        worldVersionDisplay.textContent = `v${worldviewData.version || 1}`;
    }
    
    // 填充基础设定表单
    if (document.getElementById('worldName')) {
        document.getElementById('worldName').value = identity.world_name || '';
    }
    if (document.getElementById('genreSelect')) {
        document.getElementById('genreSelect').value = identity.genre || '';
        const genreLabel = document.getElementById('genreDropdownLabel');
        if (genreLabel) {
            genreLabel.textContent = identity.genre || '请选择小说类型';
        }
    }
    if (document.getElementById('worldIdentity')) {
        document.getElementById('worldIdentity').value = position.identity || '';
    }
    if (document.getElementById('worldTone')) {
        document.getElementById('worldTone').value = position.tone || '';
    }
    if (document.getElementById('worldOverview')) {
        document.getElementById('worldOverview').value = setting.overview || '';
    }
    if (document.getElementById('worldCoreConflict')) {
        document.getElementById('worldCoreConflict').value = setting.conflict || '';
    }
    
    // 更新结构数据
    currentStructure = {
        foundation: worldviewData.foundation || {},
        power: worldviewData.power || {},
        races: worldviewData.races || {},
        society: worldviewData.society || {},
        culture: worldviewData.culture || {},
        history: worldviewData.history || {},
        special: worldviewData.special || {},
        profile: { identity: position.identity || '', tone: position.tone || '', overview: setting.overview || '', coreConflict: setting.conflict || '' },
        rules: { summary: '', axioms: [] },
        factions: [],
        locations: [],
        axioms: []
    };
    
    // 重新渲染所有层
    renderSetting(currentStructure)
    renderFoundation(currentStructure);
    renderPower(currentStructure);
    renderRaces(currentStructure);
    renderSociety(currentStructure);
    renderCulture(currentStructure);
    renderHistory(currentStructure);
    renderSpecial(currentStructure);
    
    setTimeout(() => initAutoResizeTextareas(), 100);
}

async function loadWorldData(wvId) {
    try {
        const data = await api.get(`/api/worldview/?worldview_id=${wvId}`);
        currentWorldview = data.data || data;
        
        // 更新UI
        updateWorldviewUI(currentWorldview);
        
        // 更新导航中的世界观ID（全局变量）
        worldviewId = currentWorldview.id || currentWorldview.worldview_id;
        
        console.log('世界观数据已重新加载:', currentWorldview);
        
    } catch (error) {
        console.error('Failed to load world data:', error);
        showToast('加载世界观数据失败', 'error');
    }
}


function renderAxioms() {
    const container = document.getElementById('axiomsList');
    if (!container) return;
    container.innerHTML = axioms.map((axiom, index) => `
        <input type="text" class="form-control mb-2" placeholder="核心规则 ${index + 1}" value="${escapeHtml(axiom)}" onchange="updateAxiom(${index}, this.value)" oninput="updateFoundationBtn()">
    `).join('');
}

function updateAxiom(index, value) {
    // 同步当前 DOM 中的所有值到 axioms 数组
    const inputs = document.querySelectorAll('#axiomsList input');
    axioms.length = 0;
    inputs.forEach(input => axioms.push(input.value));
    // 然后设置新值
    axioms[index] = value;
}

function addAxiom() {
    // 先同步当前 DOM 中的值到 axioms 数组
    const inputs = document.querySelectorAll('#axiomsList input');
    axioms.length = 0;
    inputs.forEach(input => axioms.push(input.value));
    
    axioms.push('');
    renderAxioms();
    const newInputs = document.querySelectorAll('#axiomsList input');
    if (newInputs.length > 0) {
        newInputs[newInputs.length - 1].focus();
    }
    updateFoundationBtn();
}


function showTab(tabName) {
    document.querySelectorAll('.sidebar-tab').forEach(btn => btn.classList.remove('active'));
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
        content.classList.remove('active');
    });
    
    const activeBtn = document.querySelector(`.sidebar-tab[onclick="showTab('${tabName}')"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
    
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) {
        targetTab.classList.remove('hidden');
        if (tabName === 'deepening' || tabName === 'consistency') {
            targetTab.classList.add('active');
        }
    }
}



function setField(id, value) {
    // 设置字段
    const el = document.getElementById(id);
    if (el && value != null && value !== '') {
        if (typeof value === 'string') {
            el.value = value;
        } else if (Array.isArray(value)) {
            el.value = value.join('\n');
        } else if (typeof value === 'object') {
            el.value = JSON.stringify(value, null, 2);
        } else {
            el.value = String(value);
        }
    }
}



function showElement(el) {
    if (el) el.classList.remove('dc-hidden');
}

function hideElement(el) {
    if (el) el.classList.add('dc-hidden');
}

function initDeepeningState() {
    // 初始化问答深化按钮状态 - 只显示主要按钮
    const deepeningPrimaryButtons = document.getElementById('deepeningPrimaryButtons');
    const deepeningAnswerButtons = document.getElementById('deepeningAnswerButtons');
    const deepeningActionButtons = document.getElementById('deepeningActionButtons');
    
    showElement(deepeningPrimaryButtons);
    hideElement(deepeningAnswerButtons);
    hideElement(deepeningActionButtons);
    
    // 初始化一致性检查按钮状态 - 只显示主要按钮
    const consistencyPrimaryButtons = document.getElementById('consistencyPrimaryButtons');
    const consistencyFixButtons = document.getElementById('consistencyFixButtons');
    const consistencyActionButtons = document.getElementById('consistencyActionButtons');
    
    showElement(consistencyPrimaryButtons);
    hideElement(consistencyFixButtons);
    hideElement(consistencyActionButtons);
    
    // 初始化一致性报告状态
    const emptyState = document.getElementById('consistencyEmptyState');
    const noIssuesState = document.getElementById('consistencyNoIssues');
    const issuesList = document.getElementById('consistencyIssuesList');
    if (emptyState) showElement(emptyState);
    if (noIssuesState) hideElement(noIssuesState);
    if (issuesList) hideElement(issuesList);
    
    // 隐藏所有预定义的问题条目（保留HTML结构）
    for (let i = 0; i < 5; i++) {
        const issueEl = document.getElementById(`consistency-issue-${i}`);
        if (issueEl) {
            hideElement(issueEl);
        }
    }
}

function initAutoResizeTextareas() {
    document.querySelectorAll('textarea.auto-resize').forEach(textarea => {
        const resize = () => {
            textarea.style.height = 'auto';
            const scrollHeight = textarea.scrollHeight;
            const maxHeight = 120;
            const minHeight = 48;
            
            let newHeight = scrollHeight;
            if (newHeight < minHeight) newHeight = minHeight;
            if (newHeight > maxHeight) {
                newHeight = maxHeight;
                textarea.style.overflowY = 'auto';
            } else {
                textarea.style.overflowY = 'hidden';
            }
            
            textarea.style.height = newHeight + 'px';
        };
        
        textarea.addEventListener('input', resize);
        textarea.addEventListener('change', resize);
        resize();
        setTimeout(() => resize(), 100);
    });
}



async function generateQuestions() {
    if (!worldviewId) return;
    showLoading('正在生成深化问题...');

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/deepening/questions/`, {
            method: 'POST'
        });

        // console.log('generateQuestions response:', data);
        
        if (data.success) {
            // 确保显示问题列表和答案按钮，隐藏操作按钮
            const questionsList = document.getElementById('questionsList');
            const suggestionsContainer = document.getElementById('suggestionsContainer');
            const primaryButtons = document.getElementById('deepeningPrimaryButtons');
            const answerButtons = document.getElementById('deepeningAnswerButtons');
            const actionButtons = document.getElementById('deepeningActionButtons');
            const questions = data.data || [];

            showElement(questionsList);
            if (suggestionsContainer) {
                hideElement(suggestionsContainer);
                suggestionsContainer.innerHTML = '';
            }
            hideElement(actionButtons);

            if (questions.length === 0) {
                showElement(primaryButtons);
                hideElement(answerButtons);
                displayQuestions([]);
                showToast('世界观已较为完善', 'success');
            } else {
                hideElement(primaryButtons);
                showElement(answerButtons);
                displayQuestions(questions);
                showToast('问题生成成功');
            }
        } else {
            showToast(data.message || '生成失败', 'error');
        }
    } catch (error) {
        console.error('Failed to generate questions:', error);
        showToast('生成失败', 'error');
    } finally {
        hideLoading();
    }
}

function displayQuestions(questions) {
    // console.log('displayQuestions called with:', questions);
    
    const container = document.getElementById('questionsList');
    if (!container) {
        console.error('questionsList container not found');
        return;
    }
    
    if (!questions || questions.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-check-circle mb-2" style="font-size: 2rem; color: #22c55e;"></i>
                <p class="text-muted mb-0" style="color: #e8b840 !important; font-size: 1.05rem;">
                    世界观设定已经比较完善了，AI 都找不到需要深化的问题
                </p>
            </div>
        `;
        return;
    }

    // console.log(`Displaying ${questions.length} questions`);
    
    container.innerHTML = questions.map((q, i) => `
        <div class="question-item border rounded p-3 mb-2">
            <p class="question-text mb-2"><strong>${i + 1}.</strong> ${escapeHtml(q.question || '')}</p>
            <textarea class="form-control auto-resize" rows="2" placeholder="输入答案..." id="answer-${q.id || i}" oninput="updateSubmitButtonState()">${escapeHtml(q.answer || '')}</textarea>
        </div>
    `).join('');

    updateSubmitButtonState();
}

function updateSubmitButtonState() {
    const submitBtn = document.getElementById('submitAnswersBtn');
    const textareas = document.querySelectorAll('[id^="answer-"]');
    let hasAnswer = false;
    textareas.forEach(textarea => {
        if (textarea.value.trim().length > 0) hasAnswer = true;
    });
    if (submitBtn) {
        submitBtn.disabled = !hasAnswer;
    }
}

async function submitAnswers() {
    if (!worldviewId) return;
    showLoading('正在提交并分析...');

    const qaList = [];
    document.querySelectorAll('[id^="answer-"]').forEach(textarea => {
        const questionId = textarea.id.replace('answer-', '');
        const questionText = textarea.closest('.question-item')?.querySelector('.question-text')?.textContent || '';
        const answerText = textarea.value.trim();
        
        if (answerText && questionText) {
            qaList.push({
                id: questionId,
                question: questionText,
                answer: answerText
            });
        }
    });

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/deepening/submit/`, {
            method: 'POST',
            body: JSON.stringify({ qaList })
        });

        if (data.success) {
            showToast('提交成功');
            
            const questionsList = document.getElementById('questionsList');
            const suggestionsContainer = document.getElementById('suggestionsContainer');
            const answerButtons = document.getElementById('deepeningAnswerButtons');
            const actionButtons = document.getElementById('deepeningActionButtons');
            
            hideElement(questionsList);
            showElement(suggestionsContainer);
            hideElement(answerButtons);
            showElement(actionButtons);
            
            displaySuggestions(data.data || []);
        }
    } catch (error) {
        console.error('Failed to submit answers:', error);
        showToast('提交失败', 'error');
    } finally {
        hideLoading();
    }
}



function displaySuggestions(suggestions) {
    const container = document.getElementById('suggestionsContainer');
    if (!container) return;

    if (suggestions.length === 0) {
        container.innerHTML = '<div class="border rounded p-4 mt-3"><p class="text-muted">没有生成修改建议</p></div>';
        return;
    }

    window.currentSuggestions = suggestions;

    container.innerHTML = `
        <div class="border rounded p-4 mt-3">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4>修改建议</h4>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" onclick="toggleAllSuggestions(true)">
                        <i class="fas fa-check-square me-1"></i>全选
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="toggleAllSuggestions(false)">
                        <i class="fas fa-square me-1"></i>取消全选
                    </button>
                </div>
            </div>
            <div id="suggestionsList">
                ${suggestions.map((s, i) => `
                    <div class="suggestion-item" data-index="${i}">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <input type="checkbox" class="suggestion-checkbox" checked data-index="${i}">
                                <span class="font-medium">修改 ${i + 1}</span>
                            </div>
                            <span class="suggestion-impact">${getImpactText(s.impact)}</span>
                        </div>
                        <div class="suggestion-content">
                            <p class="text-sm text-muted mb-1"><strong>目标:</strong> <span class="text-primary">${getLayerName(s.targetLayer)}</span> / <code class="text-sm">${s.targetField}</code></p>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>原值:</strong></p>
                                <div class="suggestion-old-value">${formatValue(s.oldValue)}</div>
                            </div>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>新值:</strong></p>
                                <textarea class="suggestion-edit" data-index="${i}" data-field="newValue">${escapeHtml(typeof s.newValue === 'object' ? JSON.stringify(s.newValue, null, 2) : (s.newValue || ''))}</textarea>
                            </div>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>原因:</strong></p>
                                <div class="suggestion-reason">${escapeHtml(s.reason || '')}</div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function toggleAllSuggestions(checked) {
    document.querySelectorAll('.suggestion-checkbox').forEach(checkbox => {
        checkbox.checked = checked;
    });
}

function formatValue(value) {
    if (value === null || value === undefined) {
        return '<span style="color: #9ca3af;">空</span>';
    }
    if (typeof value === 'object') {
        try {
            const str = JSON.stringify(value, null, 2);
            if (str.length > 200) {
                return `<pre class="text-sm" style="max-height: 100px; overflow-y: auto; background: #fff; padding: 8px; border-radius: 4px;">${escapeHtml(str.substring(0, 200))}...</pre>`;
            }
            return `<pre class="text-sm" style="background: #fff; padding: 8px; border-radius: 4px;">${escapeHtml(str)}</pre>`;
        } catch {
            return escapeHtml(String(value));
        }
    }
    if (typeof value === 'string') {
        if (value.length > 200) {
            return escapeHtml(value.substring(0, 200)) + '...';
        }
        return escapeHtml(value);
    }
    return escapeHtml(String(value));
}

function getImpactColor(impact) {
    const colors = {
        'low': 'success',
        'medium': 'warning',
        'high': 'danger'
    };
    return colors[impact] || 'secondary';
}

function getImpactText(impact) {
    const texts = {
        'low': '低影响',
        'medium': '中影响',
        'high': '高影响'
    };
    return texts[impact] || '未知';
}

function getLayerName(layer) {
    const names = {
        'setting': '基础设定',
        'foundation': '世界基础',
        'power': '力量体系',
        'races': '种族族群',
        'society': '社会结构',
        'culture': '文化人文',
        'history': '历史进程',
        'special': '特殊规则'
    };
    return names[layer] || layer;
}

function translateFieldPath(path) {
    if (!path) return '';
    
    const commonTerms = {
        'overview': '概述',
        'identity': '身份',
        'transmigration': '穿越设定',
        'conflict': '冲突',
        'natural': '自然',
        'laws': '法则',
        'cultivation': '修炼',
        'destiny': '命运',
        'energy': '能量',
        'types': '类型',
        'future': '未来',
        'race': '种族',
        'economy': '经济',
        'politics': '政治',
        'religion': '宗教',
        'art': '艺术',
        'customs': '习俗',
        'war': '战争',
        'crisis': '危机',
        'relics': '遗迹'
    };
    
    // 处理类似 "setting.conflict" 格式的路径
    return path.split('.').map(part => {
        // 先尝试作为完整部分查找
        if (commonTerms[part]) {
            return commonTerms[part];
        }
        // 尝试作为层级名称查找
        if (getLayerName(part) !== part) {
            return getLayerName(part);
        }
        return part;
    }).join(' / ');
}

function clearSuggestions() {
    const container = document.getElementById('suggestionsContainer');
    if (container) {
        container.innerHTML = '';
        hideElement(container);
    }
    
    const questionsList = document.getElementById('questionsList');
    questionsList.innerHTML = '<p class="text-muted mb-0">点击上方按钮生成深化问题</p>';
    
    hideElement(document.getElementById('deepeningAnswerButtons'));
    hideElement(document.getElementById('deepeningActionButtons'));
    showElement(document.getElementById('deepeningPrimaryButtons'));
    
    const applyBtn = document.getElementById('applyChangesBtn');
    if (applyBtn) {
        applyBtn.disabled = true;
    }
    
    window.currentSuggestions = null;
}

async function applyChanges() {
    if (!worldviewId) return;
    
    // 更新当前建议数据（从编辑框获取，仅处理 newValue）
    document.querySelectorAll('.suggestion-edit').forEach(textarea => {
        const index = parseInt(textarea.dataset.index);
        const field = textarea.dataset.field;
        
        if (!isNaN(index) && field === 'newValue' && window.currentSuggestions[index]) {
            // 尝试解析 JSON
            let value = textarea.value;
            try {
                value = JSON.parse(value);
            } catch (e) {
                // 如果不是 JSON，保持原字符串值
            }
            window.currentSuggestions[index][field] = value;
        }
    });

    const checkboxes = document.querySelectorAll('.suggestion-checkbox:checked');
    const selectedChanges = [];

    checkboxes.forEach(checkbox => {
        const index = parseInt(checkbox.dataset.index);
        if (!isNaN(index)) {
            const suggestionsData = window.currentSuggestions || [];
            if (suggestionsData[index]) {
                selectedChanges.push(suggestionsData[index]);
            }
        }
    });

    if (selectedChanges.length === 0) {
        showToast('请至少选择一个修改建议');
        return;
    }

    // console.log('发送修改:', JSON.stringify({ changes: selectedChanges }, null, 2));

    showLoading('正在应用修改...');

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/deepening/apply/`, {
            method: 'POST',

            body: JSON.stringify({ changes: selectedChanges })
        });

        // console.log('响应:', data);

        if (data.success) {
            showToast('修改已应用');
            // 不刷新页面，而是重新加载数据
            await loadWorldData(worldviewId);
            resetDeepeningPage();
        }
    } catch (error) {
        console.error('Failed to apply changes:', error);
        showToast('应用修改失败', 'error');
    } finally {
        hideLoading();
    }
}

// 重置深化问答页面到初始状态
function resetDeepeningPage() {
    const questionsList = document.getElementById('questionsList');
    const suggestionsContainer = document.getElementById('suggestionsContainer');
    
    if (questionsList) {
        questionsList.innerHTML = '<p class="text-muted mb-0">点击上方按钮生成深化问题</p>';
        showElement(questionsList);
    }
    if (suggestionsContainer) {
        suggestionsContainer.innerHTML = '';
        hideElement(suggestionsContainer);
    }
    
    hideElement(document.getElementById('deepeningAnswerButtons'));
    hideElement(document.getElementById('deepeningActionButtons'));
    showElement(document.getElementById('deepeningPrimaryButtons'));
    
    window.currentSuggestions = null;
    
    const applyBtn = document.getElementById('applyChangesBtn');
    if (applyBtn) {
        applyBtn.disabled = true;
    }
}

async function checkConsistency() {
    if (!worldviewId) return;
    showLoading('正在检查一致性...');

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/consistency/check/`, {
            method: 'POST'
        });

        if (data.success) {
            const issues = data.data?.issues || [];
            const hasIssues = data.data?.hasIssues;
        
            const primaryButtons = document.getElementById('consistencyPrimaryButtons');
            const fixButtons = document.getElementById('consistencyFixButtons');
            const actionButtons = document.getElementById('consistencyActionButtons');
            
            hideElement(actionButtons);
            
            displayConsistencyIssues(issues);
            
            if (hasIssues) {
                hideElement(primaryButtons);
                showElement(fixButtons);
            } else {
                showElement(primaryButtons);
                hideElement(fixButtons);
            }
            
            showToast('检查完成');
        } else {
            showToast(data.message || '检查失败', 'error');
        }
    } catch (error) {
        console.error('Failed to check consistency:', error);
        showToast('检查失败', 'error');
    } finally {
        hideLoading();
    }
}

function displayConsistencyIssues(issues) {
    const emptyState = document.getElementById('consistencyEmptyState');
    const noIssuesState = document.getElementById('consistencyNoIssues');
    const issuesList = document.getElementById('consistencyIssuesList');
    const template = document.getElementById('consistencyIssueTemplate');
    
    if (!emptyState || !noIssuesState || !issuesList || !template) return;
    
    // 先隐藏所有状态
    hideElement(emptyState);
    hideElement(noIssuesState);
    hideElement(issuesList);
    
    if (!issues || issues.length === 0) {
        showElement(noIssuesState);
        return;
    }
    
    issuesList.innerHTML = '';
    
    issues.forEach((issue, i) => {
        const isError = issue.severity === 'error';
        const severityLabel = isError ? '严重' : '警告';
        const targetLayer = getLayerName(issue.targetLayer || '');
        
        const clone = document.importNode(template.content, true);
        
        const titleEl = clone.querySelector('strong');
        const severityEl = clone.querySelector('.consistency-severity');
        const detailEl = clone.querySelector('.consistency-detail');
        const metaEl = clone.querySelector('.consistency-meta');
        const textarea = clone.querySelector('.consistency-note');
        
        if (titleEl) {
            titleEl.innerHTML = `${i + 1}. ${escapeHtml(issue.message || '')}`;
        }
        
        if (severityEl) {
            severityEl.textContent = severityLabel;
            severityEl.style.background = isError ? 'rgba(239, 68, 68, 0.2)' : 'rgba(234, 179, 8, 0.2)';
            severityEl.style.color = isError ? '#f87171' : '#fbbf24';
        }
        
        if (detailEl) {
            detailEl.textContent = issue.detail || '';
        }
        
        if (metaEl) {
            let metaText = `目标层级: <span style="color: #d1d5db;">${targetLayer}</span>`;
            if (issue.targetField) {
                metaText += ` / <code style="font-family: monospace; color: #a78bfa; font-size: 13px;">${escapeHtml(translateFieldPath(issue.targetField))}</code>`;
            }
            metaEl.innerHTML = metaText;
        }
        
        if (textarea) {
            textarea.id = `consistency-fix-note-${i}`;
        }
        
        issuesList.appendChild(clone);
    });
    
    showElement(issuesList);
}

// AI 修复一致性问题
async function fixConsistency() {
    if (!worldviewId) return;
    showLoading('正在生成修复建议...');

    try {
        const manualTextarea = document.getElementById('consistencyManualTextarea');
        let manualIssues = manualTextarea ? manualTextarea.value.trim() : '';

        // 收集每条问题用户填写的修复方向
        const fixNotes = [];
        document.querySelectorAll('[id^="consistency-fix-note-"]').forEach(textarea => {
            const note = textarea.value.trim();
            if (note) {
                fixNotes.push(note);
            }
        });
        if (fixNotes.length > 0) {
            manualIssues += (manualIssues ? '\n' : '') + fixNotes.join('\n');
        }

        const data = await api.request(`/api/worldview/${worldviewId}/consistency/fix/`, {
            method: 'POST',
            body: JSON.stringify({ manual_issues: manualIssues })
        });

        if (data.success) {
            window.isConsistencyFixMode = true;
            
            const report = document.getElementById('consistencyReport');
            const fixButtons = document.getElementById('consistencyFixButtons');
            const actionButtons = document.getElementById('consistencyActionButtons');
            const suggestionsContainer = document.getElementById('consistencySuggestionsContainer');
            
            hideElement(report);
            hideElement(fixButtons);
            showElement(actionButtons);
            
            // 隐藏并清空手动输入区域
            const manualInput = document.getElementById('consistencyManualInput');
            if (manualInput) {
                hideElement(manualInput);
                if (manualTextarea) manualTextarea.value = '';
            }
            
            if (suggestionsContainer) {
                showElement(suggestionsContainer);
                displayConsistencySuggestions(data.data || [], suggestionsContainer);
                showToast('修复建议已生成');
            }
        }
    } catch (error) {
        console.error('Failed to fix consistency:', error);
        showToast('生成修复建议失败', 'error');
    } finally {
        hideLoading();
    }
}

// 显示一致性修复建议
function displayConsistencySuggestions(suggestions, container) {
    if (!container) return;

    if (suggestions.length === 0) {
        container.innerHTML = `
            <div class="border rounded p-4">
                <div class="text-center py-4">
                    <i class="fas fa-check-circle mb-2" style="font-size: 2rem; color: #22c55e;"></i>
                    <p class="text-muted mb-0" style="color: #e8b840 !important; font-size: 1.05rem;">
                        无需修复，设定一致性已经很好！
                    </p>
                </div>
            </div>
        `;
        return;
    }

    window.currentSuggestions = suggestions;

    container.innerHTML = `
        <div class="border rounded p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4>修改建议</h4>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" onclick="toggleAllConsistencySuggestions(true)">
                        <i class="fas fa-check-square me-1"></i>全选
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="toggleAllConsistencySuggestions(false)">
                        <i class="fas fa-square me-1"></i>取消全选
                    </button>
                </div>
            </div>
            <div id="consistencySuggestionsList">
                ${suggestions.map((s, i) => `
                    <div class="suggestion-item" data-index="${i}">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <input type="checkbox" class="suggestion-checkbox" checked data-index="${i}">
                                <span class="font-medium">修改 ${i + 1}</span>
                            </div>
                            <span class="suggestion-impact">${getImpactText(s.impact)}</span>
                        </div>
                        <div class="suggestion-content">
                            <p class="text-sm text-muted mb-1"><strong>目标:</strong> <span class="text-primary">${getLayerName(s.targetLayer)}</span> / <code class="text-sm">${s.targetField}</code></p>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>原值:</strong></p>
                                <div class="suggestion-old-value">${formatValue(s.oldValue)}</div>
                            </div>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>新值:</strong></p>
                                <textarea class="suggestion-edit" data-index="${i}" data-field="newValue">${escapeHtml(typeof s.newValue === 'object' ? JSON.stringify(s.newValue, null, 2) : (s.newValue || ''))}</textarea>
                            </div>
                            <div class="suggestion-section">
                                <p class="text-sm mb-1"><strong>原因:</strong></p>
                                <div class="suggestion-reason">${escapeHtml(s.reason || '')}</div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// 全选/取消全选一致性修复建议
function toggleAllConsistencySuggestions(checked) {
    const checkboxes = document.querySelectorAll('#consistencySuggestionsList .suggestion-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = checked;
    });
}

// 清除一致性修复建议
function clearConsistencySuggestions() {
    const container = document.getElementById('consistencySuggestionsContainer');
    if (container) {
        container.innerHTML = '';
        hideElement(container);
    }
    
    // 重置一致性报告状态
    const emptyState = document.getElementById('consistencyEmptyState');
    const noIssuesState = document.getElementById('consistencyNoIssues');
    const issuesList = document.getElementById('consistencyIssuesList');
    if (emptyState) showElement(emptyState);
    if (noIssuesState) hideElement(noIssuesState);
    if (issuesList) hideElement(issuesList);
    
    // 隐藏所有预定义的问题条目（保留HTML结构）
    for (let i = 0; i < 5; i++) {
        const issueEl = document.getElementById(`consistency-issue-${i}`);
        if (issueEl) {
            hideElement(issueEl);
        }
    }
    
    hideElement(document.getElementById('consistencyFixButtons'));
    hideElement(document.getElementById('consistencyActionButtons'));
    showElement(document.getElementById('consistencyPrimaryButtons'));

    const manualInput = document.getElementById('consistencyManualInput');
    if (manualInput) {
        hideElement(manualInput);
        const textarea = document.getElementById('consistencyManualTextarea');
        if (textarea) textarea.value = '';
    }

    window.currentSuggestions = null;
    window.isConsistencyFixMode = false;
}

// Alpine.js 一致性检查状态对象 - 工厂函数形式
function consistencyState() {
    return {
        state: 'empty',
        issues: [],
        suggestions: [],
        
        async checkConsistency() {
            if (!worldviewId) return;
            showLoading('正在检查一致性...');
            
            try {
                const data = await api.request(`/api/worldview/${worldviewId}/consistency/check/`, {
                    method: 'POST'
                });
                
                if (data.success) {
                    this.issues = data.data?.issues || [];
                    if (this.issues.length > 0) {
                        this.state = 'hasIssues';
                    } else {
                        this.state = 'noIssues';
                    }
                    showToast('检查完成');
                } else {
                    showToast(data.message || '检查失败', 'error');
                }
            } catch (error) {
                console.error('Failed to check consistency:', error);
                showToast('检查失败', 'error');
            } finally {
                hideLoading();
            }
        },
        
        async fixConsistency() {
            if (!worldviewId) return;
            showLoading('正在生成修复建议...');
            
            try {
                let manualIssues = '';
                this.issues.forEach((issue, i) => {
                    const noteEl = document.getElementById(`consistency-fix-note-${i}`);
                    if (noteEl && noteEl.value.trim()) {
                        manualIssues += (manualIssues ? '\n' : '') + noteEl.value.trim();
                    }
                });
                
                const data = await api.request(`/api/worldview/${worldviewId}/consistency/fix/`, {
                    method: 'POST',
                    body: JSON.stringify({ manual_issues: manualIssues })
                });
                
                if (data.success) {
                    this.suggestions = (data.data || []).map(s => ({ ...s, selected: true }));
                    this.state = 'hasSuggestions';
                    window.currentSuggestions = this.suggestions;
                    showToast('修复建议已生成');
                } else {
                    showToast(data.message || '生成失败', 'error');
                }
            } catch (error) {
                console.error('Failed to fix consistency:', error);
                showToast('生成修复建议失败', 'error');
            } finally {
                hideLoading();
            }
        },
        
        resetState() {
            this.state = 'empty';
            this.issues = [];
            this.suggestions = [];
            window.currentSuggestions = null;
        },
        
        async applyConsistencyChanges() {
            if (!worldviewId) return;
            
            const selectedChanges = this.suggestions.filter(s => s.selected);
            if (selectedChanges.length === 0) {
                showToast('请至少选择一个修改建议');
                return;
            }
            
            console.log('准备发送的修改数据:', JSON.stringify({ changes: selectedChanges }, null, 2));
            
            showLoading('正在应用修改...');
            
            try {
                const data = await api.request(`/api/worldview/${worldviewId}/deepening/apply/`, {
                    method: 'POST',
                    body: JSON.stringify({ changes: selectedChanges })
                });
                
                if (data.success) {
                    console.log('应用修改成功，返回数据:', data);
                    showToast('修改已应用');
                    await loadWorldData(worldviewId);
                    this.resetState();
                } else {
                    showToast(data.message || '应用失败', 'error');
                }
            } catch (error) {
                console.error('Failed to apply changes:', error);
                showToast('应用修改失败', 'error');
            } finally {
                hideLoading();
            }
        },
        
        toggleSuggestion(index) {
            if (this.suggestions[index]) {
                this.suggestions[index].selected = !this.suggestions[index].selected;
            }
        },
        
        selectAllSuggestions(selected) {
            this.suggestions.forEach(s => s.selected = selected);
        },
        
        getLayerName(layer) {
            const names = {
                'setting': '基础设定',
                'foundation': '世界基础',
                'power': '力量体系',
                'races': '种族族群',
                'society': '社会结构',
                'culture': '文化人文',
                'history': '历史进程',
                'special': '特殊规则'
            };
            return names[layer] || layer;
        },
        
        translateFieldPath(path) {
            if (!path) return '';
            
            const commonTerms = {
                'overview': '概述',
                'identity': '身份',
                'transmigration': '穿越设定',
                'conflict': '冲突',
                'natural': '自然',
                'laws': '法则',
                'cultivation': '修炼',
                'destiny': '命运',
                'energy': '能量',
                'types': '类型',
                'future': '未来',
                'race': '种族',
                'economy': '经济',
                'politics': '政治',
                'religion': '宗教',
                'art': '艺术',
                'customs': '习俗',
                'war': '战争',
                'crisis': '危机',
                'relics': '遗迹'
            };
            
            return path.split('.').map(part => {
                if (commonTerms[part]) {
                    return commonTerms[part];
                }
                if (this.getLayerName(part) !== part) {
                    return this.getLayerName(part);
                }
                return part;
            }).join(' / ');
        },
        
        getImpactText(impact) {
            const impacts = {
                'low': '影响较小',
                'medium': '中等影响',
                'high': '影响较大',
                'critical': '关键影响'
            };
            return impacts[impact] || impact;
        },
        
        formatValue(value) {
            if (value === null || value === undefined) {
                return '<span class="text-muted">空</span>';
            }
            if (typeof value === 'object') {
                return `<pre class="text-sm" style="white-space: pre-wrap;">${JSON.stringify(value, null, 2)}</pre>`;
            }
            return `<span>${value}</span>`;
        }
    };
}

// 重置一致性检查UI到初始状态（保留用于兼容旧代码）
function resetConsistencyUI() {
    // 由于 Alpine.js 使用工厂函数，这里通过全局状态对象重置
    if (window.consistencyStateInstance) {
        window.consistencyStateInstance.resetState();
    }
}

// 应用一致性修复建议
async function applyConsistencyChanges() {
    if (!worldviewId) return;
    
    // 更新当前建议数据（从编辑框获取，仅处理 newValue）
    document.querySelectorAll('#consistencySuggestionsList .suggestion-edit').forEach(textarea => {
        const index = parseInt(textarea.dataset.index);
        const field = textarea.dataset.field;
        
        if (!isNaN(index) && field === 'newValue' && window.currentSuggestions[index]) {
            // 尝试解析 JSON
            let value = textarea.value;
            try {
                value = JSON.parse(value);
            } catch (e) {
                // 如果不是 JSON，保持原字符串值
            }
            window.currentSuggestions[index][field] = value;
        }
    });

    const checkboxes = document.querySelectorAll('#consistencySuggestionsList .suggestion-checkbox:checked');
    const selectedChanges = [];

    checkboxes.forEach(checkbox => {
        const index = parseInt(checkbox.dataset.index);
        if (!isNaN(index)) {
            const suggestionsData = window.currentSuggestions || [];
            if (suggestionsData[index]) {
                selectedChanges.push(suggestionsData[index]);
            }
        }
    });

    if (selectedChanges.length === 0) {
        showToast('请至少选择一个修改建议');
        return;
    }

    console.log('发送修改:', JSON.stringify({ changes: selectedChanges }, null, 2));

    showLoading('正在应用修改...');

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/deepening/apply/`, {
            method: 'POST',

            body: JSON.stringify({ changes: selectedChanges })
        });

        console.log('响应:', data);

        if (data.success) {
            showToast('修改已应用');
            // 不刷新页面，而是重新加载数据
            await loadWorldData(worldviewId);
            // 重置一致性检查UI到初始状态
            resetConsistencyUI();
        }
    } catch (error) {
        console.error('Failed to apply changes:', error);
        showToast('应用修改失败', 'error');
    } finally {
        hideLoading();
    }
}

function createSnapshot() {
    const label = document.getElementById('snapshotLabel')?.value.trim();
    if (!label) {
        showToast('请输入快照标签', 'error');
        return;
    }
    showToast('快照功能开发中');
}

function exportWorld(format) {
    showToast(`导出 ${format.toUpperCase()} 功能开发中`);
}

function goBack() {
    window.history.back();
}

function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

function getCookie(name) {
    let v = null;
    if (document.cookie && document.cookie !== '') {
        const cs = document.cookie.split(';');
        for (let i = 0; i < cs.length; i++) {
            const c = cs[i].trim();
            if (c.substring(0, name.length + 1) === (name + '=')) {
                v = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
    }
    return v;
}

function getAxiomsText() {
    const inputs = document.querySelectorAll('#axiomsList input');
    return Array.from(inputs).map(i => i.value.trim()).filter(v => v).join('\n');
}

function setAxiomsFromText(data) {
    let list;
    if (Array.isArray(data)) {
        list = data.map(v => String(v).trim()).filter(v => v);
    } else if (typeof data === 'string') {
        list = data.split('\n').map(v => v.trim()).filter(v => v);
    } else {
        return;
    }
    if (list.length === 0) return;
    axioms.length = 0;
    list.forEach(v => axioms.push(v));
    renderAxioms();
}






function updateFoundationBtn() {
    const continent = document.getElementById('foundationContinent')?.value.trim() || '';
    const terrain = document.getElementById('foundationTerrain')?.value.trim() || '';
    const era = document.getElementById('foundationEra')?.value.trim() || '';
    const days = document.getElementById('foundationDays')?.value.trim() || '';
    const seasons = document.getElementById('foundationSeasons')?.value.trim() || '';
    const festivals = document.getElementById('foundationFestivals')?.value.trim() || '';
    const laws = document.getElementById('foundationLaws')?.value.trim() || '';
    const boundary = document.getElementById('foundationBoundary')?.value.trim() || '';
    const axiomsText = getAxiomsText();
    const balance = document.getElementById('foundationBalance')?.value.trim() || '';
}


function updatePowerBtn() {
    const energyType = document.getElementById('powerEnergyType')?.value.trim() || '';
    const energyDist = document.getElementById('powerEnergyDistribution')?.value.trim() || '';
    const energyTraits = document.getElementById('powerEnergyTraits')?.value.trim() || '';
    const levels = document.getElementById('powerLevels')?.value.trim() || '';
    const martialCat = document.getElementById('powerMartialCategory')?.value.trim() || '';
    const martialHeritage = document.getElementById('powerMartialHeritage')?.value.trim() || '';
    const treasureCat = document.getElementById('powerTreasureCategory')?.value.trim() || '';
    const treasurePill = document.getElementById('powerTreasurePill')?.value.trim() || '';
    const beastLevel = document.getElementById('powerBeastLevel')?.value.trim() || '';
    const beastLegend = document.getElementById('powerBeastLegend')?.value.trim() || '';
}

function updateRacesBtn() {
    const category = document.getElementById('racesCategory')?.value.trim() || '';
    const value = document.getElementById('racesValue')?.value.trim() || '';
    const lifespan = document.getElementById('racesLifespan')?.value.trim() || '';
    const reproduction = document.getElementById('racesReproduction')?.value.trim() || '';
    const constitution = document.getElementById('racesConstitution')?.value.trim() || '';
    const relation = document.getElementById('racesRelation')?.value.trim() || '';
}

function updateSocietyBtn() {
    const government = document.getElementById('societyGovernment')?.value.trim() || '';
    const bureaucracy = document.getElementById('societyBureaucracy')?.value.trim() || '';
    const sectLevel = document.getElementById('societySectLevel')?.value.trim() || '';
    const sectHeritage = document.getElementById('societySectHeritage')?.value.trim() || '';
    const martialFaction = document.getElementById('societyMartialFaction')?.value.trim() || '';
    const martialGuild = document.getElementById('societyMartialGuild')?.value.trim() || '';
    const external = document.getElementById('societyExternal')?.value.trim() || '';
    const classLevel = document.getElementById('societyClassLevel')?.value.trim() || '';
    const classMobility = document.getElementById('societyClassMobility')?.value.trim() || '';
    const currencyType = document.getElementById('societyCurrencyType')?.value.trim() || '';
    const currencyRule = document.getElementById('societyCurrencyRule')?.value.trim() || '';
    const resource = document.getElementById('societyResource')?.value.trim() || '';
}

function updateCultureBtn() {
    const festival = document.getElementById('cultureFestival')?.value.trim() || '';
    const ritual = document.getElementById('cultureRitual')?.value.trim() || '';
    const language = document.getElementById('cultureLanguage')?.value.trim() || '';
    const script = document.getElementById('cultureScript')?.value.trim() || '';
    const clothing = document.getElementById('cultureClothing')?.value.trim() || '';
    const food = document.getElementById('cultureFood')?.value.trim() || '';
    const architecture = document.getElementById('cultureArchitecture')?.value.trim() || '';
    const transport = document.getElementById('cultureTransport')?.value.trim() || '';
    const deity = document.getElementById('cultureDeity')?.value.trim() || '';
    const religionOrg = document.getElementById('cultureReligionOrg')?.value.trim() || '';
    const faithDiff = document.getElementById('cultureFaithDiff')?.value.trim() || '';
}

function updateHistoryBtn() {
    const ancient = document.getElementById('historyAncient')?.value.trim() || '';
    const modern = document.getElementById('historyModern')?.value.trim() || '';
    const crisis = document.getElementById('historyCrisis')?.value.trim() || '';
    const destiny = document.getElementById('historyDestiny')?.value.trim() || '';
    const future = document.getElementById('historyFuture')?.value.trim() || '';
}

function updateSpecialBtn() {
    const taboo = document.getElementById('specialTaboo')?.value.trim() || '';
    const secret = document.getElementById('specialSecret')?.value.trim() || '';
    const fortune = document.getElementById('specialFortune')?.value.trim() || '';
    const destiny = document.getElementById('specialDestiny')?.value.trim() || '';
    const soul = document.getElementById('specialSoul')?.value.trim() || '';
    const reincarnation = document.getElementById('specialReincarnation')?.value.trim() || '';
    const transmigration = document.getElementById('specialTransmigration')?.value.trim() || '';
    const system = document.getElementById('specialSystem')?.value.trim() || '';
    const rules = document.getElementById('specialRules')?.value.trim() || '';
}



/** 渲染 */
function renderSetting(structure) {
    // 渲染  世界基础
    const f = structure.setting || {};
    // 处理嵌套对象结构
    const identity = f.identity || {}
    const position = f.position || {};
    const overview = f.overview || '';
    const conflict = f.conflict || '';
    
    setField('worldName', identity.worldName);
    setField('genreSelect', identity.genre);
    setField('worldIdentity', position.identity);
    setField('worldTone', position.tone);
    setField('worldOverview', overview);
    setField('worldCoreConflict', conflict);
}

function renderFoundation(structure) {
    // 渲染  世界基础
    const f = structure.foundation || {};
    // 处理嵌套对象结构
    const geography = f.geography || {};
    const calendar = f.calendar || {};
    const rules = f.rules || {};
    
    setField('foundationContinent', geography.continent_distribution);
    setField('foundationTerrain', geography.special_terrain);
    setField('foundationEra', calendar.era);
    setField('foundationDays', calendar.days_per_year);
    setField('foundationSeasons', calendar.seasons);
    setField('foundationFestivals', calendar.festivals);
    setField('foundationLaws', rules.natural_laws);
    setField('foundationBoundary', rules.boundaries);
    if (rules.axioms) {
        const axiomList = Array.isArray(rules.axioms) ? rules.axioms : String(rules.axioms).split('\n').map(v => v.trim()).filter(v => v);
        axioms.length = 0;
        axiomList.forEach(v => axioms.push(v));
    }
    renderAxioms();
    setField('foundationBalance', f.balance);
}

function renderPower(structure) {
    // 渲染 力量体系
    const p = structure.power || {};
    const energy = p.energy || {};
    const martial = p.martial || {};
    const treasure = p.treasure || {};
    const beast = p.beast || {};
    
    setField('powerEnergyType', energy.types);
    setField('powerEnergyDistribution', energy.distribution);
    setField('powerEnergyTraits', energy.properties);
    setField('powerLevels', p.level);
    setField('powerMartialCategory', martial.categories);
    setField('powerMartialHeritage', martial.inheritance);
    setField('powerTreasureCategory', treasure.categories);
    setField('powerTreasurePill', treasure.pills);
    setField('powerBeastLevel', beast.levels);
    setField('powerBeastLegend', beast.mythical);
}

function renderSpecial(structure) {
    const s = structure.special || {};
    const fate = s.fate || {};
    const reincarnation = s.reincarnation || {};
    
    setField('specialTaboo', s.taboo);
    setField('specialSecret', s.secret);
    setField('specialFortune', fate.fortune_rules);
    setField('specialDestiny', fate.destiny_types);
    setField('specialSoul', reincarnation.soul_rules);
    setField('specialReincarnation', reincarnation.mechanics);
    setField('specialTransmigration', s.transmigration);
    setField('specialSystem', s.system);
    setField('specialRules', s.rules);
}

function renderHistory(structure) {
    const h = structure.history || {};
    setField('historyAncient', h.ancient);
    setField('historyModern', h.modern);
    setField('historyCrisis', h.crisis);
    setField('historyDestiny', h.destiny);
    setField('historyFuture', h.future);
}

function renderCulture(structure) {
    const c = structure.culture || {};
    const custom = c.custom || {};
    const language = c.language || {};
    const daily = c.daily || {};
    const religion = c.religion || {};
    
    setField('cultureFestival', custom.festivals);
    setField('cultureRitual', custom.rituals);
    setField('cultureLanguage', language.languages);
    setField('cultureScript', language.writing_system);
    setField('cultureClothing', daily.clothing);
    setField('cultureFood', daily.food);
    setField('cultureArchitecture', daily.architecture);
    setField('cultureTransport', daily.transportation);
    setField('cultureDeity', religion.deity);
    setField('cultureReligionOrg', religion.organization);
    setField('cultureFaithDiff', religion.faith_diff);
}

function renderSociety(structure) {
    const s = structure.society || {};
    const court = s.court || {};
    const sect = s.sect || {};
    const martial = s.martial || {};
    const social_class = s.class || {};
    const currency = s.currency || {};
    
    setField('societyGovernment', court.political_system);
    setField('societyBureaucracy', court.bureaucracy);
    setField('societySectLevel', sect.levels);
    setField('societySectHeritage', sect.relationships);
    setField('societyMartialFaction', martial.factions);
    setField('societyMartialGuild', martial.alliances);
    setField('societyExternal', s.external);
    setField('societyClassLevel', social_class.social_classes);
    setField('societyClassMobility', social_class.mobility);
    setField('societyCurrencyType', currency.types);
    setField('societyCurrencyRule', currency.rules);
    setField('societyResource', s.resource);
}

function renderRaces(structure) {
    const r = structure.races || {};
    const trait = r.trait || {};
    
    setField('racesCategory', r.category);
    setField('racesValue', r.value);
    setField('racesLifespan', trait.lifespan);
    setField('racesReproduction', trait.reproduction);
    setField('racesConstitution', trait.physique);
    setField('racesRelation', r.relation);
}



/* 切换展示*/

function showSettingSection(sectionName) {
    const sidebar = document.querySelector('#tab-overview .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showSettingSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('setting-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-overview .section-content');
    if (content) {
        content.querySelectorAll('.setting-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`setting-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showFoundationSection(sectionName) {
    const sidebar = document.querySelector('#tab-foundation .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showFoundationSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('foundation-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-foundation .section-content');
    if (content) {
        content.querySelectorAll('.foundation-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`foundation-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showPowerSection(sectionName) {
    const sidebar = document.querySelector('#tab-power .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showPowerSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('power-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-power .section-content');
    if (content) {
        content.querySelectorAll('.power-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`power-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showRacesSection(sectionName) {
    const sidebar = document.querySelector('#tab-races .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showRacesSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('races-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-races .section-content');
    if (content) {
        content.querySelectorAll('.races-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`races-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showSocietySection(sectionName) {
    const sidebar = document.querySelector('#tab-society .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showSocietySection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('society-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-society .section-content');
    if (content) {
        content.querySelectorAll('.society-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`society-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showCultureSection(sectionName) {
    const sidebar = document.querySelector('#tab-culture .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showCultureSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('culture-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-culture .section-content');
    if (content) {
        content.querySelectorAll('.culture-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`culture-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showHistorySection(sectionName) {
    const sidebar = document.querySelector('#tab-history .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showHistorySection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('history-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-history .section-content');
    if (content) {
        content.querySelectorAll('.history-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`history-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}

function showSpecialSection(sectionName) {
    const sidebar = document.querySelector('#tab-special .section-sidebar');
    if (sidebar) {
        sidebar.querySelectorAll('.section-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = sidebar.querySelector(`[onclick="showSpecialSection('${sectionName}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            const title = document.getElementById('special-title');
            if (title) title.textContent = activeBtn.textContent;
        }
    }
    
    const content = document.querySelector('#tab-special .section-content');
    if (content) {
        content.querySelectorAll('.special-section').forEach(section => section.classList.add('hidden'));
        const targetSection = document.getElementById(`special-${sectionName}`);
        if (targetSection) targetSection.classList.remove('hidden');
    }
}







/** 保存 */

async function saveSetting() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const worldName = document.getElementById('worldName')?.value?.trim() || '';
    showLoading('正在保存故事设定...');

    try {
        const data = await api.request(`/api/worldview/${worldviewId}/setting/`, {
            method: 'PUT',
            body: JSON.stringify({
                world_name: worldName,
                genre: getSelectedGenre(),
                identity: document.getElementById('worldIdentity')?.value || '',
                tone: document.getElementById('worldTone')?.value || '',
                overview: document.getElementById('worldOverview')?.value || '',
                conflict: document.getElementById('worldCoreConflict')?.value || '',
            })
        });

        if (data.success) {
            // 直接将页面数据更新到本地
            if (!currentWorldview.setting) {
                currentWorldview.setting = {};
            }
            if (!currentWorldview.setting.identity) {
                currentWorldview.setting.identity = {};
            }
            if (!currentWorldview.setting.position) {
                currentWorldview.setting.position = {};
            }
            currentWorldview.setting.identity.world_name = worldName;
            currentWorldview.setting.identity.genre = getSelectedGenre();
            currentWorldview.setting.position.identity = document.getElementById('worldIdentity')?.value || '';
            currentWorldview.setting.position.tone = document.getElementById('worldTone')?.value || '';
            currentWorldview.setting.overview = document.getElementById('worldOverview')?.value || '';
            currentWorldview.setting.conflict = document.getElementById('worldCoreConflict')?.value || '';
            
            // 重新 渲染 故事设定
            renderSetting(currentWorldview);
            showToast('基础设定已保存');
        } else {
            throw new Error(data.message || '保存失败');
        }
    } catch (error) {
        console.error('Save basic settings failed:', error);
        showToast('保存失败: ' + (error.message || '未知错误'), 'error');
    } finally {
        hideLoading();
    }
}

async function saveFoundation() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存世界基础...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/foundation/`, {
            method: 'PUT',
            body: JSON.stringify({
                continent: document.getElementById('foundationContinent')?.value || '',
                terrain: document.getElementById('foundationTerrain')?.value || '',
                era: document.getElementById('foundationEra')?.value || '',
                days: document.getElementById('foundationDays')?.value || '',
                seasons: document.getElementById('foundationSeasons')?.value || '',
                festivals: document.getElementById('foundationFestivals')?.value || '',
                laws: document.getElementById('foundationLaws')?.value || '',
                boundary: document.getElementById('foundationBoundary')?.value || '',
                axioms: getAxiomsText(),
                balance: document.getElementById('foundationBalance')?.value || '',
            })
        });
        
        if (response.success) {
            // 更新本地数据
            if (!currentWorldview.foundation) {
                currentWorldview.foundation = {};
            }
            currentWorldview.foundation = response.data.foundation;
            currentStructure.foundation = response.data.foundation;
            
            // 更新 currentStructure 中的 axioms
            if (currentStructure.rules) {
                currentStructure.rules.axioms = getAxiomsText().split('\n').filter(a => a.trim());
            }
            
            showToast('世界基础保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save foundation failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function savePower() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存力量体系...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/power/`, {
            method: 'PUT',
            body: JSON.stringify({
                energy_types: document.getElementById('powerEnergyType')?.value || '',
                energy_distribution: document.getElementById('powerEnergyDistribution')?.value || '',
                energy_properties: document.getElementById('powerEnergyTraits')?.value || '',
                level: document.getElementById('powerLevels')?.value || '',
                martial_categories: document.getElementById('powerMartialCategory')?.value || '',
                martial_inheritance: document.getElementById('powerMartialHeritage')?.value || '',
                treasure_categories: document.getElementById('powerTreasureCategory')?.value || '',
                treasure_pills: document.getElementById('powerTreasurePill')?.value || '',
                beast_levels: document.getElementById('powerBeastLevel')?.value || '',
                beast_mythical: document.getElementById('powerBeastLegend')?.value || '',
            })
        });
        
        if (response.success) {
            // 更新本地数据
            if (!currentWorldview.power) {
                currentWorldview.power = {};
            }
            currentWorldview.power = response.data.power;
            currentStructure.power = response.data.power;
            
            // 重新渲染力量体系表单
            renderPower(currentStructure);
            
            showToast('力量体系保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save power failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function saveRaces() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存种族族群...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/races/`, {
            method: 'PUT',

            body: JSON.stringify({
                category: document.getElementById('racesCategory')?.value || '',
                value: document.getElementById('racesValue')?.value || '',
                lifespan: document.getElementById('racesLifespan')?.value || '',
                reproduction: document.getElementById('racesReproduction')?.value || '',
                physique: document.getElementById('racesConstitution')?.value || '',
                relation: document.getElementById('racesRelation')?.value || '',
            })
        });

        if (response.success) {
            if (!currentWorldview.races) {
                currentWorldview.races = {};
            }
            currentWorldview.races = response.data.races;
            currentStructure.races = response.data.races;
            
            // 重新渲染种族族群表单
            renderRaces(currentStructure);
            
            showToast('种族族群保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save races failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function saveSociety() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存社会结构...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/society/`, {
            method: 'PUT',
            body: JSON.stringify({
                government: document.getElementById('societyGovernment')?.value || '',
                bureaucracy: document.getElementById('societyBureaucracy')?.value || '',
                sect_level: document.getElementById('societySectLevel')?.value || '',
                sect_heritage: document.getElementById('societySectHeritage')?.value || '',
                martial_faction: document.getElementById('societyMartialFaction')?.value || '',
                martial_guild: document.getElementById('societyMartialGuild')?.value || '',
                external: document.getElementById('societyExternal')?.value || '',
                class_level: document.getElementById('societyClassLevel')?.value || '',
                class_mobility: document.getElementById('societyClassMobility')?.value || '',
                currency_type: document.getElementById('societyCurrencyType')?.value || '',
                currency_rule: document.getElementById('societyCurrencyRule')?.value || '',
                resource: document.getElementById('societyResource')?.value || '',
            })
        });

        if (response.success) {
            if (!currentWorldview.society) {
                currentWorldview.society = {};
            }
            currentWorldview.society = response.data.society;
            currentStructure.society = response.data.society;
            
            // 重新渲染社会结构表单
            renderSociety(currentStructure);
            
            showToast('社会结构保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save society failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function saveCulture() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存文化人文...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/culture/`, {
            method: 'PUT',

            body: JSON.stringify({
                festival: document.getElementById('cultureFestival')?.value || '',
                ritual: document.getElementById('cultureRitual')?.value || '',
                language: document.getElementById('cultureLanguage')?.value || '',
                script: document.getElementById('cultureScript')?.value || '',
                clothing: document.getElementById('cultureClothing')?.value || '',
                food: document.getElementById('cultureFood')?.value || '',
                architecture: document.getElementById('cultureArchitecture')?.value || '',
                transport: document.getElementById('cultureTransport')?.value || '',
                deity: document.getElementById('cultureDeity')?.value || '',
                religion_org: document.getElementById('cultureReligionOrg')?.value || '',
                faith_diff: document.getElementById('cultureFaithDiff')?.value || '',
            })
        });

        if (response.success) {
            if (!currentWorldview.culture) {
                currentWorldview.culture = {};
            }
            currentWorldview.culture = response.data.culture;
            currentStructure.culture = response.data.culture;
            
            // 重新渲染文化人文表单
            renderCulture(currentStructure);
            
            showToast('文化人文保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save culture failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function saveHistory() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存历史进程...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/history/`, {
            method: 'PUT',

            body: JSON.stringify({
                ancient: document.getElementById('historyAncient')?.value || '',
                modern: document.getElementById('historyModern')?.value || '',
                crisis: document.getElementById('historyCrisis')?.value || '',
                destiny: document.getElementById('historyDestiny')?.value || '',
                future: document.getElementById('historyFuture')?.value || '',
            })
        });

        if (response.success) {
            if (!currentWorldview.history) {
                currentWorldview.history = {};
            }
            currentWorldview.history = response.data.history;
            currentStructure.history = response.data.history;
            
            // 重新渲染历史进程表单
            renderHistory(currentStructure);
            
            showToast('历史进程保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save history failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

async function saveSpecial() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }
    showLoading('正在保存特殊设定...');
    
    try {
        const response = await api.request(`/api/worldview/${worldviewId}/special/`, {
            method: 'PUT',

            body: JSON.stringify({
                taboo: document.getElementById('specialTaboo')?.value || '',
                secret: document.getElementById('specialSecret')?.value || '',
                fortune: document.getElementById('specialFortune')?.value || '',
                destiny: document.getElementById('specialDestiny')?.value || '',
                soul: document.getElementById('specialSoul')?.value || '',
                reincarnation: document.getElementById('specialReincarnation')?.value || '',
                transmigration: document.getElementById('specialTransmigration')?.value || '',
                system: document.getElementById('specialSystem')?.value || '',
                rules: document.getElementById('specialRules')?.value || '',
            })
        });

        if (response.success) {
            if (!currentWorldview.special) {
                currentWorldview.special = {};
            }
            currentWorldview.special = response.data.special;
            currentStructure.special = response.data.special;
            
            // 重新渲染特殊规则表单
            renderSpecial(currentStructure);
            
            showToast('特色地标保存成功');
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error('Save special failed:', error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}











/* AI 优化 */

async function aiFillSetting() {
    if (!worldviewId) return;

    // 检查所有基础设定字段是否已填写
    const fields = [
        { id: 'worldName', label: '世界名称' },
        { id: 'genreSelect', label: '小说类型', type: 'hidden' },
        { id: 'worldIdentity', label: '世界身份 / 类型气质' },
        { id: 'worldTone', label: '整体调性' },
        { id: 'worldOverview', label: '世界概述' },
        { id: 'worldCoreConflict', label: '核心冲突' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? (field.type === 'hidden' ? el.value : el.value.trim()) : '';
        if (!val) {
            emptyFields.push(field.label);
        }
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善基础设定：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化基础设定...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/setting/`, {
            method: 'POST',
            body: JSON.stringify({
                world_name: document.getElementById('worldName').value.trim(),
                genre: getSelectedGenre(),
                identity: document.getElementById('worldIdentity').value.trim(),
                tone: document.getElementById('worldTone').value.trim(),
                overview: document.getElementById('worldOverview').value.trim(),
                conflict: document.getElementById('worldCoreConflict').value.trim(),
            })
        });

        // 解析返回的结果（嵌套结构）
        let setting;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                setting = JSON.parse(jsonMatch[1]);
            } else {
                setting = JSON.parse(fullContent);
            }
        } else {
            setting = fullContent;
        }

        // 更新表单字段
        setField('worldName', setting.identity?.world_name || '');
        setField('worldIdentity', setting.position?.identity || '');
        setField('worldTone', setting.position?.tone || '');
        setField('worldOverview', setting.overview || '');
        setField('worldCoreConflict', setting.conflict || '');
        
        // 更新本地 currentWorldview（嵌套结构）
        if (!currentWorldview.setting) {
            currentWorldview.setting = {};
        }
        if (!currentWorldview.setting.identity) {
            currentWorldview.setting.identity = {};
        }
        if (!currentWorldview.setting.position) {
            currentWorldview.setting.position = {};
        }
        // console.debug(setting)
        currentWorldview.setting.identity.world_name = setting.identity?.world_name || '';
        currentWorldview.setting.identity.genre = getSelectedGenre();
        currentWorldview.setting.position.identity = setting.position?.identity || '';
        currentWorldview.setting.position.tone = setting.position?.tone || '';
        currentWorldview.setting.overview = setting.overview || '';
        currentWorldview.setting.conflict = setting.conflict || '';
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to expand:', error);
        showToast('完善失败', 'error');
    } finally {
        hideLoading();
        updateExpandBtn();
    }
}

async function aiFillFoundation() {
    // AI生成 世界基础
    if (!worldviewId) return;

    const fields = [
        { id: 'foundationContinent', label: '大陆分布' },
        { id: 'foundationTerrain', label: '特殊地形' },
        { id: 'foundationEra', label: '纪年方式' },
        { id: 'foundationDays', label: '一年天数' },
        { id: 'foundationSeasons', label: '季节划分' },
        { id: 'foundationFestivals', label: '特殊节气/节日' },
        { id: 'foundationLaws', label: '自然法则' },
        { id: 'foundationBoundary', label: '世界边界' },
        { id: 'foundationBalance', label: '平衡机制' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }
    if (!getAxiomsText()) emptyFields.push('核心公理');

    if (emptyFields.length > 0) {
        showToast(`请先完善世界基础：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化世界基础...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/foundation/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                continent: document.getElementById('foundationContinent').value.trim(),
                terrain: document.getElementById('foundationTerrain').value.trim(),
                era: document.getElementById('foundationEra').value.trim(),
                days: document.getElementById('foundationDays').value.trim(),
                seasons: document.getElementById('foundationSeasons').value.trim(),
                festivals: document.getElementById('foundationFestivals').value.trim(),
                laws: document.getElementById('foundationLaws').value.trim(),
                boundary: document.getElementById('foundationBoundary').value.trim(),
                axioms: getAxiomsText(),
                balance: document.getElementById('foundationBalance').value.trim(),
            })
        });

        let foundation;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                foundation = JSON.parse(jsonMatch[1]);
            } else {
                foundation = JSON.parse(fullContent);
            }
        } else {
            foundation = fullContent;
        }

        // 更新表单字段
        setField('foundationContinent', foundation.geography?.continent_distribution || '');
        setField('foundationTerrain', foundation.geography?.special_terrain || '');
        setField('foundationEra', foundation.calendar?.era || '');
        setField('foundationDays', foundation.calendar?.days_per_year || '');
        setField('foundationSeasons', foundation.calendar?.seasons || '');
        setField('foundationFestivals', foundation.calendar?.festivals || '');
        setField('foundationLaws', foundation.rules?.natural_laws || '');
        setField('foundationBoundary', foundation.rules?.boundaries || '');
        if (foundation.rules?.axioms) setAxiomsFromText(foundation.rules.axioms);
        setField('foundationBalance', foundation.balance || '');
        
        // 更新本地数据
        if (!currentWorldview.foundation) {
            currentWorldview.foundation = {};
        }
        if (!currentWorldview.foundation.geography) {
            currentWorldview.foundation.geography = {};
        }
        if (!currentWorldview.foundation.calendar) {
            currentWorldview.foundation.calendar = {};
        }
        if (!currentWorldview.foundation.rules) {
            currentWorldview.foundation.rules = {};
        }
        
        currentWorldview.foundation.geography.continent_distribution = foundation.geography?.continent_distribution || '';
        currentWorldview.foundation.geography.special_terrain = foundation.geography?.special_terrain || '';
        currentWorldview.foundation.calendar.era = foundation.calendar?.era || '';
        currentWorldview.foundation.calendar.days_per_year = foundation.calendar?.days_per_year || '';
        currentWorldview.foundation.calendar.seasons = foundation.calendar?.seasons || '';
        currentWorldview.foundation.calendar.festivals = foundation.calendar?.festivals || '';
        currentWorldview.foundation.rules.natural_laws = foundation.rules?.natural_laws || '';
        currentWorldview.foundation.rules.boundaries = foundation.rules?.boundaries || '';
        if (foundation.rules?.axioms) {
            if (typeof foundation.rules.axioms === 'string') {
                currentWorldview.foundation.rules.axioms = foundation.rules.axioms.split('\n').filter(a => a.trim());
            } else {
                currentWorldview.foundation.rules.axioms = foundation.rules.axioms;
            }
        }
        currentWorldview.foundation.balance = foundation.balance || '';
        
        // 同步更新 currentStructure
        currentStructure.foundation = JSON.parse(JSON.stringify(currentWorldview.foundation));
        if (currentStructure.foundation.rules) {
            currentStructure.rules = {
                ...currentStructure.rules,
                axioms: currentStructure.foundation.rules.axioms || []
            };
        }
        
        // 更新 axioms 数组和 DOM
        if (currentStructure.foundation.rules?.axioms) {
            axioms.length = 0;
            currentStructure.foundation.rules.axioms.forEach(v => axioms.push(v));
            renderAxioms();
        }
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to expand foundation:', error);
        showToast('完善失败', 'error');
    } finally {
        hideLoading();
        updateFoundationBtn();
    }
}

async function aiFillPower() {
    if (!worldviewId) return;

    const fields = [
        { id: 'powerEnergyType', label: '主要能量类型' },
        { id: 'powerEnergyDistribution', label: '能量分布' },
        { id: 'powerEnergyTraits', label: '能量特性' },
        { id: 'powerLevels', label: '修炼等级' },
        { id: 'powerMartialCategory', label: '功法分类' },
        { id: 'powerMartialHeritage', label: '传承方式' },
        { id: 'powerTreasureCategory', label: '法宝分类' },
        { id: 'powerTreasurePill', label: '丹药体系' },
        { id: 'powerBeastLevel', label: '妖兽等级' },
        { id: 'powerBeastLegend', label: '神兽传说' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善力量体系：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化力量体系...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/power/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                energy_types: document.getElementById('powerEnergyType').value.trim(),
                energy_distribution: document.getElementById('powerEnergyDistribution').value.trim(),
                energy_properties: document.getElementById('powerEnergyTraits').value.trim(),
                level: document.getElementById('powerLevels').value.trim(),
                martial_categories: document.getElementById('powerMartialCategory').value.trim(),
                martial_inheritance: document.getElementById('powerMartialHeritage').value.trim(),
                treasure_categories: document.getElementById('powerTreasureCategory').value.trim(),
                treasure_pills: document.getElementById('powerTreasurePill').value.trim(),
                beast_levels: document.getElementById('powerBeastLevel').value.trim(),
                beast_mythical: document.getElementById('powerBeastLegend').value.trim(),
            })
        });

        let power;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                power = JSON.parse(jsonMatch[1]);
            } else {
                power = JSON.parse(fullContent);
            }
        } else {
            power = fullContent;
        }

        // 更新表单字段
        setField('powerEnergyType', power.energy?.types || '');
        setField('powerEnergyDistribution', power.energy?.distribution || '');
        setField('powerEnergyTraits', power.energy?.properties || '');
        setField('powerLevels', power.level || '');
        setField('powerMartialCategory', power.martial?.categories || '');
        setField('powerMartialHeritage', power.martial?.inheritance || '');
        setField('powerTreasureCategory', power.treasure?.categories || '');
        setField('powerTreasurePill', power.treasure?.pills || '');
        setField('powerBeastLevel', power.beast?.levels || '');
        setField('powerBeastLegend', power.beast?.mythical || '');
        
        // 更新本地数据
        if (!currentWorldview.power) {
            currentWorldview.power = {};
        }
        currentWorldview.power = JSON.parse(JSON.stringify(power));
        currentStructure.power = JSON.parse(JSON.stringify(power));
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to expand power:', error);
        showToast('完善失败', 'error');
    } finally {
        hideLoading();
    }
}

async function aiFillRaces() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const fields = [
        { id: 'racesCategory', label: '种族分类' },
        { id: 'racesValue', label: '种族价值观' },
        { id: 'racesLifespan', label: '寿命特征' },
        { id: 'racesReproduction', label: '繁衍方式' },
        { id: 'racesConstitution', label: '体质特征' },
        { id: 'racesRelation', label: '种族关系' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善种族族群：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化种族族群...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/races/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                category: document.getElementById('racesCategory').value.trim() || '请生成完整的种族设定',
                value: document.getElementById('racesValue').value.trim() || '请生成种族价值观设定',
                lifespan: document.getElementById('racesLifespan').value.trim() || '',
                reproduction: document.getElementById('racesReproduction').value.trim() || '',
                physique: document.getElementById('racesConstitution').value.trim() || '',
                relation: document.getElementById('racesRelation').value.trim() || '请生成种族关系设定',
            })
        });

        let races;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                races = JSON.parse(jsonMatch[1]);
            } else {
                races = JSON.parse(fullContent);
            }
        } else if (fullContent && typeof fullContent === 'object') {
            races = fullContent;
        } else {
            throw new Error('AI返回数据格式错误');
        }

        // 更新表单字段
        setField('racesCategory', races.category || '');
        setField('racesValue', races.value || '');
        setField('racesLifespan', races.trait?.lifespan || '');
        setField('racesReproduction', races.trait?.reproduction || '');
        setField('racesConstitution', races.trait?.physique || '');
        setField('racesRelation', races.relation || '');

        // 更新本地数据
        if (!currentWorldview.races) {
            currentWorldview.races = {};
        }
        if (!currentWorldview.races.trait) {
            currentWorldview.races.trait = {};
        }
        currentWorldview.races.category = races.category || '';
        currentWorldview.races.value = races.value || '';
        currentWorldview.races.trait.lifespan = races.trait?.lifespan || '';
        currentWorldview.races.trait.reproduction = races.trait?.reproduction || '';
        currentWorldview.races.trait.physique = races.trait?.physique || '';
        currentWorldview.races.relation = races.relation || '';
        currentStructure.races = JSON.parse(JSON.stringify(currentWorldview.races));
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to fill races:', error);
        showToast('补全失败', 'error');
    } finally {
        hideLoading();
    }
}

async function aiFillSociety() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const fields = [
        { id: 'societyGovernment', label: '国家体制' },
        { id: 'societyBureaucracy', label: '官僚体系' },
        { id: 'societySectLevel', label: '门派等级' },
        { id: 'societySectHeritage', label: '传承关系' },
        { id: 'societyMartialFaction', label: '武林帮派' },
        { id: 'societyMartialGuild', label: '商会联盟' },
        { id: 'societyExternal', label: '域外势力' },
        { id: 'societyClassLevel', label: '社会等级' },
        { id: 'societyClassMobility', label: '阶层流动' },
        { id: 'societyCurrencyType', label: '货币类型' },
        { id: 'societyCurrencyRule', label: '货币规则' },
        { id: 'societyResource', label: '资源分布' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善社会结构：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化社会结构...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/society/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                government: document.getElementById('societyGovernment').value.trim() || '请生成国家体制设定',
                bureaucracy: document.getElementById('societyBureaucracy').value.trim() || '',
                sect_level: document.getElementById('societySectLevel').value.trim() || '',
                sect_heritage: document.getElementById('societySectHeritage').value.trim() || '',
                martial_faction: document.getElementById('societyMartialFaction').value.trim() || '',
                martial_guild: document.getElementById('societyMartialGuild').value.trim() || '',
                external: document.getElementById('societyExternal').value.trim() || '请生成域外势力设定',
                class_level: document.getElementById('societyClassLevel').value.trim() || '请生成社会等级设定',
                class_mobility: document.getElementById('societyClassMobility').value.trim() || '',
                currency_type: document.getElementById('societyCurrencyType').value.trim() || '',
                currency_rule: document.getElementById('societyCurrencyRule').value.trim() || '',
                resource: document.getElementById('societyResource').value.trim() || '',
            })
        });
        // console.log(typeof fullContent)
        // console.log(fullContent)
        let society;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                society = JSON.parse(jsonMatch[1]);
            } else {
                society = JSON.parse(fullContent);
            }
        } else {
            society = fullContent;
        }
        
        

        // 更新表单字段
        setField('societyGovernment', society.court?.political_system || '');
        setField('societyBureaucracy', society.court?.bureaucracy || '');
        setField('societySectLevel', society.sect?.levels || '');
        setField('societySectHeritage', society.sect?.relationships || '');
        setField('societyMartialFaction', society.martial?.factions || '');
        setField('societyMartialGuild', society.martial?.alliances || '');
        setField('societyExternal', society.external || '');
        setField('societyClassLevel', society.class?.social_classes || '');
        setField('societyClassMobility', society.class?.mobility || '');
        setField('societyCurrencyType', society.currency?.types || '');
        setField('societyCurrencyRule', society.currency?.rules || '');
        setField('societyResource', society.resource || '');

        // 更新本地数据
        if (!currentWorldview.society) {
            currentWorldview.society = {};
        }
        if (!currentWorldview.society.court) {
            currentWorldview.society.court = {};
        }
        if (!currentWorldview.society.sect) {
            currentWorldview.society.sect = {};
        }
        if (!currentWorldview.society.martial) {
            currentWorldview.society.martial = {};
        }
        if (!currentWorldview.society.class) {
            currentWorldview.society.class = {};
        }
        if (!currentWorldview.society.currency) {
            currentWorldview.society.currency = {};
        }
        currentWorldview.society.court.political_system = society.court?.political_system || '';
        currentWorldview.society.court.bureaucracy = society.court?.bureaucracy || '';
        currentWorldview.society.sect.levels = society.sect?.levels || '';
        currentWorldview.society.sect.relationships = society.sect?.relationships || '';
        currentWorldview.society.martial.factions = society.martial?.factions || '';
        currentWorldview.society.martial.alliances = society.martial?.alliances || '';
        currentWorldview.society.external = society.external || '';
        currentWorldview.society.class.social_classes = society.class?.social_classes || '';
        currentWorldview.society.class.mobility = society.class?.mobility || '';
        currentWorldview.society.currency.types = society.currency?.types || '';
        currentWorldview.society.currency.rules = society.currency?.rules || '';
        currentWorldview.society.resource = society.resource || '';
        currentStructure.society = JSON.parse(JSON.stringify(currentWorldview.society));
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to fill society:', error);
        showToast(error.message || '补全失败', 'error');
    } finally {
        hideLoading();
    }
}

async function aiFillCulture() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const fields = [
        { id: 'cultureFestival', label: '节日庆典' },
        { id: 'cultureRitual', label: '仪式习俗' },
        { id: 'cultureLanguage', label: '语言文字' },
        { id: 'cultureScript', label: '书写系统' },
        { id: 'cultureClothing', label: '服饰风格' },
        { id: 'cultureFood', label: '饮食文化' },
        { id: 'cultureArchitecture', label: '建筑特色' },
        { id: 'cultureTransport', label: '交通方式' },
        { id: 'cultureDeity', label: '神祇信仰' },
        { id: 'cultureReligionOrg', label: '宗教组织' },
        { id: 'cultureFaithDiff', label: '信仰差异' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善文化人文：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化文化人文...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/culture/`, {
            method: 'POST',

            body: JSON.stringify({
                genre: getSelectedGenre(),
                festival: document.getElementById('cultureFestival').value.trim() || '请生成节日庆典设定',
                ritual: document.getElementById('cultureRitual').value.trim() || '',
                language: document.getElementById('cultureLanguage').value.trim() || '请生成语言文字设定',
                script: document.getElementById('cultureScript').value.trim() || '',
                clothing: document.getElementById('cultureClothing').value.trim() || '',
                food: document.getElementById('cultureFood').value.trim() || '',
                architecture: document.getElementById('cultureArchitecture').value.trim() || '',
                transport: document.getElementById('cultureTransport').value.trim() || '',
                deity: document.getElementById('cultureDeity').value.trim() || '请生成宗教信仰设定',
                religion_org: document.getElementById('cultureReligionOrg').value.trim() || '',
                faith_diff: document.getElementById('cultureFaithDiff').value.trim() || '',
            })
        });

        let culture;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                culture = JSON.parse(jsonMatch[1]);
            } else {
                culture = JSON.parse(fullContent);
            }
        } else if (fullContent && typeof fullContent === 'object') {
            culture = fullContent;
        } else {
            throw new Error('AI返回数据格式错误');
        }

        // 更新表单字段
        setField('cultureFestival', culture.custom?.festivals || '');
        setField('cultureRitual', culture.custom?.rituals || '');
        setField('cultureLanguage', culture.language?.languages || '');
        setField('cultureScript', culture.language?.writing_system || '');
        setField('cultureClothing', culture.daily?.clothing || '');
        setField('cultureFood', culture.daily?.food || '');
        setField('cultureArchitecture', culture.daily?.architecture || '');
        setField('cultureTransport', culture.daily?.transportation || '');
        setField('cultureDeity', culture.religion?.deity || '');
        setField('cultureReligionOrg', culture.religion?.organization || '');
        setField('cultureFaithDiff', culture.religion?.faith_diff || '');

        // 更新本地数据
        if (!currentWorldview.culture) {
            currentWorldview.culture = {};
        }
        if (!currentWorldview.culture.custom) {
            currentWorldview.culture.custom = {};
        }
        if (!currentWorldview.culture.language) {
            currentWorldview.culture.language = {};
        }
        if (!currentWorldview.culture.daily) {
            currentWorldview.culture.daily = {};
        }
        if (!currentWorldview.culture.religion) {
            currentWorldview.culture.religion = {};
        }
        currentWorldview.culture.custom.festivals = culture.custom?.festivals || '';
        currentWorldview.culture.custom.rituals = culture.custom?.rituals || '';
        currentWorldview.culture.language.languages = culture.language?.languages || '';
        currentWorldview.culture.language.writing_system = culture.language?.writing_system || '';
        currentWorldview.culture.daily.clothing = culture.daily?.clothing || '';
        currentWorldview.culture.daily.food = culture.daily?.food || '';
        currentWorldview.culture.daily.architecture = culture.daily?.architecture || '';
        currentWorldview.culture.daily.transportation = culture.daily?.transportation || '';
        currentWorldview.culture.religion.deity = culture.religion?.deity || '';
        currentWorldview.culture.religion.organization = culture.religion?.organization || '';
        currentWorldview.culture.religion.faith_diff = culture.religion?.faith_diff || '';
        currentStructure.culture = JSON.parse(JSON.stringify(currentWorldview.culture));
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to fill culture:', error);
        showToast('补全失败', 'error');
    } finally {
        hideLoading();
    }
}

async function aiFillHistory() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const fields = [
        { id: 'historyAncient', label: '上古往事' },
        { id: 'historyModern', label: '近代变故' },
        { id: 'historyCrisis', label: '世界隐患' },
        { id: 'historyDestiny', label: '宿命轨迹' },
        { id: 'historyFuture', label: '未来走向' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善历史进程：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化历史进程...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/history/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                ancient: document.getElementById('historyAncient').value.trim(),
                modern: document.getElementById('historyModern').value.trim(),
                crisis: document.getElementById('historyCrisis').value.trim(),
                destiny: document.getElementById('historyDestiny').value.trim(),
                future: document.getElementById('historyFuture').value.trim(),
            })
        });

        let history;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                history = JSON.parse(jsonMatch[1]);
            } else {
                history = JSON.parse(fullContent);
            }
        } else if (fullContent && typeof fullContent === 'object') {
            history = fullContent;
        } else {
            throw new Error('AI返回数据格式错误');
        }

        const result = history.success && history.data ? history.data.history : history;

        // 更新表单字段
        setField('historyAncient', result.ancient || '');
        setField('historyModern', result.modern || '');
        setField('historyCrisis', result.crisis || '');
        setField('historyDestiny', result.destiny || '');
        setField('historyFuture', result.future || '');

        // 更新本地数据
        if (!currentWorldview.history) {
            currentWorldview.history = {};
        }
        currentWorldview.history.ancient = result.ancient || '';
        currentWorldview.history.modern = result.modern || '';
        currentWorldview.history.crisis = result.crisis || '';
        currentWorldview.history.destiny = result.destiny || '';
        currentWorldview.history.future = result.future || '';
        currentStructure.history = JSON.parse(JSON.stringify(currentWorldview.history));

        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to fill history:', error);
        showToast('优化失败', 'error');
    } finally {
        hideLoading();
    }
}

async function aiFillSpecial() {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const fields = [
        { id: 'specialTaboo', label: '世界禁忌' },
        { id: 'specialSecret', label: '隐藏秘密' },
        { id: 'specialFortune', label: '运势规则' },
        { id: 'specialDestiny', label: '命运类型' },
        { id: 'specialSoul', label: '灵魂规则' },
        { id: 'specialReincarnation', label: '轮回机制' },
        { id: 'specialTransmigration', label: '穿越规则' },
        { id: 'specialSystem', label: '系统规则' },
        { id: 'specialRules', label: '特殊规则' },
    ];

    const emptyFields = [];
    for (const field of fields) {
        const el = document.getElementById(field.id);
        const val = el ? el.value.trim() : '';
        if (!val) emptyFields.push(field.label);
    }

    if (emptyFields.length > 0) {
        showToast(`请先完善特殊规则：${emptyFields.join('、')}`, 'error');
        return;
    }

    showLoading('AI正在优化特殊规则...');

    try {
        const fullContent = await api.streamRequest(`/api/worldview/${worldviewId}/special/`, {
            method: 'POST',
            body: JSON.stringify({
                genre: getSelectedGenre(),
                taboo: document.getElementById('specialTaboo').value.trim(),
                secret: document.getElementById('specialSecret').value.trim(),
                fortune: document.getElementById('specialFortune').value.trim(),
                destiny: document.getElementById('specialDestiny').value.trim(),
                soul: document.getElementById('specialSoul').value.trim(),
                reincarnation: document.getElementById('specialReincarnation').value.trim(),
                transmigration: document.getElementById('specialTransmigration').value.trim(),
                system: document.getElementById('specialSystem').value.trim(),
                rules: document.getElementById('specialRules').value.trim(),
            })
        });

        let special;
        if (typeof fullContent === 'string') {
            let jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*?\})\s*```/s);
            if (jsonMatch) {
                special = JSON.parse(jsonMatch[1]);
            } else {
                special = JSON.parse(fullContent);
            }
        } else if (fullContent && typeof fullContent === 'object') {
            special = fullContent;
        } else {
            throw new Error('AI返回数据格式错误');
        }

        // 更新表单字段
        setField('specialTaboo', special.taboo || '');
        setField('specialSecret', special.secret || '');
        setField('specialFortune', special.fate?.fortune_rules || '');
        setField('specialDestiny', special.fate?.destiny_types || '');
        setField('specialSoul', special.reincarnation?.soul_rules || '');
        setField('specialReincarnation', special.reincarnation?.mechanics || '');
        setField('specialTransmigration', special.transmigration || '');
        setField('specialSystem', special.system || '');
        setField('specialRules', special.rules || '');

        // 更新本地数据
        if (!currentWorldview.special) {
            currentWorldview.special = {};
        }
        if (!currentWorldview.special.fate) {
            currentWorldview.special.fate = {};
        }
        if (!currentWorldview.special.reincarnation) {
            currentWorldview.special.reincarnation = {};
        }
        currentWorldview.special.taboo = special.taboo || '';
        currentWorldview.special.secret = special.secret || '';
        currentWorldview.special.fate.fortune_rules = special.fate?.fortune_rules || '';
        currentWorldview.special.fate.destiny_types = special.fate?.destiny_types || '';
        currentWorldview.special.reincarnation.soul_rules = special.reincarnation?.soul_rules || '';
        currentWorldview.special.reincarnation.mechanics = special.reincarnation?.mechanics || '';
        currentWorldview.special.transmigration = special.transmigration || '';
        currentWorldview.special.system = special.system || '';
        currentWorldview.special.rules = special.rules || '';
        currentStructure.special = JSON.parse(JSON.stringify(currentWorldview.special));
        
        showToast('AI优化完成');
    } catch (error) {
        console.error('Failed to fill special:', error);
        showToast('优化失败', 'error');
    } finally {
        hideLoading();
    }
}











// async function saveStructurePart(partName, data) {
//     try {
//         const response = await api.request(`/api/worldview/${worldviewId}/structure/`, {
//             method: 'PUT',
// 
//             body: JSON.stringify({
//                 structure: { ...currentStructure, [partName]: data }
//             })
//         });
//         
//         if (response.success) {
//             currentStructure[partName] = data;
//         } else {
//             throw new Error(response.message || '保存失败');
//         }
//     } catch (error) {
//         throw error;
//     }
// }



// async function generateWorldOverview() {
//     if (!worldviewId) return;
//     
//     const name = document.getElementById('worldName').value.trim();
//     if (!name) {
//         showToast('请先输入世界名称', 'error');
//         return;
//     }
//     
//     showLoading('AI正在生成世界总览...');
//     
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/generate/overview/`, {
//             method: 'POST',
// 
//             body: JSON.stringify({ 
//                 name: name, 
//                 genre: getSelectedGenre(),
//                 description: document.getElementById('worldOverview').value.trim(),
//                 background: document.getElementById('worldCoreConflict').value.trim()
//             })
//         });
//         
//         if (data.success && data.data) {
//             if (data.data.description) {
//                 document.getElementById('worldOverview').value = data.data.description;
//             }
//             if (data.data.background) {
//                 document.getElementById('worldCoreConflict').value = data.data.background;
//             }
//             showToast('世界总览已生成');
//             updateExpandBtn();
//         }
//     } catch (error) {
//         console.error('Failed to generate overview:', error);
//         showToast('生成失败', 'error');
//     } finally {
//         hideLoading();
//     }
// }




// function renderStructure(structure) {
//     const profileIdentity = document.getElementById('worldIdentity');
//     const profileTone = document.getElementById('worldTone');
    
//     if (profileIdentity) profileIdentity.value = structure.profile?.identity || '';
//     if (profileTone) profileTone.value = structure.profile?.tone || '';

//     const factionsSection = document.getElementById('factionsSection');
//     if (factionsSection) {
//         const factions = structure.factions || [];
//         factionsSection.innerHTML = factions.length > 0 ? factions.map((f, i) => `
//             <div class="border rounded p-3 mb-3">
//                 <div class="d-flex justify-content-between align-items-center mb-2">
//                     <span class="badge bg-success">势力 #${i + 1}</span>
//                 </div>
//                 <div class="mb-2">
//                     <input type="text" class="form-control form-control-sm" placeholder="阵营名称" value="${escapeHtml(f.name || '')}">
//                 </div>
//                 <div class="mb-2">
//                     <input type="text" class="form-control form-control-sm" placeholder="立场 / 世界站队" value="${escapeHtml(f.position || '')}">
//                 </div>
//                 <textarea class="form-control form-control-sm" rows="2" placeholder="阵营理念">${escapeHtml(f.doctrine || '')}</textarea>
//             </div>
//         `).join('') : '<p class="text-muted small">暂无势力数据</p>';
//     }

//     const locationsSection = document.getElementById('locationsSection');
//     if (locationsSection) {
//         const locations = structure.locations || [];
//         locationsSection.innerHTML = locations.length > 0 ? locations.map((l, i) => `
//             <div class="border rounded p-3 mb-3">
//                 <div class="d-flex justify-content-between align-items-center mb-2">
//                     <span class="badge bg-warning text-dark">地点 #${i + 1}</span>
//                 </div>
//                 <div class="mb-2">
//                     <input type="text" class="form-control form-control-sm" placeholder="地点名称" value="${escapeHtml(l.name || '')}">
//                 </div>
//                 <div class="mb-2">
//                     <input type="text" class="form-control form-control-sm" placeholder="地形 / 地貌" value="${escapeHtml(l.terrain || '')}">
//                 </div>
//                 <textarea class="form-control form-control-sm" rows="2" placeholder="地点概述">${escapeHtml(l.summary || '')}</textarea>
//             </div>
//         `).join('') : '<p class="text-muted small">暂无地点数据</p>';
//     }

//     const relationsSection = document.getElementById('relationsSection');
//     if (relationsSection) {
//         const relations = structure.relations || [];
//         const relationTypeLabels = {
//             'alliance': '同盟', 'enemy': '敌对', 'neutral': '中立',
//             'subordinate': '从属', 'trade': '贸易', 'conflict': '冲突',
//             'allied': '友好', 'rivalry': '竞争', 'ancestor': '渊源', 'other': '其他'
//         };
        
//         relationsSection.innerHTML = relations.length > 0 ? relations.map((r, i) => `
//             <div class="border rounded p-3 mb-3">
//                 <div class="d-flex justify-content-between align-items-center mb-2">
//                     <span class="badge bg-info">关系 #${i + 1}</span>
//                     <span class="badge bg-secondary">${relationTypeLabels[r.type] || '其他'}</span>
//                 </div>
//                 <div class="d-flex items-center gap-2 mb-2">
//                     <span class="font-medium">${escapeHtml(r.source || '')}</span>
//                     <i class="fas fa-arrow-right text-muted"></i>
//                     <span class="font-medium">${escapeHtml(r.target || '')}</span>
//                 </div>
//                 <textarea class="form-control form-control-sm" rows="2" placeholder="关系描述">${escapeHtml(r.description || '')}</textarea>
//             </div>
//         `).join('') : '<p class="text-muted small">暂无关系数据</p>';
//     }
// }





// function updateLayerStates() {
//     if (!currentWorldview) return;
// 
//     const layers = ['foundation', 'power', 'society', 'culture', 'history'];
//     layers.forEach(layerKey => {
//         const textarea = document.getElementById(`layer-${layerKey}`);
//         if (textarea && currentWorldview.layers && currentWorldview.layers[layerKey]) {
//             const layerData = currentWorldview.layers[layerKey];
//             textarea.value = typeof layerData === 'object' ? (layerData.content || '') : (layerData || '');
//         }
//     });
// }
// 
// async function generateSingleLayer(layerKey) {
//     if (!worldviewId) return;
//     
//     showLoading(`正在生成${getLayerName(layerKey)}...`);
//     
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/layers/${layerKey}/generate/`, {
//             method: 'POST'
//         });
//         
//         if (data.success && data.data) {
//             const textarea = document.getElementById(`layer-${layerKey}`);
//             if (textarea) {
//                 textarea.value = data.data.content;
//             }
//             showToast(`${getLayerName(layerKey)}生成成功`);
//         }
//     } catch (error) {
//         console.error('Failed to generate layer:', error);
//         showToast('生成失败', 'error');
//     } finally {
//         hideLoading();
//     }
// }
// 
// async function saveSingleLayer(layerKey) {
//     if (!worldviewId) return;
//     const textarea = document.getElementById(`layer-${layerKey}`);
//     if (!textarea) return;
//     const content = textarea.value;
// 
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/layers/${layerKey}/`, {
//             method: 'PUT',
// 
//             body: JSON.stringify({ content })
//         });
// 
//         if (data.success) {
//             showToast(`${getLayerName(layerKey)}保存成功`);
//         }
//     } catch (error) {
//         console.error('Failed to save layer:', error);
//         showToast('保存失败', 'error');
//     }
// }



// function renderEmptyStructure() {
//     currentStructure = {
//         profile: { identity: '', tone: '', summary: '', coreConflict: '' },
//         rules: { summary: '', axioms: [] },
//         foundation: {},
//         power: {},
//         races: {},
//         society: {},
//         culture: {},
//         history: {},
//         special: {},
//         factions: [],
//         locations: [],
//         axioms: []
//     };
//     renderFoundation(currentStructure);
//     renderPower(currentStructure);
//     renderAxioms();
//     renderStructure(currentStructure);
//     renderRaces(currentStructure);
//     renderSociety(currentStructure);
//     renderCulture(currentStructure);
//     renderHistory(currentStructure);
//     renderSpecial(currentStructure);
//     setTimeout(() => initAutoResizeTextareas(), 100);
// }



// function showAddFactionModal() {
//     const modal = document.getElementById('addFactionModal');
//     if (modal) {
//         modal.classList.add('show');
//         document.getElementById('factionNameInput').value = '';
//         document.getElementById('factionPositionInput').value = '';
//         document.getElementById('factionDoctrineInput').value = '';
//     }
// }
// 
// function hideAddFactionModal() {
//     const modal = document.getElementById('addFactionModal');
//     if (modal) {
//         modal.classList.remove('show');
//     }
// }

// async function generateFactionByAI() {
//     const doctrine = document.getElementById('factionDoctrineInput').value.trim();
//     const name = document.getElementById('factionNameInput').value.trim();
//     const position = document.getElementById('factionPositionInput').value.trim();
//     
//     if (!doctrine) {
//         showToast('请先填写阵营理念描述', 'error');
//         return;
//     }
//     
//     showLoading('AI正在生成阵营设定...');
//
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/factions/generate/`, {
//             method: 'POST',
//
//             body: JSON.stringify({ doctrine: doctrine, name: name, position: position })
//         });
//
//         if (data.success) {
//             if (data.data?.name) {
//                 document.getElementById('factionNameInput').value = data.data.name;
//             }
//             if (data.data?.position) {
//                 document.getElementById('factionPositionInput').value = data.data.position;
//             }
//             if (data.data?.doctrine) {
//                 document.getElementById('factionDoctrineInput').value = data.data.doctrine;
//             }
//             showToast('AI生成完成');
//         } else {
//             showToast(data.message || '生成失败，请重试', 'error');
//         }
//     } catch (error) {
//         console.error('Failed to generate faction:', error);
//         showToast('生成失败，请重试', 'error');
//     } finally {
//         hideLoading();
//     }
// }

// function saveNewFaction() {
//     const name = document.getElementById('factionNameInput').value.trim();
//     const position = document.getElementById('factionPositionInput').value.trim();
//     const doctrine = document.getElementById('factionDoctrineInput').value.trim();
//
//     if (!name) {
//         showToast('请输入阵营名称', 'error');
//         return;
//     }
//
//     if (!currentStructure.factions) currentStructure.factions = [];
//     currentStructure.factions.push({ name: name, position: position, doctrine: doctrine });
//     renderStructure(currentStructure);
//     hideAddFactionModal();
//     showToast('势力添加成功');
// }

// function showAddLocationModal() {
//     const modal = document.getElementById('addLocationModal');
//     if (modal) {
//         modal.classList.add('show');
//         document.getElementById('locationNameInput').value = '';
//         document.getElementById('locationTerrainInput').value = '';
//         document.getElementById('locationSummaryInput').value = '';
//     }
// }
// 
// function hideAddLocationModal() {
//     const modal = document.getElementById('addLocationModal');
//     if (modal) {
//         modal.classList.remove('show');
//     }
// }

// async function generateLocationByAI() {
//     const summary = document.getElementById('locationSummaryInput').value.trim();
//     const name = document.getElementById('locationNameInput').value.trim();
//     const terrain = document.getElementById('locationTerrainInput').value.trim();
//
//     if (!summary) {
//         showToast('请先填写地点概述描述', 'error');
//         return;
//     }
//     
//     showLoading('AI正在生成地点设定...');
//
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/locations/generate/`, {
//             method: 'POST',
//
//             body: JSON.stringify({ summary: summary, name: name, terrain: terrain })
//         });
//
//         if (data.success) {
//             if (data.data?.name) {
//                 document.getElementById('locationNameInput').value = data.data.name;
//             }
//             if (data.data?.terrain) {
//                 document.getElementById('locationTerrainInput').value = data.data.terrain;
//             }
//             if (data.data?.summary) {
//                 document.getElementById('locationSummaryInput').value = data.data.summary;
//             }
//             showToast('AI生成完成');
//         } else {
//             showToast(data.message || '生成失败，请重试', 'error');
//         }
//     } catch (error) {
//         console.error('Failed to generate location:', error);
//         showToast('生成失败，请重试', 'error');
//     } finally {
//         hideLoading();
//     }
// }

// function saveNewLocation() {
//     const name = document.getElementById('locationNameInput').value.trim();
//     const terrain = document.getElementById('locationTerrainInput').value.trim();
//     const summary = document.getElementById('locationSummaryInput').value.trim();
//
//     if (!name) {
//         showToast('请输入地点名称', 'error');
//         return;
//     }
//
//     if (!currentStructure.locations) currentStructure.locations = [];
//     currentStructure.locations.push({ name: name, terrain: terrain, summary: summary });
//     renderStructure(currentStructure);
//     hideAddLocationModal();
//     showToast('地点添加成功');
// }

// function showAddRelationModal() {
//     const modal = document.getElementById('addRelationModal');
//     if (modal) {
//         modal.classList.add('show');
//         document.getElementById('relationTypeInput').value = 'neutral';
//         document.getElementById('relationDescriptionInput').value = '';
//         populateFactionSelects();
//     }
// }
// 
// function populateFactionSelects() {
//     const sourceSelect = document.getElementById('relationSourceInput');
//     const targetSelect = document.getElementById('relationTargetInput');
//     const factions = currentStructure.factions || [];
//     
//     sourceSelect.innerHTML = '<option value="">请选择源势力</option>';
//     targetSelect.innerHTML = '<option value="">请选择目标势力</option>';
//     
//     factions.forEach(faction => {
//         const option1 = document.createElement('option');
//         option1.value = faction.name;
//         option1.textContent = faction.name;
//         sourceSelect.appendChild(option1);
//         
//         const option2 = document.createElement('option');
//         option2.value = faction.name;
//         option2.textContent = faction.name;
//         targetSelect.appendChild(option2);
//     });
// }
// 
// function hideAddRelationModal() {
//     const modal = document.getElementById('addRelationModal');
//     if (modal) {
//         modal.classList.remove('show');
//     }
// }

// function saveNewRelation() {
//     const source = document.getElementById('relationSourceInput').value.trim();
//     const type = document.getElementById('relationTypeInput').value;
//     const target = document.getElementById('relationTargetInput').value.trim();
//     const description = document.getElementById('relationDescriptionInput').value.trim();
//
//     if (!source || !target) {
//         showToast('请填写源实体和目标实体', 'error');
//         return;
//     }
//
//     if (!currentStructure.relations) currentStructure.relations = [];
//     currentStructure.relations.push({ 
//         source: source, 
//         type: type, 
//         target: target, 
//         description: description 
//     });
//     renderStructure(currentStructure);
//     hideAddRelationModal();
//     showToast('关系添加成功');
// }

// async function generateRelationByAI() {
//     const source = document.getElementById('relationSourceInput').value.trim();
//     const target = document.getElementById('relationTargetInput').value.trim();
//     const relationType = document.getElementById('relationTypeInput').value;
//     
//     const factions = currentStructure.factions || [];
//     if (factions.length < 2) {
//         showToast(`需要至少2个势力才能使用AI生成（当前${factions.length}个）`, 'error');
//         return;
//     }
//
//     showLoading('AI正在生成关系描述...');
//
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/relations/generate/`, {
//             method: 'POST',
//
//             body: JSON.stringify({ source: source, target: target, type: relationType })
//         });
//
//         if (data.success) {
//             if (data.data?.description) {
//                 document.getElementById('relationDescriptionInput').value = data.data.description;
//             }
//             showToast('AI生成完成');
//         } else {
//             showToast(data.message || '生成失败，请重试', 'error');
//         }
//     } catch (error) {
//         console.error('Failed to generate relation:', error);
//         showToast('生成失败，请重试', 'error');
//     } finally {
//         hideLoading();
//     }
// }



// async function saveAxioms() {
//     if (!worldviewId) return;
// 
//     const normalizedAxioms = axioms.filter(a => a.trim());
// 
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/structure/`, {
//             method: 'PUT',
// 
//             body: JSON.stringify({
//                 structure: { ...currentStructure, axioms: normalizedAxioms }
//             })
//         });
// 
//         if (data.success) {
//             showToast('公理已保存');
//         } else {
//             throw new Error(data.message || '保存失败');
//         }
//     } catch (error) {
//         console.error('Save failed:', error);
//         showToast('保存失败', 'error');
//     }
// }

// async function deleteWorld() {
//     if (!worldviewId) return;
// 
//     if (!confirm('确定要删除这个世界观吗？此操作无法撤销。')) return;
// 
//     try {
//         const data = await api.request(`/api/worldview/${worldviewId}/delete/`, {
//             method: 'DELETE'
//         });
// 
//         if (data.success) {
//             if (new URLSearchParams(window.location.search).get("project_id")) {
//                 window.location.href = `/project/${new URLSearchParams(window.location.search).get("project_id")}/`;
//             } else {
//                 window.location.href = '/project/';
//             }
//         } else {
//             throw new Error(data.message || '删除失败');
//         }
//     } catch (error) {
//         console.error('Delete failed:', error);
//         showToast('删除失败', 'error');
//     }
// }

