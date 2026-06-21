let currentProjectId = null;
let worldviewId = null;
let axioms = [''];
let currentWorldview = null;
let currentStructure = null;
let _originalFlatData = {};  // { layerName: { flatKey: originalValue, ... } } — dirty tracking 快照

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


// ==================== Dirty Tracking 辅助函数 ====================

function captureOriginalLayerData(layerName) {
    /** 快照当前层所有字段的 DOM 值，用于后续 dirty 检测 */
    const config = LAYER_SAVE_CONFIG[layerName];
    if (!config || !config.fields) return;
    if (!_originalFlatData[layerName]) _originalFlatData[layerName] = {};
    for (const field of config.fields) {
        const val = field.valueFn
            ? field.valueFn()
            : (document.getElementById(field.id)?.value || '');
        _originalFlatData[layerName][field.key] = val;
    }
}

function getDirtyFields(layerName) {
    /** 对比当前 DOM 值与快照，返回脏字段 */
    const config = LAYER_SAVE_CONFIG[layerName];
    if (!config || !config.fields) return { dirtyData: {}, changedKeys: [] };
    const snapshot = _originalFlatData[layerName] || {};
    const dirtyData = {};
    const changedKeys = [];
    for (const field of config.fields) {
        const currentVal = field.valueFn
            ? field.valueFn()
            : (document.getElementById(field.id)?.value || '');
        const originalVal = snapshot[field.key] !== undefined ? snapshot[field.key] : '';
        if (currentVal !== originalVal) {
            dirtyData[field.key] = currentVal;
            changedKeys.push(field.key);
        }
    }
    return { dirtyData, changedKeys };
}

