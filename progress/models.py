from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from content.models import Course, Lesson, Module, VideoLesson
from groups.models import Group


class CourseEnrollment(models.Model):
    """Зачисление студента на курс"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Студент'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Курс'
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollments',
        verbose_name='Группа'
    )

    enrolled_at = models.DateTimeField('Дата зачисления', auto_now_add=True, db_index=True)

    progress_percentage = models.DecimalField(
        'Процент прохождения',
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    completed_lessons_count = models.PositiveIntegerField(
        'Завершено уроков',
        default=0
    )

    last_activity_at = models.DateTimeField(
        'Последняя активность',
        null=True,
        blank=True,
        db_index=True,
        help_text='False = удален из группы или дедлайн истек'
    )

    is_active = models.BooleanField('Активно', default=True, db_index=True)

    class Meta:
        verbose_name = 'Зачисление на курс'
        verbose_name_plural = 'Зачисления на курсы'
        ordering = ['-enrolled_at']
        unique_together = [['user', 'course']]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['course', 'is_active']),
            models.Index(fields=['-enrolled_at']),
        ]

    def has_access(self):
        """
        Проверка доступа к курсу.
        Доступ есть ТОЛЬКО если есть активное членство в группе.
        """
        if not self.group:
            return False

        from groups.models import GroupMembership
        return GroupMembership.objects.filter(
            user=self.user,
            group=self.group,
            is_active=True
        ).exists()

    def sync_active_status(self):
        """
        Синхронизировать is_active с состоянием GroupMembership.
        Вызывается автоматически при изменении GroupMembership.
        """
        has_access = self.has_access()

        if self.is_active != has_access:
            self.is_active = has_access
            self.save(update_fields=['is_active'])

    def __str__(self):
        status = '✅' if self.has_access() else '❌'
        group_name = self.group.name if self.group else "без группы"
        return f"{status} {self.user.get_full_name()} → {self.course.title} ({group_name})"


    def calculate_progress(self):
        """Рассчитать прогресс по курсу"""
        # Получаем все уроки курса
        total_lessons = Lesson.objects.filter(
            module__course=self.course
        ).count()

        if total_lessons == 0:
            self.progress_percentage = 0
            self.completed_lessons_count = 0
            self.save()
            return

        # Считаем завершенные уроки
        completed_lessons = LessonProgress.objects.filter(
            user=self.user,
            lesson__module__course=self.course,
            is_completed=True
        ).count()

        # Рассчитываем процент
        percentage = (completed_lessons / total_lessons) * 100

        self.progress_percentage = round(percentage, 2)
        self.completed_lessons_count = completed_lessons
        self.save()

    def get_progress_percentage(self):
        """Получить текущий прогресс"""
        return float(self.progress_percentage)

    def update_last_activity(self):
        """Обновить время последней активности"""
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])

    def get_current_lesson(self):
        """Получить текущий урок (первый незавершенный)"""
        completed_lesson_ids = LessonProgress.objects.filter(
            user=self.user,
            lesson__module__course=self.course,
            is_completed=True
        ).values_list('lesson_id', flat=True)

        # Находим первый незавершенный урок
        return Lesson.objects.filter(
            module__course=self.course
        ).exclude(
            id__in=completed_lesson_ids
        ).order_by('module__order', 'order').first()

    def get_completed_modules_count(self):
        """Количество полностью завершенных модулей"""
        modules = Module.objects.filter(course=self.course)
        completed_count = 0

        for module in modules:
            total_lessons = module.lessons.count()
            if total_lessons == 0:
                continue

            completed_lessons = LessonProgress.objects.filter(
                user=self.user,
                lesson__module=module,
                is_completed=True
            ).count()

            if completed_lessons == total_lessons:
                completed_count += 1

        return completed_count

    def check_group_access(self):
        """
        Проверить доступ через группу.
        Если группы нет или она неактивна - деактивировать зачисление.
        """
        if not self.group:
            # Нет группы = нет доступа
            if self.is_active:
                self.is_active = False
                self.save()
            return False

        # Проверяем активное членство
        from groups.models import GroupMembership
        active_membership = GroupMembership.objects.filter(
            user=self.user,
            group=self.group,
            is_active=True
        ).exists()

        if not active_membership:
            # Нет активного членства = нет доступа
            if self.is_active:
                self.is_active = False
                self.save()
            return False

        # Есть активное членство = есть доступ
        if not self.is_active:
            self.is_active = True
            self.save()
        return True


class LessonProgress(models.Model):
    """Прогресс по уроку"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
        verbose_name='Студент'
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress_records',
        verbose_name='Урок'
    )

    is_completed = models.BooleanField('Завершен', default=False, db_index=True)

    started_at = models.DateTimeField('Начало', null=True, blank=True)
    completed_at = models.DateTimeField('Завершение', null=True, blank=True, db_index=True)

    available_at = models.DateTimeField(
        'Доступен с',
        null=True,
        blank=True,
        help_text='Когда урок станет доступен (учитывается задержка)'
    )

    completion_data = models.JSONField(
        'Данные о завершении',
        default=dict,
        blank=True,
        help_text='Дополнительная информация (баллы теста, оценка задания и т.д.)'
    )

    class Meta:
        verbose_name = 'Прогресс по уроку'
        verbose_name_plural = 'Прогресс по урокам'
        ordering = ['lesson__module__order', 'lesson__order']
        unique_together = [['user', 'lesson']]
        indexes = [
            models.Index(fields=['user', 'lesson']),
            models.Index(fields=['user', 'is_completed']),
            models.Index(fields=['lesson', 'is_completed']),
        ]

    def __str__(self):
        status = '✅' if self.is_completed else '⏳'
        return f"{status} {self.user.get_full_name()} - {self.lesson.title}"

    def mark_completed(self, completion_data=None):
        """Отметить урок как завершенный"""
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()

            if completion_data:
                self.completion_data.update(completion_data)

            self.save()

            # Обновить прогресс по курсу
            try:
                enrollment = CourseEnrollment.objects.get(
                    user=self.user,
                    course=self.lesson.module.course
                )
                enrollment.calculate_progress()
                enrollment.update_last_activity()

                # Если достигнут 100% прогресс - создать выпускника
                if enrollment.progress_percentage >= 100:
                    from graduates.models import Graduate
                    graduate = Graduate.create_from_enrollment(enrollment)

                    if graduate:
                        # Удаляем из группы
                        if enrollment.group:
                            enrollment.group.remove_student(self.user)

                        # Деактивируем зачисление
                        enrollment.is_active = False
                        enrollment.save()

            except CourseEnrollment.DoesNotExist:
                pass

    def calculate_available_at(self):
        """Рассчитать время доступности урока"""
        # Если урок не требует завершения предыдущего
        if not self.lesson.requires_previous_completion:
            self.available_at = timezone.now()
            self.save()
            return

        # Получаем предыдущий урок
        previous_lesson = self.lesson.get_previous_lesson()
        if not previous_lesson:
            # Первый урок модуля - доступен сразу
            self.available_at = timezone.now()
            self.save()
            return

        # Проверяем прогресс предыдущего урока
        try:
            previous_progress = LessonProgress.objects.get(
                user=self.user,
                lesson=previous_lesson
            )

            if previous_progress.is_completed and previous_progress.completed_at:
                # Добавляем задержку если нужно
                if self.lesson.access_delay_hours > 0:
                    self.available_at = previous_progress.completed_at + timezone.timedelta(
                        hours=self.lesson.access_delay_hours
                    )
                else:
                    self.available_at = previous_progress.completed_at
                self.save()

        except LessonProgress.DoesNotExist:
            # Предыдущий урок не начат - текущий недоступен
            self.available_at = None
            self.save()

    def is_available(self):
        """Проверка доступности урока"""
        if not self.available_at:
            return False
        return timezone.now() >= self.available_at

    def get_duration_seconds(self):
        """Длительность работы над уроком"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return 0


class VideoProgress(models.Model):
    """Прогресс просмотра видео"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_progress',
        verbose_name='Студент'
    )

    video_lesson = models.ForeignKey(
        VideoLesson,
        on_delete=models.CASCADE,
        related_name='progress_records',
        verbose_name='Видео-урок'
    )

    current_position = models.PositiveIntegerField(
        'Текущая позиция (секунды)',
        default=0
    )

    watch_percentage = models.DecimalField(
        'Процент просмотра',
        max_digits=5,
        decimal_places=2,
        default=0
    )

    total_watch_time = models.PositiveIntegerField(
        'Общее время просмотра (секунды)',
        default=0,
        help_text='Суммарное время всех просмотров'
    )

    watch_count = models.PositiveIntegerField(
        'Количество просмотров',
        default=0
    )

    is_completed = models.BooleanField('Завершен', default=False, db_index=True)

    last_watched_at = models.DateTimeField('Последний просмотр', auto_now=True)

    class Meta:
        verbose_name = 'Прогресс видео'
        verbose_name_plural = 'Прогресс видео'
        unique_together = [['user', 'video_lesson']]
        indexes = [
            models.Index(fields=['user', 'video_lesson']),
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.video_lesson.lesson.title} ({self.watch_percentage}%)"

    def update_progress(self, current_position, session_watch_time=0):
        """Обновить прогресс просмотра"""
        self.current_position = current_position
        self.total_watch_time += session_watch_time
        self.watch_count += 1

        # Рассчитываем процент просмотра
        if self.video_lesson.video_duration > 0:
            self.watch_percentage = round(
                (current_position / self.video_lesson.video_duration) * 100, 2
            )

        # Проверяем завершение
        if self.watch_percentage >= self.video_lesson.completion_threshold and not self.is_completed:
            self.is_completed = True

            # Обновляем прогресс урока
            LessonProgress.objects.update_or_create(
                user=self.user,
                lesson=self.video_lesson.lesson,
                defaults={
                    'is_completed': True,
                    'completed_at': timezone.now(),
                    'completion_data': {
                        'watch_percentage': float(self.watch_percentage),
                        'total_watch_time': self.total_watch_time
                    }
                }
            )

        self.save()

    def get_remaining_time(self):
        """Оставшееся время просмотра в секундах"""
        return max(0, self.video_lesson.video_duration - self.current_position)

    def format_watch_time(self):
        """Форматированное время просмотра"""
        minutes = self.total_watch_time // 60
        seconds = self.total_watch_time % 60
        return f"{minutes}:{seconds:02d}"