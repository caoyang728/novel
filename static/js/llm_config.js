let configs = [];
// 连接状态缓存: { configId: 'testing'|'success'|'fail', message: '' }
let connectionStatus = {};
// 标记弹窗中是否手动触发过测试
let modalTested = false;
// LLM供应商默认配置
let providerPresets = {};
// 分组场景配置（后端返回）
let groupedScenes = {};

document.addEventListener('DOMContentLoaded', async function() {
    showLoading('加载中...');
    // 加载供应商预设配置
    try {
        const resp = await fetch('/static/data/llm_providers.json');
        providerPresets = await resp.json();
    } catch (e) {
        console.error('Failed to load provider presets:', e);
    }
    Promise.all([loadUserInfo(), loadConfigs(true)]).finally(() => hideLoading());
});

async function loadConfigs(testAll = false) {
    try {
        const data = await api.get('/api/llm-config/');
        if (data.success) {
            configs = data.configs;
            window.taskConfigs = data.task_configs;
            groupedScenes = data.grouped_scenes || {};
            renderConfigs(data.configs);
            renderTaskConfigs(data.task_configs);
            populateConfigSelect();
            if (testAll) {
                testAllConnections(data.configs);
            }
        }
    } catch (error) {
        console.error('Failed to load configs:', error);
    }
}

function renderConfigs(configs) {
    const container = document.getElementById('configs-container');
    
    if (configs.length === 0) {
        container.innerHTML = '<p class="text-center text-muted py-4">暂无LLM配置，请添加</p>';
        return;
    }

    container.innerHTML = configs.map(config => {
        const status = connectionStatus[config.id];
        let statusHtml = '';
        if (status === 'testing') {
            statusHtml = '<span class="connection-status testing"><i class="fas fa-spinner fa-spin"></i><span class="status-text">连接中</span></span>';
        } else if (status === 'success') {
            statusHtml = '<span class="connection-status success"><i class="fas fa-circle"></i><span class="status-text">已连接</span></span>';
        } else if (status === 'fail') {
            const msg = connectionStatus[config.id + '_msg'] || '连接失败';
            statusHtml = `<span class="connection-status fail"><i class="fas fa-circle"></i><span class="status-text">${msg}</span></span>`;
        } else {
            statusHtml = '<span class="connection-status unknown"><i class="fas fa-circle"></i></span>';
        }

        return `
        <div class="config-card ${config.is_default ? 'default' : ''} ${!config.is_active ? 'disabled' : ''}">
            <div class="config-card-row">
                <div class="config-card-left">
                    <i class="fas fa-box"></i>
                    <span class="config-name">${config.name}</span>
                    ${config.is_default ? '<span class="badge badge-success ms-2">默认</span>' : ''}
                </div>
                ${statusHtml}
                <div class="config-card-center">${getProviderName(config.provider)}</div>
                <div class="config-card-right">
                    <button class="btn btn-outline-primary btn-sm" onclick="editConfig(${config.id})" title="编辑">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteConfig(${config.id})" title="删除">
                        <i class="fas fa-trash"></i>
                    </button>
                    <label class="toggle-switch">
                        <input type="checkbox" ${config.is_active ? 'checked' : ''} onchange="toggleConfigActive(${config.id}, this)">
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
        </div>
    `;
    }).join('');
}

