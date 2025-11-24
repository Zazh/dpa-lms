from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q, F
from .decorators import backoffice_required, instructor_required
from groups.models import Group, GroupMembership
from assignments.models import AssignmentSubmission
from progress.models import CourseEnrollment


@backoffice_required
def dashboard(request):
    """Главная страница backoffice - редирект в зависимости от роли"""

    user = request.user

    # Инструкторы → страница проверки ДЗ
    if user.is_instructor():
        return redirect('backoffice:assignments_check')

    # Менеджеры → страница групп (в будущем)
    elif user.is_manager():
        return redirect('backoffice:groups_list')

    # Остальные → главная
    else:
        return render(request, 'backoffice/dashboard.html')


@instructor_required
def assignment_detail(request, submission_id):
    """Детали ДЗ + проверка"""

    submission = get_object_or_404(
        AssignmentSubmission,
        id=submission_id
    )

    # Проверка доступа для обычного инструктора
    user = request.user
    if not user.is_super_instructor():
        # Проверяем что студент в доступной группе
        accessible_groups = user.get_accessible_groups()
        enrollment = CourseEnrollment.objects.filter(
            user=submission.user,
            course=submission.assignment.lesson.module.course,
            group__in=accessible_groups
        ).first()

        if not enrollment:
            messages.error(request, 'У вас нет доступа к этой работе')
            return redirect('backoffice:assignments_check')

    # Комментарии
    comments = submission.comments.select_related('author').order_by('created_at')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Добавить комментарий
        if action == 'add_comment':
            from assignments.models import AssignmentComment

            message_text = request.POST.get('message', '').strip()
            if message_text:
                AssignmentComment.objects.create(
                    submission=submission,
                    author=request.user,
                    message=message_text,
                    is_instructor=True
                )
                messages.success(request, 'Комментарий добавлен')
                return redirect('backoffice:assignment_detail', submission_id=submission_id)

        # Зачесть
        elif action == 'pass':
            score = request.POST.get('score')
            feedback = request.POST.get('feedback', '')

            if not score:
                messages.error(request, 'Укажите балл')
            else:
                try:
                    score = int(score)
                    submission.mark_passed(request.user, score, feedback)
                    messages.success(request, 'Работа зачтена!')
                    return redirect('backoffice:assignments_check')
                except ValueError:
                    messages.error(request, 'Неверный формат балла')

        # Отправить на доработку
        elif action == 'needs_revision':
            feedback = request.POST.get('feedback', '').strip()
            if not feedback:
                messages.error(request, 'Укажите что нужно исправить')
            else:
                submission.mark_needs_revision(request.user, feedback)
                messages.success(request, 'Работа отправлена на доработку')
                return redirect('backoffice:assignments_check')

    context = {
        'submission': submission,
        'comments': comments,
    }

    return render(request, 'backoffice/assignment_detail.html', context)


@instructor_required
def groups_list(request):
    """Список групп"""

    user = request.user

    # Получаем доступные группы
    groups = user.get_accessible_groups().annotate(
        students_count=Count('memberships', filter=Q(memberships__is_active=True))
    ).select_related('course').order_by('-created_at')

    context = {
        'groups': groups,
    }

    return render(request, 'backoffice/groups_list.html', context)


@instructor_required
def group_detail(request, group_id):
    """Детали группы + список студентов"""

    user = request.user
    group = get_object_or_404(Group, id=group_id)

    # Проверка доступа для обычного инструктора
    if not user.is_super_instructor():
        accessible_groups = user.get_accessible_groups()
        if group not in accessible_groups:
            messages.error(request, 'У вас нет доступа к этой группе')
            return redirect('backoffice:groups_list')

    # Активные студенты
    memberships = GroupMembership.objects.filter(
        group=group,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    context = {
        'group': group,
        'memberships': memberships,
        'students_count': memberships.count(),
    }

    return render(request, 'backoffice/group_detail.html', context)


@instructor_required
def student_progress(request, user_id, group_id):
    """Прогресс конкретного студента"""

    from account.models import User
    from progress.models import LessonProgress

    instructor = request.user
    student = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)

    # Проверка доступа для обычного инструктора
    if not instructor.is_super_instructor():
        accessible_groups = instructor.get_accessible_groups()
        if group not in accessible_groups:
            messages.error(request, 'У вас нет доступа к этой группе')
            return redirect('backoffice:groups_list')

    # Проверка что студент в группе
    membership = get_object_or_404(
        GroupMembership,
        user=student,
        group=group,
        is_active=True
    )

    # Зачисление на курс
    try:
        enrollment = CourseEnrollment.objects.get(
            user=student,
            course=group.course
        )
    except CourseEnrollment.DoesNotExist:
        messages.error(request, 'Студент не зачислен на курс')
        return redirect('backoffice:group_detail', group_id=group_id)

    # Прогресс по урокам
    lessons_progress = LessonProgress.objects.filter(
        user=student,
        lesson__module__course=group.course
    ).select_related('lesson', 'lesson__module').order_by(
        'lesson__module__order',
        'lesson__order'
    )

    context = {
        'student': student,
        'group': group,
        'membership': membership,
        'enrollment': enrollment,
        'lessons_progress': lessons_progress,
    }

    return render(request, 'backoffice/student_progress.html', context)


