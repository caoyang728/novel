// 角色库管理脚本
let currentProjectId = null;
let characters = [];
let filteredCharacters = [];
let allFactions = [];  // 所有势力列表
let currentRelationships = [];  // 当前编辑的角色关系

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

async function checkAuth() {
    try {
        const data = await api.get('/api/auth/user/');
        if (!data.success) {
            window.location.href = '/login.html';
        }
    } catch (error) {
        window.location.href = '/login.html';
    }
}

function initPage() {
    // 从URL查询参数获取项目ID
    const urlParams = new URLSearchParams(window.location.search);
    currentProjectId = urlParams.get('project_id');

    // 设置返回按钮链接
    const backBtn = document.querySelector('.btn-back');
    if (backBtn && currentProjectId) {
        backBtn.onclick = () => { window.location.href = `project.html?project_id=${currentProjectId}`; };
    }

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

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/characters/`);

        if (data.success) {
            characters = data.characters;
            filteredCharacters = [...characters];
            updateFactionFilterOptions();
            renderCharacterList();
        }
    } catch (error) {
        console.error('加载角色失败:', error);
        showError('加载角色失败');
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

    renderCharacterList();
}

function renderCharacterList() {
    const listContainer = document.getElementById('characterList');
    const loading = document.getElementById('loadingState');
    const empty = document.getElementById('emptyState');

    loading.style.display = 'none';

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

    listContainer.innerHTML = filteredCharacters.map(c => {
        const factions = c.faction ? c.faction.split(',').map(f => f.trim()).filter(f => f) : [];
        return `
        <div class="char-item" onclick="openEditDialog(${c.id})">
            <div class="char-item-header">
                <div class="char-item-avatar">${escapeHtml(c.name.charAt(0))}</div>
                <div class="char-item-info">
                    <h4>${escapeHtml(c.name)}</h4>
                    <div class="char-item-tags">
                        <span class="role-tag">${c.role_type_display || c.role_type}</span>
                        ${factions.map(f => `<span class="faction-tag">${escapeHtml(f)}</span>`).join('')}
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
}

function showEmptyState() {
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('characterList').style.display = 'none';
    document.getElementById('emptyState').style.display = 'flex';
}

