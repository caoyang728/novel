// 角色库管理脚本
let currentProjectId = null;
let characters = [];
let filteredCharacters = [];
let allFactions = [];  // 所有势力列表
let currentRelationships = [];  // 当前编辑的角色关系
let currentExperiences = [];  // 当前编辑的角色经历
let searchDebounceTimer = null;  // 搜索防抖计时器

// 角色字段统一配置：API 字段名 → { suffix: 表单 ID 后缀, label: 中文标签 }
// suffix 为 null 表示该字段无对应表单元素（如 relationships/experiences 有自定义渲染）
// 注意：tagline 使用 suffix 'Tags'，但 AI 返回的是 tags，applyPolishResult 中有兼容 shim
const CHARACTER_FIELDS = {
    'gender':        { suffix: 'Gender',        label: '性别' },
    'role_type':     { suffix: 'Role',          label: '角色定位' },
    'age':           { suffix: 'Age',           label: '年龄' },
    'identity':      { suffix: 'Identity',      label: '身份/称号' },
    'personality':   { suffix: 'Personality',   label: '性格特点' },
    'strengths':     { suffix: 'Strengths',     label: '优点' },
    'flaws':         { suffix: 'Flaws',         label: '缺点' },
    'obsession':     { suffix: 'Obsession',     label: '执念/软肋' },
    'motivation':    { suffix: 'Motivation',    label: '核心动机' },
    'appearance':    { suffix: 'Appearance',    label: '外貌特征' },
    'faction':       { suffix: 'Faction',       label: '势力/阵营' },
    'abilities':     { suffix: 'Abilities',     label: '能力' },
    'taboos':        { suffix: 'Taboos',        label: '禁忌' },
    'dark_history':  { suffix: 'DarkHistory',   label: '过往黑历史' },
    'secrets':       { suffix: 'Secrets',       label: '秘密' },
    'backstory':     { suffix: 'Background',    label: '背景故事' },
    'development':   { suffix: 'Development',   label: '成长轨迹' },
    'weaknesses':    { suffix: 'Weaknesses',    label: '弱点代价' },
    'tagline':       { suffix: 'Tags',          label: '标签' },
    'relationships': { suffix: null,            label: '人际关系' },
    'experiences':   { suffix: null,            label: '经历' },
};

// 从 CHARACTER_FIELDS 派生：API 字段名 → 表单元素 ID 后缀
const CHARACTER_FIELD_MAP = {};
for (const [key, cfg] of Object.entries(CHARACTER_FIELDS)) {
    if (cfg.suffix) CHARACTER_FIELD_MAP[key] = cfg.suffix;
}

// 从 CHARACTER_FIELDS 派生：API 字段名 → 中文标签
const FIELD_LABELS = {};
for (const [key, cfg] of Object.entries(CHARACTER_FIELDS)) {
    FIELD_LABELS[key] = cfg.label;
}

// ==================== 通用工具函数 ====================

/**
 * 初始化字符计数显示（name 字段 100 字符限制，textarea 字段 5000 字符限制）
 */
function initCharCounts() {
    // name 字段计数
    ['createName', 'aiGeneratedName', 'editName'].forEach(id => {
        const el = document.getElementById(id);
        const countEl = document.getElementById(id + 'Count');
        if (!el || !countEl) return;
        const update = () => {
            const len = el.value.length;
            const max = 100;
            countEl.textContent = `${len}/${max}`;
            countEl.className = 'char-count-inline' + (len > max * 0.8 ? (len >= max ? ' over' : ' warn') : '');
        };
        el.addEventListener('input', update);
        update();
    });
}

/**
 * 初始化长文本 textarea 的字符计数
 * @param {string} id - textarea 元素 ID
 * @param {number} max - 最大字符数（默认 5000）
 */
function initTextareaCount(id, max = 5000) {
    const el = document.getElementById(id);
    if (!el) return;
    // 创建或复用计数元素
    let countEl = el.parentElement.querySelector('.char-count-inline');
    if (!countEl) {
        countEl = document.createElement('span');
        countEl.className = 'char-count-inline';
        el.parentElement.appendChild(countEl);
    }
    const update = () => {
        const len = el.value.length;
        countEl.textContent = `${len}/${max}`;
        countEl.className = 'char-count-inline' + (len > max * 0.8 ? (len >= max ? ' over' : ' warn') : '');
    };
    el.addEventListener('input', update);
    update();
}

/**
 * 设置按钮加载/空闲状态
 * @param {string|HTMLElement} btn - 按钮 ID 或 DOM 元素
 * @param {boolean} loading - true=加载中, false=恢复
 * @param {string} loadingText - 加载时显示的文本
 * @param {string} [normalHtml] - 恢复时的原始 HTML（不传则用 dataset 缓存）
 */
function setCharBtnLoading(btn, loading, loadingText, normalHtml) {
    const el = typeof btn === 'string' ? document.getElementById(btn) : btn;
    if (!el) return;
    el.disabled = loading;
    if (loading) {
        el.dataset.originalHtml = el.innerHTML;
        el.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + (loadingText || '处理中...');
    } else {
        el.innerHTML = normalHtml || el.dataset.originalHtml || el.innerHTML;
    }
}

/**
 * 利用 CHARACTER_FIELD_MAP 批量清空表单字段
 */
function clearFormFields(prefix, selectDefaults = {}) {
    for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
        const el = document.getElementById(prefix + suffix);
        if (el) {
            if (el.tagName === 'SELECT') {
                el.value = selectDefaults[key] || '';
            } else {
                el.value = '';
            }
        }
    }
    const nameEl = document.getElementById(prefix + 'Name');
    if (nameEl) nameEl.value = '';
}

/**
 * 利用 CHARACTER_FIELD_MAP 批量设置表单字段
 */
function setFormFields(prefix, values, fieldMapping = {}) {
    for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
        const el = document.getElementById(prefix + suffix);
        if (el) {
            const mappedKey = fieldMapping[key] || key;
            el.value = values[mappedKey] !== undefined ? values[mappedKey] : (values[key] || '');
        }
    }
    const nameEl = document.getElementById(prefix + 'Name');
    if (nameEl) nameEl.value = values.name || '';
}

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    showLoading('加载中...');
    loadRelationshipTypes();
    initPage();
    setupCreateFormValidation();
    setupEventListeners();
});

function initPage() {
    // 从URL查询参数获取项目ID
    const urlParams = new URLSearchParams(window.location.search);
    const rawProjectId = urlParams.get('project_id');

    // 校验 project_id 为有效数字
    if (rawProjectId && /^\d+$/.test(rawProjectId)) {
        currentProjectId = rawProjectId;
    } else {
        currentProjectId = null;
    }

    initBackToProjectButton('#backBtn');

    // 默认选中"全部角色"
    const roleFilter = document.getElementById('roleFilter');
    if (roleFilter) {
        roleFilter.value = '';
    }

    if (currentProjectId) {
        loadProjectInfo(currentProjectId);
        loadCharacters();
    } else {
        showEmptyState();
    }
}

