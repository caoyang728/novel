/**
 * 通用工具函数
 */

// 禁止从 bfcache (往返缓存) 恢复页面，确保每次都重新加载
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        window.location.reload();
    }
});

function getProjectIdFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id');
    return projectId || null;
}

/**
 * 初始化返回项目按钮
 * @param {string} selector - 返回按钮的选择器
 * @param {string} targetPage - 目标页面，默认为 'project.html'
 */
function initBackToProjectButton(selector = '.back-btn', targetPage = 'project.html') {
    const backBtn = document.querySelector(selector);
    if (!backBtn) return;

    const urlParams = new URLSearchParams(window.location.search);
    const projectId = urlParams.get('project_id');
    
    // 移除原有的 onclick 事件
    backBtn.removeAttribute('onclick');

    if (projectId) {
        backBtn.onclick = () => {
            window.location.href = `${targetPage}?project_id=${projectId}`;
        };
    } else {
        // 如果没有项目ID，使用浏览器后退
        backBtn.onclick = () => {
            window.history.back();
        };
    }
}

// ==================== 数据存储相关 ====================

// 待恢复数据存储（内存）
const _pendingData = {};

// 保存待恢复数据
function savePendingData(key, data) {
    const currentData = _pendingData[key] || [];
    currentData.push({
        timestamp: Date.now(),
        data: data,
        url: window.location.pathname
    });
    _pendingData[key] = currentData;

    localStorage.setItem('pending_' + key, JSON.stringify(_pendingData[key]));
}

// 恢复待处理数据
function restorePendingData(key) {
    let data = _pendingData[key];
    if (!data) {
        const stored = localStorage.getItem('pending_' + key);
        if (stored) {
            data = JSON.parse(stored);
            _pendingData[key] = data;
        }
    }
    return data;
}

// 清除待处理数据
function clearPendingData(key) {
    delete _pendingData[key];
    localStorage.removeItem('pending_' + key);
}

// ==================== Token 和用户相关 ====================

// 获取 access token
function getToken() {
    return localStorage.getItem('access_token');
}

// 获取用户信息
function getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
}

// 检查是否已登录
function isAuthenticated() {
    return !!getToken();
}

// 检查当前是否是 index.html
function isIndexPage() {
    return window.location.pathname === '/index.html' || window.location.pathname === '/';
}

// 获取 Cookie
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

// ==================== 登录弹窗相关 ====================

let _loginModal = null;
let _onLoginSuccess = null;
let _onLoginCancel = null;

// 显示登录弹窗
function showLoginModal(onSuccess = null, onCancel = null) {
    _onLoginSuccess = onSuccess;
    _onLoginCancel = onCancel;

    if (!_loginModal) {
        _createLoginModal();
    }

    _loginModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    const errorElement = document.getElementById('login-modal-error');
    if (errorElement) {
        errorElement.style.display = 'none';
    }

    const usernameInput = document.getElementById('login-modal-username');
    const passwordInput = document.getElementById('login-modal-password');
    if (usernameInput) usernameInput.value = '';
    if (passwordInput) passwordInput.value = '';
}

