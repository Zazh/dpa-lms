from django.urls import path
from . import api_views

app_name = 'progress'

urlpatterns = [
    # API endpoints для прогресса
    path('courses/my/', api_views.MyCoursesView.as_view(), name='api-my-courses'),
    path('courses/<int:pk>/progress/', api_views.CourseProgressView.as_view(), name='api-course-progress'),
    path('lessons/<int:pk>/complete/', api_views.LessonCompleteView.as_view(), name='api-lesson-complete'),
    path('lessons/<int:pk>/video-progress/', api_views.VideoProgressUpdateView.as_view(), name='api-video-progress'),
]