// ============ 创建角色 ============
function openCreateDialog() {
    // 清空表单 - 基础字段
    document.getElementById('createName').value = '';
    document.getElementById('createRole').value = 'supporting';
    document.getElementById('createGender').value = 'unknown';
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
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const aiActionBtn = document.getElementById('aiActionBtn');
    const saveCreateBtn = document.getElementById('saveCreateBtn');

    if (tab === 'manual') {
        document.querySelector('.create-tab:nth-child(1)').classList.add('active');
        document.getElementById('manualCreateTab').classList.add('active');
        aiActionBtn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
        aiActionBtn.dataset.action = 'polish';
        saveCreateBtn.innerHTML = '<i class="fas fa-save"></i> 保存角色';
        validateManualCreateButtons();
    } else if (tab === 'ai') {
        document.querySelector('.create-tab:nth-child(2)').classList.add('active');
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
        document.querySelector('.create-tab:nth-child(3)').classList.add('active');
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
    const tabType = activeTab ? activeTab.textContent.trim() : 'manual';
    
    if (tabType.includes('手动')) {
        await createCharacter();
    } else if (tabType.includes('AI 生成')) {
        await saveAiGeneratedCharacter();
    } else if (tabType.includes('批量')) {
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
        const data = await api.request(`/api/projects/${currentProjectId}/characters/`, {
            method: 'POST',
            body: JSON.stringify({
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
                extra: {
                    strengths: document.getElementById('createStrengths').value,
                    flaws: document.getElementById('createFlaws').value,
                    obsession: document.getElementById('createObsession').value,
                    abilities: document.getElementById('createAbilities').value,
                    taboos: document.getElementById('createTaboos').value,
                    secrets: document.getElementById('createSecrets').value,
                    dark_history: document.getElementById('createDarkHistory').value,
                    development: document.getElementById('createDevelopment').value,
                    weaknesses: document.getElementById('createWeaknesses').value
                }
            })
        });

        if (data.success) {
            showSuccess('角色创建成功');
            closeCreateDialog();
            loadCharacters();
        } else {
            showError(data.error || '创建失败');
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
let streamingBuffer = '';  // 流式数据缓冲区
let currentCharacterData = {};  // 当前角色数据

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
    currentCharacterData = {};
    streamingBuffer = '';

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
        const decoder = new TextDecoder();
        let buffer = '';

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
                    if (json.type === 'complete' && json.data) {
                        hideLoading();
                        let result = JSON.parse(json.data);
                        if (Array.isArray(result) && result.length > 0) {
                            result = result[0];
                        }
                        currentAiGenerated = result;
                        displayAiGeneratedCharacter(currentAiGenerated);
                        btn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
                        saveBtn.disabled = false;
                        showSuccess('角色生成完成，请确认后保存');
                    } else if (json.type === 'error') {
                        hideLoading();
                        showError(json.message || '生成失败');
                    }
                } catch (e) {
                    console.error('解析失败:', e);
                    showError('解析失败，请重试');
                }
                searchStart = msgEnd + 2;
            }
            if (searchStart > 0) {
                buffer = buffer.substring(searchStart);
            }
        }
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

function processStreamingBuffer() {
    // 定义分隔符
    const ITEM_START = '════ITEM_START════';
    const ITEM_END = '════ITEM_END════';

    // 处理所有完整的 item
    let startIdx;
    while ((startIdx = streamingBuffer.indexOf(ITEM_START)) !== -1) {
        const rest = streamingBuffer.substring(startIdx + ITEM_START.length);
        const endIdx = rest.indexOf(ITEM_END);
        
        if (endIdx === -1) {
            // 不完整的 item，等待更多数据
            break;
        }
        
        // 找到完整的 item，解析并显示
        const itemContent = rest.substring(0, endIdx);
        streamingBuffer = streamingBuffer.substring(startIdx + ITEM_START.length + endIdx + ITEM_END.length);
        
        // 同步解析显示
        parseItem(itemContent);
        
        // 让出主线程，让浏览器渲染
        if (typeof requestAnimationFrame !== 'undefined') {
            requestAnimationFrame(() => {});
        }
    }
}

// 处理 SSE 格式数据
let sseBuffer = '';

function processSSEBuffer() {
    // 查找所有的 "data: " 并提取内容，直到 \n\n
    // SSE 格式: data: {"type":"chunk","data":"..."}\n\n
    let searchStart = 0;
    let dataStart;
    
    while ((dataStart = sseBuffer.indexOf('data: ', searchStart)) !== -1) {
        // 找到 data: 后，查找下一个 \n\n
        const msgEnd = sseBuffer.indexOf('\n\n', dataStart);
        
        if (msgEnd === -1) {
            // 不完整的消息，等待更多数据
            break;
        }
        
        // 提取 data: 后面的内容（到 \n\n 之前）
        const dataContent = sseBuffer.substring(dataStart + 6, msgEnd);
        
        // 解析 JSON 获取 data 字段
        try {
            const json = JSON.parse(dataContent);
            if (json.type === 'chunk' && json.data) {
                streamingBuffer += json.data;
                processStreamingBuffer();
            }
        } catch (e) {
            // JSON 解析失败，可能是中间的数据
        }
        
        searchStart = msgEnd + 2;
    }
    
    // 保留未处理的部分
    if (searchStart > 0) {
        sseBuffer = sseBuffer.substring(searchStart);
    }
}

function parseItem(itemContent) {
    try {
        // 查找第一个 { 和最后一个 }
        const firstBrace = itemContent.indexOf('{');
        const lastBrace = itemContent.lastIndexOf('}');

        if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
            let jsonStr = itemContent.substring(firstBrace, lastBrace + 1);
            // 修复 LLM 可能输出的转义引号 \" -> "
            jsonStr = jsonStr.replace(/\\"/g, '"');
            const data = JSON.parse(jsonStr);
            if (data.type && data.data !== undefined) {
                // 映射字段名到表单ID
                const fieldMap = {
                    'name': 'aiGeneratedName',
                    'role': 'aiGeneratedRole',
                    'age': 'aiGeneratedAge',
                    'identity': 'aiGeneratedIdentity',
                    'personality': 'aiGeneratedPersonality',
                    'strengths': 'aiGeneratedStrengths',
                    'flaws': 'aiGeneratedFlaws',
                    'obsession': 'aiGeneratedObsession',
                    'motivation': 'aiGeneratedMotivation',
                    'appearance': 'aiGeneratedAppearance',
                    'faction': 'aiGeneratedFaction',
                    'relationships': 'aiGeneratedRelationships',
                    'abilities': 'aiGeneratedAbilities',
                    'taboos': 'aiGeneratedTaboos',
                    'dark_history': 'aiGeneratedDarkHistory',
                    'secrets': 'aiGeneratedSecrets',
                    'background': 'aiGeneratedBackground',
                    'development': 'aiGeneratedDevelopment',
                    'weaknesses': 'aiGeneratedWeaknesses',
                    'tags': 'aiGeneratedTags'
                };

                const fieldId = fieldMap[data.type];
                if (fieldId) {
                    // 特殊处理 role 字段
                    if (data.type === 'role') {
                        const roleValue = mapRoleType(data.data);
                        document.getElementById(fieldId).value = roleValue;
                        currentCharacterData['role'] = data.data;
                    } else {
                        document.getElementById(fieldId).value += data.data;
                        currentCharacterData[data.type] = (currentCharacterData[data.type] || '') + data.data;
                    }
                }
            }
        }
    } catch (e) {
        console.warn('解析item失败:', e, itemContent);
    }
}

function parseFieldGroup(fieldGroup) {
    // 字段组结束，清空当前角色数据，开始下一个
    // 这里可以做一些收尾工作
}

function clearAiGeneratedFields() {
    document.getElementById('aiGeneratedName').value = '';
    document.getElementById('aiGeneratedRole').value = 'supporting';
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
    document.getElementById('aiGeneratedRole').value = mapRoleType(charData.role);
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

function mapRoleType(role) {
    const roleMap = {
        '主角': 'protagonist',
        '男主角': 'protagonist',
        '女主角': 'protagonist',
        '反派': 'antagonist',
        '配角': 'supporting',
        '导师': 'supporting',
        '恋人': 'supporting',
        '路人': 'minor',
        'protagonist': 'protagonist',
        'antagonist': 'antagonist',
        'supporting': 'supporting',
        'minor': 'minor'
    };
    return roleMap[role] || 'supporting';
}

function mapGender(gender) {
    const genderMap = {
        '男': 'male',
        '女': 'female',
        'male': 'male',
        'female': 'female'
    };
    return genderMap[gender] || 'unknown';
}

async function regenerateCharacter() {
    await generateCharacterPreview();
}

async function generateCharacter() {
    await generateCharacterPreview();
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
        const data = await api.request(`/api/projects/${currentProjectId}/characters/`, {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                role_type: document.getElementById('aiGeneratedRole').value,
                personality: document.getElementById('aiGeneratedPersonality').value,
                backstory: document.getElementById('aiGeneratedBackground').value,
                appearance: document.getElementById('aiGeneratedAppearance').value,
                motivation: document.getElementById('aiGeneratedMotivation').value,
                tagline: document.getElementById('aiGeneratedTags').value,
                faction: document.getElementById('aiGeneratedFaction').value,
                extra: {
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
                    weaknesses: document.getElementById('aiGeneratedWeaknesses').value
                }
            })
        });

        if (data.success) {
            showSuccess('角色保存成功');
            closeCreateDialog();
            document.getElementById('aiGeneratedContent').style.display = 'none';
            document.getElementById('aiDescription').value = '';
            currentAiGenerated = null;
            loadCharacters();
        } else {
            showError(data.error || '保存失败');
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
let batchStreamingBuffer = '';
let batchSSEBuffer = '';

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
    document.getElementById('popupGeneratedCount').textContent = '0';
    
    currentBatchGenerated = [];
    batchStreamingBuffer = '';

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
        const decoder = new TextDecoder();
        let buffer = '';

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
                    if (json.type === 'complete' && json.data) {
                        hideLoading();
                        const results = JSON.parse(json.data);
                        if (Array.isArray(results)) {
                            currentBatchGenerated = results.map((char, index) => ({
                                ...char,
                                selected: true,
                                index: index
                            }));
                            renderBatchCharacters();
                            document.getElementById('batchGeneratedContent').style.display = 'block';
                            document.getElementById('popupGeneratedCount').textContent = currentBatchGenerated.length.toString();
                            btn.innerHTML = '<i class="fas fa-redo"></i> AI 重新生成';
                            validateBatchCreateButtons();
                            showSuccess(`成功生成 ${currentBatchGenerated.length} 个角色`);
                        } else {
                            showError('生成失败，格式错误');
                        }
                    } else if (json.type === 'error') {
                        hideLoading();
                        showError(json.message || '生成失败');
                    }
                } catch (e) {
                    console.error('解析失败:', e);
                    showError('解析失败，请重试');
                }
                searchStart = msgEnd + 2;
            }
            if (searchStart > 0) {
                buffer = buffer.substring(searchStart);
            }
        }
    } catch (error) {
        console.error('批量生成角色失败:', error);
        showError('网络错误，请重试');
    } finally {
        hideLoading();
        btn.disabled = false;
    }
}