async function loadCharacters() {
    if (!currentProjectId) return;

    showLoading('加载角色列表...');

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/characters/`);
        if (!data) return;

        if (data.success) {
            characters = data.characters;
            updateRoleFilterCounts();
            updateFactionFilterOptions();
            // 重新应用当前筛选条件，而非直接显示全部
            filterCharacters();
        }
    } catch (error) {
        console.error('加载角色失败:', error);
        showError('加载角色失败');
    } finally {
        hideLoading();
    }
}

/**
 * 更新角色定位筛选下拉框的统计数字
 */
function updateRoleFilterCounts() {
    const activeChars = characters.filter(c => !c.is_deleted);
    const total = activeChars.length;

    // 按角色定位统计
    const roleCounts = {};
    activeChars.forEach(c => {
        const role = c.role_type || '未知';
        roleCounts[role] = (roleCounts[role] || 0) + 1;
    });

    const roleFilter = document.getElementById('roleFilter');
    if (!roleFilter) return;

    // 更新「全部角色」
    const allOption = roleFilter.querySelector('option[value=""]');
    if (allOption) allOption.textContent = `全部角色 (${total})`;

    // 更新各角色定位选项
    ['主角', '反派', '配角', '路人'].forEach(role => {
        const option = roleFilter.querySelector(`option[value="${role}"]`);
        if (option) {
            const count = roleCounts[role] || 0;
            option.textContent = `${role} (${count})`;
        }
    });
}

function updateFactionFilterOptions() {
    // 收集所有不重复的势力并统计数量（仅统计未删除角色）
    const activeChars = characters.filter(c => !c.is_deleted);
    const factionCounts = {};
    activeChars.forEach(c => {
        if (c.faction) {
            c.faction.split(',').forEach(f => {
                const trimmed = f.trim();
                if (trimmed) {
                    factionCounts[trimmed] = (factionCounts[trimmed] || 0) + 1;
                }
            });
        }
    });

    allFactions = Object.keys(factionCounts).sort();

    const factionFilter = document.getElementById('factionFilter');
    const currentValue = factionFilter.value;

    factionFilter.innerHTML = `<option value="">全部势力 (${activeChars.length})</option>`;
    allFactions.forEach(f => {
        const option = document.createElement('option');
        option.value = f;
        option.textContent = `${f} (${factionCounts[f]})`;
        factionFilter.appendChild(option);
    });

    // 恢复之前的选中值
    if (currentValue && allFactions.includes(currentValue)) {
        factionFilter.value = currentValue;
    }
}

function filterCharacters() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(_doFilterCharacters, 200);
}

function _doFilterCharacters() {
    const searchText = document.getElementById('searchInput').value.toLowerCase().trim();
    const roleFilter = document.getElementById('roleFilter').value;
    const factionFilter = document.getElementById('factionFilter').value;

    filteredCharacters = characters.filter(c => {
        const matchName = !searchText || c.name.toLowerCase().includes(searchText);
        const matchRole = !roleFilter || c.role_type === roleFilter;
        
        // 支持多阵营匹配
        let matchFaction = true;
        if (factionFilter) {
            const characterFactions = c.faction ? c.faction.split(',').map(f => f.trim()) : [];
            matchFaction = characterFactions.some(f => f === factionFilter);
        }
        
        return matchName && matchRole && matchFaction;
    });

    // 已删除角色排在最后
    filteredCharacters.sort((a, b) => {
        if (a.is_deleted !== b.is_deleted) return a.is_deleted ? 1 : -1;
        return 0;
    });

    renderCharacterList();
}

function renderCharacterList() {
    const listContainer = document.getElementById('characterList');
    const empty = document.getElementById('emptyState');

    const activeChars = filteredCharacters.filter(c => c.is_deleted !== true);
    const deletedChars = filteredCharacters.filter(c => c.is_deleted === true);

    if (filteredCharacters.length === 0) {
        listContainer.style.display = 'none';
        if (characters.length === 0) {
            empty.querySelector('h3').textContent = '暂无角色';
            empty.querySelector('p').textContent = '点击右上角「创建角色」按钮开始添加';
        } else {
            empty.querySelector('h3').textContent = '没有找到匹配的角色';
            empty.querySelector('p').textContent = '尝试调整搜索条件';
        }
        empty.style.display = 'flex';
        return;
    }

    empty.style.display = 'none';
    listContainer.style.display = 'grid';

    function renderCharCard(c) {
        const factions = c.faction ? c.faction.split(',').map(f => f.trim()).filter(f => f) : [];
        const isDeleted = c.is_deleted === true;
        return `
        <div class="char-item${isDeleted ? ' char-item-deleted' : ''}" data-char-id="${c.id}">
            <div class="char-item-header">
                <div class="char-item-avatar">${escapeHtml(c.name.charAt(0))}</div>
                <div class="char-item-info">
                    <h4>${escapeHtml(c.name)}</h4>
                    <div class="char-item-tags">
                        ${isDeleted ? '<span class="deleted-tag">已删除</span>' : ''}
                        <span class="role-tag">${escapeHtml(c.role_type)}</span>
                        ${factions.map(f => `<span class="faction-tag">${escapeHtml(f)}</span>`).join('')}
                    </div>
                </div>
            </div>
            ${isDeleted ? `<div class="char-item-actions"><button class="btn-restore" data-restore-id="${c.id}"><i class="fas fa-undo"></i> 恢复</button></div>` : ''}
        </div>`;
    }

    let html = '';
    if (activeChars.length > 0) {
        html += activeChars.map(renderCharCard).join('');
    }
    if (deletedChars.length > 0) {
        html += `<div class="deleted-section">
            <div class="deleted-section-header">
                <i class="fas fa-trash-alt"></i>
                <span>已删除角色</span>
                <span class="deleted-section-count">${deletedChars.length}</span>
            </div>
            <div class="deleted-section-grid">
                ${deletedChars.map(renderCharCard).join('')}
            </div>
        </div>`;
    }
    listContainer.innerHTML = html;
}

function showEmptyState() {
    document.getElementById('characterList').style.display = 'none';
    document.getElementById('emptyState').style.display = 'flex';
}

// ============ 恢复已删除角色 ============
async function restoreCharacter(id) {
    try {
        const data = await api.put(`/api/projects/${currentProjectId}/characters/${id}/`, {
            action: 'restore'
        });
        if (!data) return;

        if (data.success) {
            showSuccess('角色已恢复');
            loadCharacters();
        } else {
            showError(data.error || '恢复失败');
        }
    } catch (error) {
        showError('网络错误');
    }
}

// ============ 创建角色 ============
function openCreateDialog() {
    clearFormFields('create', { 'role_type': '配角', 'gender': '未知' });
    document.getElementById('createRelationships').value = '';
    
    // 清空AI生成相关字段
    document.getElementById('aiDescription').value = '';
    document.getElementById('batchDescription').value = '';
    document.getElementById('aiDescriptionSection').style.display = '';
    document.getElementById('aiGeneratedContent').style.display = 'none';
    document.getElementById('batchDescriptionSection').style.display = '';
    document.getElementById('batchGeneratedContent').style.display = 'none';
    currentAiGenerated = null;
    currentBatchGenerated = [];

    // 初始化为手动创建标签页并验证按钮状态
    switchCreateTab('manual');

    // 显示弹窗并锁定背景滚动
    lockScroll();
    document.getElementById('createDialog').classList.add('show');
}

function setupCreateFormValidation() {
    document.getElementById('createName').addEventListener('input', validateManualCreateButtons);
    document.getElementById('aiDescription').addEventListener('input', validateAiGenerateButtons);
    document.getElementById('batchDescription').addEventListener('input', validateBatchCreateButtons);
}

function setupEventListeners() {
    // 初始化字符计数
    initCharCounts();

    // 搜索/筛选事件
    const searchInput = document.getElementById('searchInput');
    const searchClearBtn = document.getElementById('searchClearBtn');
    const roleFilter = document.getElementById('roleFilter');
    const factionFilter = document.getElementById('factionFilter');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterCharacters();
            if (searchClearBtn) {
                searchClearBtn.style.display = this.value ? 'flex' : 'none';
            }
        });
    }
    if (searchClearBtn) {
        searchClearBtn.addEventListener('click', function() {
            searchInput.value = '';
            searchInput.focus();
            this.style.display = 'none';
            filterCharacters();
        });
    }
    if (roleFilter) roleFilter.addEventListener('change', filterCharacters);
    if (factionFilter) factionFilter.addEventListener('change', filterCharacters);

    // 按钮事件
    const checkBtn = document.getElementById('checkBtn');
    if (checkBtn) checkBtn.addEventListener('click', checkAllCharacters);
    const createCharBtn = document.getElementById('createCharBtn');
    if (createCharBtn) createCharBtn.addEventListener('click', openCreateDialog);

    // 势力字段归一化
    document.querySelectorAll('[id$="Faction"]').forEach(el => {
        el.addEventListener('blur', function() { normalizeFactionInputField(this); });
    });

    // 角色列表事件委托（替代内联 onclick）
    const charList = document.getElementById('characterList');
    if (charList) {
        charList.addEventListener('click', function(e) {
            // 恢复按钮
            const restoreBtn = e.target.closest('.btn-restore');
            if (restoreBtn) {
                e.stopPropagation();
                const restoreId = restoreBtn.dataset.restoreId;
                if (restoreId) restoreCharacter(parseInt(restoreId));
                return;
            }
            // 角色卡片点击 → 打开编辑
            const charItem = e.target.closest('.char-item');
            if (charItem && !charItem.classList.contains('char-item-deleted')) {
                const charId = charItem.dataset.charId;
                if (charId) openEditDialog(parseInt(charId));
            }
        });
    }
}

function closeCreateDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('createDialog').classList.remove('show');
    unlockScroll();
    // 清空AI生成的内容
    document.getElementById('aiDescription').value = '';
    document.getElementById('aiDescriptionSection').style.display = '';
    document.getElementById('aiGeneratedContent').style.display = 'none';
    currentAiGenerated = null;
    // 清空批量创建的内容
    document.getElementById('batchDescription').value = '';
    document.getElementById('batchDescriptionSection').style.display = '';
    document.getElementById('batchGeneratedContent').style.display = 'none';
    currentBatchGenerated = [];
    // 切换回手动创建标签
    switchCreateTab('manual');
}

function switchCreateTab(tab) {
    document.querySelectorAll('.create-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#createDialog .tab-content').forEach(c => c.classList.remove('active'));

    const aiActionBtn = document.getElementById('aiActionBtn');
    const saveCreateBtn = document.getElementById('saveCreateBtn');

    if (tab === 'manual') {
        document.querySelector('.create-tab[data-tab="manual"]').classList.add('active');
        document.getElementById('manualCreateTab').classList.add('active');
        aiActionBtn.style.display = '';
        aiActionBtn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
        aiActionBtn.dataset.action = 'polish';
        saveCreateBtn.style.display = '';
        saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
        validateManualCreateButtons();
    } else if (tab === 'ai') {
        document.querySelector('.create-tab[data-tab="ai"]').classList.add('active');
        document.getElementById('aiCreateTab').classList.add('active');
        if (currentAiGenerated && Object.keys(currentAiGenerated).length > 0) {
            aiActionBtn.style.display = 'none';
            saveCreateBtn.style.display = '';
            saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
        } else {
            aiActionBtn.style.display = '';
            aiActionBtn.innerHTML = '<i class="fas fa-magic"></i> AI 生成';
            saveCreateBtn.style.display = 'none';
        }
        aiActionBtn.dataset.action = 'generate';
        validateAiGenerateButtons();
    } else if (tab === 'batch') {
        document.querySelector('.create-tab[data-tab="batch"]').classList.add('active');
        document.getElementById('batchCreateTab').classList.add('active');
        if (currentBatchGenerated && currentBatchGenerated.length > 0) {
            aiActionBtn.style.display = 'none';
            saveCreateBtn.style.display = '';
            saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 批量保存';
        } else {
            aiActionBtn.style.display = '';
            aiActionBtn.innerHTML = '<i class="fas fa-magic"></i> 批量生成';
            saveCreateBtn.style.display = 'none';
        }
        aiActionBtn.dataset.action = 'batch';
        validateBatchCreateButtons();
    }
}

function handleAiAction() {
    const action = document.getElementById('aiActionBtn').dataset.action;
    if (action === 'polish') {
        polishCharacter();
    } else if (action === 'generate') {
        generateCharacterPreview();
    } else if (action === 'batch') {
        generateBatchCharacters();
    }
}

function validateManualCreateButtons() {
    const aiActionBtn = document.getElementById('aiActionBtn');
    const saveCreateBtn = document.getElementById('saveCreateBtn');
    const name = document.getElementById('createName').value.trim();
    
    aiActionBtn.disabled = !name;
    saveCreateBtn.disabled = !name;
}

function validateAiGenerateButtons() {
    const aiActionBtn = document.getElementById('aiActionBtn');
    const saveCreateBtn = document.getElementById('saveCreateBtn');
    const description = document.getElementById('aiDescription').value.trim();
    
    aiActionBtn.disabled = !description;
    saveCreateBtn.disabled = !currentAiGenerated;
}

function validateBatchCreateButtons() {
    const aiActionBtn = document.getElementById('aiActionBtn');
    const saveCreateBtn = document.getElementById('saveCreateBtn');
    const description = document.getElementById('batchDescription').value.trim();
    
    aiActionBtn.disabled = !description;
    
    const hasSelected = currentBatchGenerated && currentBatchGenerated.some(c => c.selected);
    saveCreateBtn.disabled = !hasSelected;
}

async function submitCharacter() {
    const activeTab = document.querySelector('.create-tab.active');
    const tabType = activeTab ? activeTab.dataset.tab : 'manual';
    
    if (tabType === 'manual') {
        await createCharacter();
    } else if (tabType === 'ai') {
        await saveAiGeneratedCharacter();
    } else if (tabType === 'batch') {
        await saveBatchCharacters();
    }
}

async function createCharacter() {
    const name = document.getElementById('createName').value.trim();

    if (!name) {
        showError('请输入角色名称');
        return;
    }

    setCharBtnLoading('saveCreateBtn', true, '创建中...');

    try {
        const bodyData = collectCharacterFields('create');
        bodyData.relationships = document.getElementById('createRelationships').value;

        const data = await api.post(`/api/projects/${currentProjectId}/characters/`, bodyData);
        if (!data) { setCharBtnLoading('saveCreateBtn', false, null, '<i class="fas fa-save"></i> 保存角色'); return; }

        if (data.success) {
            showSuccess('角色创建成功');
            closeCreateDialog();
            loadCharacters();
        } else {
            if (data.error_type === 'duplicate') {
                showError('角色名称已存在');
            } else {
                showError(data.error || '创建失败');
            }
        }
    } catch (error) {
        showError('网络错误');
    } finally {
        setCharBtnLoading('saveCreateBtn', false, null, '<i class="fas fa-save"></i> 保存角色');
    }
}

// ============ AI生成角色预览（流式） ============
let currentAiGenerated = null;

async function generateCharacterPreview() {
    const description = document.getElementById('aiDescription').value.trim();

    if (!description) {
        showError('请输入角色描述');
        return;
    }

    setCharBtnLoading('aiActionBtn', true, '生成中...');
    document.getElementById('saveCreateBtn').disabled = true;

    // 显示生成内容区域并清空，隐藏描述输入区
    document.getElementById('aiDescriptionSection').style.display = 'none';
    document.getElementById('aiGeneratedContent').style.display = 'block';
    clearAiGeneratedFields();

    showLoading('正在生成角色...');

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/generate/`, {
            requirement: description
        });

        hideLoading();
        if (!data || !data.success) {
            showError(data?.error || '生成失败');
            return;
        }

        const resultStr = data.data;
        let result = extractJsonFromString(resultStr);
        if (Array.isArray(result) && result.length > 0) {
            result = result[0];
        }
        currentAiGenerated = result;
        displayAiGeneratedCharacter(currentAiGenerated);
        document.getElementById('aiActionBtn').style.display = 'none';
        const saveCreateBtn = document.getElementById('saveCreateBtn');
        saveCreateBtn.style.display = '';
        saveCreateBtn.disabled = false;
        showSuccess('角色生成完成，请确认后保存');
    } catch (error) {
        hideLoading();
        console.error('生成角色失败:', error);
        showError(error.message || '网络错误，请重试');
    } finally {
        const redoHtml = '<i class="fas fa-redo"></i> AI 重新生成';
        const magicHtml = '<i class="fas fa-magic"></i> AI 生成';
        const hasContent = currentAiGenerated && Object.keys(currentAiGenerated).length > 0;
        setCharBtnLoading('aiActionBtn', false, null, hasContent ? redoHtml : magicHtml);
    }
}