// 创建登录弹窗
function _createLoginModal() {
    const modalHTML = `
        <div id="api-login-modal">
            <div class="login-modal-container">
                <div class="login-modal-header">
                    <div class="login-modal-header-decoration"></div>
                    <div>
                        <h3 class="login-modal-title">Novel Agent</h3>
                        <p class="login-modal-subtitle">登录以继续创作</p>
                    </div>
                </div>

                <div class="login-modal-body">
                    <div id="login-modal-error" class="login-modal-error">
                        <i>&#x26A0;&#xFE0F;</i>
                        <span id="login-modal-error-text">登录失败</span>
                    </div>

                    <form id="login-modal-form" class="login-modal-form">
                        <div class="login-modal-form-group">
                            <div class="login-modal-label-row">
                                <i class="login-modal-label-icon">&#x1F464;</i>
                                <label class="login-modal-label">用户名</label>
                            </div>
                            <div class="login-modal-input-wrapper">
                                <input type="text" id="login-modal-username" class="login-modal-input" placeholder="请输入用户名" autocomplete="username" required>
                                <div class="login-modal-input-icon">&#x1F464;</div>
                            </div>
                        </div>

                        <div class="login-modal-form-group">
                            <div class="login-modal-label-row">
                                <i class="login-modal-label-icon">&#x1F512;</i>
                                <label class="login-modal-label">密码</label>
                            </div>
                            <div class="login-modal-input-wrapper">
                                <input type="password" id="login-modal-password" class="login-modal-input" placeholder="请输入密码" autocomplete="current-password" required>
                                <div class="login-modal-input-icon">&#x1F512;</div>
                            </div>
                        </div>

                        <button type="submit" id="login-modal-submit" class="login-modal-btn login-modal-btn-primary">
                            <i id="login-modal-spinner" style="display: none;">&#x21BB;</i>
                            <span id="login-modal-btn-text">登  录</span>
                        </button>
                    </form>

                    <div class="login-modal-links">
                        <a href="/register.html" class="login-modal-link">注册账号</a>
                        <a href="/reset-password/" class="login-modal-link">忘记密码</a>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
    _loginModal = document.getElementById('api-login-modal');

    document.getElementById('login-modal-form').addEventListener('submit', _handleLoginSubmit);
}

// 隐藏登录弹窗
function hideLoginModal() {
    if (_loginModal) {
        _loginModal.style.display = 'none';
    }
    document.body.style.overflow = '';

    if (_onLoginCancel) {
        _onLoginCancel();
        _onLoginCancel = null;
    }
}

// 处理登录提交
async function _handleLoginSubmit(e) {
    e.preventDefault();

    const username = document.getElementById('login-modal-username').value;
    const password = document.getElementById('login-modal-password').value;
    const submitBtn = document.getElementById('login-modal-submit');
    const spinner = document.getElementById('login-modal-spinner');
    const btnText = document.getElementById('login-modal-btn-text');
    const errorDiv = document.getElementById('login-modal-error');
    const errorText = document.getElementById('login-modal-error-text');
    
    submitBtn.disabled = true;
    spinner.style.display = 'inline-block';
    btnText.textContent = '登录中...';
    errorDiv.style.display = 'none';

    try {
        const data = await api.post('/login/', { username, password });

        if (data.success) {
            localStorage.setItem('access_token', data.access);
            localStorage.setItem('refresh_token', data.refresh);
            localStorage.setItem('user', JSON.stringify(data.user));
            
            hideLoginModal();
            
            if (_onLoginSuccess) {
                _onLoginSuccess(data.user);
                _onLoginSuccess = null;
            }
            
            showSuccess('登录成功！');
        } else {
            errorText.textContent = data.message || '登录失败';
            errorDiv.style.display = 'flex';
        }
    } catch (error) {
        errorText.textContent = '网络错误，请重试';
        errorDiv.style.display = 'flex';
    } finally {
        submitBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = '登录';
    }
}

// ==================== Toast 提示相关 ====================

// 显示提示消息
function showToast(message, type = 'success', duration = null) {
    const container = document.getElementById('api-toast-container') || _createToastContainer();
    const toast = document.createElement('div');
    const typeClass = type === 'error' ? ' api-toast-error' : type === 'warning' ? ' api-toast-warning' : '';
    toast.className = 'api-toast-item' + typeClass;

    let closeBtnHtml = '';
    if (type === 'error' || type === 'warning') {
        closeBtnHtml = '<button class="api-toast-close">&times;</button>';
    }

    const icon = type === 'success' ? '&#x2705;' : type === 'warning' ? '&#x26A0;&#xFE0F;' : '&#x274C;';
    toast.innerHTML = `<i>${icon}</i><span class="api-toast-message">${message}</span>${closeBtnHtml}`;
    container.appendChild(toast);

    const closeBtn = toast.querySelector('.api-toast-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            toast.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        });
    }

    const autoClose = duration !== null ? duration : (type === 'success' ? 3000 : null);

    if (autoClose) {
        setTimeout(() => {
            toast.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, autoClose);
    }
}

// 创建 toast 容器
function _createToastContainer() {
    const container = document.createElement('div');
    container.id = 'api-toast-container';
    document.body.appendChild(container);
    return container;
}

// 滚动锁定/解锁（模态框等场景）
function lockScroll() {
    document.body.style.overflow = 'hidden';
}

function unlockScroll() {
    document.body.style.overflow = '';
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 从 LLM 返回的流式文本中提取 JSON 对象/数组
 * 兼容 SSE 包裹和纯 JSON 字符串
 */
function extractJsonFromString(str) {
    if (!str) return null;
    const trimmed = str.trim();
    // 尝试直接解析
    try {
        return JSON.parse(trimmed);
    } catch (e) {
        // 尝试提取 JSON 对象
        const objMatch = trimmed.match(/\{[\s\S]*\}/);
        if (objMatch) {
            try { return JSON.parse(objMatch[0]); } catch (e2) {}
        }
        // 尝试提取 JSON 数组
        const arrMatch = trimmed.match(/\[[\s\S]*\]/);
        if (arrMatch) {
            try { return JSON.parse(arrMatch[0]); } catch (e3) {}
        }
    }
    return null;
}

// 安全的 Markdown 解析：DOMPurify 消毒 + 错误兜底
function safeMarkdownParse(text) {
    if (!text) return '';
    try {
        if (typeof marked !== 'undefined') {
            const rawHtml = marked.parse(text);
            return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(rawHtml) : rawHtml;
        }
        return escapeHtml(text).replace(/\n/g, '<br>');
    } catch (e) {
        console.error('Markdown 解析失败:', e);
        return escapeHtml(text).replace(/\n/g, '<br>');
    }
}

// 显示成功提示
function showSuccess(message, duration = 3000) {
    showToast(message, 'success', duration);
}

// 显示错误提示
function showError(message, duration = null) {
    showToast(message, 'error', duration);
}

function showWarning(message, duration = null) {
    showToast(message, 'warning', duration);
}

// ==================== 加载动画相关 ====================

// 显示加载动画
function showLoading(message = '加载中...', opacity = 0.6, blur = 4) {
    let loadingEl = document.getElementById('global-loading');
    if (!loadingEl) {
        loadingEl = document.createElement('div');
        loadingEl.id = 'global-loading';
        loadingEl.innerHTML = `
            <div class="loading-overlay active" style="background-color: rgba(15, 23, 42, ${opacity}); backdrop-filter: blur(${blur}px); -webkit-backdrop-filter: blur(${blur}px)">
                <div class="loading-content">
                    <div class="loading-spinner">
                        <div class="loading-spinner-outer"></div>
                        <div class="loading-spinner-inner"></div>
                    </div>
                    <p id="loading-message">加载中...</p>
                </div>
            </div>
        `;
        document.body.appendChild(loadingEl);
    }
    const messageEl = loadingEl.querySelector('#loading-message');
    if (messageEl) {
        messageEl.textContent = message;
    }
    const overlay = loadingEl.querySelector('.loading-overlay');
    if (overlay) {
        overlay.style.backgroundColor = `rgba(15, 23, 42, ${opacity})`;
        overlay.style.backdropFilter = `blur(${blur}px)`;
        overlay.style.webkitBackdropFilter = `blur(${blur}px)`;
    }
}

// 隐藏加载动画
function hideLoading() {
    const loadingEl = document.getElementById('global-loading');
    if (loadingEl) {
        loadingEl.remove();
    }
}

// ==================== 认证检查 ====================

// 统一认证检查：校验 token 有效性，失败时弹窗登录
async function checkAuth() {
    if (!api.isAuthenticated()) {
        api.forceReLogin();
        return false;
    }
    try {
        const data = await api.get('/api/auth/user/');
        if (!data || !data.success) {
            api.forceReLogin();
            return false;
        }
        return true;
    } catch (error) {
        api.forceReLogin();
        return false;
    }
}

// ==================== 退出登录 ====================

function logout(redirectUrl = null, saveData = false) {
    if (saveData) {
        savePendingData('page_state', {
            path: window.location.pathname,
            search: window.location.search,
            scrollY: window.scrollY
        });
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    localStorage.removeItem('has_llm_config');

    if (!redirectUrl) {
        showLoginModal();
        return;
    }

    window.location.href = redirectUrl;
}

// ==================== 确认弹窗相关 ====================

let modalAction = null;

// 显示确认弹窗
function showModal(title, message, action) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').textContent = message;
    // 隐藏可能存在的 modal-input
    const modalInput = document.getElementById('modal-input');
    if (modalInput) modalInput.style.display = 'none';
    document.getElementById('confirm-modal').classList.add('show');
    modalAction = action;
}

// 关闭确认弹窗
function closeModal() {
    document.getElementById('confirm-modal').classList.remove('show');
    modalAction = null;
    document.body.style.overflow = '';
}

// 执行确认弹窗的操作
function executeModalAction() {
    if (modalAction) {
        modalAction();
    }
}

// ==================== API 请求封装 ====================

/** 需要 LLM 服务商配置的 API 路径特征（URL 包含以下任一字符串时拦截） */
const _LLM_PATH_MARKERS = ['/worldviews/', '/outline/', '/chapter/',
    '/timeline/', '/note/', '/volume/',
    '/characters/generate/', '/characters/polish/',
    '/characters/check/', '/characters/optimize/'];

function _isLLMRequired(url, method) {
    if (method === 'GET' || method === 'DELETE') return false;
    return _LLM_PATH_MARKERS.some(p => url.includes(p));
}

/** 无需认证即可访问的路径 */
const _NO_AUTH_PATHS = ['/login/', '/register/'];

function _isNoAuthUrl(url) {
    return _NO_AUTH_PATHS.some(p => url.startsWith(p));
}

function _isLLMConfigured() {
    const val = localStorage.getItem('has_llm_config');
    return val === '1';
}

/** 确保 LLM 配置状态已缓存；未缓存时实时查询 */
let _llmConfigPromise = null;
async function _ensureLLMConfigured() {
    const val = localStorage.getItem('has_llm_config');
    if (val !== null) return val === '1';
    // 防止并发重复查询
    if (_llmConfigPromise) return _llmConfigPromise;
    _llmConfigPromise = _fetchLLMConfigStatus();
    try {
        return await _llmConfigPromise;
    } finally {
        _llmConfigPromise = null;
    }
}
async function _fetchLLMConfigStatus() {
    try {
        const token = getToken();
        if (!token) return false;
        const res = await fetch('/api/auth/user/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const json = await res.json();
            if (json.success && json.user) {
                _updateLLMConfigStatus(json.user);
                return json.user.has_llm_config === true;
            }
        }
    } catch (e) {
        // 查询失败，默认未配置
    }
    return false;
}

function _showLLMConfigRequired() {
    if (document.getElementById('llm-config-modal')) return;
    const overlay = document.createElement('div');
    overlay.id = 'llm-config-modal';
    overlay.className = 'dialog-overlay show';
    overlay.style.background = 'rgba(0,0,0,0.6)';
    overlay.innerHTML = `
        <div class="dialog dialog-sm">
            <div class="dialog-body">
                <i class="fas fa-exclamation-triangle" style="font-size:2.5rem;color:#f59e0b;margin-bottom:1rem;display:block;"></i>
                <h3 style="color:#f9fafb;margin:0 0 0.75rem;font-size:1.1rem;">未配置 LLM 服务商</h3>
                <p style="color:#9ca3af;margin:0;line-height:1.6;">
                    请先在「LLM 配置」页面添加并测试模型配置，<br>完成后即可使用 AI 功能。
                </p>
            </div>
            <div class="dialog-footer" style="justify-content: space-around;">
                <button class="btn-cancel" onclick="document.getElementById('llm-config-modal').remove();">取消</button>
                <button class="btn-success" onclick="window.location.href='/llm_config.html'">前往配置</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function _updateLLMConfigStatus(userData) {
    if (userData && userData.has_llm_config !== undefined) {
        localStorage.setItem('has_llm_config', userData.has_llm_config ? '1' : '0');
    }
}

// Token 静默刷新：防止并发刷新请求
let _refreshPromise = null;

const api = {
    // 获取 access token
    getToken: getToken,

    // 使用 refresh_token 静默刷新 access_token，返回新 token 或 null
    async refreshAccessToken() {
        if (_refreshPromise) return _refreshPromise;
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) return null;

        _refreshPromise = (async () => {
            try {
                const response = await fetch('/api/auth/refresh/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ refresh: refreshToken }),
                });

                if (!response.ok) return null;

                const data = await response.json();
                if (data.success && data.access) {
                    localStorage.setItem('access_token', data.access);
                    if (data.refresh) {
                        localStorage.setItem('refresh_token', data.refresh);
                    }
                    return data.access;
                }
                return null;
            } catch (error) {
                console.error('Token 刷新失败:', error);
                return null;
            } finally {
                _refreshPromise = null;
            }
        })();

        return _refreshPromise;
    },

    // 获取用户信息
    getUser: getUser,

    // 获取 Cookie
    getCookie: getCookie,

    // 检查是否已登录
    isAuthenticated: isAuthenticated,

    // 通用请求方法
    async request(url, options = {}) {
        const token = getToken();
        if (!token && !_isNoAuthUrl(url)) {
            this.forceReLogin();
            return null;
        }
        // 检查 LLM 服务商配置（仅 LLM 相关路径才拦截）
        const reqMethod = options.method || 'GET';
        if (_isLLMRequired(url, reqMethod)) {
            const configured = await _ensureLLMConfigured();
            if (!configured) {
                _showLLMConfigRequired();
                return null;
            }
        }
        const headers = {
            'Content-Type': options.contentType || 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // 提取 options 中可能覆盖 headers 的属性，避免 ...options spread 覆盖手动构造的 headers
        const { headers: _omittedHeaders, contentType: _omittedContentType, ...safeOptions } = options;

        const config = {
            method: options.method || 'GET',
            headers,
            ...safeOptions
        };

        if (options.body) {
            config.body = options.body;
        }

        try {
            const response = await fetch(url, config);

            if (response.status === 401 && !options._isRefreshRetry) {
                const newToken = await this.refreshAccessToken();
                if (newToken) {
                    return this.request(url, { ...options, _isRefreshRetry: true });
                }
            }

            if (response.status === 401) {
                api.forceReLogin(() => {
                    if (options.onUnauthorizedRetry && options.onUnauthorizedRetry === false) {
                        return;
                    }
                    this.request(url, { ...options, onUnauthorizedRetry: false });
                });
                return null;
            }

            if (!response.ok) {
                const contentType = response.headers.get('content-type');
                // 4xx 且返回 JSON 时，返回 JSON 让调用方处理业务错误
                if (response.status >= 400 && response.status < 500 && contentType && contentType.includes('application/json')) {
                    return await response.json();
                }
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `请求失败: ${response.status}`);
            }

            if (options.stream) {
                return response;
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const json = await response.json();
                // 从用户信息响应中缓存 LLM 配置状态
                if (url === '/api/auth/user/' && json && json.success && json.user) {
                    _updateLLMConfigStatus(json.user);
                }
                // 检测 LLM 未配置错误，弹窗而非让页面 toast
                if (_isLLMRequired(url, reqMethod) && json && json.success === false) {
                    const msg = json.message || json.error || '';
                    if (msg.includes('未配置 LLM') || msg.includes('LLM 服务商')) {
                        _showLLMConfigRequired();
                        return null;
                    }
                }
                return json;
            }

            return await response.text();
        } catch (error) {
            if (options.onError) {
                options.onError(error);
            } else {
                console.error('API请求错误:', error);
                throw error;
            }
        }
    },

    async get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    },

    async post(url, data, options = {}) {
        const body = typeof data === 'string' ? data : JSON.stringify(data);
        return this.request(url, { ...options, method: 'POST', body });
    },

    async put(url, data, options = {}) {
        const body = typeof data === 'string' ? data : JSON.stringify(data);
        return this.request(url, { ...options, method: 'PUT', body });
    },

    async delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    },

    // 流式请求（聚合返回）
    // 支持的 SSE 协议格式（优先级从高到低）：
    //   1. {"type":"chunk","data":"..."} + {"type":"complete","data":"..."} + {"type":"error","message":"..."}
    //   2. data: [DONE] + {"content":"..."} 或 {"data":"..."}（旧格式兼容）
    async streamRequest(url, options = {}) {
        const token = getToken();
        if (!token && !_isNoAuthUrl(url)) {
            this.forceReLogin();
            return null;
        }
        // 检查 LLM 服务商配置
        if (_isLLMRequired(url, 'POST')) {
            const configured = await _ensureLLMConfigured();
            if (!configured) {
                _showLLMConfigRequired();
                return null;
            }
        }
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const body = options.body ?
            (typeof options.body === 'string' ? options.body : JSON.stringify(options.body)) :
            undefined;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers,
                body,
            });

            if (response.status === 401 && !options._isRefreshRetry) {
                const newToken = await this.refreshAccessToken();
                if (newToken) {
                    return this.streamRequest(url, { ...options, _isRefreshRetry: true });
                }
            }

            if (response.status === 401) {
                this.forceReLogin();
                return null;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `请求失败: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let result = '';
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const data = line.slice(6);
                    if (data === '[DONE]') return result;

                    let parsed;
                    try {
                        parsed = JSON.parse(data);
                    } catch (e) {
                        continue;  // 非 JSON 数据跳过
                    }

                    // 格式1: type: chunk|complete|error
                    if (parsed.type === 'complete') {
                        return parsed.data !== undefined ? parsed.data : result;
                    }
                    if (parsed.type === 'error') {
                        const errMsg = parsed.message || '操作失败';
                        if (errMsg.includes('未配置 LLM') || errMsg.includes('LLM 服务商')) {
                            _showLLMConfigRequired();
                            return null;
                        }
                        throw new Error(errMsg);
                    }
                    if (parsed.type === 'chunk') {
                        result += (parsed.content || parsed.data || '');
                        continue;
                    }

                    // 格式2: 旧格式兼容 {content: "..."} 或 {data: "..."}
                    const chunkContent = parsed.content || parsed.data || '';
                    if (chunkContent) result += chunkContent;
                }
            }

            return result;
        } catch (error) {
            if (options.onError) {
                options.onError(error);
            } else {
                console.error('流式请求错误:', error);
                throw error;
            }
        }
    },

    // 流式请求（实时回调）
    async streamRequestRaw(url, options = {}, onChunk) {
        const token = getToken();
        if (!token && !_isNoAuthUrl(url)) {
            this.forceReLogin();
            return null;
        }
        // 检查 LLM 服务商配置
        if (_isLLMRequired(url, 'POST')) {
            const configured = await _ensureLLMConfigured();
            if (!configured) {
                _showLLMConfigRequired();
                return null;
            }
        }
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const body = options.body ?
            (typeof options.body === 'string' ? options.body : JSON.stringify(options.body)) :
            undefined;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers,
                body,
            });

            if (response.status === 401 && !options._isRefreshRetry) {
                const newToken = await this.refreshAccessToken();
                if (newToken) {
                    return this.streamRequestRaw(url, { ...options, _isRefreshRetry: true }, onChunk);
                }
            }

            if (response.status === 401) {
                this.forceReLogin();
                return null;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `请求失败: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullContent = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            onChunk && onChunk({ done: true, content: '' });
                            return fullContent;
                        }
                        try {
                            const parsed = JSON.parse(data);
                            // 检测 LLM 未配置的 SSE 错误事件
                            if (parsed.type === 'error') {
                                const errMsg = parsed.message || '';
                                if (errMsg.includes('未配置 LLM') || errMsg.includes('LLM 服务商')) {
                                    _showLLMConfigRequired();
                                    return null;
                                }
                            }
                            const chunkContent = parsed.content || parsed.data || '';
                            if (chunkContent) {
                                fullContent += chunkContent;
                            }
                            onChunk && onChunk({ done: false, content: chunkContent, data: parsed });
                        } catch (e) {
                        }
                    }
                }
            }

            return fullContent;
        } catch (error) {
            if (options.onError) {
                options.onError(error);
            } else {
                console.error('流式请求错误:', error);
                throw error;
            }
        }
    },

    // 强制重新登录
    forceReLogin(onSuccess = null) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        showLoginModal(onSuccess);
    }
};