function processBatchSSEBuffer() {
    let searchStart = 0;
    let dataStart;
    while ((dataStart = batchSSEBuffer.indexOf('data: ', searchStart)) !== -1) {
        const msgEnd = batchSSEBuffer.indexOf('\n\n', dataStart);
        if (msgEnd === -1) break;
        const dataContent = batchSSEBuffer.substring(dataStart + 6, msgEnd);
        try {
            const json = JSON.parse(dataContent);
            if (json.type === 'chunk' && json.data) {
                batchStreamingBuffer += json.data;
                processBatchStreamingBuffer();
            }
        } catch (e) {
        }
        searchStart = msgEnd + 2;
    }
    if (searchStart > 0) {
        batchSSEBuffer = batchSSEBuffer.substring(searchStart);
    }
}

function processBatchStreamingBuffer(isFinal = false) {
    const CHAR_START = '════CHARACTER_START════';
    const CHAR_END = '════CHARACTER_END════';

    while (true) {
        const startIdx = batchStreamingBuffer.indexOf(CHAR_START);
        if (startIdx === -1) break;

        const charContentStart = startIdx + CHAR_START.length;
        const endIdx = batchStreamingBuffer.indexOf(CHAR_END, charContentStart);

        if (endIdx === -1) {
            if (isFinal) {
                const remaining = batchStreamingBuffer.substring(charContentStart).trim();
                if (remaining) tryParseBatchCharacter(remaining);
                batchStreamingBuffer = '';
            }
            break;
        }

        const charContent = batchStreamingBuffer.substring(charContentStart, endIdx).trim();
        tryParseBatchCharacter(charContent);

        batchStreamingBuffer = batchStreamingBuffer.substring(endIdx + CHAR_END.length);
    }
}

