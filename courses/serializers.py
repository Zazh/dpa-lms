from rest_framework import serializers
from .models import Course, Lesson, CourseEnrollment, LessonProgress, LessonMaterial


class LessonMaterialSerializer(serializers.ModelSerializer):
    """Сериализатор для материалов урока"""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LessonMaterial
        fields = ['id', 'title', 'description', 'file_url', 'url', 'file_type', 'file_size', 'order']

    def get_file_url(self, obj):
        """Полный URL файла"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None


class LessonSerializer(serializers.ModelSerializer):
    """Сериализатор для урока"""
    is_available = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    materials = LessonMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'content', 'order',
            'video_url', 'video_duration', 'timecodes',
            'requires_previous_completion', 'is_available', 'is_completed',
            'materials'
        ]

    def get_is_available(self, obj):
        """Проверка доступности урока для пользователя"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        # Если урок не требует завершения предыдущего - доступен
        if not obj.requires_previous_completion:
            return True

        # Проверяем, завершен ли предыдущий урок
        previous_lesson = obj.get_previous_lesson()
        if not previous_lesson:
            return True

        # Проверяем прогресс по предыдущему уроку
        previous_progress = LessonProgress.objects.filter(
            user=request.user,
            lesson=previous_lesson,
            is_completed=True
        ).exists()

        return previous_progress

    def get_is_completed(self, obj):
        """Проверка завершения урока пользователем"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        return LessonProgress.objects.filter(
            user=request.user,
            lesson=obj,
            is_completed=True
        ).exists()


class LessonListSerializer(serializers.ModelSerializer):
    """Краткий сериализатор урока для списка"""
    is_available = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    materials_count = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'order', 'has_video', 'materials_count',
            'requires_previous_completion', 'is_available', 'is_completed'
        ]

    def get_is_available(self, obj):
        """Проверка доступности урока для пользователя"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        if not obj.requires_previous_completion:
            return True

        previous_lesson = obj.get_previous_lesson()
        if not previous_lesson:
            return True

        previous_progress = LessonProgress.objects.filter(
            user=request.user,
            lesson=previous_lesson,
            is_completed=True
        ).exists()

        return previous_progress

    def get_is_completed(self, obj):
        """Проверка завершения урока пользователем"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        return LessonProgress.objects.filter(
            user=request.user,
            lesson=obj,
            is_completed=True
        ).exists()

    def get_has_video(self, obj):
        """Есть ли видео"""
        return bool(obj.video_url)

    def get_materials_count(self, obj):
        """Количество материалов"""
        return obj.materials.count()


class CourseDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор курса с уроками"""
    lessons = LessonListSerializer(many=True, read_only=True)
    total_lessons = serializers.IntegerField(source='get_total_lessons', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    enrolled_at = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'total_lessons',
            'progress_percentage', 'enrolled_at', 'lessons', 'label', 'duration'
        ]

    def get_progress_percentage(self, obj):
        """Прогресс пользователя по курсу"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0

        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=obj
        ).first()

        return enrollment.get_progress_percentage() if enrollment else 0

    def get_enrolled_at(self, obj):
        """Дата записи на курс"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=obj
        ).first()

        return enrollment.enrolled_at if enrollment else None


class CourseListSerializer(serializers.ModelSerializer):
    """Сериализатор списка курсов"""
    total_lessons = serializers.IntegerField(source='get_total_lessons', read_only=True)
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'total_lessons', 'progress_percentage', 'label', 'duration', ]

    def get_progress_percentage(self, obj):
        """Прогресс пользователя по курсу"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0

        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=obj
        ).first()

        return enrollment.get_progress_percentage() if enrollment else 0


class LessonProgressSerializer(serializers.ModelSerializer):
    """Сериализатор для отметки прогресса урока"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)

    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'lesson_title', 'is_completed', 'started_at', 'completed_at']
        read_only_fields = ['started_at', 'completed_at']