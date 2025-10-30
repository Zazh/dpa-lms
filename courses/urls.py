from django.urls import path
from .views import (
    MyCourseListView,
    CourseDetailView,
    LessonDetailView,
    CompleteLessonView,
    MyProgressView
)

app_name = 'courses'

urlpatterns = [
    # Список моих курсов
    path('my-courses/', MyCourseListView.as_view(), name='my-courses'),

    # Детальная информация о курсе
    path('<int:course_id>/', CourseDetailView.as_view(), name='course-detail'),

    # Детальная информация об уроке
    path('lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),

    # Завершить урок
    path('lessons/<int:lesson_id>/complete/', CompleteLessonView.as_view(), name='lesson-complete'),

    # Мой прогресс
    path('my-progress/', MyProgressView.as_view(), name='my-progress'),
]