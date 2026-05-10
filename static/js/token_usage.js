document.addEventListener('DOMContentLoaded', function() {
    loadUserInfo();
    loadStats('today');
});

async function loadUserInfo() {
    try {
        const response = await fetch('/api/auth/user/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            document.getElementById('username').textContent = data.user.username;
        }
    } catch (error) {
        window.location.href = 'login.html';
    }
    
    try {
        const response = await fetch('/api/token-usage/today/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            const total = data.usage.total_tokens || 0;
            const formatted = total >= 1000 ? (total / 1000).toFixed(1) + 'k' : total;
            document.getElementById('token-usage').textContent = '今日 Token: ' + formatted;
        }
    } catch (error) {
        console.error('Failed to load token usage:', error);
    }
}

async function loadStats(range, btnElement) {
    if (btnElement) {
        document.querySelectorAll('.btn-outline-primary').forEach(el => el.classList.remove('active'));
        btnElement.classList.add('active');
    }

    const statsContainer = document.querySelector('.stat-cards-container');
    const tableContainer = document.querySelector('.table-container');
    const chartContainer = document.querySelector('.chart-container');
    
    if (statsContainer) statsContainer.classList.add('refreshing');
    if (tableContainer) tableContainer.classList.add('refreshing');
    if (chartContainer) chartContainer.classList.add('refreshing');

    try {
        const response = await fetch(`/api/token-usage/stats/?range=${range}`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            const usage = data.usage;
            const currentUsage = usage[range] || usage.all;
            
            document.getElementById('stat-total').textContent = formatNumber(currentUsage.total_tokens);
            document.getElementById('stat-hit').textContent = formatNumber(currentUsage.prompt_hit);
            document.getElementById('stat-miss').textContent = formatNumber(currentUsage.prompt_miss);
            document.getElementById('stat-output').textContent = formatNumber(currentUsage.completion_tokens);
            
            renderUsageChart(usage[range] || usage.all);
            renderLogsTable(data.usage.logs || []);
            renderProjectStats(data.usage.project_stats || []);
            
            setTimeout(() => {
                if (statsContainer) statsContainer.classList.remove('refreshing');
                if (tableContainer) tableContainer.classList.remove('refreshing');
                if (chartContainer) chartContainer.classList.remove('refreshing');
            }, 300);
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
        if (statsContainer) statsContainer.classList.remove('refreshing');
        if (tableContainer) tableContainer.classList.remove('refreshing');
        if (chartContainer) chartContainer.classList.remove('refreshing');
    }
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num || 0;
}

function renderUsageChart(usage) {
    const canvas = document.getElementById('usageChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    if (window.usageChartInstance) {
        window.usageChartInstance.destroy();
    }
    
    window.usageChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Cache Hit (Prompt)', 'Cache Miss (Prompt)', 'Completion'],
            datasets: [{
                data: [usage.prompt_hit || 0, usage.prompt_miss || 0, usage.completion_tokens || 0],
                backgroundColor: ['#22c55e', '#f59e0b', '#0ea5e9'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logs-table-body');
    if (!tbody) return;
    
    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = logs.map(log => `
        <tr>
            <td>${log.created_at || '-'}</td>
            <td>${log.project || '-'}</td>
            <td>${getTaskTypeText(log.task_type)}</td>
            <td>${formatNumber(log.total_tokens)}</td>
            <td>${log.cache_hit ? '<span class="badge badge-success">Cache Hit</span>' : '<span class="badge badge-warning">Cache Miss</span>'}</td>
        </tr>
    `).join('');
}

function renderProjectStats(stats) {
    const container = document.getElementById('project-stats');
    if (!container) return;
    
    if (stats.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">暂无数据</div>';
        return;
    }
    
    container.innerHTML = stats.map(stat => `
        <div class="project-stat-card">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0">${stat.project_title}</h6>
                <span class="badge badge-info">${formatNumber(stat.total_tokens)} tokens</span>
            </div>
            <div class="progress" style="height: 6px;">
                <div class="progress-bar" style="width: ${Math.min((stat.total_tokens / (stats[0].total_tokens || 1)) * 100, 100)}%"></div>
            </div>
            <div class="d-flex justify-content-between mt-2 small text-muted">
                <span>Cache Hit: ${stat.cache_hits || 0}</span>
                <span>Cache Miss: ${stat.cache_misses || 0}</span>
            </div>
        </div>
    `).join('');
}

function getTaskTypeText(taskType) {
    const texts = {
        'outline': '大纲生成',
        'volume': '卷结构生成',
        'chapter': '章节概要生成',
        'content': '章节内容生成',
        'other': '其他任务'
    };
    return texts[taskType] || taskType;
}

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