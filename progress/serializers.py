from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import serializers

from content.models import Lesson, Module, VideoLesson
from .models import CourseEnrollment, LessonProgress, VideoProgress


class VideoProgressSerializer(serializers.ModelSerializer):
    """Прогресс видео"""

    class Meta:
        model = VideoProgress
        fields = ['watch_percentage', 'started_at', 'last_watched_at']


class LessonProgressSerializer(serializers.ModelSerializer):
    """Прогресс урока с доступностью"""
    lesson = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    available_at = serializers.DateTimeField(read_only=True)
    available_in = serializers.SerializerMethodField()
    video_duration = serializers.SerializerMethodField()

    class Meta:
        model = LessonProgress
        fields = [
            'id', 'lesson', 'is_completed', 'is_available', 'available_at',
            'available_in', 'started_at', 'completed_at', 'video_duration'
        ]

    def get_lesson(self, obj):
        """Получить данные урока (без дополнительных запросов)"""
        lesson = obj.lesson

        # Базовые данные урока
        data = {
            'id': lesson.id,
            'title': lesson.title,
            'description': lesson.description,
            'type': lesson.lesson_type,
            'type_display': lesson.get_lesson_type_display(),
            'order': lesson.order,
            'videolesson': None
        }

        # Если это видео-урок, берём данные из prefetch (без запроса!)
        if lesson.lesson_type == 'video':
            # Проверяем prefetch cache
            video_lessons = getattr(lesson, '_prefetched_video', None)
            if video_lessons is None:
                # Fallback: проверяем стандартный prefetch
                if hasattr(lesson, 'videolesson'):
                    try:
                        video = lesson.videolesson
                        data['videolesson'] = self._serialize_video(video)
                    except VideoLesson.DoesNotExist:
                        pass
            elif video_lessons:
                data['videolesson'] = self._serialize_video(video_lessons[0])

        return data

    def _serialize_video(self, video):
        """Сериализация видео без дополнительных запросов"""
        request = self.context.get('request')

        thumbnail_url = None
        if video.thumbnail:
            if request:
                thumbnail_url = request.build_absolute_uri(video.thumbnail.url)
            else:
                from django.conf import settings
                thumbnail_url = f"{settings.MEDIA_URL}{video.thumbnail.name}"

        # Форматируем длительность
        duration = video.video_duration or 0
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        formatted = f"{minutes}:{seconds:02d}"

        return {
            'vimeo_video_id': video.vimeo_video_id,
            'embed_url': video.get_vimeo_embed_url(),
            'video_duration': video.video_duration,
            'formatted_duration': formatted,
            'completion_threshold': video.completion_threshold,
            'thumbnail_url': thumbnail_url,
            'timecodes': video.timecodes,
        }

    def get_is_available(self, obj):
        return obj.is_available()

    def get_available_in(self, obj):
        """Человекочитаемое время до доступности"""
        if not obj.available_at:
            return None

        if obj.is_available():
            return "доступен сейчас"

        delta = obj.available_at - timezone.now()

        if delta.total_seconds() < 0:
            return "доступен сейчас"

        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)

        if hours > 0 and minutes > 0:
            return f"через {hours} ч. {minutes} мин."
        elif hours > 0:
            return f"через {hours} ч."
        else:
            return f"через {minutes} мин."

    def get_video_duration(self, obj):
        """Длительность видео (из prefetch, без запроса!)"""
        if obj.lesson.lesson_type != 'video':
            return None

        # Используем уже загруженные данные
        if hasattr(obj.lesson, 'videolesson'):
            try:
                video = obj.lesson.videolesson
                duration = video.video_duration or 0
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                return f"{minutes}:{seconds:02d}"
            except VideoLesson.DoesNotExist:
                pass

        return None