def no_access(request):
    """Страница "Доступ запрещен" """
    return render(request, 'backoffice/no_access.html')


@instructor_required
def quiz_attempts_list(request):
    """Список попыток тестов"""

    user = request.user

    # Фильтр по статусу
    status_filter = request.GET.get('status', 'completed')

    # Базовый queryset
    from quizzes.models import QuizAttempt

    attempts = QuizAttempt.objects.select_related(
        'user',
        'quiz__lesson__module__course'
    )

    # Фильтр по доступным группам для обычного инструктора
    if not user.is_super_instructor():
        accessible_groups = user.get_accessible_groups()
        if accessible_groups.exists():
            attempts = attempts.filter(
                user__enrollments__group__in=accessible_groups
            ).distinct()

    # Применяем фильтр по статусу для отображения
    filtered_attempts = attempts.filter(status=status_filter).order_by('-started_at')

    # Статистика - ТОЖЕ с учетом групп!
    stats = {
        'total': attempts.filter(status='completed').count(),
        'passed': attempts.filter(
            status='completed',
            score_percentage__gte=F('quiz__passing_score')
        ).count(),
        'failed': attempts.filter(
            status='completed',
            score_percentage__lt=F('quiz__passing_score')
        ).count(),
    }

    context = {
        'attempts': filtered_attempts,
        'status_filter': status_filter,
        'stats': stats,
    }

    return render(request, 'backoffice/quiz_attempts_list.html', context)


@instructor_required
def quiz_attempt_detail(request, attempt_id):
    """Детали попытки теста"""

    from quizzes.models import QuizAttempt

    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id
    )

    # Проверка доступа для обычного инструктора
    user = request.user
    if not user.is_super_instructor():
        accessible_groups = user.get_accessible_groups()
        enrollment = CourseEnrollment.objects.filter(
            user=attempt.user,
            course=attempt.quiz.lesson.module.course,
            group__in=accessible_groups
        ).first()

        if not enrollment:
            messages.error(request, 'У вас нет доступа к этой попытке')
            return redirect('backoffice:quiz_attempts_list')

    # Получаем ответы с правильными/неправильными
    responses = attempt.responses.select_related('question').prefetch_related(
        'selected_answers',
        'question__answers'
    ).order_by('question__order')

    context = {
        'attempt': attempt,
        'responses': responses,
        'passed': attempt.is_passed(),
    }

    return render(request, 'backoffice/quiz_attempt_detail.html', context)


@instructor_required
def assignments_check(request):
    """Список ДЗ на проверке (для инструкторов)"""

    user = request.user

    # Фильтр по статусу
    status_filter = request.GET.get('status', 'in_review')

    # Базовый queryset БЕЗ фильтра по статусу
    submissions = AssignmentSubmission.objects.select_related(
        'user',
        'assignment__lesson__module__course',
        'reviewed_by'
    )

    # Фильтр по доступным группам ТОЛЬКО для обычного инструктора
    if not user.is_super_instructor():  # ← СУПЕР НЕ ФИЛЬТРУЕТСЯ!
        accessible_groups = user.get_accessible_groups()
        if accessible_groups.exists():
            submissions = submissions.filter(
                user__enrollments__group__in=accessible_groups
            ).distinct()

    # Применяем фильтр по статусу для отображения
    filtered_submissions = submissions.filter(status=status_filter).order_by('-submitted_at')

    # Статистика - с учетом групп (для обычного) или все (для супер)
    stats = {
        'in_review': submissions.filter(status='in_review').count(),
        'needs_revision': submissions.filter(status='needs_revision').count(),
        'passed': submissions.filter(status='passed').count(),
    }

    context = {
        'submissions': filtered_submissions,
        'status_filter': status_filter,
        'stats': stats,
    }

    return render(request, 'backoffice/assignments_check.html', context)