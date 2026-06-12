// 角色库管理脚本
let currentProjectId = null;
let characters = [];
let filteredCharacters = [];
let allFactions = [];  // 所有势力列表
let currentRelationships = [];  // 当前编辑的角色关系
let currentExperiences = [];  // 当前编辑的角色经历
let searchDebounceTimer = null;  // 搜索防抖计时器

// 共享字段映射：API 字段名 → 表单元素 ID 后缀（配合 formPrefix 使用）
const CHARACTER_FIELD_MAP = {
    'gender': 'Gender',
    'role': 'Role',
    'age': 'Age',
    'identity': 'Identity',
    'personality': 'Personality',
    'strengths': 'Strengths',
    'flaws': 'Flaws',
    'obsession': 'Obsession',
    'motivation': 'Motivation',
    'appearance': 'Appearance',
    'faction': 'Faction',
    'abilities': 'Abilities',
    'taboos': 'Taboos',
    'dark_history': 'DarkHistory',
    'secrets': 'Secrets',
    'backstory': 'Background',
    'development': 'Development',
    'weaknesses': 'Weaknesses',
    'tags': 'Tags'
};

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    initPage();
    setupCreateFormValidation();
});

// ============ 弹窗滚动锁定 ============
function lockScroll() {
    document.body.style.overflow = 'hidden';
}