function clearAiGeneratedFields() {
    clearFormFields('aiGenerated');
}

/**
 * 归一化 role_type 值，确保匹配 select 选项
 */
function normalizeRoleType(val) {
    if (!val) return '配角';
    const trimmed = String(val).trim();
    const ROLE_MAP = {
        '主角': '主角', '主人公': '主角', '男主': '主角', '女主': '主角',
        'protagonist': '主角', 'main': '主角', 'hero': '主角', 'heroine': '主角',
        '反派': '反派', '恶人': '反派', '对手': '反派',
        'villain': '反派', 'antagonist': '反派', 'enemy': '反派',
        '配角': '配角', 'supporting': '配角', 'side': '配角',
        '路人': '路人', '龙套': '路人', 'npc': '路人', 'extra': '路人',
    };
    return ROLE_MAP[trimmed] || ROLE_MAP[trimmed.toLowerCase()] || '配角';
}

function displayAiGeneratedCharacter(charData) {
    document.getElementById('aiGeneratedContent').style.display = 'block';

    // 兼容 shim：AI 返回 tags，模型字段名为 tagline
    if (charData.tags !== undefined && charData.tagline === undefined) {
        charData.tagline = charData.tags;
    }
    // 兼容 shim：AI 可能返回 role 而不是 role_type
    if (charData.role !== undefined && !charData.role_type) {
        charData.role_type = charData.role;
    }
    // 归一化 role_type 值
    if (charData.role_type) {
        charData.role_type = normalizeRoleType(charData.role_type);
    }

    // 构造统一值对象
    const values = {};
    for (const key of Object.keys(CHARACTER_FIELD_MAP)) {
        values[key] = charData[key] || '';
    }
    values.name = charData.name || '';
    // 默认值
    if (!values.role_type) values.role_type = '配角';

    setFormFields('aiGenerated', values);
}

