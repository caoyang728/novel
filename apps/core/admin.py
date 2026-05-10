from django.contrib import admin
from .models import Project, OutlineMessage, Volume, Chapter, OutlineVersion, VolumeVersion, ChapterVersion

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_at', 'updated_at']
    search_fields = ['title']

@admin.register(OutlineVersion)
class OutlineVersionAdmin(admin.ModelAdmin):
    list_display = ['project', 'version_number', 'is_finalized', 'created_at']
    list_filter = ['project', 'is_finalized']

@admin.register(OutlineMessage)
class OutlineMessageAdmin(admin.ModelAdmin):
    list_display = ['outline_version', 'role', 'created_at']
    list_filter = ['role']

@admin.register(VolumeVersion)
class VolumeVersionAdmin(admin.ModelAdmin):
    list_display = ['project', 'outline_version', 'version_number', 'is_finalized', 'created_at']
    list_filter = ['project', 'is_finalized']

@admin.register(Volume)
class VolumeAdmin(admin.ModelAdmin):
    list_display = ['volume_version', 'volume_number', 'title']
    list_filter = ['volume_version']

@admin.register(ChapterVersion)
class ChapterVersionAdmin(admin.ModelAdmin):
    list_display = ['volume', 'version_number', 'is_finalized', 'created_at']
    list_filter = ['is_finalized']

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['chapter_version', 'chapter_number', 'title']
    list_filter = ['chapter_version']
