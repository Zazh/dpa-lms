from rest_framework import serializers
from .models import Graduate


class GraduateSerializer(serializers.ModelSerializer):
    """Информация о выпуске"""

    course_id = serializers.IntegerField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_label = serializers.CharField(source='course.label', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    certificate_number = serializers.SerializerMethodField()
    certificate_issued_at = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()

    class Meta:
        model = Graduate
        fields = [
            'id',
            'course_id',
            'status',
            'status_display',
            'course_title',
            'course_label',
            'group_name',
            'completed_at',
            'graduated_at',
            'final_score',
            'total_lessons_completed',
            'average_quiz_score',
            'total_study_days',
            'certificate_number',
            'certificate_url',
            'certificate_issued_at',
        ]

    def get_certificate_number(self, obj):
        """Номер сертификата из Certificate"""
        if hasattr(obj, 'certificate') and obj.certificate:
            return obj.certificate.number
        return None

    def get_certificate_issued_at(self, obj):
        """Дата выдачи из Certificate"""
        if hasattr(obj, 'certificate') and obj.certificate:
            return obj.certificate.issued_at
        return None

    def get_certificate_url(self, obj):
        """URL сертификата (без печати)"""
        if hasattr(obj, 'certificate') and obj.certificate and obj.certificate.status == 'ready':
            if obj.certificate.file_without_stamp:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.certificate.file_without_stamp.url)
        return None


class GraduateDetailSerializer(GraduateSerializer):
    """Детальная информация о выпуске"""

    quiz_attempts = serializers.SerializerMethodField()
    completion_details = serializers.JSONField(read_only=True)

    class Meta(GraduateSerializer.Meta):
        fields = GraduateSerializer.Meta.fields + [
            'quiz_attempts',
            'completion_details',
        ]

    def get_quiz_attempts(self, obj):
        """Попытки тестов"""
        return obj.get_quiz_attempts_summary()