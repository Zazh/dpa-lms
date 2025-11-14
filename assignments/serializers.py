from rest_framework import serializers
from .models import AssignmentLesson, AssignmentSubmission, AssignmentComment
from account.serializers import UserSerializer


class AssignmentLessonDetailSerializer(serializers.ModelSerializer):
    """Детали домашнего задания"""

    lesson_id = serializers.IntegerField(source='lesson.id', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)

    class Meta:
        model = AssignmentLesson
        fields = [
            'id',
            'lesson_id',
            'lesson_title',
            'instructions',
            'require_text',
            'require_file',
            'max_score',
            'deadline_days',
            'allow_late_submission',
            'allow_resubmission'
        ]


class AssignmentCommentSerializer(serializers.ModelSerializer):
    """Комментарий к сдаче"""

    author = UserSerializer(read_only=True)
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentComment
        fields = [
            'id',
            'author',
            'author_name',
            'message',
            'is_instructor',
            'is_read',
            'created_at'
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name()


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    """Сдача задания (список)"""

    assignment_title = serializers.CharField(source='assignment.lesson.title', read_only=True)
    score_percentage = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment_title',
            'submission_number',
            'status',
            'score',
            'score_percentage',
            'file_url',
            'submitted_at',
            'reviewed_at',
            'comments_count'
        ]

    def get_score_percentage(self, obj):
        return obj.get_score_percentage()

    def get_file_url(self, obj):
        if obj.submission_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.submission_file.url)
        return None

    def get_comments_count(self, obj):
        return obj.get_comments_count()


class AssignmentSubmissionDetailSerializer(serializers.ModelSerializer):
    """Детальная информация о сдаче"""

    assignment = AssignmentLessonDetailSerializer(read_only=True)
    comments = AssignmentCommentSerializer(many=True, read_only=True)
    score_percentage = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    can_resubmit = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'submission_number',
            'submission_text',
            'file_url',
            'status',
            'score',
            'score_percentage',
            'feedback',
            'reviewed_by_name',
            'submitted_at',
            'reviewed_at',
            'comments',
            'can_resubmit'
        ]

    def get_score_percentage(self, obj):
        return obj.get_score_percentage()

    def get_file_url(self, obj):
        if obj.submission_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.submission_file.url)
        return None

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name()
        return None

    def get_can_resubmit(self, obj):
        """Может ли студент пересдать"""
        if obj.status == 'needs_revision':
            return obj.assignment.allow_resubmission
        return False


class AssignmentSubmitSerializer(serializers.Serializer):
    """Сериализатор для сдачи задания"""

    submission_text = serializers.CharField(required=False, allow_blank=True)
    submission_file = serializers.FileField(required=False, allow_null=True)

    def validate(self, data):
        """Проверка что отправлено хотя бы что-то"""
        assignment = self.context.get('assignment')

        if not assignment:
            raise serializers.ValidationError('Задание не найдено')

        text = data.get('submission_text', '').strip()
        file = data.get('submission_file')

        # Проверка требований
        if assignment.require_text and not text:
            raise serializers.ValidationError('Требуется текстовый ответ')

        if assignment.require_file and not file:
            raise serializers.ValidationError('Требуется прикрепить файл')

        if not text and not file:
            raise serializers.ValidationError('Необходимо отправить текст или файл')

        return data


class CommentCreateSerializer(serializers.Serializer):
    """Создание комментария"""

    message = serializers.CharField(max_length=2000)