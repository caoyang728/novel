/**
 * 角色 AI 检测与优化模块
 * 依赖：characters.js（需先加载）
 * 使用全局变量: characters, currentProjectId, FIELD_LABELS, api, escapeHtml, extractJsonFromString,
 *              showLoading, hideLoading, showError, showSuccess, lockScroll, unlockScroll,
 *              setCharBtnLoading, loadCharacters
 */

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

    setCharBtnLoading('checkBtn', true, '检测中...');

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

        const result = extractJsonFromString(resultStr) || {};
        currentCheckIssues = result.issues || [];
        lockScroll();
        document.getElementById('checkDialog').classList.add('show');
        renderCheckResult(result);
        showSuccess('检测完成');
    } catch (error) {
        hideLoading();
        console.error('角色检测失败:', error);
        showError('网络错误，请重试');
    } finally {
        setCharBtnLoading('checkBtn', false, null, '<i class="fas fa-search-plus"></i> AI检测');
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
                    ${charNames ? `<span class="check-result-chars">${charNames}</span>` : ''}
                    <span class="check-result-type ${issue.type}">${typeLabel}</span>
                    <span class="check-result-severity ${issue.severity}">${issue.severity === 'high' ? '严重' : issue.severity === 'medium' ? '中等' : '轻微'}</span>
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

    // 禁用优化按钮防止重复提交
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    const originalHtml = optimizeBtn.innerHTML;
    optimizeBtn.disabled = true;

    try {
        const resultStr = await api.streamRequest(`/api/projects/${currentProjectId}/characters/optimize/`, {
            body: JSON.stringify({ issues: issuesWithInstructions })
        });

        hideLoading();
        if (!resultStr) {
            showError('优化结果为空');
            return;
        }
        // 尝试解析 JSON 数组
        const trimmed = resultStr.trim();
        const parsed = extractJsonFromString(trimmed);
        if (Array.isArray(parsed)) {
            currentOptimizeResult = parsed;
        } else if (parsed && typeof parsed === 'object') {
            currentOptimizeResult = parsed.optimizations || parsed.data || parsed;
        } else {
            showError('优化结果解析失败');
            return;
        }
        renderOptimizeResult(currentOptimizeResult);
        optimizeBtn.disabled = false;
        showSuccess('优化完成');
    } catch (error) {
        hideLoading();
        console.error('AI优化失败:', error);
        showError(error.message || '网络错误，请重试');
        optimizeBtn.disabled = false;
        optimizeBtn.innerHTML = originalHtml;
    }
}

const TYPE_LABELS = {
    'modify': '修改',
    'add': '新增',
    'delete': '删除'
};

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

    // 切换底部按钮：优化→保存，关闭→取消
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    optimizeBtn.innerHTML = '<i class="fas fa-save"></i> 保存优化';
    optimizeBtn.onclick = saveOptimizeResult;
    optimizeBtn.classList.remove('btn-ai');
    optimizeBtn.classList.add('btn-save');

    const closeBtn = document.getElementById('checkCloseBtn');
    closeBtn.textContent = '取消';
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

    setCharBtnLoading('optimizeCheckBtn', true, '保存中...');

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/characters/optimize/save/`, {
            optimizations: saveItems
        });
        if (!data) return;

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
        setCharBtnLoading('optimizeCheckBtn', false, null, '<i class="fas fa-save"></i> 保存优化');
    }
}

function closeCheckDialog(e) {
    if (e) e.stopPropagation();
    document.getElementById('checkDialog').classList.remove('show');
    unlockScroll();
    // 重置优化按钮
    const optimizeBtn = document.getElementById('optimizeCheckBtn');
    optimizeBtn.innerHTML = '<i class="fas fa-magic"></i> AI优化';
    optimizeBtn.onclick = optimizeFromCheck;
    optimizeBtn.classList.remove('btn-save');
    optimizeBtn.classList.add('btn-ai');
    optimizeBtn.hidden = true;
    document.getElementById('checkCloseBtn').textContent = '关闭';
    currentCheckIssues = [];
    currentOptimizeResult = null;
}