async function saveAiGeneratedCharacter() {
    const name = document.getElementById('aiGeneratedName').value.trim();

    if (!name) {
        showError('请输入角色名称');
        return;
    }

    setCharBtnLoading('saveCreateBtn', true, '保存中...');

    try {
        // 收集 relationships（LLM 可能返回对象数组或字符串）
        let relationships = [];
        if (currentAiGenerated && currentAiGenerated.relationships) {
            relationships = parseRelationshipsFromLLM(currentAiGenerated.relationships);
        }

        const bodyData = collectCharacterFields('aiGenerated');
        bodyData.relationships = relationships;

        const data = await api.post(`/api/projects/${currentProjectId}/characters/`, bodyData);
        if (!data) { setCharBtnLoading('saveCreateBtn', false, null, '<i class="fas fa-save"></i> 保存角色'); return; }

        if (data.success) {
            showSuccess('角色保存成功');
            closeCreateDialog();
            loadCharacters();
        } else {
            if (data.error_type === 'duplicate') {
                showError('角色名称已存在');
            } else {
                showError(data.error || '保存失败');
            }
        }
    } catch (error) {
        console.error('保存角色失败:', error);
        showError('网络错误');
    } finally {
        setCharBtnLoading('saveCreateBtn', false, null, '<i class="fas fa-save"></i> 保存角色');
    }
}