function unlockScroll() {
    document.body.style.overflow = '';
}

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

        if (data.success) {
            characters = data.characters;
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

function updateFactionFilterOptions() {
    // 收集所有不重复的势力
    const allFactionsSet = new Set();
    characters.forEach(c => {
        if (c.faction) {
            c.faction.split(',').forEach(f => {
                const trimmed = f.trim();
                if (trimmed) {
                    allFactionsSet.add(trimmed);
                }
            });
        }
    });
    
    allFactions = Array.from(allFactionsSet).sort();

    const factionFilter = document.getElementById('factionFilter');
    const currentValue = factionFilter.value;

    factionFilter.innerHTML = '<option value="">全部势力</option>';
    allFactions.forEach(f => {
        const option = document.createElement('option');
        option.value = f;
        option.textContent = f;
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
        <div class="char-item${isDeleted ? ' char-item-deleted' : ''}" ${isDeleted ? '' : `onclick="openEditDialog(${c.id})"`}>
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
            ${isDeleted ? `<div class="char-item-actions"><button class="btn btn-sm btn-restore" onclick="event.stopPropagation(); restoreCharacter(${c.id})"><i class="fas fa-undo"></i> 恢复</button></div>` : ''}
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
    // 清空表单 - 基础字段
    document.getElementById('createName').value = '';
    document.getElementById('createRole').value = '配角';
    document.getElementById('createGender').value = '未知';
    document.getElementById('createAge').value = '';
    document.getElementById('createIdentity').value = '';
    document.getElementById('createPersonality').value = '';
    document.getElementById('createBackground').value = '';
    document.getElementById('createAppearance').value = '';
    document.getElementById('createTags').value = '';
    document.getElementById('createFaction').value = '';
    document.getElementById('createDevelopment').value = '';
    document.getElementById('createWeaknesses').value = '';
    
    // 清空新增字段
    document.getElementById('createStrengths').value = '';
    document.getElementById('createFlaws').value = '';
    document.getElementById('createObsession').value = '';
    document.getElementById('createMotivation').value = '';
    document.getElementById('createAbilities').value = '';
    document.getElementById('createTaboos').value = '';
    document.getElementById('createDarkHistory').value = '';
    document.getElementById('createSecrets').value = '';
    document.getElementById('createRelationships').value = '';
    
    // 清空AI生成相关字段
    document.getElementById('aiDescription').value = '';
    document.getElementById('batchDescription').value = '';
    document.getElementById('aiGeneratedContent').style.display = 'none';
    document.getElementById('batchGeneratedContent').style.display = 'none';
    currentAiGenerated = null;
    currentBatchGenerated = [];

    // 初始化为手动创建标签页并验证按钮状态
    switchCreateTab('manual');

    // 显示弹窗并锁定背景滚动
    lockScroll();
    document.getElementById('createDialog').classList.add('active');
}

function setupCreateFormValidation() {
    document.getElementById('createName').addEventListener('input', validateManualCreateButtons);
    document.getElementById('aiDescription').addEventListener('input', validateAiGenerateButtons);
    document.getElementById('batchDescription').addEventListener('input', validateBatchCreateButtons);
}

function closeCreateDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('createDialog').classList.remove('active');
    unlockScroll();
    // 清空AI生成的内容
    document.getElementById('aiDescription').value = '';
    document.getElementById('aiGeneratedContent').style.display = 'none';
    currentAiGenerated = null;
    // 清空批量创建的内容
    document.getElementById('batchDescription').value = '';
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
        aiActionBtn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
        aiActionBtn.dataset.action = 'polish';
        saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
        validateManualCreateButtons();
    } else if (tab === 'ai') {
        document.querySelector('.create-tab[data-tab="ai"]').classList.add('active');
        document.getElementById('aiCreateTab').classList.add('active');
        if (currentAiGenerated && Object.keys(currentAiGenerated).length > 0) {
            aiActionBtn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
        } else {
            aiActionBtn.innerHTML = '<i class="fas fa-magic"></i> AI 生成';
        }
        aiActionBtn.dataset.action = 'generate';
        saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
        validateAiGenerateButtons();
    } else if (tab === 'batch') {
        document.querySelector('.create-tab[data-tab="batch"]').classList.add('active');
        document.getElementById('batchCreateTab').classList.add('active');
        if (currentBatchGenerated && currentBatchGenerated.length > 0) {
            aiActionBtn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
        } else {
            aiActionBtn.innerHTML = '<i class="fas fa-magic"></i> 批量生成';
        }
        aiActionBtn.dataset.action = 'batch';
        saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 批量保存';
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

    const btn = document.getElementById('saveCreateBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 创建中...';

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/`, {
            name: name,
            gender: document.getElementById('createGender').value,
            role_type: document.getElementById('createRole').value,
            age: document.getElementById('createAge').value,
            identity: document.getElementById('createIdentity').value,
            personality: document.getElementById('createPersonality').value,
            backstory: document.getElementById('createBackground').value,
            appearance: document.getElementById('createAppearance').value,
            motivation: document.getElementById('createMotivation').value,
            tagline: document.getElementById('createTags').value,
            faction: normalizeFactionInput(document.getElementById('createFaction').value),
            relationships: document.getElementById('createRelationships').value,
            strengths: document.getElementById('createStrengths').value,
            flaws: document.getElementById('createFlaws').value,
            obsession: document.getElementById('createObsession').value,
            abilities: document.getElementById('createAbilities').value,
            taboos: document.getElementById('createTaboos').value,
            secrets: document.getElementById('createSecrets').value,
            dark_history: document.getElementById('createDarkHistory').value,
            development: document.getElementById('createDevelopment').value,
            weaknesses: document.getElementById('createWeaknesses').value
        });

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
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
    }
}

// ============ AI生成角色预览（流式） ============
let currentAiGenerated = null;

// ============ 通用SSE流解析辅助函数 ============
async function parseSSEStream(reader, onComplete, onError) {
    const decoder = new TextDecoder();
    let buffer = '';
    let fullContent = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let searchStart = 0;
        let dataStart;
        while ((dataStart = buffer.indexOf('data: ', searchStart)) !== -1) {
            const msgEnd = buffer.indexOf('\n\n', dataStart);
            if (msgEnd === -1) break;

            const dataContent = buffer.substring(dataStart + 6, msgEnd);
            try {
                const json = JSON.parse(dataContent);
                if (json.type === 'chunk' && json.data) {
                    fullContent += json.data;
                } else if (json.type === 'complete' && json.data) {
                    onComplete(json.data, fullContent);
                    return;
                } else if (json.type === 'error') {
                    onError(json.message || '操作失败');
                    return;
                }
            } catch (e) {
                console.error('解析失败:', e);
            }
            searchStart = msgEnd + 2;
        }
        if (searchStart > 0) {
            buffer = buffer.substring(searchStart);
        }
    }

    // 流结束但未收到complete，尝试用fullContent
    if (fullContent) {
        onComplete(null, fullContent);
    }
}

async function generateCharacterPreview() {
    const description = document.getElementById('aiDescription').value.trim();

    if (!description) {
        showError('请输入角色描述');
        return;
    }

    const btn = document.getElementById('aiActionBtn');
    const saveBtn = document.getElementById('saveCreateBtn');

    btn.disabled = true;
    saveBtn.disabled = true;

    // 显示生成内容区域并清空
    document.getElementById('aiGeneratedContent').style.display = 'block';
    clearAiGeneratedFields();

    showLoading('正在生成角色...');

    try {
        const response = await api.request(`/api/projects/${currentProjectId}/characters/generate/`, {
            method: 'POST',
            stream: true,
            body: JSON.stringify({
                requirement: description
            })
        });

        const reader = response.body.getReader();

        await parseSSEStream(reader,
            function(completeData, fullContent) {
                hideLoading();
                try {
                    let result;
                    if (completeData) {
                        result = JSON.parse(completeData);
                    } else if (fullContent) {
                        const jsonMatch = fullContent.match(/\{[\s\S]*\}/);
                        if (jsonMatch) result = JSON.parse(jsonMatch[0]);
                    }
                    if (result) {
                        if (Array.isArray(result) && result.length > 0) {
                            result = result[0];
                        }
                        currentAiGenerated = result;
                        displayAiGeneratedCharacter(currentAiGenerated);
                        btn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
                        saveBtn.disabled = false;
                        showSuccess('角色生成完成，请确认后保存');
                    }
                } catch (e) {
                    console.error('解析失败:', e);
                    showError('解析失败，请重试');
                }
            },
            function(errorMessage) {
                hideLoading();
                showError(errorMessage || '生成失败');
            }
        );
    } catch (error) {
        console.error('生成角色失败:', error);
        showError('网络错误，请重试');
    } finally {
        hideLoading();
        btn.disabled = false;
        if (currentAiGenerated && Object.keys(currentAiGenerated).length > 0) {
            btn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
        } else {
            btn.innerHTML = '<i class="fas fa-magic"></i> AI 生成';
        }
    }
}

function clearAiGeneratedFields() {
    document.getElementById('aiGeneratedName').value = '';
    document.getElementById('aiGeneratedRole').value = '配角';
    document.getElementById('aiGeneratedGender').value = '未知';
    document.getElementById('aiGeneratedAge').value = '';
    document.getElementById('aiGeneratedIdentity').value = '';
    document.getElementById('aiGeneratedStrengths').value = '';
    document.getElementById('aiGeneratedFlaws').value = '';
    document.getElementById('aiGeneratedObsession').value = '';
    document.getElementById('aiGeneratedMotivation').value = '';
    document.getElementById('aiGeneratedPersonality').value = '';
    document.getElementById('aiGeneratedAppearance').value = '';
    document.getElementById('aiGeneratedAbilities').value = '';
    document.getElementById('aiGeneratedTaboos').value = '';
    document.getElementById('aiGeneratedSecrets').value = '';
    document.getElementById('aiGeneratedDarkHistory').value = '';
    document.getElementById('aiGeneratedBackground').value = '';
    document.getElementById('aiGeneratedDevelopment').value = '';
    document.getElementById('aiGeneratedWeaknesses').value = '';
    document.getElementById('aiGeneratedFaction').value = '';
    document.getElementById('aiGeneratedTags').value = '';
}

function displayAiGeneratedCharacter(charData) {
    document.getElementById('aiGeneratedContent').style.display = 'block';

    // 填充表单
    document.getElementById('aiGeneratedName').value = charData.name || '';
    document.getElementById('aiGeneratedRole').value = charData.role || '配角';
    document.getElementById('aiGeneratedGender').value = charData.gender || '未知';
    document.getElementById('aiGeneratedAge').value = charData.age || '';
    document.getElementById('aiGeneratedIdentity').value = charData.identity || '';
    document.getElementById('aiGeneratedStrengths').value = charData.strengths || '';
    document.getElementById('aiGeneratedFlaws').value = charData.flaws || '';
    document.getElementById('aiGeneratedObsession').value = charData.obsession || '';
    document.getElementById('aiGeneratedMotivation').value = charData.motivation || '';
    document.getElementById('aiGeneratedPersonality').value = charData.personality || '';
    document.getElementById('aiGeneratedAppearance').value = charData.appearance || '';
    document.getElementById('aiGeneratedAbilities').value = charData.abilities || '';
    document.getElementById('aiGeneratedTaboos').value = charData.taboos || '';
    document.getElementById('aiGeneratedSecrets').value = charData.secrets || '';
    document.getElementById('aiGeneratedDarkHistory').value = charData.dark_history || '';
    document.getElementById('aiGeneratedBackground').value = charData.background || charData.backstory || '';
    document.getElementById('aiGeneratedDevelopment').value = charData.development || '';
    document.getElementById('aiGeneratedWeaknesses').value = charData.weaknesses || '';
    document.getElementById('aiGeneratedFaction').value = charData.faction || '';
    document.getElementById('aiGeneratedTags').value = charData.tags || '';
}

async function saveAiGeneratedCharacter() {
    const name = document.getElementById('aiGeneratedName').value.trim();

    if (!name) {
        showError('请输入角色名称');
        return;
    }

    const btn = document.getElementById('saveCreateBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        // 收集 relationships（LLM 可能返回对象数组或字符串）
        let relationships = [];
        if (currentAiGenerated && currentAiGenerated.relationships) {
            relationships = parseRelationshipsFromLLM(currentAiGenerated.relationships);
        }

        const data = await api.post(`/api/projects/${currentProjectId}/characters/`, {
            name: name,
            gender: document.getElementById('aiGeneratedGender').value,
            role_type: document.getElementById('aiGeneratedRole').value,
            personality: document.getElementById('aiGeneratedPersonality').value,
            backstory: document.getElementById('aiGeneratedBackground').value,
            appearance: document.getElementById('aiGeneratedAppearance').value,
            motivation: document.getElementById('aiGeneratedMotivation').value,
            tagline: document.getElementById('aiGeneratedTags').value,
            faction: normalizeFactionInput(document.getElementById('aiGeneratedFaction').value),
            age: document.getElementById('aiGeneratedAge').value,
            identity: document.getElementById('aiGeneratedIdentity').value,
            strengths: document.getElementById('aiGeneratedStrengths').value,
            flaws: document.getElementById('aiGeneratedFlaws').value,
            obsession: document.getElementById('aiGeneratedObsession').value,
            abilities: document.getElementById('aiGeneratedAbilities').value,
            taboos: document.getElementById('aiGeneratedTaboos').value,
            secrets: document.getElementById('aiGeneratedSecrets').value,
            dark_history: document.getElementById('aiGeneratedDarkHistory').value,
            development: document.getElementById('aiGeneratedDevelopment').value,
            weaknesses: document.getElementById('aiGeneratedWeaknesses').value,
            relationships: relationships
        });

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
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
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

    const btn = document.getElementById('aiActionBtn');
    const saveBtn = document.getElementById('saveCreateBtn');

    btn.disabled = true;
    saveBtn.disabled = true;

    document.getElementById('batchGeneratedContent').style.display = 'none';
    document.getElementById('batchCharactersList').innerHTML = '';
    
    currentBatchGenerated = [];

    showLoading('正在生成角色...');

    try {
        const response = await api.request(`/api/projects/${currentProjectId}/characters/generate/`, {
            method: 'POST',
            stream: true,
            body: JSON.stringify({
                requirement: description,
                is_batch: true
            })
        });

        const reader = response.body.getReader();

        await parseSSEStream(reader,
            function(completeData, fullContent) {
                hideLoading();
                try {
                    let results;
                    if (completeData) {
                        results = JSON.parse(completeData);
                    } else if (fullContent) {
                        const jsonMatch = fullContent.match(/\[[\s\S]*\]/);
                        if (jsonMatch) results = JSON.parse(jsonMatch[0]);
                    }
                    if (results) {
                        if (Array.isArray(results)) {
                            currentBatchGenerated = results.map((char, index) => ({
                                ...char,
                                selected: true,
                                index: index
                            }));
                            renderBatchCharacters();
                            document.getElementById('batchGeneratedContent').style.display = 'block';
                            btn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
                            validateBatchCreateButtons();
                            showSuccess(`成功生成 ${currentBatchGenerated.length} 个角色`);
                        } else {
                            showError('生成失败，格式错误');
                        }
                    }
                } catch (e) {
                    console.error('解析失败:', e);
                    showError('解析失败，请重试');
                }
            },
            function(errorMessage) {
                hideLoading();
                showError(errorMessage || '生成失败');
            }
        );
    } catch (error) {
        console.error('批量生成角色失败:', error);
        showError('网络错误，请重试');
    } finally {
        hideLoading();
        btn.disabled = false;
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
                    <span class="batch-character-role">${escapeHtml(char.role || '配角')}</span>
                </div>
                <div class="batch-character-info">
                    ${char.age ? `<span class="info-item">年龄: ${escapeHtml(char.age)}</span>` : ''}
                    ${char.identity ? `<span class="info-item">身份: ${escapeHtml(char.identity)}</span>` : ''}
                    ${char.faction ? `<span class="info-item">势力: ${escapeHtml(char.faction)}</span>` : ''}
                </div>
                <div class="batch-character-description">
                    ${char.personality ? `<p><strong>性格:</strong> ${escapeHtml(char.personality)}</p>` : ''}
                    ${char.background || char.backstory ? `<p><strong>背景:</strong> ${escapeHtml((char.background || char.backstory).substring(0, 100))}${(char.background || char.backstory).length > 100 ? '...' : ''}</p>` : ''}
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

async function saveBatchCharacters() {
    const selectedCharacters = currentBatchGenerated.filter(c => c.selected);

    if (selectedCharacters.length === 0) {
        showError('请至少选择一个角色');
        return;
    }

    const btn = document.getElementById('saveCreateBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        // 串行保存，避免并发请求过多
        let successCount = 0;
        for (const char of selectedCharacters) {
            try {
                const result = await api.post(`/api/projects/${currentProjectId}/characters/`, {
                    name: char.name || `角色${Date.now()}`,
                    gender: char.gender || '未知',
                    role_type: char.role || '配角',
                    personality: char.personality || '',
                    backstory: char.background || char.backstory || '',
                    appearance: char.appearance || '',
                    motivation: char.motivation || '',
                    tagline: char.tags || '',
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
                if (result && result.success) successCount++;
            } catch (err) {
                console.warn(`保存角色 ${char.name} 失败:`, err);
            }
        }

        showSuccess(`成功保存 ${successCount} 个角色`);
        closeCreateDialog();
        loadCharacters();
    } catch (error) {
        console.error('批量保存角色失败:', error);
        showError('网络错误');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 批量保存';
    }
}

// ============ 确认弹窗 ============
let _confirmCallback = null;

function showConfirmDialog(message, onConfirm) {
    document.getElementById('confirmMessage').textContent = message;
    _confirmCallback = onConfirm;
    lockScroll();
    document.getElementById('confirmDialog').classList.add('active');
}

function closeConfirmDialog() {
    document.getElementById('confirmDialog').classList.remove('active');
    _confirmCallback = null;
    unlockScroll();
}

function confirmOk() {
    const cb = _confirmCallback;
    closeConfirmDialog();
    if (cb) cb();
}

// ============ 编辑角色 ============
async function openEditDialog(id) {
    try {
        const data = await api.get(`/api/projects/${currentProjectId}/characters/${id}/`);
        
        if (!data.success || !data.character) {
            showError('加载角色失败');
            return;
        }
        
        const character = data.character;

        document.getElementById('editCharacterId').value = character.id;
        document.getElementById('editName').value = character.name || '';
        document.getElementById('editRole').value = character.role_type || '配角';
        document.getElementById('editGender').value = character.gender || '未知';
        document.getElementById('editAge').value = character.age || '';
        document.getElementById('editIdentity').value = character.identity || '';
        document.getElementById('editTags').value = character.tagline || '';
        document.getElementById('editFaction').value = character.faction || '';
        document.getElementById('editAppearance').value = character.appearance || '';
        document.getElementById('editPersonality').value = character.personality || '';
        document.getElementById('editBackground').value = character.backstory || '';
        document.getElementById('editMotivation').value = character.motivation || '';
        document.getElementById('editDevelopment').value = character.development || '';
        document.getElementById('editStrengths').value = character.strengths || '';
        document.getElementById('editFlaws').value = character.flaws || '';
        document.getElementById('editObsession').value = character.obsession || '';
        document.getElementById('editTaboos').value = character.taboos || '';
        document.getElementById('editAbilities').value = character.abilities || '';
        document.getElementById('editSecrets').value = character.secrets || '';
        document.getElementById('editDarkHistory').value = character.dark_history || '';
        document.getElementById('editWeaknesses').value = character.weaknesses || '';

        // 加载关系数据
        currentRelationships = parseRelationshipsFromLLM(character.relationships);
        renderRelationshipsTable();

        // 加载经历数据
        currentExperiences = Array.isArray(character.experiences) ? character.experiences : [];
        renderExperienceTable();

        // 切换到第一个标签页
        switchEditTab('basic');

        lockScroll();
        document.getElementById('editDialog').classList.add('active');
    } catch (error) {
        console.error('加载角色详情失败:', error);
        showError('加载角色失败');
    }
}

function closeEditDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('editDialog').classList.remove('active');
    unlockScroll();
}

// 从编辑弹窗删除角色
async function deleteCharacter() {
    const id = document.getElementById('editCharacterId').value;
    showConfirmDialog('确定要删除这个角色吗？', async () => {
        try {
            const data = await api.delete(`/api/projects/${currentProjectId}/characters/${id}/`);

            if (data.success) {
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
// 关系类型（直接使用中文，数据库保存中文）
// 约定：以本人为基准，描述"对方相对于本人"的角色
const RELATIONSHIP_TYPES = [
    '朋友', '恋人', '配偶', '父母', '子女', '兄弟姐妹',
    '师父', '徒弟', '敌人', '对手', '导师', '门生',
    '盟友', '亲属', '君主', '臣子', '其他'
];

// 英文→中文映射（兼容 LLM 返回英文或数据库旧数据）
const RELATIONSHIP_EN_TO_CN = {
    'friend': '朋友', 'lover': '恋人', 'spouse': '配偶',
    'parent': '父母', 'child': '子女', 'sibling': '兄弟姐妹',
    'master': '师父', 'apprentice': '徒弟', 'disciple': '徒弟',
    'enemy': '敌人', 'rival': '对手', 'mentor': '导师',
    'protégé': '门生', 'protege': '门生', 'partner': '盟友',
    'ally': '盟友', 'family': '亲属', 'other': '其他',
};

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

    const btn = document.getElementById('editSubmitBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

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

        const data = await api.put(`/api/projects/${currentProjectId}/characters/${id}/`, {
            name: name,
            role_type: document.getElementById('editRole').value,
            gender: document.getElementById('editGender').value,
            tagline: document.getElementById('editTags').value,
            faction: normalizeFactionInput(document.getElementById('editFaction').value),
            appearance: document.getElementById('editAppearance').value,
            personality: document.getElementById('editPersonality').value,
            backstory: document.getElementById('editBackground').value,
            motivation: document.getElementById('editMotivation').value,
            age: document.getElementById('editAge').value,
            identity: document.getElementById('editIdentity').value,
            relationships: cleanedRelationships,
            experiences: currentExperiences,
            development: document.getElementById('editDevelopment').value,
            strengths: document.getElementById('editStrengths').value,
            flaws: document.getElementById('editFlaws').value,
            obsession: document.getElementById('editObsession').value,
            taboos: document.getElementById('editTaboos').value,
            abilities: document.getElementById('editAbilities').value,
            secrets: document.getElementById('editSecrets').value,
            dark_history: document.getElementById('editDarkHistory').value,
            weaknesses: document.getElementById('editWeaknesses').value
        });

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
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 保存修改';
    }
}

// ============ AI润色 ============

// ============ 通用润色结果应用 ============
function applyPolishResult(formPrefix, data) {
    // 默认值映射
    const defaults = { 'gender': '未知', 'role': '配角' };

    for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
        if (data[key] !== undefined) {
            const el = document.getElementById(formPrefix + suffix);
            if (el) {
                el.value = data[key] !== undefined ? data[key] : (defaults[key] || '');
            }
        }
    }

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

    const btn = document.getElementById(btnId);
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 润色中...';

    showLoading('正在润色角色...');

    // 收集表单数据
    const fieldIds = {};
    for (const [key, suffix] of Object.entries(CHARACTER_FIELD_MAP)) {
        fieldIds[key] = formPrefix + suffix;
    }
    if (formPrefix === 'create') {
        fieldIds.relationships = 'createRelationships';
    }

    const bodyData = { name: name };
    for (const [key, id] of Object.entries(fieldIds)) {
        const el = document.getElementById(id);
        bodyData[key] = el ? el.value.trim() : '';
    }

    // 编辑表单的 relationships 使用 currentRelationships 数组
    if (formPrefix === 'edit' && currentRelationships.length > 0) {
        bodyData.relationships = currentRelationships;
    }

    try {
        const response = await api.request(`/api/projects/${currentProjectId}/characters/polish/`, {
            method: 'POST',
            stream: true,
            body: JSON.stringify(bodyData)
        });

        const reader = response.body.getReader();

        await parseSSEStream(reader,
            function(completeData, fullContent) {
                hideLoading();
                try {
                    let result;
                    if (completeData) {
                        let contentStr = completeData;
                        const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
                        if (jsonMatch) contentStr = jsonMatch[0];
                        result = JSON.parse(contentStr);
                    } else if (fullContent) {
                        const jsonMatch = fullContent.match(/\{[\s\S]*\}/);
                        if (jsonMatch) result = JSON.parse(jsonMatch[0]);
                    }
                    if (result) {
                        applyPolishResult(formPrefix, result);
                        showSuccess('AI润色完成');
                    }
                } catch (e) {
                    console.error('解析完整结果失败:', e);
                    showError('解析结果失败');
                }
            },
            function(errorMessage) {
                hideLoading();
                showError(errorMessage || '润色失败');
            }
        );
    } catch (error) {
        console.error('AI润色失败:', error);
        showError('网络错误');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
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

// ==================== AI角色检测 ====================

const CHECK_TYPE_LABELS = {
    'contradiction': '设定矛盾',
    'duplicate': '角色重复',
    'conflict': '关系冲突',
    'missing': '设定缺失',
    'unreasonable': '逻辑不合理'
};

// 当前检测结果的问题列表（供优化使用）
let currentCheckIssues = [];

async function checkAllCharacters() {
    if (characters.length === 0) {
        showError('暂无角色可检测');
        return;
    }

    const btn = document.getElementById('checkBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检测中...';

    // 隐藏优化按钮并重置文字
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    optimizeBtn.hidden = true;
    optimizeBtn.innerHTML = '<i class="fas fa-magic"></i> AI优化';
    optimizeBtn.onclick = optimizeFromCheck;
    currentCheckIssues = [];

    showLoading('正在检测所有角色...');

    try {
        const resultStr = await api.streamRequest(`/api/projects/${currentProjectId}/characters/check/`, {
            method: 'POST',
            body: JSON.stringify({})
        });

        hideLoading();

        if (!resultStr) {
            showError('检测结果为空');
            return;
        }

        // resultStr 是 streamRequest 拼接返回的纯文本字符串
        let contentStr = resultStr;
        const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
        if (jsonMatch) contentStr = jsonMatch[0];
        const result = JSON.parse(contentStr);
        currentCheckIssues = result.issues || [];
        lockScroll();
        document.getElementById('checkDialog').classList.add('active');
        renderCheckResult(result);
        showSuccess('检测完成');
    } catch (error) {
        hideLoading();
        console.error('角色检测失败:', error);
        showError('网络错误，请重试');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search-plus"></i> AI检测';
    }
}

function renderCheckResult(result) {
    const body = document.getElementById('checkResultBody');
    const issues = result.issues || [];

    if (issues.length === 0) {
        body.innerHTML = `
            <div class="check-no-issues">
                <i class="fas fa-check-circle"></i>
                <h3 style="margin-bottom: 8px;">所有角色设定良好</h3>
                <p style="color: #9ca3af;">未发现设定矛盾、角色重复或其他问题</p>
            </div>`;
        document.getElementById('optimizeCheckBtn').hidden = true;
        document.getElementById('checkCloseBtn').textContent = '关闭';
        return;
    }

    // 显示优化按钮，关闭按钮改为取消
    document.getElementById('optimizeCheckBtn').hidden = false;
    document.getElementById('checkCloseBtn').textContent = '取消';

    // 统计
    const highCount = issues.filter(i => i.severity === 'high').length;
    const mediumCount = issues.filter(i => i.severity === 'medium').length;
    const lowCount = issues.filter(i => i.severity === 'low').length;

    let html = '<div class="check-summary">';
    html += `<div class="check-summary-item">共 <span>${issues.length}</span> 个问题</div>`;
    if (highCount > 0) html += `<div class="check-summary-item high">严重 <span>${highCount}</span></div>`;
    if (mediumCount > 0) html += `<div class="check-summary-item medium">中等 <span>${mediumCount}</span></div>`;
    if (lowCount > 0) html += `<div class="check-summary-item low">轻微 <span>${lowCount}</span></div>`;
    html += '</div>';

    // 按严重程度排序
    const severityOrder = { high: 0, medium: 1, low: 2 };
    issues.sort((a, b) => (severityOrder[a.severity] || 2) - (severityOrder[b.severity] || 2));

    issues.forEach((issue, index) => {
        const typeLabel = CHECK_TYPE_LABELS[issue.type] || issue.type;
        const charNames = (issue.characters || []).map(n => escapeHtml(n)).join('、');
        html += `
            <div class="check-result-item" data-issue-index="${index}">
                <div class="check-result-header">
                    <span class="check-result-type ${issue.type}">${typeLabel}</span>
                    <span class="check-result-severity ${issue.severity}">${issue.severity === 'high' ? '严重' : issue.severity === 'medium' ? '中等' : '轻微'}</span>
                    ${charNames ? `<span class="check-result-chars">${charNames}</span>` : ''}
                </div>
                <div class="check-result-desc">${escapeHtml(issue.description)}</div>
                ${issue.suggestion ? `<div class="check-result-suggestion"><strong>建议：</strong>${escapeHtml(issue.suggestion)}</div>` : ''}
                <div class="check-result-input">
                    <input type="text" class="opt-instruction-input" data-index="${index}" placeholder="输入优化指示（留空则自动优化）">
                </div>
            </div>`;
    });

    body.innerHTML = html;
}

// ==================== AI优化（从检测结果） ====================

let currentOptimizeResult = null;

async function optimizeFromCheck() {
    if (currentCheckIssues.length === 0) {
        showError('没有需要优化的问题');
        return;
    }

    // 收集每个问题的用户指示
    const issuesWithInstructions = currentCheckIssues.map((issue, index) => {
        const input = document.querySelector(`.opt-instruction-input[data-index="${index}"]`);
        const instruction = input ? input.value.trim() : '';
        return {
            type: issue.type,
            characters: issue.characters || [],
            description: issue.description || '',
            instruction: instruction || issue.suggestion || '请自动优化'
        };
    });

    showLoading('正在AI优化角色...');

    try {
        const resultStr = await api.streamRequest(`/api/projects/${currentProjectId}/characters/optimize/`, {
            method: 'POST',
            body: JSON.stringify({ issues: issuesWithInstructions })
        });

        hideLoading();

        if (!resultStr) {
            showError('优化结果为空');
            return;
        }

        // resultStr 是 streamRequest 拼接返回的 JSON 数组字符串
        let contentStr = resultStr;
        // 如果是 JSON 数组，直接用 JSON.parse
        const trimmed = contentStr.trim();
        if (trimmed.startsWith('[')) {
            currentOptimizeResult = JSON.parse(trimmed);
        } else {
            // 兼容对象格式的 fallback
            const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
            if (jsonMatch) contentStr = jsonMatch[0];
            const obj = JSON.parse(contentStr);
            currentOptimizeResult = obj.optimizations || obj.data || obj;
        }
        renderOptimizeResult(currentOptimizeResult);
        showSuccess('优化完成');
    } catch (error) {
        console.error('AI优化失败:', error);
        showError('网络错误，请重试');
    } finally {
        hideLoading();
    }
}

// 字段名中文映射
const FIELD_LABELS = {
    'personality': '性格特点',
    'appearance': '外貌特征',
    'backstory': '背景故事',
    'motivation': '核心动机',
    'faction': '势力/阵营',
    'strengths': '优点',
    'flaws': '缺点',
    'obsession': '执念/软肋',
    'abilities': '能力',
    'taboos': '禁忌',
    'secrets': '秘密',
    'dark_history': '过往黑历史',
    'development': '成长轨迹',
    'weaknesses': '弱点代价',
    'relationships': '人际关系',
    'experiences': '经历'
};

const TYPE_LABELS = {
    'modify': '修改',
    'add': '新增',
    'delete': '删除'
};

/**
 * 将 LLM 返回的 relationships 解析为标准对象数组
 * 支持格式：
 * - 对象数组: [{targetName, relationshipType, description}]
 * - 字符串: "师父-青云门掌门-亦师亦父,兄弟姐妹-李若兰-亲如姐妹"
 * - 混合: [对象, 字符串, ...]
 */
function parseRelationshipsFromLLM(rels) {
    if (!rels) return [];

    // 字符串格式：逗号分隔的 "类型-目标名-描述"
    if (typeof rels === 'string') {
        return rels.split(',').map(s => s.trim()).filter(Boolean).map(s => {
            const parts = s.split('-', 3);
            if (parts.length >= 2) {
                return {
                    targetName: parts[1].trim(),
                    relationshipType: normalizeRelationshipType(parts[0].trim()),
                    description: parts.length > 2 ? parts[2].trim() : '',
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
                const parts = r.split('-', 3);
                if (parts.length >= 2) {
                    return {
                        targetName: parts[1].trim(),
                        relationshipType: normalizeRelationshipType(parts[0].trim()),
                        description: parts.length > 2 ? parts[2].trim() : '',
                        createReverse: true
                    };
                }
            }
            return null;
        }).filter(Boolean);
    }

    return [];
}

/**
 * 将关系数据格式化为可读文本
 * 支持格式：
 * - 对象: {targetName, relationshipType, description}
 * - 字符串: "刘禅是我的父母" 或 "父母-刘禅-描述"
 */
function formatRelForDisplay(r) {
    if (typeof r === 'object' && r !== null) {
        const type = r.relationshipType || '其他';
        const target = r.targetName || '';
        const desc = r.description ? ` (${r.description})` : '';
        return `${target} → ${type}${desc}`;
    }
    if (typeof r === 'string') {
        // 尝试解析 "XXX是我的YYY" 格式
        const match = r.match(/(.+?)是我的(.+?)(?:\s*-\s*(.+))?$/);
        if (match) {
            const target = match[1];
            const type = match[2];
            const desc = match[3] ? ` (${match[3]})` : '';
            return `${target} → ${type}${desc}`;
        }
        return r;
    }
    return String(r);
}

function renderOptimizeResult(items) {
    const body = document.getElementById('checkResultBody');
    const list = Array.isArray(items) ? items : (items.optimizations || []);

    if (list.length === 0) {
        body.innerHTML = `
            <div class="check-no-issues">
                <i class="fas fa-info-circle" style="color: #818cf8;"></i>
                <h3 style="margin-bottom: 8px; color: #d1d5db;">无需优化</h3>
                <p style="color: #9ca3af;">AI未找到需要修改的内容</p>
            </div>`;
        document.getElementById('optimizeCheckBtn').hidden = true;
        return;
    }

    let html = '<div class="check-summary"><div class="check-summary-item">AI优化建议 <span>' + list.length + '</span> 项</div></div>';
    html += '<p style="font-size: 13px; color: #9ca3af; margin-bottom: 16px;">勾选要应用的优化，点击「保存优化」按钮确认</p>';

    list.forEach((item, index) => {
        const typeLabel = TYPE_LABELS[item.type] || item.type;
        const params = item.params || [];
        const typeIcon = item.type === 'add' ? 'fa-plus-circle' : item.type === 'delete' ? 'fa-minus-circle' : 'fa-pen';
        const typeColor = item.type === 'add' ? '#22c55e' : item.type === 'delete' ? '#f87171' : '#a5b4fc';

        html += `<div class="check-result-item" data-opt-index="${index}">`;
        html += `<div class="check-result-header">
            <label class="opt-item-header">
                <input type="checkbox" class="opt-checkbox" data-index="${index}" checked>
                <span class="check-result-chars">${escapeHtml(item.name)}</span>
                <i class="fas ${typeIcon}" style="color: ${typeColor};"></i>
                <span style="color: ${typeColor}; font-weight: 600;">${typeLabel}</span>
            </label>
        </div>`;

        if (params.length > 0) {
            html += `<div class="opt-params-container">`;
            params.forEach(p => {
                const fieldLabel = FIELD_LABELS[p.param] || p.param;
                const isRelationships = p.param === 'relationships';
                if (item.type === 'add') {
                    if (isRelationships) {
                        html += `<div class="opt-field-block">
                            <span class="opt-field-block-label">${fieldLabel}：</span>
                            <div class="opt-rel-container">`;
                        const rels = Array.isArray(p.new) ? p.new : (p.new ? [p.new] : []);
                        rels.forEach(r => {
                            const rText = formatRelForDisplay(r);
                            html += `<span class="opt-value-add">${escapeHtml(rText)}</span>`;
                        });
                        html += `</div></div>`;
                    } else {
                        const displayVal = typeof p.new === 'object' ? JSON.stringify(p.new, null, 2) : String(p.new);
                        html += `<div class="opt-field-row">
                            <span class="opt-field-label">${fieldLabel}：</span>
                            <span class="opt-field-value">${escapeHtml(displayVal)}</span>
                        </div>`;
                    }
                } else {
                    if (isRelationships) {
                        html += `<div class="opt-field-block">
                            <span class="opt-field-block-label">${fieldLabel}：</span>
                            <div style="margin-top: 4px;">`;
                        const origRels = Array.isArray(p.origin) ? p.origin : (p.origin ? [p.origin] : []);
                        const newRels = Array.isArray(p.new) ? p.new : (p.new ? [p.new] : []);
                        if (origRels.length > 0) {
                            html += `<div class="opt-field-sublabel">原值：</div>`;
                            origRels.forEach(r => {
                                const rText = formatRelForDisplay(r);
                                html += `<div class="opt-value-old">${escapeHtml(rText)}</div>`;
                            });
                        }
                        if (newRels.length > 0) {
                            html += `<div class="opt-field-sublabel-top">新值：</div>`;
                            newRels.forEach(r => {
                                const rText = formatRelForDisplay(r);
                                html += `<div class="opt-value-new">${escapeHtml(rText)}</div>`;
                            });
                        }
                        html += `</div></div>`;
                    } else {
                        const origVal = typeof p.origin === 'object' ? JSON.stringify(p.origin, null, 2) : String(p.origin || '');
                        const newVal = typeof p.new === 'object' ? JSON.stringify(p.new, null, 2) : String(p.new);
                        html += `<div class="opt-field-block">
                            <span class="opt-field-block-label">${fieldLabel}：</span>
                            <div class="opt-change-row">
                                <span class="opt-value-old">${escapeHtml(origVal)}</span>
                                <i class="fas fa-arrow-right opt-change-arrow"></i>
                                <span class="opt-value-new">${escapeHtml(newVal)}</span>
                            </div>
                        </div>`;
                    }
                }
            });
            html += `</div>`;
        } else if (item.type === 'delete') {
            html += `<div class="opt-delete-notice">该角色将被删除</div>`;
        }

        html += `</div>`;
    });

    body.innerHTML = html;

    // 切换按钮为保存
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    optimizeBtn.innerHTML = '<i class="fas fa-save"></i> 保存优化';
    optimizeBtn.onclick = saveOptimizeResult;
}

async function saveOptimizeResult() {
    if (!currentOptimizeResult) {
        showError('优化结果已失效，请重新优化');
        return;
    }

    const list = Array.isArray(currentOptimizeResult) ? currentOptimizeResult : (currentOptimizeResult.optimizations || []);
    const checkboxes = document.querySelectorAll('.opt-checkbox');
    const saveItems = [];

    checkboxes.forEach(cb => {
        if (!cb.checked) return;
        const index = parseInt(cb.dataset.index);
        const item = list[index];
        if (!item) return;
        saveItems.push(item);
    });

    if (saveItems.length === 0) {
        showError('请至少选择一项优化');
        return;
    }

    const btn = document.getElementById('optimizeCheckBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/optimize/save/`, {
            optimizations: saveItems
        });

        if (data.success) {
            showSuccess(`已保存 ${data.saved_count} 个角色的优化`);
            closeCheckDialog();
            loadCharacters();
        } else {
            showError(data.error || '保存失败');
        }
    } catch (error) {
        console.error('保存优化失败:', error);
        showError('网络错误');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 保存优化';
    }
}

function closeCheckDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('checkDialog').classList.remove('active');
    unlockScroll();
    // 重置优化按钮
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    optimizeBtn.innerHTML = '<i class="fas fa-magic"></i> AI优化';
    optimizeBtn.onclick = optimizeFromCheck;
    optimizeBtn.hidden = true;
    document.getElementById('checkCloseBtn').textContent = '关闭';
    currentCheckIssues = [];
    currentOptimizeResult = null;
}
