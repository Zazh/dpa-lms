from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'iin', 'first_name', 'last_name', 'role', 'is_verified', 'is_active',
                    'date_joined')  # ← добавили role
    list_filter = ('is_active', 'is_staff', 'is_verified', 'role', 'date_joined')  # ← добавили role
    search_fields = ('email', 'iin', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'middle_name', 'iin', 'phone')}),
        ('Роль и доступ', {  # ← НОВАЯ СЕКЦИЯ
            'fields': ('role', 'assigned_groups')
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