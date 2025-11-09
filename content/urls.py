from django.urls import path
from . import api_views

app_name = 'content'

urlpatterns = [
    # API endpoints для студентов
    path('courses/', api_views.CourseListView.as_view(), name='api-course-list'),
    path('courses/<int:pk>/', api_views.CourseDetailView.as_view(), name='api-course-detail'),
    path('lessons/<int:pk>/', api_views.LessonDetailView.as_view(), name='api-lesson-detail'),
]