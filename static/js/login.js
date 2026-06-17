document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const loginBtn = document.getElementById('login-btn');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        loginBtn.disabled = true;
        loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
        errorMessage.classList.add('d-none');

        try {
            const data = await api.post('/login/', { username, password });
            
            if (data.success) {
                // 保存 token 到 localStorage
                localStorage.setItem('access_token', data.access);
                localStorage.setItem('refresh_token', data.refresh);
                localStorage.setItem('user', JSON.stringify(data.user));
                
                // 检查是否有 next 参数
                const params = new URLSearchParams(window.location.search);
                const nextUrl = params.get('next');
                if (nextUrl) {
                    window.location.href = decodeURIComponent(nextUrl);
                } else {
                    window.location.href = '/';
                }
            } else {
                errorText.textContent = data.message || '登录失败';
                errorMessage.classList.remove('d-none');
            }
        } catch (error) {
            errorText.textContent = '网络错误，请重试';
            errorMessage.classList.remove('d-none');
        } finally {
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt me-2"></i>登录';
        }
    });
});