// ============ 批量创建角色 ============
let currentBatchGenerated = [];

async function generateBatchCharacters() {
    const description = document.getElementById('batchDescription').value.trim();

    if (!description) {
        showError('请输入角色描述');
        return;
    }

    setCharBtnLoading('aiActionBtn', true, '生成中...');
    document.getElementById('saveCreateBtn').disabled = true;

    document.getElementById('batchGeneratedContent').style.display = 'none';
    document.getElementById('batchCharactersList').innerHTML = '';
    showLoading('正在生成角色...');
    currentBatchGenerated = [];

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/generate/`, {
            requirement: description,
            is_batch: true
        });

        hideLoading();
        if (!data || !data.success) {
            showError(data?.error || '生成失败');
            return;
        }

        const resultStr = data.data;
        let results = extractJsonFromString(resultStr);
        if (Array.isArray(results)) {
            currentBatchGenerated = results.map((char, index) => {
                // 兼容 shim：AI 返回 tags/role 而非 tagline/role_type
                if (char.tags !== undefined && char.tagline === undefined) char.tagline = char.tags;
                if (char.role !== undefined && !char.role_type) char.role_type = char.role;
                if (char.role_type) char.role_type = normalizeRoleType(char.role_type);
                return {
                    ...char,
                    selected: true,
                    index: index
                };
            });
            renderBatchCharacters();
            document.getElementById('batchDescriptionSection').style.display = 'none';
            document.getElementById('batchGeneratedContent').style.display = 'block';
            document.getElementById('aiActionBtn').style.display = 'none';
            document.getElementById('saveCreateBtn').style.display = '';
            validateBatchCreateButtons();
            showSuccess(`成功生成 ${currentBatchGenerated.length} 个角色`);
        } else {
            showError('生成失败，格式错误');
        }
    } catch (error) {
        hideLoading();
        console.error('批量生成角色失败:', error);
        showError(error.message || '网络错误，请重试');
    } finally {
        const redoHtml = '<i class="fas fa-redo"></i> AI 重新生成';
        const magicHtml = '<i class="fas fa-magic"></i> 批量生成';
        const hasContent = currentBatchGenerated && currentBatchGenerated.length > 0;
        setCharBtnLoading('aiActionBtn', false, null, hasContent ? redoHtml : magicHtml);
    }
}

function renderBatchCharacters() {
    const container = document.getElementById('batchCharactersList');
    if (!container || !currentBatchGenerated) return;

    container.innerHTML = currentBatchGenerated.map((char, index) => `
        <div class="batch-character-item" data-index="${index}">
            <label class="batch-character-checkbox">
                <input type="checkbox" ${char.selected ? 'checked' : ''} 
                    onchange="toggleBatchCharacterSelection(${index})">
            </label>
            <div class="batch-character-content">
                <div class="batch-character-header">
                    <span class="batch-character-name">${escapeHtml(char.name || '未命名')}</span>
                    <span class="batch-character-role">${escapeHtml(char.role_type || '配角')}</span>
                </div>
                <div class="batch-character-info">
                    ${char.age != null && char.age !== '' ? `<span class="info-item">年龄: ${escapeHtml(char.age)}</span>` : ''}
                    ${char.identity ? `<span class="info-item">身份: ${escapeHtml(char.identity)}</span>` : ''}
                    ${char.faction ? `<span class="info-item">势力: ${escapeHtml(char.faction)}</span>` : ''}
                </div>
                <div class="batch-character-description">
                    ${char.personality ? `<div class="batch-desc-block"><strong>性格</strong><span>${escapeHtml(char.personality)}</span></div>` : ''}
                    ${char.backstory ? `<div class="batch-desc-block"><strong>背景</strong><span>${escapeHtml(char.backstory.substring(0, 100))}${char.backstory.length > 100 ? '...' : ''}</span></div>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function toggleBatchCharacterSelection(index) {
    if (!currentBatchGenerated || index >= currentBatchGenerated.length) return;
    
    currentBatchGenerated[index].selected = !currentBatchGenerated[index].selected;
    validateBatchCreateButtons();
}

async function saveCharacterToApi(char) {
    const charName = (char.name || '').trim();
    if (!charName) return { success: false, skipped: true };

    try {
        const result = await api.post(`/api/projects/${currentProjectId}/characters/`, {
            name: charName,
            gender: char.gender || '未知',
            role_type: char.role_type || '配角',
            personality: char.personality || '',
            backstory: char.backstory || '',
            appearance: char.appearance || '',
            motivation: char.motivation || '',
            tagline: char.tagline || '',
            faction: normalizeFactionInput(char.faction || ''),
            age: char.age || '',
            identity: char.identity || '',
            strengths: char.strengths || '',
            flaws: char.flaws || '',
            obsession: char.obsession || '',
            abilities: char.abilities || '',
            taboos: char.taboos || '',
            secrets: char.secrets || '',
            dark_history: char.dark_history || '',
            development: char.development || '',
            weaknesses: char.weaknesses || '',
            relationships: parseRelationshipsFromLLM(char.relationships)
        });
        return { success: result && result.success, skipped: false };
    } catch (err) {
        console.warn(`保存角色 ${char.name} 失败:`, err);
        return { success: false, skipped: false };
    }
}

async function saveBatchCharacters() {
    const selectedCharacters = currentBatchGenerated.filter(c => c.selected);

    if (selectedCharacters.length === 0) {
        showError('请至少选择一个角色');
        return;
    }

    setCharBtnLoading('saveCreateBtn', true, '保存中...');

    try {
        // 获取已有角色名集合
        const existingNames = new Set(characters.filter(c => !c.is_deleted).map(c => c.name));

        // 过滤：跳过空名和已存在的角色
        const toSave = selectedCharacters.filter(char => {
            const name = (char.name || '').trim();
            if (!name) return false;
            if (existingNames.has(name)) {
                console.warn(`角色 "${name}" 已存在，已跳过`);
                return false;
            }
            return true;
        });

        const skippedCount = selectedCharacters.length - toSave.length;
        const CONCURRENCY = 3;
        let successCount = 0;
        let failCount = 0;

        // 分块并发保存
        for (let i = 0; i < toSave.length; i += CONCURRENCY) {
            const chunk = toSave.slice(i, i + CONCURRENCY);
            const results = await Promise.allSettled(
                chunk.map(char => saveCharacterToApi(char))
            );

            for (let j = 0; j < results.length; j++) {
                const result = results[j];
                if (result.status === 'fulfilled' && result.value.success) {
                    successCount++;
                } else {
                    failCount++;
                    // 失败后重试一次（覆盖 API 返回失败和网络异常两种场景）
                    const shouldRetry = result.status === 'rejected'
                        || (result.status === 'fulfilled' && !result.value.skipped);
                    if (shouldRetry) {
                        const retryChar = chunk[j];
                        const retryResult = await saveCharacterToApi(retryChar);
                        if (retryResult.success) {
                            successCount++;
                            failCount--;
                        }
                    }
                }
            }
        }

        const parts = [`成功保存 ${successCount} 个角色`];
        if (skippedCount > 0) parts.push(`${skippedCount} 个已跳过`);
        if (failCount > 0) parts.push(`${failCount} 个保存失败`);
        showSuccess(parts.join('，'));
        closeCreateDialog();
        loadCharacters();
    } catch (error) {
        console.error('批量保存角色失败:', error);
        showError('网络错误');
    } finally {
        setCharBtnLoading('saveCreateBtn', false, null, '<i class="fas fa-save"></i> 批量保存');
    }
}

// ============ 编辑角色 ============
async function openEditDialog(id) {
    // 先弹出弹窗并显示加载覆盖层
    lockScroll();
    document.getElementById('editDialog').classList.add('show');
    showEditDialogLoading(true);

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/characters/${id}/`);
        if (!data) {
            closeEditDialog();
            return;
        }

        if (!data.success || !data.character) {
            closeEditDialog();
            showError('加载角色失败');
            return;
        }

        const character = data.character;

        document.getElementById('editCharacterId').value = character.id;

        // 用 setFormFields 批量填充字段
        const values = { name: character.name || '' };
        for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
            values[key] = character[key] || '';
        }
        setFormFields('edit', values);

        // 加载关系数据
        currentRelationships = parseRelationshipsFromLLM(character.relationships);
        renderRelationshipsTable();

        // 加载经历数据
        currentExperiences = Array.isArray(character.experiences) ? character.experiences : [];
        renderExperienceTable();

        // 切换到第一个标签页
        switchEditTab('basic');

        // 更新字符计数
        initCharCounts();
    } catch (error) {
        closeEditDialog();
        console.error('加载角色详情失败:', error);
        showError('加载角色失败');
    } finally {
        showEditDialogLoading(false);
    }
}