function tryParseBatchCharacter(content) {
    try {
        const jsonMatch = content.match(/\{[\s\S]*\}/);
        if (!jsonMatch) return;

        const character = JSON.parse(jsonMatch[0]);
        character.selected = true;
        character.index = currentBatchGenerated.length;
        currentBatchGenerated.push(character);

        // 更新loading进度显示（弹窗）
        document.getElementById('popupGeneratedCount').textContent = currentBatchGenerated.length.toString();
        document.getElementById('popupLoadingStatus').textContent = `正在生成角色 ${character.name}...`;

        renderBatchCharacters();
        document.getElementById('batchGeneratedContent').style.display = 'block';
    } catch (e) {
        console.warn('解析角色失败:', e);
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
                    <span class="batch-character-role">${char.role || '配角'}</span>
                </div>
                <div class="batch-character-info">
                    ${char.age ? `<span class="info-item">年龄: ${char.age}</span>` : ''}
                    ${char.identity ? `<span class="info-item">身份: ${char.identity}</span>` : ''}
                    ${char.faction ? `<span class="info-item">势力: ${char.faction}</span>` : ''}
                </div>
                <div class="batch-character-description">
                    ${char.personality ? `<p><strong>性格:</strong> ${escapeHtml(char.personality)}</p>` : ''}
                    ${char.background ? `<p><strong>背景:</strong> ${escapeHtml(char.background.substring(0, 100))}${char.background.length > 100 ? '...' : ''}</p>` : ''}
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
        const savedCount = 0;
        for (const char of selectedCharacters) {
            const data = await api.request(`/api/projects/${currentProjectId}/characters/`, {
                method: 'POST',
                body: JSON.stringify({
                    name: char.name || `角色${Date.now()}`,
                    gender: mapGender(char.gender),
                    role_type: mapRoleType(char.role),
                    personality: char.personality || '',
                    backstory: char.background || char.backstory || '',
                    appearance: char.appearance || '',
                    motivation: char.motivation || '',
                    tagline: char.tags || '',
                    faction: char.faction || '',
                    extra: {
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
                        weaknesses: char.weaknesses || ''
                    }
                })
            });
            
            if (!data.success) {
                console.warn(`保存角色 ${char.name} 失败:`, data.error);
            }
        }

        showSuccess(`成功保存 ${selectedCharacters.length} 个角色`);
        closeCreateDialog();
        currentBatchGenerated = null;
        loadCharacters();
    } catch (error) {
        console.error('批量保存角色失败:', error);
        showError('网络错误');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> 批量保存';
    }
}

