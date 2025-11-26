from rest_framework import serializers
from .models import Graduate


class GraduateSerializer(serializers.ModelSerializer):
    """Информация о выпуске"""
    
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_label = serializers.CharField(source='course.label', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    certificate_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Graduate
        fields = [
            'id',
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
    
    def get_certificate_url(self, obj):
        """URL сертификата (только для graduated)"""
        if obj.status == 'graduated' and obj.certificate_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.certificate_file.url)
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
