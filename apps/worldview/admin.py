from django.contrib import admin
from .models import WorldView, WorldViewChatHistory


@admin.register(WorldView)
class WorldViewAdmin(admin.ModelAdmin):
    list_display = ('project', 'version', 'is_finalized', 'is_deleted', 'created_at', 'updated_at')
    list_filter = ('is_finalized', 'is_deleted')
    search_fields = ('project__name',)
    raw_id_fields = ('project',)


@admin.register(WorldViewChatHistory)
class WorldViewChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('worldview', 'role', 'created_at')
    list_filter = ('role',)
    raw_id_fields = ('worldview',)