// ==================== 通用聊天多选删除 ====================
// 使用方式：页面需定义全局变量 let isSelectionMode = false; let selectedMessages = new Set();
// 聊天头部 HTML 需包含 #toggle-selection-btn, #selection-actions, #cancel-selection-btn,
//   #delete-selected-btn, #select-all-btn 等元素

function enterSelectionMode() {
    isSelectionMode = true;
    selectedMessages.clear();
    const toggleBtn = document.getElementById('toggle-selection-btn');
    const selActions = document.getElementById('selection-actions');
    const ctxSelect = document.getElementById('context-count-select');
    const chatMessages = document.getElementById('chat-messages');
    if (toggleBtn) toggleBtn.style.display = 'none';
    if (selActions) selActions.style.display = 'flex';
    if (ctxSelect) ctxSelect.style.display = 'none';
    if (chatMessages) chatMessages.classList.add('selection-mode');
    if (typeof onSelectionModeChanged === 'function') onSelectionModeChanged();
}

function cancelSelection() {
    isSelectionMode = false;
    selectedMessages.clear();
    const toggleBtn = document.getElementById('toggle-selection-btn');
    const selActions = document.getElementById('selection-actions');
    const ctxSelect = document.getElementById('context-count-select');
    const chatMessages = document.getElementById('chat-messages');
    if (toggleBtn) toggleBtn.style.display = 'flex';
    if (selActions) selActions.style.display = 'none';
    if (ctxSelect) ctxSelect.style.display = 'flex';
    if (chatMessages) chatMessages.classList.remove('selection-mode');
    if (typeof onSelectionModeChanged === 'function') onSelectionModeChanged();
}

