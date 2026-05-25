from django.contrib import admin
from .models import WorldViewChatHistory


# @admin.register(World)
# class WorldAdmin(admin.ModelAdmin):
#     list_display = ['id', 'name', 'project', 'version', 'created_at', 'updated_at']
#     list_filter = ['project', 'created_at']
#     search_fields = ['name', 'description']


# @admin.register(WorldViewChatHistory)
# class WorldViewChatHistoryAdmin(admin.ModelAdmin):
#     list_display = ['id', 'worldview', 'role', 'created_at']
#     list_filter = ['worldview', 'role', 'created_at']
#     search_fields = ['content']