class ModuleProgressSerializer(serializers.Serializer):
    """Модуль с прогрессом уроков"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    order = serializers.IntegerField()
    lessons = LessonProgressSerializer(many=True)
    completed_lessons = serializers.IntegerField()
    total_lessons = serializers.IntegerField()
    progress_percentage = serializers.CharField()


class CourseProgressSerializer(serializers.ModelSerializer):
    """Прогресс по курсу - ОПТИМИЗИРОВАННАЯ ВЕРСИЯ"""
    course = serializers.SerializerMethodField()
    current_lesson = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    class Meta:
        model = CourseEnrollment
        fields = ['progress_percentage', 'completed_lessons_count', 'current_lesson', 'course', 'modules']

    def get_course(self, obj):
        return {
            'id': obj.course.id,
            'title': obj.course.title,
            'label': obj.course.label,
            'duration': obj.course.duration
        }

    def get_current_lesson(self, obj):
        """Текущий урок (первый незавершенный) - из кэша"""
        # Используем prefetch если есть
        lessons_progress = getattr(obj, '_prefetched_lessons_progress', None)

        if lessons_progress is not None:
            for lp in lessons_progress:
                if not lp.is_completed and lp.is_available():
                    return {
                        'id': lp.lesson.id,
                        'title': lp.lesson.title,
                        'type': lp.lesson.lesson_type
                    }
            return None

        # Fallback к стандартному методу
        lesson = obj.get_current_lesson()
        if lesson:
            return {
                'id': lesson.id,
                'title': lesson.title,
                'type': lesson.lesson_type
            }
        return None

    def get_modules(self, obj):
        """
        Модули с прогрессом уроков - ОПТИМИЗИРОВАНО!

        Было: N+1 запросов (1 + количество модулей)
        Стало: 2 запроса (модули + прогресс уроков)
        """
        # 1. Получаем все модули курса с prefetch уроков и видео
        modules = Module.objects.filter(
            course=obj.course
        ).prefetch_related(
            Prefetch(
                'lessons',
                queryset=Lesson.objects.select_related('videolesson').order_by('order')
            )
        ).order_by('order')

        # 2. ОДИН запрос для всего прогресса пользователя по курсу
        all_progress = LessonProgress.objects.filter(
            user=obj.user,
            lesson__module__course=obj.course
        ).select_related(
            'lesson',
            'lesson__videolesson'
        ).order_by('lesson__module__order', 'lesson__order')

        # 3. Группируем прогресс по module_id для быстрого доступа
        progress_by_module = {}
        for lp in all_progress:
            module_id = lp.lesson.module_id
            if module_id not in progress_by_module:
                progress_by_module[module_id] = []
            progress_by_module[module_id].append(lp)

        # Сохраняем для get_current_lesson
        obj._prefetched_lessons_progress = list(all_progress)

        # 4. Собираем результат
        result = []
        for module in modules:
            lessons_progress = progress_by_module.get(module.id, [])

            total_lessons = len(lessons_progress)
            completed_lessons = sum(1 for lp in lessons_progress if lp.is_completed)
            progress_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

            result.append({
                'id': module.id,
                'title': module.title,
                'description': module.description,
                'order': module.order,
                'lessons': LessonProgressSerializer(
                    lessons_progress,
                    many=True,
                    context=self.context
                ).data,
                'completed_lessons': completed_lessons,
                'total_lessons': total_lessons,
                'progress_percentage': f"{progress_percentage:.2f}"
            })

        return result


class MyCourseSerializer(serializers.Serializer):
    """Мой курс с прогрессом и группой"""
    course = serializers.SerializerMethodField()
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    completed_lessons = serializers.IntegerField(source='completed_lessons_count')
    total_lessons = serializers.SerializerMethodField()
    current_lesson = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    has_access = serializers.SerializerMethodField()

    def get_course(self, obj):
        return {
            'id': obj.course.id,
            'title': obj.course.title,
            'label': obj.course.label,
            'duration': obj.course.duration
        }

    def get_total_lessons(self, obj):
        # Используем аннотацию если есть
        if hasattr(obj, 'total_lessons_count'):
            return obj.total_lessons_count

        return Lesson.objects.filter(module__course=obj.course).count()

    def get_current_lesson(self, obj):
        lesson = obj.get_current_lesson()
        if lesson:
            return {
                'id': lesson.id,
                'title': lesson.title,
                'type': lesson.lesson_type
            }
        return None

    def get_group(self, obj):
        if not obj.group:
            return None

        # Используем prefetch если есть
        membership = getattr(obj, '_prefetched_membership', None)

        if membership is None:
            from groups.models import GroupMembership
            membership = GroupMembership.objects.filter(
                user=obj.user,
                group=obj.group,
                is_active=True
            ).first()

        days_left = None
        if membership and membership.personal_deadline_at:
            delta = membership.personal_deadline_at - timezone.now()
            days_left = max(0, delta.days)

        return {
            'name': obj.group.name,
            'deadline': membership.personal_deadline_at if membership else None,
            'days_left': days_left
        }

    def get_has_access(self, obj):
        return obj.has_access()