document.addEventListener('DOMContentLoaded', async function() {
    showLoading('加载中...');
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id');
    currentProjectId = projectId;

    if (projectId) {
        loadProjectInfo(projectId);
    }

    initGenreDropdown();
    initAutoResizeTextareas();

    if (projectId) {
        try {
            const data = await api.get(`/api/projects/${currentProjectId}/worldviews/`);
            if (data.success && data.data) {
                worldviewId = data.data.worldview_id;
                currentWorldview = data.data;
                updateWorldviewUI(data.data);
            } else {
                showError(data.message || '获取世界观失败');
            }
        } catch (error) {
            console.error('Failed to load world by project:', error);
            showError('获取世界观失败');
        }
    } else if (worldviewId) {
        await loadWorldData(worldviewId);
    } else {
        showError('无法加载世界观数据');
    }
    hideLoading();
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

    // 初始化 dirty tracking 快照（渲染后所有 DOM 值已就绪）
    const allLayers = ['setting', 'foundation', 'power', 'races', 'society', 'culture', 'history', 'special'];
    allLayers.forEach(l => captureOriginalLayerData(l));

    setTimeout(() => initAutoResizeTextareas(), 100);
}

async function loadWorldData(wvId) {
    try {
        const data = await api.get(`/api/projects/${currentProjectId}/worldviews/${wvId}/`);
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
        <input type="text" class="form-control mb-2" placeholder="核心规则 ${index + 1}" value="${escapeHtml(axiom)}" onchange="updateAxiom(${index}, this.value)">
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
        targetTab.classList.add('active');
    }
}



/* setField 已迁移到 common.js */



/* showElement 已迁移到 common.js（增强版支持 d-none 类和元素 ID） */

/* hideElement 已迁移到 common.js（增强版支持自定义隐藏类名和元素 ID） */

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

const worldviewSuggestionMixin = {
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

    getImpactText(impact) {
        const impacts = {
            'low': '影响较小',
            'medium': '中等影响',
            'high': '影响较大',
            'critical': '关键影响'
        };
        return impacts[impact] || impact;
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

// Alpine.js 宏观缺口检测状态对象 - 工厂函数形式
function deepeningState() {
    return {
        state: 'empty',  // empty | hasQuestions | noQuestions | hasSuggestions
        questions: [],
        suggestions: [],

        get hasAnswer() {
            return this.questions.some(q => (q.answer || '').trim().length > 0);
        },

        async generateQuestions() {
            if (!worldviewId) return;
            showLoading('正在检测宏观缺口...');

            try {
                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/deepening/questions/`, {
                    method: 'POST'
                });

                if (data.success) {
                    const questions = (data.data || []).map(q => ({ ...q, answer: q.answer || '' }));
                    this.questions = questions;

                    if (questions.length === 0) {
                        this.state = 'noQuestions';
                        showToast('世界观已较为完善');
                    } else {
                        this.state = 'hasQuestions';
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
        },

        async submitAnswers() {
            if (!worldviewId) return;
            showLoading('正在提交并分析...');

            const qaList = [];
            this.questions.forEach(q => {
                const answerText = (q.answer || '').trim();
                if (answerText) {
                    qaList.push({
                        id: q.id,
                        question: q.question,
                        answer: answerText
                    });
                }
            });

            try {
                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/deepening/submit/`, {
                    method: 'POST',
                    body: JSON.stringify({ qaList })
                });

                if (data.success) {
                    this.suggestions = (data.data || []).map(s => ({ ...s, selected: true }));
                    this.state = 'hasSuggestions';
                    window.currentSuggestions = this.suggestions;
                    showToast('提交成功');
                }
            } catch (error) {
                console.error('Failed to submit answers:', error);
                showToast('提交失败', 'error');
            } finally {
                hideLoading();
            }
        },

        async applyChanges() {
            if (!worldviewId) return;

            const selectedChanges = this.suggestions.filter(s => s.selected);
            if (selectedChanges.length === 0) {
                showToast('请至少选择一个修改建议');
                return;
            }

            showLoading('正在应用修改...');

            try {
                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/deepening/apply/`, {
                    method: 'POST',
                    body: JSON.stringify({ changes: selectedChanges })
                });

                if (data.success) {
                    showToast('修改已应用');
                    await loadWorldData(worldviewId);
                    this.resetState();
                }
            } catch (error) {
                console.error('Failed to apply changes:', error);
                showToast('应用修改失败', 'error');
            } finally {
                hideLoading();
            }
        },

        resetState() {
            this.state = 'empty';
            this.questions = [];
            this.suggestions = [];
        },

        ...worldviewSuggestionMixin
    };
}

// Alpine.js 宏观一致性检测状态对象 - 工厂函数形式
function consistencyState() {
    return {
        state: 'empty',
        issues: [],
        suggestions: [],

        async checkConsistency() {
            if (!worldviewId) return;
            showLoading('正在检测宏观一致性...');

            try {
                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/consistency/check/`, {
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

                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/consistency/fix/`, {
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
        },

        async applyConsistencyChanges() {
            if (!worldviewId) return;

            const selectedChanges = this.suggestions.filter(s => s.selected);
            if (selectedChanges.length === 0) {
                showToast('请至少选择一个修改建议');
                return;
            }

            showLoading('正在应用修改...');

            try {
                const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/deepening/apply/`, {
                    method: 'POST',
                    body: JSON.stringify({ changes: selectedChanges })
                });

                if (data.success) {
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

        ...worldviewSuggestionMixin
    };
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
    setField('cultureFood', daily.cuisine || daily.food);
    setField('cultureArchitecture', daily.architecture);
    setField('cultureTransport', daily.transportation);
    setField('cultureDeity', religion.deities || religion.deity);
    setField('cultureReligionOrg', religion.organization);
    setField('cultureFaithDiff', religion.faith_differences || religion.faith_diff);
}

function renderSociety(structure) {
    const s = structure.society || {};
    const court = s.court || {};
    const sect = s.sect || {};
    const martial = s.martial || {};
    const strata = s.strata || {};
    const currency = s.currency || {};
    
    setField('societyGovernment', court.political_system);
    setField('societyBureaucracy', court.bureaucracy);
    setField('societySectLevel', sect.levels);
    setField('societySectRelation', sect.relationships);
    setField('societyMartialFaction', martial.factions);
    setField('societyMartialGuild', martial.alliances);
    setField('societyExternal', s.external);
    setField('societyClassLevel', strata.social_classes);
    setField('societyClassMobility', strata.mobility);
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







/* 保存 - 通用分层配置 */

const LAYER_SAVE_CONFIG = {
    setting: {
        sectionName: '基础设定',
        fields: [
            { key: 'world_name', id: 'worldName' },
            { key: 'genre', valueFn: getSelectedGenre },
            { key: 'identity', id: 'worldIdentity' },
            { key: 'tone', id: 'worldTone' },
            { key: 'overview', id: 'worldOverview' },
            { key: 'conflict', id: 'worldCoreConflict' },
        ],
    },
    foundation: {
        sectionName: '世界基础',
        fields: [
            { key: 'continent', id: 'foundationContinent' },
            { key: 'terrain', id: 'foundationTerrain' },
            { key: 'era', id: 'foundationEra' },
            { key: 'days', id: 'foundationDays' },
            { key: 'seasons', id: 'foundationSeasons' },
            { key: 'festivals', id: 'foundationFestivals' },
            { key: 'laws', id: 'foundationLaws' },
            { key: 'boundary', id: 'foundationBoundary' },
            { key: 'axioms', valueFn: getAxiomsText },
            { key: 'balance', id: 'foundationBalance' },
        ],
        postSave() {
            if (currentStructure.rules) {
                currentStructure.rules.axioms = getAxiomsText().split('\n').filter(a => a.trim());
            }
        },
    },
    power: {
        sectionName: '力量体系',
        fields: [
            { key: 'energy_types', id: 'powerEnergyType' },
            { key: 'energy_distribution', id: 'powerEnergyDistribution' },
            { key: 'energy_properties', id: 'powerEnergyTraits' },
            { key: 'level', id: 'powerLevels' },
            { key: 'martial_categories', id: 'powerMartialCategory' },
            { key: 'martial_inheritance', id: 'powerMartialHeritage' },
            { key: 'treasure_categories', id: 'powerTreasureCategory' },
            { key: 'treasure_pills', id: 'powerTreasurePill' },
            { key: 'beast_levels', id: 'powerBeastLevel' },
            { key: 'beast_mythical', id: 'powerBeastLegend' },
        ],
    },
    races: {
        sectionName: '种族族群',
        fields: [
            { key: 'category', id: 'racesCategory' },
            { key: 'value', id: 'racesValue' },
            { key: 'lifespan', id: 'racesLifespan' },
            { key: 'reproduction', id: 'racesReproduction' },
            { key: 'physique', id: 'racesConstitution' },
            { key: 'relation', id: 'racesRelation' },
        ],
    },
    society: {
        sectionName: '社会结构',
        fields: [
            { key: 'government', id: 'societyGovernment' },
            { key: 'bureaucracy', id: 'societyBureaucracy' },
            { key: 'sect_level', id: 'societySectLevel' },
            { key: 'sect_heritage', id: 'societySectHeritage' },
            { key: 'martial_faction', id: 'societyMartialFaction' },
            { key: 'martial_guild', id: 'societyMartialGuild' },
            { key: 'external', id: 'societyExternal' },
            { key: 'class_level', id: 'societyClassLevel' },
            { key: 'class_mobility', id: 'societyClassMobility' },
            { key: 'currency_type', id: 'societyCurrencyType' },
            { key: 'currency_rule', id: 'societyCurrencyRule' },
            { key: 'resource', id: 'societyResource' },
        ],
    },
    culture: {
        sectionName: '文化人文',
        fields: [
            { key: 'festival', id: 'cultureFestival' },
            { key: 'ritual', id: 'cultureRitual' },
            { key: 'language', id: 'cultureLanguage' },
            { key: 'script', id: 'cultureScript' },
            { key: 'clothing', id: 'cultureClothing' },
            { key: 'food', id: 'cultureFood' },
            { key: 'architecture', id: 'cultureArchitecture' },
            { key: 'transport', id: 'cultureTransport' },
            { key: 'deity', id: 'cultureDeity' },
            { key: 'religion_org', id: 'cultureReligionOrg' },
            { key: 'faith_diff', id: 'cultureFaithDiff' },
        ],
    },
    history: {
        sectionName: '历史进程',
        fields: [
            { key: 'ancient', id: 'historyAncient' },
            { key: 'modern', id: 'historyModern' },
            { key: 'crisis', id: 'historyCrisis' },
            { key: 'destiny', id: 'historyDestiny' },
            { key: 'future', id: 'historyFuture' },
        ],
    },
    special: {
        sectionName: '特殊设定',
        fields: [
            { key: 'taboo', id: 'specialTaboo' },
            { key: 'secret', id: 'specialSecret' },
            { key: 'fortune', id: 'specialFortune' },
            { key: 'destiny', id: 'specialDestiny' },
            { key: 'soul', id: 'specialSoul' },
            { key: 'reincarnation', id: 'specialReincarnation' },
            { key: 'transmigration', id: 'specialTransmigration' },
            { key: 'system', id: 'specialSystem' },
            { key: 'rules', id: 'specialRules' },
        ],
    },
};

async function saveLayer(layerName) {
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const config = LAYER_SAVE_CONFIG[layerName];
    if (!config) return;

    showLoading(`正在保存${config.sectionName}...`);

    try {
        // Build request body from config
        const body = {};
        for (const field of config.fields) {
            body[field.key] = field.valueFn
                ? field.valueFn()
                : (document.getElementById(field.id)?.value || '');
        }

        const response = await api.request(
            `/api/projects/${currentProjectId}/worldviews/${worldviewId}/layer/${layerName}/`,
            { method: 'PUT', body: JSON.stringify(body) }
        );

        if (response.success) {
            // Update local data from server response
            if (!currentWorldview[layerName]) currentWorldview[layerName] = {};
            currentWorldview[layerName] = response.data[layerName];
            currentStructure[layerName] = response.data[layerName];

            // Post-save hook (e.g., foundation axioms sync)
            if (config.postSave) config.postSave();

            // Re-render form
            const capitalized = layerName.charAt(0).toUpperCase() + layerName.slice(1);
            const renderFn = window[`render${capitalized}`];
            if (renderFn) renderFn(currentStructure);

            // 保存后更新 dirty tracking 快照
            captureOriginalLayerData(layerName);

            showToast(`${config.sectionName}保存成功`);
        } else {
            throw new Error(response.message || '保存失败');
        }
    } catch (error) {
        console.error(`Save ${layerName} failed:`, error);
        showToast('保存失败', 'error');
    } finally {
        hideLoading();
    }
}

/* AI 优化 */

const LAYER_CONFIG = {
    setting: {
        sectionName: '基础设定',
        fields: [
            { id: 'worldName', label: '世界名称' },
            { id: 'genreSelect', label: '小说类型', trim: false },
            { id: 'worldIdentity', label: '世界身份 / 类型气质' },
            { id: 'worldTone', label: '整体调性' },
            { id: 'worldOverview', label: '世界概述' },
            { id: 'worldCoreConflict', label: '核心冲突' },
        ],
        setFormFields(data) {
            setField('worldName', data.identity?.world_name || '');
            setField('worldIdentity', data.position?.identity || '');
            setField('worldTone', data.position?.tone || '');
            setField('worldOverview', data.overview || '');
            setField('worldCoreConflict', data.conflict || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.setting) currentWorldview.setting = {};
            if (!currentWorldview.setting.identity) currentWorldview.setting.identity = {};
            if (!currentWorldview.setting.position) currentWorldview.setting.position = {};
            currentWorldview.setting.identity.world_name = data.identity?.world_name || '';
            currentWorldview.setting.identity.genre = getSelectedGenre();
            currentWorldview.setting.position.identity = data.position?.identity || '';
            currentWorldview.setting.position.tone = data.position?.tone || '';
            currentWorldview.setting.overview = data.overview || '';
            currentWorldview.setting.conflict = data.conflict || '';
        }
    },

    foundation: {
        sectionName: '世界基础',
        fields: [
            { id: 'foundationContinent', label: '大陆分布' },
            { id: 'foundationTerrain', label: '特殊地形' },
            { id: 'foundationEra', label: '纪年方式' },
            { id: 'foundationDays', label: '一年天数' },
            { id: 'foundationSeasons', label: '季节划分' },
            { id: 'foundationFestivals', label: '特殊节气/节日' },
            { id: 'foundationLaws', label: '自然法则' },
            { id: 'foundationBoundary', label: '世界边界' },
            { id: 'foundationBalance', label: '平衡机制' },
        ],
        preValidate() {
            if (!getAxiomsText()) {
                showToast('请先填写核心公理', 'error');
                return false;
            }
            return true;
        },
        setFormFields(data) {
            setField('foundationContinent', data.geography?.continent_distribution || '');
            setField('foundationTerrain', data.geography?.special_terrain || '');
            setField('foundationEra', data.calendar?.era || '');
            setField('foundationDays', data.calendar?.days_per_year || '');
            setField('foundationSeasons', data.calendar?.seasons || '');
            setField('foundationFestivals', data.calendar?.festivals || '');
            setField('foundationLaws', data.rules?.natural_laws || '');
            setField('foundationBoundary', data.rules?.boundaries || '');
            if (data.rules?.axioms) setAxiomsFromText(data.rules.axioms);
            setField('foundationBalance', data.balance || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.foundation) currentWorldview.foundation = {};
            if (!currentWorldview.foundation.geography) currentWorldview.foundation.geography = {};
            if (!currentWorldview.foundation.calendar) currentWorldview.foundation.calendar = {};
            if (!currentWorldview.foundation.rules) currentWorldview.foundation.rules = {};
            currentWorldview.foundation.geography.continent_distribution = data.geography?.continent_distribution || '';
            currentWorldview.foundation.geography.special_terrain = data.geography?.special_terrain || '';
            currentWorldview.foundation.calendar.era = data.calendar?.era || '';
            currentWorldview.foundation.calendar.days_per_year = data.calendar?.days_per_year || '';
            currentWorldview.foundation.calendar.seasons = data.calendar?.seasons || '';
            currentWorldview.foundation.calendar.festivals = data.calendar?.festivals || '';
            currentWorldview.foundation.rules.natural_laws = data.rules?.natural_laws || '';
            currentWorldview.foundation.rules.boundaries = data.rules?.boundaries || '';
            if (data.rules?.axioms) {
                currentWorldview.foundation.rules.axioms = typeof data.rules.axioms === 'string'
                    ? data.rules.axioms.split('\n').filter(a => a.trim())
                    : data.rules.axioms;
            }
            currentWorldview.foundation.balance = data.balance || '';
            currentStructure.foundation = JSON.parse(JSON.stringify(currentWorldview.foundation));
            if (currentStructure.foundation.rules) {
                currentStructure.rules = { ...currentStructure.rules, axioms: currentStructure.foundation.rules.axioms || [] };
            }
            if (currentStructure.foundation.rules?.axioms) {
                axioms.length = 0;
                currentStructure.foundation.rules.axioms.forEach(v => axioms.push(v));
                renderAxioms();
            }
        }
    },

    power: {
        sectionName: '力量体系',
        fields: [
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
        ],
        setFormFields(data) {
            setField('powerEnergyType', data.energy?.types || '');
            setField('powerEnergyDistribution', data.energy?.distribution || '');
            setField('powerEnergyTraits', data.energy?.properties || '');
            setField('powerLevels', data.level || '');
            setField('powerMartialCategory', data.martial?.categories || '');
            setField('powerMartialHeritage', data.martial?.inheritance || '');
            setField('powerTreasureCategory', data.treasure?.categories || '');
            setField('powerTreasurePill', data.treasure?.pills || '');
            setField('powerBeastLevel', data.beast?.levels || '');
            setField('powerBeastLegend', data.beast?.mythical || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.power) currentWorldview.power = {};
            currentWorldview.power = JSON.parse(JSON.stringify(data));
            currentStructure.power = JSON.parse(JSON.stringify(data));
        }
    },

    races: {
        sectionName: '种族族群',
        fields: [
            { id: 'racesCategory', label: '种族分类' },
            { id: 'racesValue', label: '种族价值观' },
            { id: 'racesLifespan', label: '寿命特征' },
            { id: 'racesReproduction', label: '繁衍方式' },
            { id: 'racesConstitution', label: '体质特征' },
            { id: 'racesRelation', label: '种族关系' },
        ],
        setFormFields(data) {
            setField('racesCategory', data.category || '');
            setField('racesValue', data.value || '');
            setField('racesLifespan', data.trait?.lifespan || '');
            setField('racesReproduction', data.trait?.reproduction || '');
            setField('racesConstitution', data.trait?.physique || '');
            setField('racesRelation', data.relation || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.races) currentWorldview.races = {};
            if (!currentWorldview.races.trait) currentWorldview.races.trait = {};
            currentWorldview.races.category = data.category || '';
            currentWorldview.races.value = data.value || '';
            currentWorldview.races.trait.lifespan = data.trait?.lifespan || '';
            currentWorldview.races.trait.reproduction = data.trait?.reproduction || '';
            currentWorldview.races.trait.physique = data.trait?.physique || '';
            currentWorldview.races.relation = data.relation || '';
            currentStructure.races = JSON.parse(JSON.stringify(currentWorldview.races));
        }
    },

    society: {
        sectionName: '社会结构',
        fields: [
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
        ],
        setFormFields(data) {
            setField('societyGovernment', data.court?.political_system || '');
            setField('societyBureaucracy', data.court?.bureaucracy || '');
            setField('societySectLevel', data.sect?.levels || '');
            setField('societySectHeritage', data.sect?.relationships || '');
            setField('societyMartialFaction', data.martial?.factions || '');
            setField('societyMartialGuild', data.martial?.alliances || '');
            setField('societyExternal', data.external || '');
            setField('societyClassLevel', data.strata?.social_classes || '');
            setField('societyClassMobility', data.strata?.mobility || '');
            setField('societyCurrencyType', data.currency?.types || '');
            setField('societyCurrencyRule', data.currency?.rules || '');
            setField('societyResource', data.resource || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.society) currentWorldview.society = {};
            if (!currentWorldview.society.court) currentWorldview.society.court = {};
            if (!currentWorldview.society.sect) currentWorldview.society.sect = {};
            if (!currentWorldview.society.martial) currentWorldview.society.martial = {};
            if (!currentWorldview.society.strata) currentWorldview.society.strata = {};
            if (!currentWorldview.society.currency) currentWorldview.society.currency = {};
            currentWorldview.society.court.political_system = data.court?.political_system || '';
            currentWorldview.society.court.bureaucracy = data.court?.bureaucracy || '';
            currentWorldview.society.sect.levels = data.sect?.levels || '';
            currentWorldview.society.sect.relationships = data.sect?.relationships || '';
            currentWorldview.society.martial.factions = data.martial?.factions || '';
            currentWorldview.society.martial.alliances = data.martial?.alliances || '';
            currentWorldview.society.external = data.external || '';
            currentWorldview.society.strata.social_classes = data.strata?.social_classes || '';
            currentWorldview.society.strata.mobility = data.strata?.mobility || '';
            currentWorldview.society.currency.types = data.currency?.types || '';
            currentWorldview.society.currency.rules = data.currency?.rules || '';
            currentWorldview.society.resource = data.resource || '';
            currentStructure.society = JSON.parse(JSON.stringify(currentWorldview.society));
        }
    },

    culture: {
        sectionName: '文化人文',
        fields: [
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
        ],
        setFormFields(data) {
            setField('cultureFestival', data.custom?.festivals || '');
            setField('cultureRitual', data.custom?.rituals || '');
            setField('cultureLanguage', data.language?.languages || '');
            setField('cultureScript', data.language?.writing_system || '');
            setField('cultureClothing', data.daily?.clothing || '');
            setField('cultureFood', data.daily?.cuisine || data.daily?.food || '');
            setField('cultureArchitecture', data.daily?.architecture || '');
            setField('cultureTransport', data.daily?.transportation || '');
            setField('cultureDeity', data.religion?.deities || data.religion?.deity || '');
            setField('cultureReligionOrg', data.religion?.organization || '');
            setField('cultureFaithDiff', data.religion?.faith_differences || data.religion?.faith_diff || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.culture) currentWorldview.culture = {};
            if (!currentWorldview.culture.custom) currentWorldview.culture.custom = {};
            if (!currentWorldview.culture.language) currentWorldview.culture.language = {};
            if (!currentWorldview.culture.daily) currentWorldview.culture.daily = {};
            if (!currentWorldview.culture.religion) currentWorldview.culture.religion = {};
            currentWorldview.culture.custom.festivals = data.custom?.festivals || '';
            currentWorldview.culture.custom.rituals = data.custom?.rituals || '';
            currentWorldview.culture.language.languages = data.language?.languages || '';
            currentWorldview.culture.language.writing_system = data.language?.writing_system || '';
            currentWorldview.culture.daily.clothing = data.daily?.clothing || '';
            currentWorldview.culture.daily.food = data.daily?.food || '';
            currentWorldview.culture.daily.architecture = data.daily?.architecture || '';
            currentWorldview.culture.daily.transportation = data.daily?.transportation || '';
            currentWorldview.culture.religion.deity = data.religion?.deity || '';
            currentWorldview.culture.religion.organization = data.religion?.organization || '';
            currentWorldview.culture.religion.faith_diff = data.religion?.faith_diff || '';
            currentStructure.culture = JSON.parse(JSON.stringify(currentWorldview.culture));
        }
    },

    history: {
        sectionName: '历史进程',
        fields: [
            { id: 'historyAncient', label: '上古往事' },
            { id: 'historyModern', label: '近代变故' },
            { id: 'historyCrisis', label: '世界隐患' },
            { id: 'historyDestiny', label: '宿命轨迹' },
            { id: 'historyFuture', label: '未来走向' },
        ],
        preprocessResponse(data) {
            return data.success && data.data ? data.data.history : data;
        },
        setFormFields(data) {
            setField('historyAncient', data.ancient || '');
            setField('historyModern', data.modern || '');
            setField('historyCrisis', data.crisis || '');
            setField('historyDestiny', data.destiny || '');
            setField('historyFuture', data.future || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.history) currentWorldview.history = {};
            currentWorldview.history.ancient = data.ancient || '';
            currentWorldview.history.modern = data.modern || '';
            currentWorldview.history.crisis = data.crisis || '';
            currentWorldview.history.destiny = data.destiny || '';
            currentWorldview.history.future = data.future || '';
            currentStructure.history = JSON.parse(JSON.stringify(currentWorldview.history));
        }
    },

    special: {
        sectionName: '特殊规则',
        fields: [
            { id: 'specialTaboo', label: '世界禁忌' },
            { id: 'specialSecret', label: '隐藏秘密' },
            { id: 'specialFortune', label: '运势规则' },
            { id: 'specialDestiny', label: '命运类型' },
            { id: 'specialSoul', label: '灵魂规则' },
            { id: 'specialReincarnation', label: '轮回机制' },
            { id: 'specialTransmigration', label: '穿越规则' },
            { id: 'specialSystem', label: '系统规则' },
            { id: 'specialRules', label: '特殊规则' },
        ],
        setFormFields(data) {
            setField('specialTaboo', data.taboo || '');
            setField('specialSecret', data.secret || '');
            setField('specialFortune', data.fate?.fortune_rules || '');
            setField('specialDestiny', data.fate?.destiny_types || '');
            setField('specialSoul', data.reincarnation?.soul_rules || '');
            setField('specialReincarnation', data.reincarnation?.mechanics || '');
            setField('specialTransmigration', data.transmigration || '');
            setField('specialSystem', data.system || '');
            setField('specialRules', data.rules || '');
        },
        updateLocalData(data) {
            if (!currentWorldview.special) currentWorldview.special = {};
            if (!currentWorldview.special.fate) currentWorldview.special.fate = {};
            if (!currentWorldview.special.reincarnation) currentWorldview.special.reincarnation = {};
            currentWorldview.special.taboo = data.taboo || '';
            currentWorldview.special.secret = data.secret || '';
            currentWorldview.special.fate.fortune_rules = data.fate?.fortune_rules || '';
            currentWorldview.special.fate.destiny_types = data.fate?.destiny_types || '';
            currentWorldview.special.reincarnation.soul_rules = data.reincarnation?.soul_rules || '';
            currentWorldview.special.reincarnation.mechanics = data.reincarnation?.mechanics || '';
            currentWorldview.special.transmigration = data.transmigration || '';
            currentWorldview.special.system = data.system || '';
            currentWorldview.special.rules = data.rules || '';
            currentStructure.special = JSON.parse(JSON.stringify(currentWorldview.special));
        }
    }
};

async function aiPolishLayer(layerName) {
    /** AI 润色：仅润色用户修改过的字段（dirty fields），其余字段不动 */
    if (!worldviewId) {
        showToast('世界观未加载', 'error');
        return;
    }

    const config = LAYER_CONFIG[layerName];
    if (!config) return;

    // Pre-validate (e.g., foundation checks axioms)
    if (config.preValidate && !config.preValidate()) return;

    // 获取脏字段
    const { dirtyData, changedKeys } = getDirtyFields(layerName);
    if (changedKeys.length === 0) {
        showToast('没有需要润色的修改，请先编辑字段内容', 'warning');
        return;
    }

    showLoading(`AI正在润色${config.sectionName}...`);

    try {
        const fullContent = await api.streamRequest(
            `/api/projects/${currentProjectId}/worldviews/${worldviewId}/optimize/${layerName}/`,
            {
                method: 'POST',
                body: JSON.stringify({
                    genre: getSelectedGenre(),
                    layer_data: dirtyData,
                    changed_keys: changedKeys,
                })
            }
        );

        _handleOptimizeResponse(layerName, config, fullContent);
    } catch (error) {
        console.error(`Polish ${layerName} failed:`, error);
        showToast(error.message || '润色失败', 'error');
    } finally {
        hideLoading();
    }
}

function _handleOptimizeResponse(layerName, config, fullContent) {
    /** 解析 LLM 润色返回结果并更新 UI + 快照 */
    let result;
    if (typeof fullContent === 'string') {
        const jsonMatch = fullContent.match(/```(?:json)?\s*(\{.*\})\s*```/s);
        result = jsonMatch ? JSON.parse(jsonMatch[1]) : JSON.parse(fullContent);
    } else if (fullContent && typeof fullContent === 'object') {
        result = fullContent;
    } else {
        throw new Error('AI返回数据格式错误');
    }

    // Unwrap: LLM always returns {layer_name, polished_data}, extract polished_data
    if (result.polished_data && typeof result.polished_data === 'object') {
        result = result.polished_data;
    }

    // Preprocess (e.g., history unwraps success.data.history)
    if (config.preprocessResponse) {
        result = config.preprocessResponse(result);
    }

    // Update form fields
    config.setFormFields(result);

    // Update local data
    config.updateLocalData(result);

    // 更新 dirty tracking 快照
    captureOriginalLayerData(layerName);

    showToast('AI润色完成');
}

// 保留旧函数名作为 polish 模式的别名，兼容可能的旧引用
async function aiFillLayer(layerName) {
    return aiPolishLayer(layerName);
}










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
//         const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/factions/generate/`, {
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
//         const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/locations/generate/`, {
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
//         const data = await api.request(`/api/projects/${currentProjectId}/worldviews/${worldviewId}/relations/generate/`, {
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