function clearBatchGenerated() {
    currentBatchGenerated = null;
    document.getElementById('batchGeneratedContent').style.display = 'none';
    document.getElementById('batchDescription').value = '';
    document.getElementById('batchCount').value = '5';
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
        const extra = character.extra || {};

        document.getElementById('editCharacterId').value = character.id;
        document.getElementById('editName').value = character.name || '';
        document.getElementById('editRole').value = character.role_type || 'supporting';
        document.getElementById('editGender').value = character.gender || 'unknown';
        document.getElementById('editAge').value = extra.age || '';
        document.getElementById('editIdentity').value = extra.identity || '';
        document.getElementById('editTags').value = character.tagline || '';
        document.getElementById('editFaction').value = character.faction || '';
        document.getElementById('editAppearance').value = character.appearance || '';
        document.getElementById('editPersonality').value = character.personality || '';
        document.getElementById('editBackground').value = character.backstory || '';
        document.getElementById('editMotivation').value = extra.motivation || character.motivation || '';
        document.getElementById('editDevelopment').value = character.motivation || extra.development || '';
        document.getElementById('editStrengths').value = extra.strengths || '';
        document.getElementById('editFlaws').value = extra.flaws || '';
        document.getElementById('editObsession').value = extra.obsession || '';
        document.getElementById('editTaboos').value = extra.taboos || '';
        document.getElementById('editAbilities').value = extra.abilities || '';
        document.getElementById('editSecrets').value = extra.secrets || '';
        document.getElementById('editDarkHistory').value = extra.dark_history || '';

        // 加载关系数据
        currentRelationships = extra.relationships ? parseRelationships(extra.relationships) : [];
        renderRelationshipsTable();

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
    if (!confirm('确定要删除这个角色吗？')) return;

    try {
        const data = await api.request(`/api/projects/${currentProjectId}/characters/${id}/`, {
            method: 'DELETE'
        });

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
}

// ==================== 人际关系表格 ====================
// 关系类型映射（包含反向关系）
const RELATIONSHIP_TYPES = [
    { value: 'friend', label: '朋友', reverse: 'friend' },
    { value: 'lover', label: '恋人', reverse: 'lover' },
    { value: 'spouse', label: '配偶', reverse: 'spouse' },
    { value: 'parent', label: '父母', reverse: 'child' },
    { value: 'child', label: '子女', reverse: 'parent' },
    { value: 'sibling', label: '兄弟姐妹', reverse: 'sibling' },
    { value: 'master', label: '师父', reverse: 'apprentice' },
    { value: 'apprentice', label: '徒弟', reverse: 'master' },
    { value: 'enemy', label: '敌人', reverse: 'enemy' },
    { value: 'rival', label: '对手', reverse: 'rival' },
    { value: 'mentor', label: '导师', reverse: 'protégé' },
    { value: 'protégé', label: '门生', reverse: 'mentor' },
    { value: 'ally', label: '盟友', reverse: 'ally' },
    { value: 'family', label: '亲属', reverse: 'family' },
    { value: 'other', label: '其他', reverse: 'other' },
];

// 解析关系数据（支持字符串和数组格式）
function parseRelationships(data) {
    if (Array.isArray(data)) {
        // 确保每个关系都有 createReverse 标志
        return data.map(rel => {
            if (typeof rel === 'object' && rel !== null) {
                return {
                    ...rel,
                    createReverse: rel.createReverse !== false // 默认 true，除非显式 false
                };
            }
            return rel;
        });
    }
    if (typeof data === 'string' && data.trim()) {
        // 尝试从旧格式解析
        return data.split(/[,，]/).map(rel => {
            const parts = rel.split(/[-—]/);
            if (parts.length >= 2) {
                return {
                    targetName: parts[0].trim(),
                    relationshipType: parts[1].trim(),
                    description: parts.length > 2 ? parts.slice(2).join('-').trim() : '',
                    createReverse: true // 旧数据也默认创建反向
                };
            }
            return null;
        }).filter(r => r !== null);
    }
    return [];
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
    targetSelect.style.width = '100%';
    targetSelect.style.padding = '8px 12px';
    targetSelect.style.border = '1px solid #e2e8f0';
    targetSelect.style.borderRadius = '8px';
    targetSelect.innerHTML = `
        <option value="">选择角色...</option>
        <option value="custom" ${rel.targetName && !availableCharacters.find(c => c.name === rel.targetName) ? 'selected' : ''}>自定义...</option>
        ${availableCharacters.map(c => `<option value="${c.name}" ${rel.targetName === c.name ? 'selected' : ''}>${c.name}</option>`).join('')}
    `;

    const customInput = document.createElement('input');
    customInput.style.width = '100%';
    customInput.style.marginTop = '8px';
    customInput.style.padding = '8px 12px';
    customInput.style.border = '1px solid #e2e8f0';
    customInput.style.borderRadius = '8px';
    customInput.placeholder = '输入角色名';
    customInput.value = rel.targetName || '';
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
    typeSelect.style.width = '100%';
    typeSelect.style.padding = '8px 12px';
    typeSelect.style.border = '1px solid #e2e8f0';
    typeSelect.style.borderRadius = '8px';
    typeSelect.innerHTML = RELATIONSHIP_TYPES.map(t => 
        `<option value="${t.value}" ${rel.relationshipType === t.value ? 'selected' : ''}>${t.label}</option>`
    ).join('');
    typeSelect.addEventListener('change', function() {
        currentRelationships[index].relationshipType = this.value;
        const typeInfo = RELATIONSHIP_TYPES.find(t => t.value === this.value);
        if (typeInfo) {
            currentRelationships[index].reverseRelationship = typeInfo.reverse;
        }
    });
    typeCell.appendChild(typeSelect);
    row.appendChild(typeCell);

    // 关系描述
    const descCell = document.createElement('td');
    const descInput = document.createElement('textarea');
    descInput.style.width = '100%';
    descInput.style.padding = '8px 12px';
    descInput.style.border = '1px solid #e2e8f0';
    descInput.style.borderRadius = '8px';
    descInput.style.minHeight = '40px';
    descInput.placeholder = '描述关系...';
    descInput.rows = 1;
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
        relationshipType: 'friend',
        description: '',
        createReverse: true, // 默认创建反向关系
        reverseRelationship: 'friend'
    });
    renderRelationshipsTable();
}

