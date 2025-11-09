from rest_framework import serializers
from .models import CourseEnrollment, LessonProgress, VideoProgress
from content.models import Lesson
from content.serializers import LessonListSerializer
from django.utils import timezone


class VideoProgressSerializer(serializers.ModelSerializer):
    """Прогресс видео"""

    class Meta:
        model = VideoProgress
        fields = ['watch_percentage', 'started_at', 'last_watched_at']


class LessonProgressSerializer(serializers.ModelSerializer):
    """Прогресс урока с доступностью"""
    lesson = LessonListSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    available_at = serializers.DateTimeField(read_only=True)
    available_in = serializers.SerializerMethodField()

    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'is_completed', 'is_available', 'available_at', 'available_in', 'started_at',
                  'completed_at']

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


class ModuleProgressSerializer(serializers.Serializer):
    """Модуль с прогрессом уроков"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    order = serializers.IntegerField()
    lessons = LessonProgressSerializer(many=True)


class CourseProgressSerializer(serializers.ModelSerializer):
    """Прогресс по курсу"""
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
        """Текущий урок (первый незавершенный)"""
        lesson = obj.get_current_lesson()
        if lesson:
            return {
                'id': lesson.id,
                'title': lesson.title,
                'type': lesson.lesson_type
            }
        return None

    def get_modules(self, obj):
        """Модули с прогрессом уроков"""
        from content.models import Module

        modules = Module.objects.filter(course=obj.course).prefetch_related('lessons').order_by('order')
        result = []

        for module in modules:
            lessons_progress = LessonProgress.objects.filter(
                user=obj.user,
                lesson__module=module
            ).select_related('lesson').order_by('lesson__order')

            result.append({
                'id': module.id,
                'title': module.title,
                'description': module.description,
                'order': module.order,
                'lessons': LessonProgressSerializer(lessons_progress, many=True).data
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
        from content.models import Lesson
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