from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.contrib import messages
from django.utils import timezone
from .models import Graduate


@admin.register(Graduate)
class GraduateAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_info',
        'course',
        'group',
        'status_badge',
        'final_score_badge',
        'average_quiz_score_display',
        'total_lessons_completed',
        'completed_at_display',
        'graduated_at_display',
        'certificate_info',
    ]

    list_filter = [
        'status',
        'course',
        'group',
        'completed_at',
        'graduated_at',
    ]

    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'user__iin',
        'user__phone',
        'certificate__number',
    ]

    readonly_fields = [
        'user',
        'course',
        'group',
        'completed_at',
        'total_lessons_completed',
        'average_quiz_score',
        'total_study_days',
        'completion_details_display',
        'quiz_attempts_display',
        'instructor_display',
        'student_full_info',
        'certificate_display',
    ]

    fieldsets = (
        ('📊 Информация о студенте', {
            'fields': ('student_full_info',)
        }),
        ('📚 Обучение', {
            'fields': (
                'course',
                'group',
                'instructor_display',
                'completed_at',
                'total_study_days',
            )
        }),
        ('📈 Результаты', {
            'fields': (
                'total_lessons_completed',
                'average_quiz_score',
                'final_score',
            )
        }),
        ('🎯 Результаты тестов', {
            'fields': ('quiz_attempts_display',),
            'classes': ('collapse',)
        }),
        ('📝 Детали прохождения', {
            'fields': ('completion_details_display',),
            'classes': ('collapse',)
        }),
        ('🎓 Статус выпуска', {
            'fields': (
                'status',
                'graduated_at',
                'graduated_by',
            )
        }),
        ('📜 Сертификат', {
            'fields': ('certificate_display',)
        }),
        ('📝 Примечания', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    actions = [
        'approve_graduation_action',
        'reject_graduation_action',
    ]

    date_hierarchy = 'completed_at'

    # === DISPLAY МЕТОДЫ ===

    def user_info(self, obj):
        """Компактная информация о пользователе"""
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color: #666;">ИИН: {}</small><br>'
            '<small style="color: #666;">{}</small>',
            obj.user.get_full_name(),
            obj.user.iin,
            obj.user.email
        )

    user_info.short_description = 'Студент'

    def student_full_info(self, obj):
        """Полная информация о студенте"""
        phone = obj.user.phone or 'не указан'
        return format_html(
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr><td style="padding: 5px;"><strong>ID выпускника:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>ФИО:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>ИИН:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>Email:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>Телефон:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>User ID:</strong></td><td style="padding: 5px;">{}</td></tr>'
            '</table>',
            obj.id,
            obj.user.get_full_name(),
            obj.user.iin,
            obj.user.email,
            phone,
            obj.user.id
        )

    student_full_info.short_description = 'Данные студента'

    def status_badge(self, obj):
        """Статус с красивым бейджем"""
        colors = {
            'pending': '#ffc107',
            'graduated': '#28a745',
            'rejected': '#dc3545',
        }
        icons = {
            'pending': '⏳',
            'graduated': '🎓',
            'rejected': '❌',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 12px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            colors.get(obj.status, '#6c757d'),
            icons.get(obj.status, '❓'),
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def final_score_badge(self, obj):
        """Итоговая оценка с цветом"""
        score = float(obj.final_score)
        if score >= 90:
            color = '#28a745'
            icon = '🏆'
        elif score >= 80:
            color = '#17a2b8'
            icon = '⭐'
        elif score >= 70:
            color = '#ffc107'
            icon = '✅'
        else:
            color = '#6c757d'
            icon = '📝'

        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{} {}%</span>',
            color, icon, int(score)
        )

    final_score_badge.short_description = 'Итоговая оценка'

    def average_quiz_score_display(self, obj):
        """Средний балл за тесты"""
        score = float(obj.average_quiz_score)
        return f'{score:.1f}%'

    average_quiz_score_display.short_description = 'Средний балл (тесты)'

    def completed_at_display(self, obj):
        """Дата завершения обучения"""
        if obj.completed_at:
            return obj.completed_at.strftime('%d.%m.%Y %H:%M')
        return '-'

    completed_at_display.short_description = 'Завершил обучение'

    def graduated_at_display(self, obj):
        """Дата выпуска"""
        if obj.graduated_at:
            return obj.graduated_at.strftime('%d.%m.%Y %H:%M')
        return '-'

    graduated_at_display.short_description = 'Выпущен'

    def instructor_display(self, obj):
        """Инструктор группы"""
        instructor = obj.get_instructor()
        if instructor:
            return format_html(
                '👨‍🏫 <strong>{}</strong><br><small>{}</small>',
                instructor.get_full_name(),
                instructor.email
            )
        return format_html('<span style="color: #999;">Инструктор не назначен</span>')

    instructor_display.short_description = 'Инструктор группы'

    def certificate_info(self, obj):
        """Информация о сертификате в списке"""
        if hasattr(obj, 'certificate') and obj.certificate:
            cert = obj.certificate
            if cert.status == 'ready':
                return format_html(
                    '<span style="color: #28a745;">✅ {}</span>',
                    cert.number
                )
            elif cert.status == 'pending':
                return format_html('<span style="color: #ffc107;">⏳ Генерируется</span>')
            else:
                return format_html('<span style="color: #dc3545;">❌ Ошибка</span>')
        return format_html('<span style="color: #999;">—</span>')

    certificate_info.short_description = 'Сертификат'

    def certificate_display(self, obj):
        """Детальная информация о сертификате"""
        if hasattr(obj, 'certificate') and obj.certificate:
            cert = obj.certificate
            status_colors = {
                'ready': '#28a745',
                'pending': '#ffc107',
                'error': '#dc3545',
            }
            status_icons = {
                'ready': '✅',
                'pending': '⏳',
                'error': '❌',
            }

            html = f'''
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 5px;"><strong>Номер:</strong></td>
                    <td style="padding: 5px;">{cert.number}</td>
                </tr>
                <tr>
                    <td style="padding: 5px;"><strong>Статус:</strong></td>
                    <td style="padding: 5px;">
                        <span style="color: {status_colors.get(cert.status, '#999')};">
                            {status_icons.get(cert.status, '❓')} {cert.get_status_display()}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 5px;"><strong>Дата выдачи:</strong></td>
                    <td style="padding: 5px;">{cert.issued_at.strftime('%d.%m.%Y') if cert.issued_at else '—'}</td>
                </tr>
            '''

            if cert.status == 'ready':
                if cert.file_without_stamp:
                    html += f'''
                    <tr>
                        <td style="padding: 5px;"><strong>Без печати:</strong></td>
                        <td style="padding: 5px;"><a href="{cert.file_without_stamp.url}" target="_blank">📄 Скачать</a></td>
                    </tr>
                    '''
                if cert.file_with_stamp:
                    html += f'''
                    <tr>
                        <td style="padding: 5px;"><strong>С печатью:</strong></td>
                        <td style="padding: 5px;"><a href="{cert.file_with_stamp.url}" target="_blank">🎓 Скачать</a></td>
                    </tr>
                    '''

            if cert.status == 'error' and cert.error_message:
                html += f'''
                <tr>
                    <td style="padding: 5px;"><strong>Ошибка:</strong></td>
                    <td style="padding: 5px; color: #dc3545;">{cert.error_message}</td>
                </tr>
                '''

            html += '</table>'
            return format_html(html)

        return format_html('<span style="color: #999;">Сертификат не создан</span>')

    certificate_display.short_description = 'Сертификат'

    def quiz_attempts_display(self, obj):
        """Отображение попыток тестов"""
        attempts = obj.get_quiz_attempts_summary()

        if not attempts:
            return format_html('<p style="color: #999;">Тестов не было</p>')

        html = '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">'
        html += '<tr style="background-color: #f8f9fa;">'
        html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Тест</th>'
        html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Попытка</th>'
        html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Балл</th>'
        html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Статус</th>'
        html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Дата</th>'
        html += '</tr>'

        for attempt in attempts:
            passed_icon = '✅' if attempt['passed'] else '❌'
            score_color = '#28a745' if attempt['passed'] else '#dc3545'

            html += '<tr>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd;">{attempt["lesson"]}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">#{attempt["attempt_number"]}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; text-align: center; color: {score_color}; font-weight: bold;">{attempt["score"]:.1f}%</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{passed_icon}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><small>{attempt["date"]}</small></td>'
            html += '</tr>'

        html += '</table>'
        return format_html(html)

    quiz_attempts_display.short_description = 'Результаты тестов'

    def completion_details_display(self, obj):
        """Отображение деталей прохождения"""
        details = obj.completion_details

        if not details:
            return format_html('<p style="color: #999;">Детали недоступны</p>')

        html = '<div style="font-family: monospace; font-size: 12px;">'

        # Модули
        if details.get('modules'):
            html += '<h4 style="margin: 10px 0;">📦 Модули:</h4>'
            html += '<ul style="margin: 5px 0; padding-left: 20px;">'
            for module in details['modules']:
                html += f'<li><strong>{module["title"]}</strong> - {module["completed_at"]}</li>'
            html += '</ul>'

        # Уроки
        if details.get('lessons'):
            html += '<h4 style="margin: 10px 0;">📚 Уроки:</h4>'
            html += '<ul style="margin: 5px 0; padding-left: 20px;">'
            for lesson in details['lessons']:
                html += f'<li><strong>[{lesson["type"]}]</strong> {lesson["title"]} - {lesson["completed_at"]}</li>'
            html += '</ul>'

        html += '</div>'
        return format_html(html)

    completion_details_display.short_description = 'Детали прохождения'

    # === ACTIONS ===

    def approve_graduation_action(self, request, queryset):
        """Подтвердить выпуск"""
        pending = queryset.filter(status='pending')

        if not pending.exists():
            self.message_user(
                request,
                '❌ Нет студентов со статусом "Ожидает выпуска"',
                level=messages.ERROR
            )
            return

        count = 0
        for graduate in pending:
            if graduate.approve_graduation(request.user):
                count += 1

        self.message_user(
            request,
            f'🎓 Выпущено студентов: {count}. Сертификаты генерируются в фоне...',
            level=messages.SUCCESS
        )

    approve_graduation_action.short_description = '🎓 Подтвердить выпуск'

    def reject_graduation_action(self, request, queryset):
        """Отклонить выпуск"""
        pending = queryset.filter(status='pending')

        if not pending.exists():
            self.message_user(
                request,
                '❌ Нет студентов со статусом "Ожидает выпуска"',
                level=messages.ERROR
            )
            return

        count = 0
        for graduate in pending:
            if graduate.reject_graduation(request.user):
                count += 1

        self.message_user(
            request,
            f'❌ Отклонено кандидатов: {count}',
            level=messages.WARNING
        )

    reject_graduation_action.short_description = '❌ Отклонить выпуск'

    # === НАСТРОЙКИ ===

    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'user',
            'course',
            'group',
            'graduated_by',
            'certificate'
        )

    def has_add_permission(self, request):
        """Запретить создание вручную"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Удаление только для суперюзера"""
        return request.user.is_superuser