function showEditDialogLoading(show) {
    const overlay = document.getElementById('editDialogLoading');
    if (overlay) overlay.style.display = show ? 'flex' : 'none';
}

function closeEditDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('editDialog').classList.remove('show');
    unlockScroll();
}

// 从编辑弹窗删除角色
async function deleteCharacter() {
    const id = document.getElementById('editCharacterId').value;
    showModal('确认删除', '确定要删除这个角色吗？删除后可在角色列表中恢复。', async () => {
        try {
            const data = await api.delete(`/api/projects/${currentProjectId}/characters/${id}/`);
            if (!data) return;

            if (data.success) {
                closeModal();
                showSuccess('角色已删除');
                closeEditDialog();
                loadCharacters();
            } else {
                showError(data.error || '删除失败');
            }
        } catch (error) {
            showError('网络错误');
        }
    });
}

// ==================== 人际关系表格 ====================
// 关系类型（从后端 API 动态获取，保持与后端 constants.py 一致）
// 约定：以本人为基准，描述"对方相对于本人"的角色
let RELATIONSHIP_TYPES = [
    '朋友', '恋人', '配偶', '父母', '子女', '兄弟姐妹',
    '师父', '徒弟', '敌人', '对手', '导师', '门生',
    '盟友', '亲属', '君主', '臣子', '其他'
];

// 英文→中文映射（兼容 LLM 返回英文或数据库旧数据）
let RELATIONSHIP_EN_TO_CN = {
    'friend': '朋友', 'lover': '恋人', 'spouse': '配偶',
    'parent': '父母', 'child': '子女', 'sibling': '兄弟姐妹',
    'master': '师父', 'apprentice': '徒弟', 'disciple': '徒弟',
    'enemy': '敌人', 'rival': '对手', 'mentor': '导师',
    'protégé': '门生', 'protege': '门生', 'partner': '盟友',
    'ally': '盟友', 'family': '亲属', 'other': '其他',
};

/**
 * 从后端加载关系类型配置（保持与 constants.py 同步）
 */
async function loadRelationshipTypes() {
    try {
        const projectId = getProjectIdFromUrl();
        const data = await api.get(`/api/projects/${projectId}/characters/relationship-types/`);
        if (data && data.types) {
            RELATIONSHIP_TYPES = data.types;
            RELATIONSHIP_EN_TO_CN = data.en_to_cn || RELATIONSHIP_EN_TO_CN;
        }
    } catch (e) {
        // 加载失败时使用默认值（已初始化）
        console.warn('加载关系类型配置失败，使用默认值', e);
    }
}

/**
 * 归一化关系类型：英文→中文，不在白名单中的→'其他'
 */
function normalizeRelationshipType(type) {
    if (!type) return '其他';
    // 已经是中文白名单中的值
    if (RELATIONSHIP_TYPES.includes(type)) return type;
    // 英文→中文映射
    const cn = RELATIONSHIP_EN_TO_CN[type.toLowerCase()];
    if (cn) return cn;
    // 未知类型兜底
    return '其他';
}

