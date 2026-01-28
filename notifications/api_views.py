from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationListView(APIView):
    """Список уведомлений пользователя"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Получить список уведомлений
        Query params:
        - limit: количество уведомлений (по умолчанию все)
        """
        notifications = request.user.notifications.all()

        # Опциональная пагинация
        limit = request.query_params.get('limit')
        if limit:
            try:
                limit = int(limit)
                notifications = notifications[:limit]
            except ValueError:
                pass

        serializer = NotificationSerializer(notifications, many=True)

        return Response({
            'count': request.user.notifications.count(),
            'results': serializer.data
        })


class NotificationCountView(APIView):
    """Количество уведомлений"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = request.user.notifications.count()
        return Response({'count': count})


class NotificationDetailView(APIView):
    """Удаление конкретного уведомления"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        """Удалить уведомление"""
        notification = get_object_or_404(
            Notification,
            id=pk,
            user=request.user
        )
        notification.delete()

        return Response({
            'message': 'Уведомление удалено',
            'remaining_count': request.user.notifications.count()
        })


class NotificationClearAllView(APIView):
    """Очистить все уведомления"""
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        """Удалить все уведомления пользователя"""
        count = request.user.notifications.count()
        request.user.notifications.all().delete()

        return Response({
            'message': f'Удалено уведомлений: {count}',
            'deleted_count': count
        })


class NotificationPreferenceView(APIView):
    """Настройки уведомлений пользователя"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Получить настройки"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = NotificationPreferenceSerializer(preferences)
        return Response(serializer.data)

    def patch(self, request):
        """Обновить настройки"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = NotificationPreferenceSerializer(
            preferences,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Настройки обновлены',
            'preferences': serializer.data
        })