function renderTaskConfigs(taskConfigs) {
    const container = document.getElementById('task-configs-container');

    // 如果没有分组场景数据，使用旧的硬编码列表
    if (!groupedScenes || Object.keys(groupedScenes).length === 0) {
        container.innerHTML = '<p class="text-center text-muted py-4">场景配置加载失败</p>';
        return;
    }

    // 定义分组展示顺序
    const groupOrder = ['default', 'worldview', 'character', 'timeline', 'outline', 'volume', 'chapter', 'note'];
    const orderedGroups = groupOrder.filter(g => groupedScenes[g]);

    let html = '';
    for (const groupKey of orderedGroups) {
        const group = groupedScenes[groupKey];
        html += `<div class="task-group">`;
        html += `<div class="task-group-title"><i class="fas fa-layer-group"></i> ${group.name}</div>`;
        html += `<div class="task-group-items">`;
        for (const scene of group.scenes) {
            const config = taskConfigs.find(tc => tc.task_type === scene.key);
            const configInfo = config ? configs.find(c => c.id === config.llm_config_id) : null;

            html += `<div class="task-config-item">`;
            html += `  <div class="task-config-left">`;
            html += `    <div class="task-name">${scene.name}</div>`;
            html += `    <div class="task-defaults">默认: 温度 ${scene.default_temperature} | Token ${scene.default_max_tokens}</div>`;
            if (config && config.temperature && config.temperature !== scene.default_temperature) {
                html += `    <div class="task-override">自定义温度: ${config.temperature}</div>`;
            }
            if (config && config.max_tokens && config.max_tokens !== scene.default_max_tokens) {
                html += `    <div class="task-override">自定义Token: ${config.max_tokens}</div>`;
            }
            html += `  </div>`;
            html += `  <div class="task-config-right">`;
            if (configInfo) {
                html += `<span class="badge badge-info">${configInfo.name}</span>`;
            } else {
                html += `<span class="task-unconfigured">未配置</span>`;
            }
            html += `    <button class="btn btn-outline-primary btn-sm" onclick="editTaskConfig('${scene.key}')" title="编辑">`;
            html += `      <i class="fas fa-edit"></i>`;
            html += `    </button>`;
            html += `  </div>`;
            html += `</div>`;
        }
        html += `</div></div>`;
    }

    container.innerHTML = html || '<p class="text-center text-muted py-4">暂无场景配置</p>';
}

function populateConfigSelect() {
    const select = document.getElementById('task-config');
    select.innerHTML = configs.map(config => 
        `<option value="${config.id}">${config.name} (${getProviderName(config.provider)})</option>`
    ).join('');
}

function openConfigModal(configId) {
    modalTested = false;
    document.getElementById('configModal').classList.add('show');
    document.getElementById('config-id').value = configId || '';
    document.getElementById('configModalTitle').innerHTML = configId ? '<i class="fas fa-edit me-2"></i>编辑LLM配置' : '<i class="fas fa-plus-circle me-2"></i>添加LLM配置';
    document.getElementById('config-name').value = '';
    document.getElementById('config-provider').value = 'deepseek';
    document.getElementById('config-api-key').value = '';
    document.getElementById('config-base-url').value = '';
    document.getElementById('config-model').value = '';
    document.getElementById('config-temperature').value = '0.7';
    document.getElementById('config-max-tokens').value = '4096';
    document.getElementById('config-input-price').value = '0';
    document.getElementById('config-output-price').value = '0';
    document.getElementById('config-cache-hit-price').value = '0';
    document.getElementById('config-default').checked = false;

    if (configId) {
        const config = configs.find(c => c.id === configId);
        if (config) {
            document.getElementById('config-name').value = config.name;
            document.getElementById('config-provider').value = config.provider;
            document.getElementById('config-base-url').value = config.base_url || '';
            document.getElementById('config-temperature').value = config.temperature;
            document.getElementById('config-max-tokens').value = config.max_tokens;
            document.getElementById('config-input-price').value = config.input_price || 0;
            document.getElementById('config-output-price').value = config.output_price || 0;
            document.getElementById('config-cache-hit-price').value = config.cache_hit_price || 0;
            document.getElementById('config-default').checked = config.is_default;
            // 先填充模型下拉，再设置值
            populateModelSelect(config.provider, config.model_name);
        }
    } else {
        // 新增：根据当前供应商填充下拉和默认值
        onProviderChange();
    }
}

