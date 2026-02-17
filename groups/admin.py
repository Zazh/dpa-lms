from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.contrib import messages
from .models import Group, GroupMembership, GroupInstructor


class GroupMembershipInline(admin.TabularInline):
    """Inline для студентов группы"""
    model = GroupMembership
    extra = 0
    fields = ['user', 'is_active', 'enrolled_via_referral', 'personal_deadline_at', 'joined_at']
    readonly_fields = ['joined_at', 'enrolled_via_referral', 'personal_deadline_at']
    autocomplete_fields = ['user']
    ordering = ['-is_active', '-joined_at']


class GroupInstructorInline(admin.TabularInline):
    """Inline для инструкторов группы"""
    model = GroupInstructor
    extra = 0
    fields = ['instructor', 'is_active', 'can_grade', 'can_view_progress', 'assigned_at']
    readonly_fields = ['assigned_at']
    ordering = ['-is_active', '-assigned_at']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Показывать только staff пользователей"""
        if db_field.name == "instructor":
            kwargs["queryset"] = kwargs.get("queryset", db_field.related_model.objects).filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'group_type_badges', 'deadline_display', 'status_badge', 'students_info',
                    'instructors_count', 'created_at']
    list_filter = ['is_default', 'deadline_type', 'is_paid', 'is_active', 'course', 'created_at', 'final_exam_date']
    search_fields = ['name', 'description', 'course__title']
    readonly_fields = ['referral_token', 'referral_link_display', 'created_at', 'updated_at', 'students_count',
                       'instructors_count', 'available_slots_display']

    fieldsets = (
        ('Основная информация', {
            'fields': ('course', 'name', 'description')
        }),
        ('Тип группы', {
            'fields': ('is_default', 'is_paid')
        }),
        ('Дедлайн', {
            'fields': ('deadline_type', 'deadline_days', 'deadline_date'),
            'description': 'Для B2C (дефолтных) групп: deadline_days. Для B2B: deadline_date'
        }),
        ('Итоговый тест (для бесплатных групп)', {
            'fields': ('final_exam_date', 'final_exam_start_time', 'final_exam_end_time'),
            'classes': ('collapse',),
            'description': 'Расписание итогового теста. Применяется только если группа НЕ платная (is_paid=False).'
        }),
        ('Ограничения', {
            'fields': ('max_students', 'available_slots_display', 'is_active')
        }),
        ('Реферальная ссылка', {
            'fields': ('referral_token', 'referral_link_display'),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('students_count', 'instructors_count'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [GroupInstructorInline, GroupMembershipInline]
    actions = ['activate_groups', 'deactivate_groups', 'set_as_default', 'run_deactivate_expired']

    def group_type_badges(self, obj):
        badges = []
        if obj.is_default:
            badges.append(
                '<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px; margin-right: 3px;">⭐ ДЕФОЛТ</span>')
        if obj.is_paid:
            badges.append(
                '<span style="background-color: #ffc107; color: white; padding: 3px 8px; border-radius: 3px;">💰 ПЛАТНАЯ</span>')
        else:
            badges.append(
                '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px;">🎁 БЕСПЛАТНАЯ</span>')
        return format_html(''.join(badges))

    group_type_badges.short_description = 'Тип'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Активна</span>')
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">❌ Неактивна</span>')

    status_badge.short_description = 'Статус'

    def students_info(self, obj):
        count = obj.get_students_count()
        if obj.max_students > 0:
            filled_percent = (count / obj.max_students) * 100
            color = '#28a745' if filled_percent < 80 else '#ffc107' if filled_percent < 100 else '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">👥 {}/{}</span>',
                color, count, obj.max_students
            )
        return f'👥 {count}'

    students_info.short_description = 'Студенты'

    def deadline_display(self, obj):
        return obj.get_deadline_display()

    deadline_display.short_description = 'Дедлайн'

    def run_deactivate_expired(self, request, queryset):
        """Деактивировать истекшие членства"""
        count = Group.deactivate_expired_memberships()
        self.message_user(request, f'⏰ Деактивировано студентов: {count}')
    run_deactivate_expired.short_description = '⏰ Деактивировать истекшие дедлайны'

    def deadline_info(self, obj):
        if obj.deadline_days == 0:
            return '∞ Бессрочно'
        return f'📅 {obj.deadline_days} дн.'

    deadline_info.short_description = 'Дедлайн'

    def instructors_count(self, obj):
        return f'👨‍🏫 {obj.get_instructors_count()}'

    instructors_count.short_description = 'Инструкторы'

    def students_count(self, obj):
        return f'👥 {obj.get_students_count()}'

    students_count.short_description = 'Студентов в группе'

    def available_slots_display(self, obj):
        slots = obj.get_available_slots()
        if slots == '∞':
            return '∞ Без ограничения'
        return f'{slots} мест свободно'

    available_slots_display.short_description = 'Свободные места'

    def referral_link_display(self, obj):
        if obj.pk:
            link = obj.get_referral_link()
            return format_html(
                '<a href="{}" target="_blank" style="font-weight: bold;">{}</a><br>'
                '<small style="color: #6c757d;">Отправьте эту ссылку студентам для автоматического зачисления</small>',
                link, link
            )
        return '-'

    referral_link_display.short_description = 'Реферальная ссылка'

    def activate_groups(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Активировано групп: {updated}')

    activate_groups.short_description = '✅ Активировать группы'

    def deactivate_groups(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ Деактивировано групп: {updated}')

    deactivate_groups.short_description = '❌ Деактивировать группы'

    def set_as_default(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '❌ Выберите только одну группу', level=messages.ERROR)
            return

        group = queryset.first()
        # Снять флаг дефолтности со всех групп курса
        Group.objects.filter(course=group.course, is_default=True).update(is_default=False)
        # Установить для выбранной
        group.is_default = True
        group.save()

        self.message_user(request, f'⭐ Группа "{group.name}" установлена как дефолтная')

    set_as_default.short_description = '⭐ Сделать дефолтной'


    def deactivate_expired(self, request, queryset):
        """Деактивировать студентов с истекшим дедлайном"""
        total_deactivated = 0
        for group in queryset:
            deactivated = group.check_and_deactivate_expired()
            total_deactivated += deactivated

        self.message_user(request, f'⏰ Деактивировано студентов: {total_deactivated}')

    deactivate_expired.short_description = '⏰ Деактивировать с истекшим дедлайном'


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['user_info', 'group', 'status_badge', 'referral_badge', 'deadline_status', 'joined_at',
                    'duration_display']
    list_filter = ['is_active', 'enrolled_via_referral', 'group__course', 'joined_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'group__name']
    autocomplete_fields = ['user', 'group']
    readonly_fields = ['joined_at', 'left_at', 'duration_days', 'days_until_deadline_display']
    date_hierarchy = 'joined_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'user', 'is_active', 'enrolled_via_referral')
        }),
        ('Дедлайн', {
            'fields': ('personal_deadline_at', 'days_until_deadline_display')
        }),
        ('Даты', {
            'fields': ('joined_at', 'left_at', 'duration_days')
        }),
    )

    actions = ['activate_memberships', 'deactivate_memberships']

    def user_info(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.email})"

    user_info.short_description = 'Студент'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Активен</span>')
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">❌ Неактивен</span>')

    status_badge.short_description = 'Статус'

    def referral_badge(self, obj):
        if obj.enrolled_via_referral:
            return '🔗 Реферал'
        return '-'

    referral_badge.short_description = 'Источник'

    def deadline_status(self, obj):
        days_left = obj.get_days_until_deadline()
        if days_left is None:
            return '∞ Бессрочно'
        if days_left == 0:
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠️ Истек</span>')
        if days_left <= 3:
            return format_html('<span style="color: #dc3545;">⏰ {} дн.</span>', days_left)
        if days_left <= 7:
            return format_html('<span style="color: #ffc107;">📅 {} дн.</span>', days_left)
        return f'📅 {days_left} дн.'

    deadline_status.short_description = 'Дедлайн'

    def duration_display(self, obj):
        days = obj.get_duration_days()
        if days == 0:
            return '< 1 дня'
        return f'📅 {days} дн.'

    duration_display.short_description = 'Длительность'

    def duration_days(self, obj):
        return f'{obj.get_duration_days()} дней'

    duration_days.short_description = 'Длительность (дни)'

    def days_until_deadline_display(self, obj):
        days_left = obj.get_days_until_deadline()
        if days_left is None:
            return '∞ Бессрочно'
        if days_left == 0:
            return '⚠️ Истек'
        return f'{days_left} дней'

    days_until_deadline_display.short_description = 'До дедлайна'

    def activate_memberships(self, request, queryset):
        updated = queryset.update(is_active=True, left_at=None)
        self.message_user(request, f'✅ Активировано: {updated}')

    activate_memberships.short_description = '✅ Активировать членства'

    def deactivate_memberships(self, request, queryset):
        from django.utils import timezone
        count = 0
        for membership in queryset.filter(is_active=True):
            membership.is_active = False
            membership.left_at = timezone.now()
            membership.save()
            count += 1
        self.message_user(request, f'❌ Деактивировано: {count}')

    deactivate_memberships.short_description = '❌ Деактивировать членства'


@admin.register(GroupInstructor)
class GroupInstructorAdmin(admin.ModelAdmin):
    list_display = ['instructor_info', 'group', 'status_badge', 'permissions_display', 'assigned_at']
    list_filter = ['is_active', 'can_grade', 'can_view_progress', 'group__course', 'assigned_at']
    search_fields = ['instructor__email', 'instructor__first_name', 'instructor__last_name', 'group__name']
    readonly_fields = ['assigned_at']
    date_hierarchy = 'assigned_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'instructor', 'is_active')
        }),
        ('Права доступа', {
            'fields': ('can_grade', 'can_view_progress')
        }),
        ('Системная информация', {
            'fields': ('assigned_at',)
        }),
    )

    actions = ['activate_instructors', 'deactivate_instructors', 'grant_all_permissions']

    def instructor_info(self, obj):
        return f"👨‍🏫 {obj.instructor.get_full_name()} ({obj.instructor.email})"

    instructor_info.short_description = 'Инструктор'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✅ Активен</span>')
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">❌ Неактивен</span>')

    status_badge.short_description = 'Статус'

    def permissions_display(self, obj):
        return obj.get_permissions_display()

    permissions_display.short_description = 'Права'

    def activate_instructors(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Активировано: {updated}')

    activate_instructors.short_description = '✅ Активировать инструкторов'

    def deactivate_instructors(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ Деактивировано: {updated}')

    deactivate_instructors.short_description = '❌ Деактивировать инструкторов'

    def grant_all_permissions(self, request, queryset):
        updated = queryset.update(can_grade=True, can_view_progress=True)
        self.message_user(request, f'🔓 Выданы все права: {updated}')

    grant_all_permissions.short_description = '🔓 Выдать все права'