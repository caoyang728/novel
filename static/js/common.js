/**
 * 通用工具函数
 */

function getProjectIdFromUrl() {
    const pathParts = window.location.pathname.split('/').filter(p => p);
    if (pathParts.length > 0 && !isNaN(parseInt(pathParts[0]))) {
        return parseInt(pathParts[0]);
    }
    return null;
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
        const response = await fetch('/login/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

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
function showToast(message, type = 'success') {
    const container = document.getElementById('api-toast-container') || _createToastContainer();
    const toast = document.createElement('div');
    toast.className = 'api-toast-item' + (type === 'error' ? ' api-toast-error' : '');
    toast.innerHTML = `<i>${type === 'success' ? '&#x2705;' : '&#x274C;'}</i>${message}`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 创建 toast 容器
function _createToastContainer() {
    const container = document.createElement('div');
    container.id = 'api-toast-container';
    document.body.appendChild(container);
    return container;
}

// 显示成功提示
function showSuccess(message) {
    showToast(message, 'success');
}

// 显示错误提示
function showError(message) {
    showToast(message, 'error');
}

// ==================== 加载动画相关 ====================

// 显示加载动画
function showLoading(message = '加载中...') {
    let loadingEl = document.getElementById('global-loading');
    if (!loadingEl) {
        loadingEl = document.createElement('div');
        loadingEl.id = 'global-loading';
        loadingEl.innerHTML = `
            <div class="loading-overlay active">
                <div class="loading-content">
                    <div class="loading-spinner"></div>
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
}

// 隐藏加载动画
function hideLoading() {
    const loadingEl = document.getElementById('global-loading');
    if (loadingEl) {
        loadingEl.remove();
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

    if (!redirectUrl) {
        showLoginModal();
        return;
    }

    window.location.href = redirectUrl;
}

// ==================== API 请求封装 ====================

const api = {
    // 获取 access token
    getToken: getToken,

    // 获取用户信息
    getUser: getUser,

    // 获取 Cookie
    getCookie: getCookie,

    // 检查是否已登录
    isAuthenticated: isAuthenticated,

    // 通用请求方法
    async request(url, options = {}) {
        const token = getToken();
        const headers = {
            'Content-Type': options.contentType || 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            method: options.method || 'GET',
            headers,
            ...options
        };

        if (options.body) {
            config.body = options.body;
        }

        try {
            const response = await fetch(url, config);

            if (response.status === 401) {
                forceReLogin(() => {
                    if (options.onUnauthorizedRetry && options.onUnauthorizedRetry === false) {
                        return;
                    }
                    this.request(url, { ...options, onUnauthorizedRetry: false });
                });
                return null;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `请求失败: ${response.status}`);
            }

            if (options.stream) {
                return response;
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
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
    async streamRequest(url, options = {}) {
        const token = getToken();
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
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            return result;
                        }
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.content) {
                                result += parsed.content;
                            }
                        } catch (e) {
                        }
                    }
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
                            if (parsed.content) {
                                fullContent += parsed.content;
                                onChunk && onChunk({ done: false, content: parsed.content });
                            }
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