function populateModelSelect(provider, currentModelName) {
    const select = document.getElementById('config-model-select');
    const input = document.getElementById('config-model');
    const preset = providerPresets[provider];

    if (preset && preset.models && preset.models.length > 0) {
        // 有预设模型，显示下拉
        select.style.display = '';
        input.style.display = 'none';

        select.innerHTML = preset.models.map(m =>
            `<option value="${m.name}">${m.label} (${m.name})</option>`
        ).join('') + '<option value="__custom__">自定义输入...</option>';

        // 尝试匹配当前模型
        if (currentModelName) {
            const matchOption = Array.from(select.options).find(o => o.value === currentModelName);
            if (matchOption) {
                select.value = currentModelName;
            } else {
                // 当前模型不在预设中，切换到自定义输入
                select.value = '__custom__';
                select.style.display = 'none';
                input.style.display = '';
                input.value = currentModelName;
            }
        } else {
            // 默认选第一个
            select.selectedIndex = 0;
        }
    } else {
        // 无预设模型，显示文本输入
        select.style.display = 'none';
        input.style.display = '';
        input.value = currentModelName || '';
    }
}

function onProviderChange() {
    const provider = document.getElementById('config-provider').value;
    const preset = providerPresets[provider];

    // 自动填充 API 地址
    if (preset && preset.base_url) {
        document.getElementById('config-base-url').value = preset.base_url;
    }

    // 填充模型下拉
    populateModelSelect(provider, '');

    // 触发模型变更以填充价格
    onModelChange();
}

function onModelChange() {
    const select = document.getElementById('config-model-select');
    const input = document.getElementById('config-model');

    if (select.value === '__custom__') {
        // 切换到自定义输入
        select.style.display = 'none';
        input.style.display = '';
        input.value = '';
        input.focus();
        return;
    }

    if (select.style.display !== 'none' && select.value) {
        // 从预设中查找价格
        const provider = document.getElementById('config-provider').value;
        const preset = providerPresets[provider];
        if (preset && preset.models) {
            const model = preset.models.find(m => m.name === select.value);
            if (model) {
                document.getElementById('config-input-price').value = model.input_price || 0;
                document.getElementById('config-output-price').value = model.output_price || 0;
                document.getElementById('config-cache-hit-price').value = model.cache_hit_price || 0;
            }
        }
    }
}

function getSelectedModelName() {
    const select = document.getElementById('config-model-select');
    const input = document.getElementById('config-model');
    if (select.style.display !== 'none' && select.value !== '__custom__') {
        return select.value;
    }
    return input.value.trim();
}

function editConfig(configId) {
    openConfigModal(configId);
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('show');
}

async function saveConfig() {
    const configId = document.getElementById('config-id').value;
    const name = document.getElementById('config-name').value.trim();
    const provider = document.getElementById('config-provider').value;
    const apiKey = document.getElementById('config-api-key').value;
    const baseUrl = document.getElementById('config-base-url').value.trim();
    const modelName = getSelectedModelName();
    const temperature = parseFloat(document.getElementById('config-temperature').value);
    const maxTokens = parseInt(document.getElementById('config-max-tokens').value);
    const inputPrice = parseFloat(document.getElementById('config-input-price').value) || 0;
    const outputPrice = parseFloat(document.getElementById('config-output-price').value) || 0;
    const cacheHitPrice = parseFloat(document.getElementById('config-cache-hit-price').value) || 0;
    const isDefault = document.getElementById('config-default').checked;

    if (!name || !modelName) {
        showError('请填写必填字段');
        return;
    }

    try {
        const data = await api.request('/api/llm-config/', {
            method: 'POST',
            body: JSON.stringify({
                action: configId ? 'update' : 'create',
                config_id: configId || undefined,
                name,
                provider,
                api_key: apiKey || undefined,
                base_url: baseUrl || '',
                model_name: modelName,
                temperature,
                max_tokens: maxTokens,
                input_price: inputPrice,
                output_price: outputPrice,
                cache_hit_price: cacheHitPrice,
                is_default: isDefault
            })
        });

        if (data.success) {
            const savedConfigId = data.config_id || configId;
            closeConfigModal();
            // 不传 testAll，仅刷新列表数据
            await loadConfigs(false);
            showSuccess('保存成功');
            // 如果弹窗中未手动测试过，则自动测试该配置
            if (!modalTested && savedConfigId) {
                testSingleConnection(savedConfigId);
            }
        } else {
            showError(data.message || '保存失败');
        }
    } catch (error) {
        showError('保存失败，请重试');
    }
}

