from django.contrib import admin
from django.urls import path, include
from django.views.static import serve
from django.conf import settings
from apps.core.views import LoginView, RegisterView, ChapterGeneratorView
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    
    path('api/', include('apps.outline.urls')),
    path('api/', include('apps.volume.urls')),
    path('api/', include('apps.chapter.urls')),
    
    path('api/', include('apps.ai.urls')),
    path('api/ai/', include('apps.ai.urls')),
    
    path('login.html', LoginView.as_view(), name='login_html'),
    path('register.html', RegisterView.as_view(), name='register_html'),
    path('chapter_generator.html', ChapterGeneratorView.as_view(), name='chapter_generator_html'),
]

frontend_files = ['index.html', 'project.html', 'outline_builder.html', 'token_usage.html', 'llm_config.html', 'volume_generator.html', 'content_manager.html']
for file_name in frontend_files:
    urlpatterns.append(
        path(file_name, serve, {
            'document_root': os.path.join(settings.BASE_DIR, 'templates'),
            'path': file_name,
        })
    )
