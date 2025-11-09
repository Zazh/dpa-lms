from rest_framework import serializers
from .models import Course, Module, Lesson, VideoLesson, TextLesson, LessonMaterial


class LessonMaterialSerializer(serializers.ModelSerializer):
    """Материалы к уроку"""
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = LessonMaterial
        fields = ['id', 'title', 'description', 'file', 'url', 'order', 'file_size']

    def get_file_size(self, obj):
        return obj.get_file_size()


class LessonListSerializer(serializers.ModelSerializer):
    """Урок в списке (для структуры курса)"""
    type = serializers.CharField(source='lesson_type')
    type_display = serializers.CharField(source='get_lesson_type_display')

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'description', 'type', 'type_display', 'order']


class ModuleSerializer(serializers.ModelSerializer):
    """Модуль с уроками"""
    lessons = LessonListSerializer(many=True, read_only=True)
    lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'requires_previous_module', 'lessons_count', 'lessons']

    def get_lessons_count(self, obj):
        return obj.get_lessons_count()


class CourseListSerializer(serializers.ModelSerializer):
    """Курс в каталоге (список)"""
    modules_count = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'label', 'description', 'duration', 'modules_count', 'lessons_count', 'is_enrolled']

    def get_modules_count(self, obj):
        return obj.get_modules_count()

    def get_lessons_count(self, obj):
        return obj.get_lessons_count()

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        from progress.models import CourseEnrollment
        return CourseEnrollment.objects.filter(
            user=request.user,
            course=obj,
            is_active=True
        ).exists()


class CourseDetailSerializer(serializers.ModelSerializer):
    """Детальная информация о курсе"""
    modules = ModuleSerializer(many=True, read_only=True)
    modules_count = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'label', 'description', 'duration', 'modules_count', 'lessons_count', 'is_enrolled',
                  'modules']

    def get_modules_count(self, obj):
        return obj.get_modules_count()

    def get_lessons_count(self, obj):
        return obj.get_lessons_count()

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        from progress.models import CourseEnrollment
        return CourseEnrollment.objects.filter(
            user=request.user,
            course=obj,
            is_active=True
        ).exists()


class VideoLessonDetailSerializer(serializers.ModelSerializer):
    """Детали видео-урока"""
    embed_url = serializers.SerializerMethodField()
    formatted_duration = serializers.SerializerMethodField()

    class Meta:
        model = VideoLesson
        fields = ['vimeo_video_id', 'embed_url', 'video_duration', 'formatted_duration', 'completion_threshold',
                  'timecodes']

    def get_embed_url(self, obj):
        return obj.get_vimeo_embed_url()

    def get_formatted_duration(self, obj):
        return obj.format_duration()


class TextLessonDetailSerializer(serializers.ModelSerializer):
    """Детали текстового урока"""
    word_count = serializers.SerializerMethodField()

    class Meta:
        model = TextLesson
        fields = ['content', 'estimated_reading_time', 'word_count']

    def get_word_count(self, obj):
        return obj.get_word_count()