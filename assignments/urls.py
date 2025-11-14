from django.urls import path
from . import api_views

app_name = 'assignments'

urlpatterns = [
    # Сдать работу
    path('<int:assignment_id>/submit/', api_views.submit_assignment, name='submit'),

    # Мои сдачи
    path('my-submissions/', api_views.my_submissions, name='my_submissions'),

    # Детали сдачи
    path('submissions/<int:submission_id>/', api_views.submission_detail, name='submission_detail'),

    # Добавить комментарий
    path('submissions/<int:submission_id>/comment/', api_views.add_comment, name='add_comment'),

    path('submissions/<int:submission_id>/grade/', api_views.grade_assignment, name='grade_assignment'),

]