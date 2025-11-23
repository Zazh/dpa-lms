from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Сериализатор для уведомлений"""

    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'type',
            'type_display',
            'title',
            'message',
            'link',
            'created_at',
        ]
        read_only_fields = ['id', 'type', 'type_display', 'title', 'message', 'link', 'created_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Сериализатор для настроек уведомлений"""

    class Meta:
        model = NotificationPreference
        exclude = ['id', 'user', 'created_at', 'updated_at']