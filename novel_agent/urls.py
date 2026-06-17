from django.contrib import admin
from django.urls import path, include
from django.views.static import serve
from django.conf import settings
from django.http import HttpResponse
import os

urlpatterns = [
    path('admin/', admin.site.urls),

    path('favicon.ico', lambda r: HttpResponse(b'', content_type='image/x-icon')),

    # 用户认证路由
    path('', include('apps.user.urls')),

    # 项目路由
    path('', include('apps.project.urls')),

    # 大纲路由
    path('', include('apps.outline.urls')),

    # 卷路由
    path('', include('apps.volume.urls')),

    # 章节路由
    path('', include('apps.chapter.urls')),

    # 世界观路由
    path('', include('apps.worldview.urls')),

    # 随手记路由
    path('', include('apps.note.urls')),

    # 时间线路由
    path('', include('apps.timeline.urls')),
]

# 静态页面路由
frontend_files = ['index.html', 'project.html', 'outline.html', 'token.html', 'llm_config.html', 'volume.html', 'login.html', 'worldview_chat.html', 'character.html', 'character_library.html', 'chapter.html', 'register.html', 'reset_password.html', 'worldview.html', 'note.html', 'timeline.html']
for file_name in frontend_files:
    urlpatterns.append(
        path(file_name, serve, {
            'document_root': os.path.join(settings.BASE_DIR, 'templates'),
            'path': file_name,
        })
    )