function openTaskConfigModal(taskType) {
    document.getElementById('taskConfigModal').classList.add('show');
    document.getElementById('task-config-id').value = taskType || '';
    document.getElementById('taskConfigModalTitle').innerHTML = '<i class="fas fa-edit me-2"></i>编辑任务配置';

    // 显示任务类型名称（只读）
    const taskName = getTaskTypeName(taskType);
    document.getElementById('task-type-display').textContent = taskName;
    document.getElementById('task-type').value = taskType || '';

    document.getElementById('task-temperature').value = '';
    document.getElementById('task-max-tokens').value = '';

    // 设置温度和 token 的说明提示及 placeholder
    let defaultTemp = '', defaultTokens = '';
    for (const groupKey of Object.keys(groupedScenes)) {
        const scene = groupedScenes[groupKey].scenes.find(s => s.key === taskType);
        if (scene) {
            defaultTemp = scene.default_temperature;
            defaultTokens = scene.default_max_tokens;
            break;
        }
    }
    document.getElementById('task-temp-hint').textContent = defaultTemp ? `越高越有创造性` : '';
    document.getElementById('task-temperature').placeholder = defaultTemp ? `默认值: ${defaultTemp}` : '留空使用场景默认值';
    document.getElementById('task-token-hint').textContent = defaultTokens ? `越大单次可生成内容越多` : '';
    document.getElementById('task-max-tokens').placeholder = defaultTokens ? `默认值: ${defaultTokens}` : '留空使用场景默认值';

    if (taskType) {
        const taskConfigs = window.taskConfigs || [];
        const config = taskConfigs.find(tc => tc.task_type === taskType);
        if (config) {
            document.getElementById('task-config').value = config.llm_config_id;
            document.getElementById('task-temperature').value = config.temperature || '';
            document.getElementById('task-max-tokens').value = config.max_tokens || '';
        }
    }
}

function editTaskConfig(taskType) {
    openTaskConfigModal(taskType);
}

function closeTaskConfigModal() {
    document.getElementById('taskConfigModal').classList.remove('show');
}

async function saveTaskConfig() {
    const taskType = document.getElementById('task-type').value;
    const configId = document.getElementById('task-config').value;
    const temperature = document.getElementById('task-temperature').value;
    const maxTokens = document.getElementById('task-max-tokens').value;

    try {
        const data = await api.request('/api/llm-config/', {
            method: 'POST',
            body: JSON.stringify({
                action: 'set_task',
                task_type: taskType,
                config_id: configId,
                temperature: temperature ? parseFloat(temperature) : null,
                max_tokens: maxTokens ? parseInt(maxTokens) : null
            })
        });

        if (data.success) {
            closeTaskConfigModal();
            loadConfigs(false);
            showSuccess('保存成功');
        } else {
            showError(data.message || '保存失败');
        }
    } catch (error) {
        showError('保存失败，请重试');
    }
}

async function toggleConfigActive(configId, checkbox) {
    const isActive = checkbox.checked;
    
    try {
        const data = await api.request('/api/llm-config/', {
            method: 'POST',
            body: JSON.stringify({
                action: 'toggle_active',
                config_id: configId,
                is_active: isActive
            })
        });

        if (!data.success) {
            checkbox.checked = !isActive;
            showError(data.message || '操作失败');
        }
    } catch (error) {
        checkbox.checked = !isActive;
        showError('操作失败，请重试');
    }
}

