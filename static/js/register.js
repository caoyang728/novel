document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('register-form');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const successMessage = document.getElementById('success-message');
    const successText = document.getElementById('success-text');
    const registerBtn = document.getElementById('register-btn');
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const passwordConfirm = document.getElementById('password_confirm').value;
        
        if (password !== passwordConfirm) {
            errorText.textContent = '两次输入的密码不一致';
            errorMessage.classList.remove('d-none');
            return;
        }
        
        registerBtn.disabled = true;
        registerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 注册中...';
        errorMessage.classList.add('d-none');
        successMessage.classList.add('d-none');
        
        try {
            const response = await fetch('/api/auth/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ username, email, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                successText.textContent = '注册成功，请登录';
                successMessage.classList.remove('d-none');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 2000);
            } else {
                errorText.textContent = data.message || '注册失败';
                errorMessage.classList.remove('d-none');
            }
        } catch (error) {
            errorText.textContent = '网络错误，请重试';
            errorMessage.classList.remove('d-none');
        } finally {
            registerBtn.disabled = false;
            registerBtn.innerHTML = '<i class="fas fa-user-plus me-2"></i>注册';
        }
    });
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}