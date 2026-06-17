let configs = [];

document.addEventListener('DOMContentLoaded', function() {
    showLoading('加载中...');
    Promise.all([loadUserInfo(), loadConfigs()]).finally(() => hideLoading());
});

async function loadConfigs() {
    try {
        const data = await api.get('/api/llm-config/');
        if (data.success) {
            configs = data.configs;
            renderConfigs(data.configs);
            renderTaskConfigs(data.task_configs);
            populateConfigSelect();
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

    container.innerHTML = configs.map(config => `
        <div class="config-card ${config.is_default ? 'default' : ''} ${!config.is_active ? 'disabled' : ''}">
            <div class="config-header">
                <div class="d-flex align-items-center gap-3">
                    <div>
                        <span class="config-name">${config.name}</span>
                        ${config.is_default ? '<span class="badge badge-success ms-2">默认</span>' : ''}
                    </div>
                    <label class="toggle-switch">
                        <input type="checkbox" ${config.is_active ? 'checked' : ''} onchange="toggleConfigActive(${config.id}, this)">
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="btn-group gap-1">
                    <button class="btn btn-outline-primary btn-sm" onclick="editConfig(${config.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteConfig(${config.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="config-provider">${getProviderName(config.provider)}</div>
            <div class="config-info">
                <span><i class="fas fa-box me-1"></i>${config.model_name}</span>
                <span><i class="fas fa-thermometer-half me-1"></i>${config.temperature}</span>
                <span><i class="fas fa-gauge me-1"></i>${config.max_tokens}</span>
                ${config.base_url ? `<span><i class="fas fa-link me-1"></i>自定义地址</span>` : ''}
            </div>
        </div>
    `).join('');
}

function renderTaskConfigs(taskConfigs) {
    const container = document.getElementById('task-configs-container');
    const tasks = ['outline', 'volume', 'chapter', 'content'];
    
    container.innerHTML = tasks.map(task => {
        const config = taskConfigs.find(tc => tc.task_type === task);
        const configInfo = config ? configs.find(c => c.id === config.llm_config_id) : null;
        
        return `
            <div class="task-config-item">
                <div>
                    <div class="task-name">${getTaskTypeName(task)}</div>
                    ${config && (config.temperature || config.max_tokens) ? `<div class="text-muted small">温度: ${config.temperature || '默认'} | Token: ${config.max_tokens || '默认'}</div>` : ''}
                </div>
                <div>
                    ${configInfo ? `<span class="badge badge-info">${configInfo.name}</span>` : '<span class="text-muted">未配置</span>'}
                    <button class="btn btn-outline-primary btn-sm ms-2" onclick="editTaskConfig('${task}')">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function populateConfigSelect() {
    const select = document.getElementById('task-config');
    select.innerHTML = configs.map(config => 
        `<option value="${config.id}">${config.name} (${getProviderName(config.provider)})</option>`
    ).join('');
}

function openConfigModal(configId) {
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
            document.getElementById('config-model').value = config.model_name;
            document.getElementById('config-temperature').value = config.temperature;
            document.getElementById('config-max-tokens').value = config.max_tokens;
            document.getElementById('config-input-price').value = config.input_price || 0;
            document.getElementById('config-output-price').value = config.output_price || 0;
            document.getElementById('config-cache-hit-price').value = config.cache_hit_price || 0;
            document.getElementById('config-default').checked = config.is_default;
        }
    }
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
    const modelName = document.getElementById('config-model').value.trim();
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
            closeConfigModal();
            loadConfigs();
            showSuccess('保存成功');
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
    document.getElementById('taskConfigModalTitle').innerHTML = taskType ? '<i class="fas fa-edit me-2"></i>编辑任务配置' : '<i class="fas fa-plus me-2"></i>添加任务配置';
    document.getElementById('task-type').value = taskType || 'outline';
    document.getElementById('task-temperature').value = '';
    document.getElementById('task-max-tokens').value = '';
    
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
            loadConfigs();
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
                loadConfigs();
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
    const names = {
        'deepseek': 'DeepSeek',
        'openai': 'OpenAI',
        'anthropic': 'Anthropic',
        'qwen': 'Qwen',
        'gemini': 'Gemini',
        'custom': '自定义'
    };
    return names[provider] || provider;
}

function getTaskTypeName(type) {
    const names = {
        'outline': '大纲生成',
        'volume': '卷结构生成',
        'chapter': '章节概要生成',
        'content': '章节内容生成'
    };
    return names[type] || type;
}

// logout 函数使用 common.js 中的统一实现

