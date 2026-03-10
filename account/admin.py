from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserActivityLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'iin', 'first_name', 'last_name', 'role', 'registration_method', 'is_verified', 'is_active',
                    'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_verified', 'role', 'registration_method', 'date_joined')
    search_fields = ('email', 'iin', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'middle_name', 'iin', 'phone')}),
        ('Роль и доступ', {
            'fields': ('role', 'registration_method', 'assigned_groups')
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions')
        }),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'iin', 'first_name', 'last_name', 'password1', 'password2', 'role'),  # ← добавили role
        }),
    )

    # ← ДОБАВИТЬ: Для удобного управления ManyToMany полем
    filter_horizontal = ('assigned_groups', 'groups', 'user_permissions')


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'get_user_display', 'attempted_email', 'ip_address', 'short_user_agent')
    list_filter = ('action', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'attempted_email', 'ip_address')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'attempted_email', 'lesson', 'quiz_attempt', 'created_at')
    list_per_page = 50

    def get_user_display(self, obj):
        return obj.user.get_full_name() if obj.user else '—'
    get_user_display.short_description = 'Пользователь'

    def short_user_agent(self, obj):
        return obj.user_agent[:80] + '…' if len(obj.user_agent) > 80 else obj.user_agent
    short_user_agent.short_description = 'Браузер'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False