function toggleMessageSelect(index) {
    if (!isSelectionMode) return;
    if (selectedMessages.has(index)) {
        selectedMessages.delete(index);
    } else {
        selectedMessages.add(index);
    }
    const div = document.querySelector(`.chat-message[data-message-index="${index}"]`);
    if (div) div.classList.toggle('selected');
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.disabled = selectedMessages.size === 0;
}

function toggleSelectAll() {
    if (!isSelectionMode) return;
    const checkboxes = document.querySelectorAll('.chat-message-checkbox');
    const allChecked = selectedMessages.size === messages.length;
    if (allChecked) {
        selectedMessages.clear();
    } else {
        messages.forEach((_, i) => selectedMessages.add(i));
    }
    checkboxes.forEach((cb, i) => {
        cb.checked = !allChecked;
        const div = document.querySelector(`.chat-message[data-message-index="${i}"]`);
        if (div) div.classList.toggle('selected', !allChecked);
    });
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.disabled = selectedMessages.size === 0;
}

function deleteSelectedMessages() {
    if (selectedMessages.size === 0) return;
    showModal('删除对话', `确定要删除选中的 ${selectedMessages.size} 条对话吗？`, function() {
        const sorted = Array.from(selectedMessages).sort((a, b) => b - a);
        sorted.forEach(i => messages.splice(i, 1));
        selectedMessages.clear();
        cancelSelection();
        closeModal();
        showSuccess('删除成功！');
    });
}

