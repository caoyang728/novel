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
 * 通用的 API 请求封装
 * 自动携带 JWT token
 */

const api = {
    // 数据保存和恢复功能
    _pendingData: {},
    
    // 登录弹窗相关
    _loginModal: null,
    _onLoginSuccess: null,
    _onLoginCancel: null,
    
    // 获取 access token
    getToken: function() {
        return localStorage.getItem('access_token');
    },

    // 获取用户信息
    getUser: function() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },

    // 保存待恢复数据
    savePendingData: function(key, data) {
        const currentData = this._pendingData[key] || [];
        currentData.push({
            timestamp: Date.now(),
            data: data,
            url: window.location.pathname
        });
        this._pendingData[key] = currentData;
        
        // 同时保存到 localStorage 作为备份
        localStorage.setItem('pending_' + key, JSON.stringify(this._pendingData[key]));
    },
    
    // 恢复待处理数据
    restorePendingData: function(key) {
        // 先从内存中获取
        let data = this._pendingData[key];
        if (!data) {
            // 如果内存没有，从 localStorage 中获取
            const stored = localStorage.getItem('pending_' + key);
            if (stored) {
                data = JSON.parse(stored);
                this._pendingData[key] = data;
            }
        }
        return data;
    },
    
    // 清除待处理数据
    clearPendingData: function(key) {
        delete this._pendingData[key];
        localStorage.removeItem('pending_' + key);
    },

    // 显示登录弹窗
    showLoginModal: function(onSuccess = null, onCancel = null) {
        this._onLoginSuccess = onSuccess;
        this._onLoginCancel = onCancel;
        
        if (!this._loginModal) {
            this._createLoginModal();
        }
        
        this._loginModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        
        // 清空之前的错误信息
        const errorElement = document.getElementById('login-modal-error');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    },
    
    // 创建登录弹窗
    _createLoginModal: function() {
        const modalHTML = `
            <div id="api-login-modal" style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                z-index: 9999;
                display: none;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            ">
                <div style="
                    background: #fff;
                    border-radius: 20px;
                    width: 90%;
                    max-width: 420px;
                    overflow: hidden;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                    animation: loginModalFadeIn 0.2s ease;
                ">
                    <style>
                        @keyframes loginModalFadeIn {
                            from { opacity: 0; transform: scale(0.95) translateY(-10px); }
                            to { opacity: 1; transform: scale(1) translateY(0); }
                        }
                        @keyframes loginModalFadeOut {
                            from { opacity: 1; transform: scale(1); }
                            to { opacity: 0; transform: scale(0.95); }
                        }
                        .login-modal-close {
                            cursor: pointer;
                            padding: 0.5rem;
                            border-radius: 8px;
                            transition: background 0.2s;
                        }
                        .login-modal-close:hover {
                            background: #f1f5f9;
                        }
                        .login-modal-input {
                            width: 100%;
                            padding: 0.75rem;
                            border: 1px solid #e2e8f0;
                            border-radius: 12px;
                            font-size: 0.9rem;
                            transition: border-color 0.2s, box-shadow 0.2s;
                        }
                        .login-modal-input:focus {
                            outline: none;
                            border-color: #0ea5e9;
                            box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15);
                        }
                        .login-modal-btn {
                            width: 100%;
                            padding: 0.75rem;
                            border-radius: 12px;
                            font-weight: 600;
                            font-size: 0.95rem;
                            border: none;
                            cursor: pointer;
                            transition: all 0.2s;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            gap: 0.5rem;
                        }
                        .login-modal-btn-primary {
                            background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
                            color: #fff;
                        }
                        .login-modal-btn-primary:hover:not(:disabled) {
                            transform: translateY(-1px);
                            box-shadow: 0 4px 14px rgba(14, 165, 233, 0.35);
                        }
                        .login-modal-btn-primary:disabled {
                            opacity: 0.5;
                            cursor: not-allowed;
                        }
                        .login-modal-link {
                            color: #0ea5e9;
                            text-decoration: none;
                            font-size: 0.875rem;
                        }
                        .login-modal-link:hover {
                            text-decoration: underline;
                        }
                    </style>
                    
                    <div style="padding: 1.5rem; border-bottom: 1px solid #f1f5f9;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h3 style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #1e293b;">
                                    <i style="margin-right: 0.5rem; color: #0ea5e9;">&#x270D;&#xFE0F;</i>
                                    Novel Agent
                                </h3>
                                <p style="margin: 0.25rem 0 0 0; font-size: 0.85rem; color: #64748b;">
                                    登录以继续创作
                                </p>
                            </div>
                            <div id="login-modal-close-btn" class="login-modal-close">
                                <i style="font-size: 1.25rem; color: #64748b;">&#x2715;</i>
                            </div>
                        </div>
                    </div>
                    
                    <div style="padding: 1.5rem;">
                        <div id="login-modal-error" style="
                            display: none;
                            background: #fef2f2;
                            color: #dc2626;
                            padding: 0.75rem;
                            border-radius: 10px;
                            margin-bottom: 1rem;
                            font-size: 0.875rem;
                            display: flex;
                            align-items: center;
                            gap: 0.5rem;
                        ">
                            <i>&#x26A0;&#xFE0F;</i>
                            <span id="login-modal-error-text">登录失败</span>
                        </div>
                        
                        <form id="login-modal-form" style="display: flex; flex-direction: column; gap: 1rem;">
                            <div>
                                <label style="
                                    display: block;
                                    font-weight: 600;
                                    font-size: 0.85rem;
                                    color: #475569;
                                    margin-bottom: 0.375rem;
                                ">用户名</label>
                                <input type="text" id="login-modal-username" class="login-modal-input" placeholder="请输入用户名" autocomplete="username" required>
                            </div>
                            
                            <div>
                                <label style="
                                    display: block;
                                    font-weight: 600;
                                    font-size: 0.85rem;
                                    color: #475569;
                                    margin-bottom: 0.375rem;
                                ">密码</label>
                                <input type="password" id="login-modal-password" class="login-modal-input" placeholder="请输入密码" autocomplete="current-password" required>
                            </div>
                            
                            <button type="submit" id="login-modal-submit" class="login-modal-btn login-modal-btn-primary">
                                <i id="login-modal-spinner" style="display: none; animation: spin 0.8s linear infinite;">&#x21BB;</i>
                                <span id="login-modal-btn-text">登录</span>
                            </button>
                        </form>
                        
                        <div style="margin-top: 1rem; display: flex; justify-content: center; gap: 2rem;">
                            <a href="/register.html" class="login-modal-link">注册账号</a>
                            <a href="/reset-password/" class="login-modal-link">忘记密码</a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this._loginModal = document.getElementById('api-login-modal');
        
        // 添加事件监听
        document.getElementById('login-modal-close-btn').addEventListener('click', () => this.hideLoginModal());
        document.getElementById('login-modal-form').addEventListener('submit', (e) => this._handleLoginSubmit(e));
        
        // 点击遮罩关闭弹窗
        this._loginModal.addEventListener('click', (e) => {
            if (e.target === this._loginModal) {
                this.hideLoginModal();
            }
        });
    },
    
    // 隐藏登录弹窗
    hideLoginModal: function() {
        if (this._loginModal) {
            this._loginModal.style.animation = 'loginModalFadeOut 0.2s ease forwards';
            setTimeout(() => {
                this._loginModal.style.display = 'none';
                this._loginModal.style.animation = '';
            }, 200);
        }
        document.body.style.overflow = '';
        
        if (this._onLoginCancel) {
            this._onLoginCancel();
            this._onLoginCancel = null;
        }
    },
    
    // 处理登录提交
    async _handleLoginSubmit(e) {
        e.preventDefault();
        
        const username = document.getElementById('login-modal-username').value;
        const password = document.getElementById('login-modal-password').value;
        const submitBtn = document.getElementById('login-modal-submit');
        const spinner = document.getElementById('login-modal-spinner');
        const btnText = document.getElementById('login-modal-btn-text');
        const errorDiv = document.getElementById('login-modal-error');
        const errorText = document.getElementById('login-modal-error-text');
        
        // 禁用按钮并显示加载状态
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
                // 保存 token 到 localStorage
                localStorage.setItem('access_token', data.access);
                localStorage.setItem('refresh_token', data.refresh);
                localStorage.setItem('user', JSON.stringify(data.user));
                
                // 隐藏弹窗
                this.hideLoginModal();
                
                // 调用成功回调
                if (this._onLoginSuccess) {
                    this._onLoginSuccess(data.user);
                    this._onLoginSuccess = null;
                }
                
                // 显示登录成功提示
                this._showToast('登录成功！', 'success');
            } else {
                errorText.textContent = data.message || '登录失败';
                errorDiv.style.display = 'flex';
            }
        } catch (error) {
            errorText.textContent = '网络错误，请重试';
            errorDiv.style.display = 'flex';
        } finally {
            // 恢复按钮状态
            submitBtn.disabled = false;
            spinner.style.display = 'none';
            btnText.textContent = '登录';
        }
    },
    
    // 显示提示消息
    _showToast: function(message, type = 'success') {
        const container = document.getElementById('api-toast-container') || this._createToastContainer();
        const toast = document.createElement('div');
        toast.style.cssText = `
            background: ${type === 'success' ? 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)' : 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'};
            color: #fff;
            padding: 0.875rem 1.25rem;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.15);
            font-size: 0.9rem;
            font-weight: 500;
            min-width: 280px;
            animation: toastSlideIn 0.3s ease;
        `;
        toast.innerHTML = `<i>${type === 'success' ? '&#x2705;' : '&#x274C;'}</i>${message}`;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },
    
    // 创建 toast 容器
    _createToastContainer: function() {
        const container = document.createElement('div');
        container.id = 'api-toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        `;
        const style = document.createElement('style');
        style.textContent = `
            @keyframes toastSlideIn {
                from { opacity: 0; transform: translateX(100%); }
                to { opacity: 1; transform: translateX(0); }
            }
            @keyframes toastSlideOut {
                from { opacity: 1; transform: translateX(0); }
                to { opacity: 0; transform: translateX(100%); }
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(container);
        return container;
    },

    // 清除登录信息（改进版）- 使用弹窗而非重定向
    logout: function(redirectUrl = null, savePendingData = false) {
        if (savePendingData) {
            // 保存当前页面状态（可选）
            this.savePendingData('page_state', {
                path: window.location.pathname,
                search: window.location.search,
                scrollY: window.scrollY
            });
        }
        
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        
        // 如果没有指定重定向，使用弹窗登录
        if (!redirectUrl) {
            this.showLoginModal();
            return;
        }
        
        window.location.href = redirectUrl;
    },

    // 强制显示登录弹窗（当 token 完全失效时）
    forceReLogin: function(onSuccess = null) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        this.showLoginModal(onSuccess);
    },

    // 检查是否已登录
    isAuthenticated: function() {
        return !!this.getToken();
    },

    // 检查当前是否是 index.html
    isIndexPage() {
        return window.location.pathname === '/index.html' || window.location.pathname === '/';
    },

    // 获取Cookie
    getCookie(name) {
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
    },
    
    // 通用请求方法（改进版）- 根据页面不同处理方式
    async request(url, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': options.contentType || 'application/json',
            'X-CSRFToken': this.getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            // 收到 401 尝试刷新 token
            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    const retryResponse = await fetch(url, {
                        ...options,
                        headers
                    });
                    return this.handleResponse(retryResponse);
                } else {
                    // refresh token 也失效了
                    if (this.isIndexPage()) {
                        // index.html 重定向到登录页
                        window.location.href = '/login.html?next=' + encodeURIComponent(window.location.pathname + window.location.search);
                        return Promise.reject(new Error('未登录'));
                    } else {
                        // 其他页面显示登录弹窗
                        return new Promise((resolve, reject) => {
                            this.forceReLogin(async (user) => {
                                // 用户登录成功，重新发送请求
                                headers['Authorization'] = `Bearer ${this.getToken()}`;
                                try {
                                    const retryResponse = await fetch(url, {
                                        ...options,
                                        headers
                                    });
                                    const result = await this.handleResponse(retryResponse);
                                    resolve(result);
                                } catch (e) {
                                    reject(e);
                                }
                            });
                        });
                    }
                }
            }

            return this.handleResponse(response);
        } catch (error) {
            console.error('请求失败:', error);
            throw error;
        }
    },

    // 流式请求 - 等待全部返回后一次性返回结果
    async streamRequest(url, options = {}) {
        const token = this.getToken();
        const headers = {
            'Content-Type': options.contentType || 'application/json',
            'X-CSRFToken': this.getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    const retryResponse = await fetch(url, {
                        ...options,
                        headers
                    });
                    return this.handleStreamResponse(retryResponse);
                } else {
                    return new Promise((resolve, reject) => {
                        this.forceReLogin(async (user) => {
                            headers['Authorization'] = `Bearer ${this.getToken()}`;
                            try {
                                const retryResponse = await fetch(url, {
                                    ...options,
                                    headers
                                });
                                const result = await this.handleStreamResponse(retryResponse);
                                resolve(result);
                            } catch (e) {
                                reject(e);
                            }
                        });
                    });
                }
            }

            return this.handleStreamResponse(response);
        } catch (error) {
            console.error('流式请求失败:', error);
            throw error;
        }
    },

    // 流式请求 - 中转模式，原样返回数据
    async streamRequestRaw(url, options = {}, onChunk = null) {
        const token = this.getToken();
        const headers = {
            'Content-Type': options.contentType || 'application/json',
            'X-CSRFToken': this.getCookie('csrftoken'),
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    return this.streamRequestRaw(url, { ...options, headers }, onChunk);
                } else {
                    return new Promise((resolve, reject) => {
                        this.forceReLogin(async (user) => {
                            headers['Authorization'] = `Bearer ${this.getToken()}`;
                            try {
                                const result = await this.streamRequestRaw(url, { ...options, headers }, onChunk);
                                resolve(result);
                            } catch (e) {
                                reject(e);
                            }
                        });
                    });
                }
            }

            return this.handleStreamResponseRaw(response, onChunk);
        } catch (error) {
            console.error('流式请求失败:', error);
            throw error;
        }
    },

    // 处理流式响应 - 等待全部返回后一次性返回
    async handleStreamResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === 'chunk') {
                            fullContent += data.content || '';
                        } else if (data.type === 'complete') {
                            // do nothing - fullContent already has all chunks
                        } else if (data.type === 'error') {
                            throw new Error(data.message || '请求失败');
                        }
                    } catch (e) {
                        console.warn('Failed to parse stream data:', e);
                    }
                }
            }
        }

        return fullContent;
    },

    // 处理流式响应 - 中转模式
    async handleStreamResponseRaw(response, onChunk) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (onChunk && typeof onChunk === 'function') {
                            onChunk(data);
                        }
                    } catch (e) {
                        console.warn('Failed to parse stream data:', e);
                    }
                }
            }
        }

        return { success: true };
    },

    // 处理响应（改进版）
    async handleResponse(response) {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            const data = await response.json();

            // 检查业务错误 - 对于 401，先再次尝试刷新 token
            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (!refreshed) {
                    // 保存当前状态并显示登录弹窗
                    this.savePendingData('page_state', {
                        path: window.location.pathname,
                        search: window.location.search
                    });
                }
            }

            return data;
        }
        return response;
    },

    // 刷新 token
    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
            return false;
        }

        try {
            const response = await fetch('/api/auth/refresh/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh: refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access);
                return true;
            } else if (response.status === 401) {
                // refresh token 也失效了
                return false;
            }
        } catch (error) {
            console.error('刷新 token 失败:', error);
        }

        return false;
    },

    // GET 请求
    get: function(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    },

    // POST 请求
    post: function(url, body, options = {}) {
        return this.request(url, {
            ...options,
            method: 'POST',
            body: typeof body === 'string' ? body : JSON.stringify(body)
        });
    },

    // PUT 请求
    put: function(url, body, options = {}) {
        return this.request(url, {
            ...options,
            method: 'PUT',
            body: typeof body === 'string' ? body : JSON.stringify(body)
        });
    },

    // DELETE 请求
    delete: function(url, options = {}) {
        return this.request(url, {
            ...options,
            method: 'DELETE'
        });
    }
};

// 便捷方法
api.getJSON = function(url) {
    return api.get(url, { contentType: 'application/json' });
};

api.postJSON = function(url, body) {
    return api.post(url, body, { contentType: 'application/json' });
};

api.postForm = function(url, body) {
    return api.post(url, body, { contentType: 'application/x-www-form-urlencoded' });
};

// 页面加载时检查登录状态（改进版）
(async function() {
    const publicPages = ['/login.html', '/register.html', '/reset-password.html'];
    const currentPath = window.location.pathname;

    // 公开页面不需要检查
    if (publicPages.includes(currentPath)) {
        // 如果在登录页，且本地有 token，尝试直接跳转
        if (currentPath === '/login.html' && api.isAuthenticated()) {
            try {
                // 验证 token 是否有效
                const data = await api.get('/api/auth/user/');
                if (data.success) {
                    // token 有效，跳转到 index.html 或 next 参数
                    const params = new URLSearchParams(window.location.search);
                    let nextUrl = params.get('next') || '/index.html';
                    // 只在 next 不是登录页时才跳转，避免循环重定向
                    if (nextUrl && !nextUrl.includes('/login')) {
                        window.location.href = nextUrl;
                    }
                }
            } catch (e) {
                // token 无效，留在登录页
                console.log('Token 验证失败，留在登录页');
            }
        }
        return;
    }

    // 检查是否是 index.html
    const isIndex = api.isIndexPage();

    // 没有 token 时的处理
    if (!api.isAuthenticated()) {
        if (isIndex) {
            // index.html 没有 token，重定向到登录页
            window.location.href = '/login.html?next=' + encodeURIComponent(currentPath + window.location.search);
            return;
        }
        // 其他页面没有 token，在第一次 API 请求时处理
    }

    // 有 token 的情况下，index.html 和其他页面统一通过 API 请求时的 401 来处理
})();