function deleteConfig(configId) {
    showModal('删除配置', '确定要删除这个配置吗？', async function() {
        try {
            const data = await api.request('/api/llm-config/', {
                method: 'POST',
                body: JSON.stringify({
                    action: 'delete',
                    config_id: configId
                })
            });

            if (data.success) {
                loadConfigs(false);
                showSuccess('删除成功');
            } else {
                showError(data.message || '删除失败');
            }
        } catch (error) {
            showError('删除失败，请重试');
        }
        closeModal();
    });
}

function getProviderName(provider) {
    // 优先从预设配置中获取名称
    if (providerPresets[provider] && providerPresets[provider].name) {
        return providerPresets[provider].name;
    }
    const names = {
        'deepseek': 'DeepSeek',
        'openai': 'OpenAI',
        'anthropic': 'Anthropic',
        'qwen': '通义千问',
        'gemini': 'Gemini',
        'custom': '自定义'
    };
    return names[provider] || provider;
}

function getTaskTypeName(type) {
    // 从分组场景中查找名称
    for (const groupKey of Object.keys(groupedScenes)) {
        const group = groupedScenes[groupKey];
        const scene = group.scenes.find(s => s.key === type);
        if (scene) return scene.name;
    }
    return type;
}

// logout 函数使用 common.js 中的统一实现

// ============ 连接测试 ============

async function testAllConnections(configsList) {
    // 并行测试所有配置
    const promises = configsList.map(config => testSingleConnection(config.id));
    await Promise.allSettled(promises);
}

async function testSingleConnection(configId) {
    connectionStatus[configId] = 'testing';
    renderConfigs(configs);

    try {
        const data = await api.request('/api/llm-config/', {
            method: 'POST',
            body: JSON.stringify({
                action: 'test_connection',
                config_id: configId
            })
        });

        if (data.success) {
            connectionStatus[configId] = 'success';
            connectionStatus[configId + '_msg'] = data.message || '连接成功';
        } else {
            connectionStatus[configId] = 'fail';
            connectionStatus[configId + '_msg'] = data.message || '连接失败';
        }
    } catch (error) {
        connectionStatus[configId] = 'fail';
        connectionStatus[configId + '_msg'] = '请求异常';
    }

    renderConfigs(configs);
}

async function testConnectionFromModal() {
    const apiKey = document.getElementById('config-api-key').value;
    const baseUrl = document.getElementById('config-base-url').value.trim();
    const modelName = getSelectedModelName();
    const configId = document.getElementById('config-id').value;

    if (!modelName) {
        showError('请先填写模型名称');
        return;
    }

    // 前端有密钥 → 用前端参数测试；没有密钥 → 用 config_id 从数据库取密钥测试
    let requestBody;
    if (apiKey) {
        requestBody = {
            action: 'test_connection_params',
            api_key: apiKey,
            base_url: baseUrl,
            model_name: modelName
        };
    } else if (configId) {
        requestBody = {
            action: 'test_connection',
            config_id: configId
        };
    } else {
        showError('请填写API密钥');
        return;
    }

    const btn = document.getElementById('btn-test-connection');
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 测试中...';

    try {
        const data = await api.request('/api/llm-config/', {
            method: 'POST',
            body: JSON.stringify(requestBody)
        });

        if (data.success) {
            showSuccess(data.message || '连接成功');
        } else {
            showError(data.message || '连接失败');
        }

        // 标记已手动测试，保存时不再自动测试
        modalTested = true;

        // 同步更新列表中对应配置的连接状态
        const targetId = configId;
        if (targetId) {
            if (data.success) {
                connectionStatus[targetId] = 'success';
                connectionStatus[targetId + '_msg'] = data.message || '连接成功';
            } else {
                connectionStatus[targetId] = 'fail';
                connectionStatus[targetId + '_msg'] = data.message || '连接失败';
            }
            renderConfigs(configs);
        }
    } catch (error) {
        showError('测试请求失败，请重试');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