// 渲染关系表格
function renderRelationshipsTable() {
    const tbody = document.getElementById('relationshipsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    // 获取可选择的角色（排除当前角色）
    const currentId = document.getElementById('editCharacterId').value;
    const availableCharacters = characters.filter(c => c.id != currentId);
    
    currentRelationships.forEach((rel, index) => {
        const row = createRelationshipRow(rel, index, availableCharacters);
        tbody.appendChild(row);
    });
}

// 创建关系行
function createRelationshipRow(rel, index, availableCharacters) {
    const row = document.createElement('tr');
    row.dataset.index = index;

    // 对方角色（下拉框+输入）
    const targetCell = document.createElement('td');
    const targetSelect = document.createElement('select');
    targetSelect.innerHTML = `
        <option value="">选择角色...</option>
        <option value="custom" ${rel.targetName && !availableCharacters.find(c => c.name === rel.targetName) ? 'selected' : ''}>自定义...</option>
        ${availableCharacters.map(c => `<option value="${escapeHtml(c.name)}" ${rel.targetName === c.name ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}
    `;

    const customInput = document.createElement('input');
    customInput.type = 'text';
    customInput.placeholder = '输入角色名';
    customInput.value = rel.targetName || '';
    customInput.className = 'rel-custom-input';
    customInput.style.display = rel.targetName && !availableCharacters.find(c => c.name === rel.targetName) ? 'block' : 'none';
    
    targetSelect.addEventListener('change', function() {
        if (this.value === 'custom') {
            customInput.style.display = 'block';
            customInput.focus();
        } else {
            customInput.style.display = 'none';
            customInput.value = this.value;
            currentRelationships[index].targetName = this.value;
        }
    });
    
    customInput.addEventListener('input', function() {
        currentRelationships[index].targetName = this.value;
    });

    targetCell.appendChild(targetSelect);
    targetCell.appendChild(customInput);
    row.appendChild(targetCell);

    // 关系类型
    const typeCell = document.createElement('td');
    const typeSelect = document.createElement('select');
    const isCustomType = rel.relationshipType && !RELATIONSHIP_TYPES.includes(rel.relationshipType);
    typeSelect.innerHTML = RELATIONSHIP_TYPES.map(t =>
        `<option value="${escapeHtml(t)}" ${rel.relationshipType === t ? 'selected' : ''}>${escapeHtml(t)}</option>`
    ).join('') + `<option value="custom" ${isCustomType ? 'selected' : ''}>自定义...</option>`;

    const customTypeInput = document.createElement('input');
    customTypeInput.type = 'text';
    customTypeInput.placeholder = '输入关系类型';
    customTypeInput.value = isCustomType ? rel.relationshipType : '';
    customTypeInput.className = 'rel-custom-input';
    customTypeInput.style.display = isCustomType ? 'block' : 'none';

    typeSelect.addEventListener('change', function() {
        if (this.value === 'custom') {
            customTypeInput.style.display = 'block';
            customTypeInput.focus();
            currentRelationships[index].relationshipType = customTypeInput.value || '其他';
        } else {
            customTypeInput.style.display = 'none';
            customTypeInput.value = '';
            currentRelationships[index].relationshipType = this.value;
        }
    });

    customTypeInput.addEventListener('input', function() {
        currentRelationships[index].relationshipType = this.value || '其他';
    });

    typeCell.appendChild(typeSelect);
    typeCell.appendChild(customTypeInput);
    row.appendChild(typeCell);

    // 关系描述
    const descCell = document.createElement('td');
    const descInput = document.createElement('input');
    descInput.type = 'text';
    descInput.placeholder = '描述关系...';
    descInput.value = rel.description || '';
    descInput.addEventListener('input', function() {
        currentRelationships[index].description = this.value;
    });
    descCell.appendChild(descInput);
    row.appendChild(descCell);

    // 删除按钮
    const deleteCell = document.createElement('td');
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-relationship-btn';
    deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
    deleteBtn.addEventListener('click', function() {
        currentRelationships.splice(index, 1);
        renderRelationshipsTable();
    });
    deleteCell.appendChild(deleteBtn);
    row.appendChild(deleteCell);

    return row;
}

// 添加新关系
function addRelationship() {
    currentRelationships.push({
        targetName: '',
        relationshipType: '朋友',
        description: '',
        createReverse: true
    });
    renderRelationshipsTable();
}

// 切换编辑标签页
function switchEditTab(tab) {
    document.querySelectorAll('.edit-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#editDialog .tab-content').forEach(c => c.classList.remove('active'));

    document.querySelector(`.edit-tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('edit' + tab.charAt(0).toUpperCase() + tab.slice(1) + 'Tab').classList.add('active');
}

async function saveCharacter() {
    const id = document.getElementById('editCharacterId').value;
    const name = document.getElementById('editName').value.trim();

    if (!name) {
        showError('请输入角色名称');
        return;
    }

    setCharBtnLoading('editSubmitBtn', true, '保存中...');

    try {
        // 清理关系数据：只保留后端需要的字段，过滤空目标
        const cleanedRelationships = currentRelationships
            .filter(r => r.targetName && r.targetName.trim())
            .map(r => ({
                targetName: r.targetName.trim(),
                relationshipType: r.relationshipType || '其他',
                description: r.description || '',
                createReverse: r.createReverse !== false
            }));

        const bodyData = collectCharacterFields('edit');
        bodyData.relationships = cleanedRelationships;
        bodyData.experiences = currentExperiences;

        const data = await api.put(`/api/projects/${currentProjectId}/characters/${id}/`, bodyData);
        if (!data) return;

        if (data.success) {
            showSuccess('角色更新成功');
            closeEditDialog();
            loadCharacters();
        } else {
            showError(data.error || '保存失败');
        }
    } catch (error) {
        showError('网络错误');
    } finally {
        setCharBtnLoading('editSubmitBtn', false, null, '<i class="fas fa-save"></i> 保存修改');
    }
}

// ============ AI润色 ============

// ============ 通用润色结果应用 ============
function applyPolishResult(formPrefix, data) {
    // 兼容 shim：AI 返回 tags，模型字段名为 tagline
    if (data.tags !== undefined && data.tagline === undefined) {
        data.tagline = data.tags;
    }
    // 用 setFormFields 批量填充（CharacterPolishSerializer 返回的字段名与 CHARACTER_FIELD_MAP key 一致）
    setFormFields(formPrefix, data);

    // 创建表单的 relationships：对象数组转为可读文本写入 textarea
    if (formPrefix === 'create' && data.relationships) {
        const el = document.getElementById('createRelationships');
        if (el) {
            if (Array.isArray(data.relationships)) {
                el.value = data.relationships.map(r => {
                    if (typeof r === 'object' && r !== null) {
                        return `${r.relationshipType || '其他'}-${r.targetName || ''}-${r.description || ''}`;
                    }
                    return String(r);
                }).join(',');
            } else {
                el.value = data.relationships || '';
            }
        }
    }

    // 编辑表单的 relationships：更新 currentRelationships 并重新渲染
    if (formPrefix === 'edit' && data.relationships) {
        currentRelationships = parseRelationshipsFromLLM(data.relationships);
        renderRelationshipsTable();
    }
}

// 通用润色函数（合并 polishCharacter 和 polishEditCharacter）
async function _doPolishCharacter(formPrefix, btnId) {
    const name = document.getElementById(formPrefix + 'Name').value.trim();
    if (!name) {
        showError('请先输入角色名称');
        return;
    }

    setCharBtnLoading(btnId, true, '润色中...');

    showLoading('正在润色角色...');

    // 用 collectCharacterFields 收集表单数据
    const bodyData = collectCharacterFields(formPrefix);

    // 编辑表单的 relationships 使用 currentRelationships 数组
    if (formPrefix === 'edit' && currentRelationships.length > 0) {
        bodyData.relationships = currentRelationships;
    }
    // 创建表单的 relationships 来自 createRelationships textarea
    if (formPrefix === 'create') {
        bodyData.relationships = document.getElementById('createRelationships').value;
    }

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/polish/`, bodyData);

        hideLoading();

        if (!data || !data.success) {
            showError(data?.error || '润色失败，请重试');
            return;
        }

        const fullContent = data.data;
        let result = extractJsonFromString(fullContent);
        if (result && typeof result === 'object') {
            applyPolishResult(formPrefix, result);
            showSuccess('AI润色完成');
            return;
        }

        showError('润色结果解析失败，请重试');
    } catch (error) {
        hideLoading();
        console.error('AI润色失败:', error);
        showError(error.message || '网络错误');
    } finally {
        setCharBtnLoading(btnId, false, null, '<i class="fas fa-star"></i> AI 润色');
    }
}

// 创建角色弹窗的AI润色
async function polishCharacter() {
    await _doPolishCharacter('create', 'aiActionBtn');
}

// 编辑角色弹窗的AI润色
async function polishEditCharacter() {
    await _doPolishCharacter('edit', 'polishEditBtn');
}

// ============ 工具函数 ============
function normalizeFactionInput(input) {
    if (!input) return '';
    // 保留汉字、英文、数字，将其他字符替换为逗号
    return input
        .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, ',')  // 非汉字英文数字替换为逗号
        .replace(/(,\s*)+/g, ',')     // 多个逗号替换为一个
        .replace(/^,|,$/g, '')        // 去除首尾逗号
        .trim();
}

function normalizeFactionInputField(inputField) {
    inputField.value = normalizeFactionInput(inputField.value);
}

/**
 * 通用角色字段收集函数
 * 利用 CHARACTER_FIELD_MAP 从表单中动态收集字段值，减少手动枚举
 * @param {string} prefix - 表单元素 ID 前缀（如 'create'、'aiGenerated'、'edit'）
 * @returns {Object} 字段名→值的键值对，适用于 create/update API
 */
function collectCharacterFields(prefix) {
    const data = {};
    // name 特殊处理：不在 CHARACTER_FIELD_MAP 中
    const nameEl = document.getElementById(prefix + 'Name');
    if (nameEl) data.name = nameEl.value;

    // 通过 FIELD_MAP 动态收集通用字段
    for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
        const el = document.getElementById(prefix + suffix);
        if (el) {
            data[key] = el.value;
        }
    }

    // 势力字段归一化
    if (data.faction) {
        data.faction = normalizeFactionInput(data.faction);
    }

    return data;
}

// ==================== 经历表格 ====================

// 渲染经历表格
function renderExperienceTable() {
    const tbody = document.getElementById('experienceTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    currentExperiences.forEach((exp, index) => {
        const row = createExperienceRow(exp, index);
        tbody.appendChild(row);
    });
}

// 创建经历行
function createExperienceRow(exp, index) {
    const row = document.createElement('tr');
    row.dataset.index = index;

    // 章节范围
    const chapterCell = document.createElement('td');
    const chapterInput = document.createElement('input');
    chapterInput.type = 'text';
    chapterInput.placeholder = '如：第3章、第1-5章';
    chapterInput.value = exp.chapter || '';
    chapterInput.addEventListener('input', function() {
        currentExperiences[index].chapter = this.value;
    });
    chapterCell.appendChild(chapterInput);
    row.appendChild(chapterCell);

    // 事件描述
    const descCell = document.createElement('td');
    const descInput = document.createElement('textarea');
    descInput.placeholder = '描述该章节发生的重要事件...';
    descInput.rows = 2;
    descInput.value = exp.event || '';
    descInput.addEventListener('input', function() {
        currentExperiences[index].event = this.value;
    });
    descCell.appendChild(descInput);
    row.appendChild(descCell);

    // 删除按钮
    const deleteCell = document.createElement('td');
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-experience-btn';
    deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
    deleteBtn.addEventListener('click', function() {
        currentExperiences.splice(index, 1);
        renderExperienceTable();
    });
    deleteCell.appendChild(deleteBtn);
    row.appendChild(deleteCell);

    return row;
}

// 添加新经历
function addExperience() {
    currentExperiences.push({
        chapter: '',
        event: ''
    });
    renderExperienceTable();
    // 滚动到新添加的行
    const tbody = document.getElementById('experienceTableBody');
    if (tbody && tbody.lastElementChild) {
        tbody.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// AI角色检测与优化模块已拆分到 characters-check.js

/**
 * 将 LLM 返回的 relationships 解析为标准对象数组
 * 支持格式：
 * - 对象数组: [{targetName, relationshipType, description}]
 * - 字符串: "师父-青云门掌门-亦师亦父,兄弟姐妹-李若兰-亲如姐妹"
 * - 混合: [对象, 字符串, ...]
 * 被创建/编辑/优化流程共用
 */
function parseRelationshipsFromLLM(rels) {
    if (!rels) return [];

    // 字符串格式：优先匹配 "XXX是我的YYY - 描述"，回退到 "类型-目标名-描述"
    if (typeof rels === 'string') {
        return rels.split(',').map(s => s.trim()).filter(Boolean).map(s => {
            // 格式1: "XXX是我的YYY" 或 "XXX是我的YYY - 描述"
            const match = s.match(/(.+?)是我的(.+?)(?:\s*-\s*(.+))?$/);
            if (match) {
                return {
                    targetName: match[1].trim(),
                    relationshipType: normalizeRelationshipType(match[2].trim()),
                    description: (match[3] || '').trim(),
                    createReverse: true
                };
            }
            // 格式2: "类型-目标名-描述"（旧格式兼容）
            const parts = s.split('-');
            if (parts.length >= 2) {
                return {
                    targetName: parts[1].trim(),
                    relationshipType: normalizeRelationshipType(parts[0].trim()),
                    description: parts.slice(2).join('-').trim() || '',
                    createReverse: true
                };
            }
            return null;
        }).filter(Boolean);
    }

    // 数组格式
    if (Array.isArray(rels)) {
        return rels.map(r => {
            if (typeof r === 'object' && r !== null) {
                return {
                    targetName: r.targetName || '',
                    relationshipType: normalizeRelationshipType(r.relationshipType),
                    description: r.description || '',
                    createReverse: r.createReverse !== false
                };
            }
            // 数组中的字符串元素
            if (typeof r === 'string') {
                const match = r.match(/(.+?)是我的(.+?)(?:\s*-\s*(.+))?$/);
                if (match) {
                    return {
                        targetName: match[1].trim(),
                        relationshipType: normalizeRelationshipType(match[2].trim()),
                        description: (match[3] || '').trim(),
                        createReverse: true
                    };
                }
                const parts = r.split('-');
                if (parts.length >= 2) {
                    return {
                        targetName: parts[1].trim(),
                        relationshipType: normalizeRelationshipType(parts[0].trim()),
                        description: parts.slice(2).join('-').trim() || '',
                        createReverse: true
                    };
                }
            }
            return null;
        }).filter(Boolean);
    }

    return [];
}