// 切换编辑标签页
function switchEditTab(tab) {
    document.querySelectorAll('.edit-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#editDialog .tab-content').forEach(c => c.classList.remove('active'));

    const tabIndex = ['basic', 'social', 'ability', 'other'].indexOf(tab);
    document.querySelectorAll('.edit-tab')[tabIndex].classList.add('active');
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
        const data = await api.request(`/api/projects/${currentProjectId}/characters/${id}/`, {
            method: 'PUT',
            body: JSON.stringify({
                name: name,
                role_type: document.getElementById('editRole').value,
                gender: document.getElementById('editGender').value,
                tagline: document.getElementById('editTags').value,
                faction: normalizeFactionInput(document.getElementById('editFaction').value),
                appearance: document.getElementById('editAppearance').value,
                personality: document.getElementById('editPersonality').value,
                backstory: document.getElementById('editBackground').value,
                motivation: document.getElementById('editMotivation').value,
                extra: {
                    age: document.getElementById('editAge').value,
                    identity: document.getElementById('editIdentity').value,
                    relationships: currentRelationships,
                    development: document.getElementById('editDevelopment').value,
                    strengths: document.getElementById('editStrengths').value,
                    flaws: document.getElementById('editFlaws').value,
                    obsession: document.getElementById('editObsession').value,
                    taboos: document.getElementById('editTaboos').value,
                    abilities: document.getElementById('editAbilities').value,
                    secrets: document.getElementById('editSecrets').value,
                    dark_history: document.getElementById('editDarkHistory').value
                }
            })
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
        btn.innerHTML = '保存修改';
    }
}

// ============ AI润色 ============
// 创建角色弹窗的AI润色
async function polishCharacter() {
    const name = document.getElementById('createName').value.trim();
    const gender = document.getElementById('createGender')?.value || '';
    const role = document.getElementById('createRole')?.value || '';
    const age = document.getElementById('createAge')?.value || '';
    const identity = document.getElementById('createIdentity')?.value || '';
    const personality = document.getElementById('createPersonality').value.trim();
    const strengths = document.getElementById('createStrengths')?.value || '';
    const flaws = document.getElementById('createFlaws')?.value || '';
    const obsession = document.getElementById('createObsession')?.value || '';
    const motivation = document.getElementById('createMotivation')?.value || '';
    const appearance = document.getElementById('createAppearance').value.trim();
    const faction = document.getElementById('createFaction').value.trim();
    const relationships = document.getElementById('createRelationships')?.value || '';
    const abilities = document.getElementById('createAbilities')?.value || '';
    const taboos = document.getElementById('createTaboos')?.value || '';
    const darkHistory = document.getElementById('createDarkHistory')?.value || '';
    const secrets = document.getElementById('createSecrets')?.value || '';
    const backstory = document.getElementById('createBackground').value.trim();
    const development = document.getElementById('createDevelopment').value.trim();
    const weaknesses = document.getElementById('createWeaknesses').value.trim();
    const tags = document.getElementById('createTags')?.value || '';

    if (!name) {
        showError('请先输入角色名称');
        return;
    }

    const btn = document.getElementById('aiActionBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 润色中...';

    let fullContent = '';
    let isCompleted = false;

    showLoading('正在润色角色...');

    try {
        const response = await api.request(`/api/projects/${currentProjectId}/characters/polish/`, {
            method: 'POST',
            stream: true,
            body: JSON.stringify({
                name: name,
                gender: gender,
                role: role,
                age: age,
                identity: identity,
                personality: personality,
                strengths: strengths,
                flaws: flaws,
                obsession: obsession,
                motivation: motivation,
                appearance: appearance,
                faction: faction,
                relationships: relationships,
                abilities: abilities,
                taboos: taboos,
                dark_history: darkHistory,
                secrets: secrets,
                backstory: backstory,
                development: development,
                weaknesses: weaknesses,
                tags: tags
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            sseBuffer += decoder.decode(value, { stream: true });
            
            // 解析SSE
            let searchStart = 0;
            let dataStart;
            while ((dataStart = sseBuffer.indexOf('data: ', searchStart)) !== -1) {
                const msgEnd = sseBuffer.indexOf('\n\n', dataStart);
                if (msgEnd === -1) break;
                const dataContent = sseBuffer.substring(dataStart + 6, msgEnd);
                try {
                    const json = JSON.parse(dataContent);
                    
                    if (json.type === 'chunk' && json.data) {
                        fullContent += json.data;
                    } else if (json.type === 'complete') {
                        hideLoading();
                        try {
                            let contentStr = json.data || '';
                            const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
                            if (jsonMatch) contentStr = jsonMatch[0];
                            const result = JSON.parse(contentStr);
                            if (result.gender !== undefined && document.getElementById('createGender')) document.getElementById('createGender').value = mapGenderToSelect(result.gender);
                            if (result.role !== undefined && document.getElementById('createRole')) document.getElementById('createRole').value = mapRoleToSelect(result.role);
                            if (result.age !== undefined && document.getElementById('createAge')) document.getElementById('createAge').value = result.age;
                            if (result.identity !== undefined && document.getElementById('createIdentity')) document.getElementById('createIdentity').value = result.identity;
                            if (result.personality !== undefined) document.getElementById('createPersonality').value = result.personality;
                            if (result.strengths !== undefined && document.getElementById('createStrengths')) document.getElementById('createStrengths').value = result.strengths;
                            if (result.flaws !== undefined && document.getElementById('createFlaws')) document.getElementById('createFlaws').value = result.flaws;
                            if (result.obsession !== undefined && document.getElementById('createObsession')) document.getElementById('createObsession').value = result.obsession;
                            if (result.motivation !== undefined && document.getElementById('createMotivation')) document.getElementById('createMotivation').value = result.motivation;
                            if (result.appearance !== undefined) document.getElementById('createAppearance').value = result.appearance;
                            if (result.faction !== undefined) document.getElementById('createFaction').value = result.faction;
                            if (result.relationships !== undefined && document.getElementById('createRelationships')) document.getElementById('createRelationships').value = result.relationships;
                            if (result.abilities !== undefined && document.getElementById('createAbilities')) document.getElementById('createAbilities').value = result.abilities;
                            if (result.taboos !== undefined && document.getElementById('createTaboos')) document.getElementById('createTaboos').value = result.taboos;
                            if (result.dark_history !== undefined && document.getElementById('createDarkHistory')) document.getElementById('createDarkHistory').value = result.dark_history;
                            if (result.secrets !== undefined && document.getElementById('createSecrets')) document.getElementById('createSecrets').value = result.secrets;
                            if (result.backstory !== undefined) document.getElementById('createBackground').value = result.backstory;
                            if (result.development !== undefined) document.getElementById('createDevelopment').value = result.development;
                            if (result.weaknesses !== undefined) document.getElementById('createWeaknesses').value = result.weaknesses;
                            if (result.tags !== undefined && document.getElementById('createTags')) document.getElementById('createTags').value = result.tags;
                            showSuccess('AI润色完成');
                            isCompleted = true;
                        } catch (e) {
                            console.error('解析完整结果失败:', e);
                            showError('解析结果失败');
                        }
                    } else if (json.type === 'error') {
                        hideLoading();
                        showError(json.message || '润色失败');
                    }
                } catch (e) {
                }
                searchStart = msgEnd + 2;
            }
            if (searchStart > 0) {
                sseBuffer = sseBuffer.substring(searchStart);
            }
        }
        
        // 如果没收到final，尝试解析完整内容
        if (!isCompleted && fullContent) {
            const jsonMatch = fullContent.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                try {
                    const data = JSON.parse(jsonMatch[0]);
                    if (data.gender && document.getElementById('createGender')) document.getElementById('createGender').value = mapGenderToSelect(data.gender);
                    if (data.role && document.getElementById('createRole')) document.getElementById('createRole').value = mapRoleToSelect(data.role);
                    if (data.age && document.getElementById('createAge')) document.getElementById('createAge').value = data.age;
                    if (data.identity && document.getElementById('createIdentity')) document.getElementById('createIdentity').value = data.identity;
                    if (data.personality) document.getElementById('createPersonality').value = data.personality;
                    if (data.strengths && document.getElementById('createStrengths')) document.getElementById('createStrengths').value = data.strengths;
                    if (data.flaws && document.getElementById('createFlaws')) document.getElementById('createFlaws').value = data.flaws;
                    if (data.obsession && document.getElementById('createObsession')) document.getElementById('createObsession').value = data.obsession;
                    if (data.motivation && document.getElementById('createMotivation')) document.getElementById('createMotivation').value = data.motivation;
                    if (data.appearance) document.getElementById('createAppearance').value = data.appearance;
                    if (data.faction) document.getElementById('createFaction').value = data.faction;
                    if (data.relationships && document.getElementById('createRelationships')) document.getElementById('createRelationships').value = data.relationships;
                    if (data.abilities && document.getElementById('createAbilities')) document.getElementById('createAbilities').value = data.abilities;
                    if (data.taboos && document.getElementById('createTaboos')) document.getElementById('createTaboos').value = data.taboos;
                    if (data.dark_history && document.getElementById('createDarkHistory')) document.getElementById('createDarkHistory').value = data.dark_history;
                    if (data.secrets && document.getElementById('createSecrets')) document.getElementById('createSecrets').value = data.secrets;
                    if (data.backstory) document.getElementById('createBackground').value = data.backstory;
                    if (data.development) document.getElementById('createDevelopment').value = data.development;
                    if (data.weaknesses) document.getElementById('createWeaknesses').value = data.weaknesses;
                    if (data.tags && document.getElementById('createTags')) document.getElementById('createTags').value = data.tags;
                    showSuccess('AI润色完成');
                } catch (e) {
                    showError('解析结果失败');
                }
            }
        }
    } catch (error) {
        console.error('AI润色失败:', error);
        showError('网络错误');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
    }
}

function mapGenderToSelect(gender) {
    const genderMap = {
        '男': 'male',
        '女': 'female',
        'male': 'male',
        'female': 'female'
    };
    return genderMap[gender] || 'unknown';
}

function mapRoleToSelect(role) {
    const roleMap = {
        '主角': 'protagonist',
        '男主角': 'protagonist',
        '女主角': 'protagonist',
        '反派': 'antagonist',
        '配角': 'supporting',
        '导师': 'supporting',
        '恋人': 'supporting',
        '路人': 'minor',
        'protagonist': 'protagonist',
        'antagonist': 'antagonist',
        'supporting': 'supporting',
        'minor': 'minor'
    };
    return roleMap[role] || 'supporting';
}

// 编辑角色弹窗的AI润色
async function polishEditCharacter() {
    const name = document.getElementById('editName').value.trim();
    const gender = document.getElementById('editGender')?.value || '';
    const role = document.getElementById('editRole')?.value || '';
    const age = document.getElementById('editAge')?.value || '';
    const identity = document.getElementById('editIdentity')?.value || '';
    const personality = document.getElementById('editPersonality').value.trim();
    const strengths = document.getElementById('editStrengths')?.value || '';
    const flaws = document.getElementById('editFlaws')?.value || '';
    const obsession = document.getElementById('editObsession')?.value || '';
    const motivation = document.getElementById('editMotivation')?.value || '';
    const appearance = document.getElementById('editAppearance').value.trim();
    const faction = document.getElementById('editFaction')?.value || '';
    const abilities = document.getElementById('editAbilities')?.value || '';
    const taboos = document.getElementById('editTaboos')?.value || '';
    const darkHistory = document.getElementById('editDarkHistory')?.value || '';
    const secrets = document.getElementById('editSecrets')?.value || '';
    const backstory = document.getElementById('editBackground').value.trim();
    const development = document.getElementById('editDevelopment').value.trim();
    const weaknesses = document.getElementById('editWeaknesses')?.value || '';
    const tags = document.getElementById('editTags')?.value || '';

    if (!name) {
        showError('请先输入角色名称');
        return;
    }

    const btn = document.getElementById('polishEditBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 润色中...';

    let fullContent = '';
    let isCompleted = false;

    showLoading('正在润色角色...');

    try {
        const response = await api.request(`/api/projects/${currentProjectId}/characters/polish/`, {
            method: 'POST',
            stream: true,
            body: JSON.stringify({
                name: name,
                gender: gender,
                role: role,
                age: age,
                identity: identity,
                personality: personality,
                strengths: strengths,
                flaws: flaws,
                obsession: obsession,
                motivation: motivation,
                appearance: appearance,
                faction: faction,
                abilities: abilities,
                taboos: taboos,
                dark_history: darkHistory,
                secrets: secrets,
                backstory: backstory,
                development: development,
                weaknesses: weaknesses,
                tags: tags
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            sseBuffer += decoder.decode(value, { stream: true });

            // 解析SSE
            let searchStart = 0;
            let dataStart;
            while ((dataStart = sseBuffer.indexOf('data: ', searchStart)) !== -1) {
                const msgEnd = sseBuffer.indexOf('\n\n', dataStart);
                if (msgEnd === -1) break;
                const dataContent = sseBuffer.substring(dataStart + 6, msgEnd);
                try {
                    const json = JSON.parse(dataContent);

                    if (json.type === 'chunk' && json.data) {
                        fullContent += json.data;
                    } else if (json.type === 'complete') {
                        hideLoading();
                        try {
                            let contentStr = json.data || '';
                            const jsonMatch = contentStr.match(/\{[\s\S]*\}/);
                            if (jsonMatch) contentStr = jsonMatch[0];
                            const result = JSON.parse(contentStr);
                            applyPolishResultToEditForm(result);
                            showSuccess('AI润色完成');
                            isCompleted = true;
                        } catch (e) {
                            console.error('解析完整结果失败:', e);
                            showError('解析结果失败');
                        }
                    } else if (json.type === 'error') {
                        hideLoading();
                        showError(json.message || '润色失败');
                    }
                } catch (e) {
                }
                searchStart = msgEnd + 2;
            }
            if (searchStart > 0) {
                sseBuffer = sseBuffer.substring(searchStart);
            }
        }

        // 如果没收到final，尝试解析完整内容
        if (!isCompleted && fullContent) {
            const jsonMatch = fullContent.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                try {
                    const data = JSON.parse(jsonMatch[0]);
                    applyPolishResultToEditForm(data);
                    showSuccess('AI润色完成');
                } catch (e) {
                    showError('解析结果失败');
                }
            }
        }
    } catch (error) {
        console.error('AI润色失败:', error);
        showError('网络错误');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-star"></i> AI 润色';
    }
}

function applyPolishResultToEditForm(data) {
    if (data.name !== undefined) document.getElementById('editName').value = data.name;
    if (data.gender !== undefined && document.getElementById('editGender')) document.getElementById('editGender').value = mapGenderToSelect(data.gender);
    if (data.role !== undefined && document.getElementById('editRole')) document.getElementById('editRole').value = mapRoleToSelect(data.role);
    if (data.age !== undefined && document.getElementById('editAge')) document.getElementById('editAge').value = data.age;
    if (data.identity !== undefined && document.getElementById('editIdentity')) document.getElementById('editIdentity').value = data.identity;
    if (data.personality !== undefined) document.getElementById('editPersonality').value = data.personality;
    if (data.strengths !== undefined && document.getElementById('editStrengths')) document.getElementById('editStrengths').value = data.strengths;
    if (data.flaws !== undefined && document.getElementById('editFlaws')) document.getElementById('editFlaws').value = data.flaws;
    if (data.obsession !== undefined && document.getElementById('editObsession')) document.getElementById('editObsession').value = data.obsession;
    if (data.motivation !== undefined && document.getElementById('editMotivation')) document.getElementById('editMotivation').value = data.motivation;
    if (data.appearance !== undefined) document.getElementById('editAppearance').value = data.appearance;
    if (data.faction !== undefined && document.getElementById('editFaction')) document.getElementById('editFaction').value = data.faction;
    if (data.abilities !== undefined && document.getElementById('editAbilities')) document.getElementById('editAbilities').value = data.abilities;
    if (data.taboos !== undefined && document.getElementById('editTaboos')) document.getElementById('editTaboos').value = data.taboos;
    if (data.dark_history !== undefined && document.getElementById('editDarkHistory')) document.getElementById('editDarkHistory').value = data.dark_history;
    if (data.secrets !== undefined && document.getElementById('editSecrets')) document.getElementById('editSecrets').value = data.secrets;
    if (data.backstory !== undefined) document.getElementById('editBackground').value = data.backstory;
    if (data.development !== undefined) document.getElementById('editDevelopment').value = data.development;
    if (data.weaknesses !== undefined && document.getElementById('editWeaknesses')) document.getElementById('editWeaknesses').value = data.weaknesses;
    if (data.tags !== undefined && document.getElementById('editTags')) document.getElementById('editTags').value = data.tags;
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