// ==================== 项目信息加载 ====================

/**
 * 加载项目信息并更新 #project-title
 * @param {string|number} projectId - 项目ID
 * @param {Function} onSuccess - 可选回调，接收 data 参数用于额外处理
 */
async function loadProjectInfo(projectId, onSuccess) {
    try {
        const data = await api.get(`/api/projects/${projectId}/`);
        if (data && data.success) {
            const titleEl = document.getElementById('project-title');
            if (titleEl) titleEl.textContent = data.project.title || '';
            if (onSuccess) onSuccess(data);
        }
    } catch (error) {
        console.error('加载项目信息失败:', error);
    }
}

// ==================== 用户信息加载 ====================

/**
 * 加载用户信息和今日Token用量
 * @param {Object} options - 配置项
 * @param {string} options.usernameEl - 用户名元素ID，默认 'username'
 * @param {string} options.tokenUsageEl - Token用量元素ID，默认 'token-usage'
 */
async function loadUserInfo(options = {}) {
    const usernameElId = options.usernameEl || 'username';
    const tokenUsageElId = options.tokenUsageEl || 'token-usage';

    try {
        const data = await api.get('/api/auth/user/');
        if (data && data.success) {
            const el = document.getElementById(usernameElId);
            if (el) el.textContent = data.user.username;
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }

    try {
        const data = await api.get('/api/token-usage/today/');
        if (data && data.success) {
            const total = data.usage.total_tokens || 0;
            const formatted = formatTokenCount(total);
            const el = document.getElementById(tokenUsageElId);
            if (el) el.textContent = '今日 Token: ' + formatted;
        }
    } catch (error) {
        console.error('Failed to load token usage:', error);
    }
}

/**
 * 格式化 Token 数量
 * @param {number} num - 数字
 * @returns {string} 格式化后的字符串
 */
function formatTokenCount(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num || 0;
}

// ==================== 按钮状态工具 ====================

/**
 * 设置按钮为 loading 状态
 * @param {HTMLElement} btn - 按钮元素
 * @param {string} loadingText - loading 时显示的文字
 * @returns {string} 按钮原始 innerHTML，用于恢复
 */
function setButtonLoading(btn, loadingText) {
    if (!btn) return '';
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="loading-spinner"></span> ${loadingText || '处理中...'}`;
    return originalHTML;
}

/**
 * 恢复按钮状态
 * @param {HTMLElement} btn - 按钮元素
 * @param {string} originalHTML - 原始 innerHTML
 */
function resetButton(btn, originalHTML) {
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = originalHTML;
}

// ==================== 聊天输入框初始化 ====================

/**
 * 初始化聊天输入框：Enter发送 + 自动高度调整
 * @param {string|HTMLElement} inputEl - 输入框元素或选择器
 * @param {Object} options - 配置项
 * @param {Function} options.onSend - Enter发送回调
 * @param {number} options.maxHeight - 最大高度(px)，默认160
 * @param {boolean} options.shiftEnterNewline - Shift+Enter换行，默认true
 */
function initChatInput(inputEl, options = {}) {
    const input = typeof inputEl === 'string' ? document.querySelector(inputEl) : inputEl;
    if (!input) return;

    const { onSend, maxHeight = 160, shiftEnterNewline = true } = options;

    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (shiftEnterNewline && e.shiftKey) return; // Shift+Enter 换行
            e.preventDefault();
            if (onSend) onSend();
        }
    });

    input.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, maxHeight) + 'px';
    });
}

// ==================== 模态框 ID 操作（多页面共用） ====================

/**
 * 通过 ID 打开模态框（添加 show 类）
 * @param {string} id - 模态框元素 ID
 */
function openModalById(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('show');
}

/**
 * 通过 ID 关闭模态框（移除 show 类）
 * @param {string} id - 模态框元素 ID
 */
function closeModalById(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('show');
}

// ==================== ESC 键关闭模态框（全局行为） ====================

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        // 关闭所有打开的模态框
        const openModals = document.querySelectorAll('.dialog-overlay.show, .modal-overlay.show, .custom-modal-overlay.show');
        openModals.forEach(modal => modal.classList.remove('show'));
        // 恢复滚动
        document.body.style.overflow = '';
    }
});

// ==================== 通用工具函数（多页面共用） ====================

/**
 * 显示元素（移除 dc-hidden 类或 d-none 类）
 * @param {HTMLElement|string} el - 元素或元素 ID
 */
function showElement(el) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (el) {
        el.classList.remove('dc-hidden');
        el.classList.remove('d-none');
    }
}

/**
 * 隐藏元素（添加 dc-hidden 类或 d-none 类）
 * @param {HTMLElement|string} el - 元素或元素 ID
 * @param {string} [hideClass='dc-hidden'] - 隐藏类名，默认 dc-hidden
 */
function hideElement(el, hideClass) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (el) {
        el.classList.add(hideClass || 'dc-hidden');
    }
}

/**
 * 设置表单字段值（支持字符串、数组、对象）
 * @param {string} id - 元素 ID
 * @param {*} value - 值
 */
function setField(id, value) {
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

/**
 * 格式化日期字符串
 * @param {string} dateStr - 日期字符串
 * @param {boolean} [includeTime=true] - 是否包含时间
 * @returns {string} 格式化后的日期
 */
function formatDate(dateStr, includeTime = true) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    if (includeTime) {
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('zh-CN');
}

// ==================== 增强版 JSON 解析（多页面共用） ====================

/**
 * 安全的 JSON 解析（增强版）
 * 处理 LLM 输出中的常见问题：ITEM 标记、中文引号、未转义字符、控制字符、外层包裹等
 * @param {string} str - 待解析的字符串
 * @returns {Object|Array|null} 解析结果
 */
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

        // 清理 era_unit 中的"元年"/"年"后缀
        function cleanParsed(parsed) {
            if (!parsed) return parsed;
            if (parsed.era_unit && typeof parsed.era_unit === 'string') {
                parsed.era_unit = parsed.era_unit.replace(/元年$|年$/, '');
            }
            return parsed;
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
        let inner = cleaned;
        for (let attempt = 0; attempt < 3; attempt++) {
            inner = inner.trim();
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
