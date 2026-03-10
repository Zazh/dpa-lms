from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q, F
from .decorators import backoffice_required, instructor_required, instructor_or_manager_required, manager_required
from groups.models import Group, GroupMembership, GroupInstructor
from assignments.models import AssignmentSubmission
from progress.models import CourseEnrollment
from graduates.models import Graduate

from django.contrib.auth import authenticate, login, logout



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


@instructor_or_manager_required
def groups_list(request):
    """Список групп (для инструкторов и менеджеров)"""

    user = request.user

    # Получаем доступные группы
    groups = user.get_accessible_groups().annotate(
        students_count=Count('memberships', filter=Q(memberships__is_active=True))
    ).select_related('course').order_by('-created_at')

    context = {
        'groups': groups,
    }

    return render(request, 'backoffice/groups_list.html', context)


@instructor_or_manager_required
def group_detail(request, group_id):
    """Детали группы + список студентов"""

    user = request.user
    group = get_object_or_404(Group, id=group_id)

    # Проверка доступа для обычного инструктора (супер-инструкторы и менеджеры видят все)
    if not (user.is_super_instructor() or user.is_manager()):
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


@instructor_or_manager_required
def group_program(request, group_id):
    """Программа курса группы — модули с учениками и их прогрессом"""

    from content.models import Module, Lesson
    from progress.models import LessonProgress

    user = request.user
    group = get_object_or_404(Group, id=group_id)

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_manager()):
        accessible_groups = user.get_accessible_groups()
        if group not in accessible_groups:
            messages.error(request, 'У вас нет доступа к этой группе')
            return redirect('backoffice:groups_list')

    course = group.course

    # Активные студенты группы
    memberships = GroupMembership.objects.filter(
        group=group, is_active=True
    ).select_related('user').order_by('user__last_name')

    students = [m.user for m in memberships]
    student_ids = [s.id for s in students]

    # Все модули курса с уроками
    modules = Module.objects.filter(course=course).prefetch_related('lessons').order_by('order')

    # Весь прогресс студентов этой группы по урокам курса
    all_progress = LessonProgress.objects.filter(
        user_id__in=student_ids,
        lesson__module__course=course
    ).select_related('lesson', 'lesson__module', 'user')

    # Индексируем: {user_id: {lesson_id: lesson_progress}}
    progress_map = {}
    for lp in all_progress:
        progress_map.setdefault(lp.user_id, {})[lp.lesson_id] = lp

    # Собираем данные по модулям
    modules_data = []
    for module in modules:
        lessons = list(module.lessons.all().order_by('order'))
        lesson_ids = [l.id for l in lessons]
        total_lessons = len(lessons)

        # Для каждого студента определяем статус по модулю
        students_on_module = []  # Текущий модуль (в процессе)
        students_completed = []  # Завершили модуль

        for student in students:
            user_progress = progress_map.get(student.id, {})

            completed_in_module = 0
            last_completed_lp = None

            for lesson in lessons:
                lp = user_progress.get(lesson.id)
                if lp and lp.is_completed:
                    completed_in_module += 1
                    if not last_completed_lp or (lp.completed_at and (not last_completed_lp.completed_at or lp.completed_at > last_completed_lp.completed_at)):
                        last_completed_lp = lp

            if completed_in_module == total_lessons and total_lessons > 0:
                # Завершил весь модуль
                students_completed.append({
                    'user': student,
                    'completed_lessons': completed_in_module,
                    'total_lessons': total_lessons,
                    'last_ip': last_completed_lp.completed_ip if last_completed_lp else None,
                    'last_completed_at': last_completed_lp.completed_at if last_completed_lp else None,
                })
            elif completed_in_module > 0:
                # В процессе прохождения этого модуля
                students_on_module.append({
                    'user': student,
                    'completed_lessons': completed_in_module,
                    'total_lessons': total_lessons,
                    'last_ip': last_completed_lp.completed_ip if last_completed_lp else None,
                    'last_completed_at': last_completed_lp.completed_at if last_completed_lp else None,
                })

        modules_data.append({
            'module': module,
            'lessons': lessons,
            'total_lessons': total_lessons,
            'students_on_module': students_on_module,
            'students_completed': students_completed,
            'active_count': len(students_on_module),
            'completed_count': len(students_completed),
        })

    context = {
        'group': group,
        'course': course,
        'modules_data': modules_data,
        'students_count': len(students),
    }

    return render(request, 'backoffice/group_program.html', context)


@instructor_or_manager_required
def student_progress(request, user_id, group_id):
    """Прогресс конкретного студента"""

    from account.models import User
    from progress.models import LessonProgress

    instructor = request.user
    student = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)

    # Проверка доступа для обычного инструктора (супер-инструкторы и менеджеры видят все)
    if not (instructor.is_super_instructor() or instructor.is_manager()):
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

    # Подсчёт уроков
    from content.models import Lesson
    total_lessons = Lesson.objects.filter(
        module__course=group.course
    ).count()

    context = {
        'student': student,
        'group': group,
        'membership': membership,
        'enrollment': enrollment,
        'lessons_progress': lessons_progress,
        'total_lessons': total_lessons,

    }

    return render(request, 'backoffice/student_progress.html', context)


@manager_required
def group_create(request):
    """Создание группы (только для менеджеров)"""
    from content.models import Course
    from account.models import User

    courses = Course.objects.filter(is_active=True).order_by('title')
    instructors = User.objects.filter(role__in=['instructor', 'super_instructor']).order_by('last_name', 'first_name')

    if request.method == 'POST':
        course_id = request.POST.get('course')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_paid = request.POST.get('is_paid') == 'on'
        deadline_date = request.POST.get('deadline_date') or None
        final_exam_date = request.POST.get('final_exam_date') or None
        final_exam_start_time = request.POST.get('final_exam_start_time') or None
        final_exam_end_time = request.POST.get('final_exam_end_time') or None
        max_students = request.POST.get('max_students', 0)
        is_active = request.POST.get('is_active') == 'on'
        instructor_ids = request.POST.getlist('instructors')

        if not course_id or not name:
            messages.error(request, 'Курс и название группы обязательны')
        else:
            try:
                course = Course.objects.get(id=course_id, is_active=True)

                parsed_deadline_date = None
                if deadline_date:
                    from django.utils.dateparse import parse_datetime
                    parsed_deadline_date = parse_datetime(deadline_date)

                group = Group.objects.create(
                    course=course,
                    name=name,
                    description=description,
                    is_default=False,
                    is_paid=is_paid,
                    deadline_type='fixed_date',
                    deadline_date=parsed_deadline_date,
                    final_exam_date=final_exam_date or None,
                    final_exam_start_time=final_exam_start_time or None,
                    final_exam_end_time=final_exam_end_time or None,
                    max_students=int(max_students) if max_students else 0,
                    is_active=is_active,
                )

                # Назначить выбранных инструкторов
                for instructor_id in instructor_ids:
                    GroupInstructor.objects.create(
                        group=group,
                        instructor_id=int(instructor_id),
                    )

                messages.success(request, f'Группа "{group.name}" успешно создана!')
                return redirect('backoffice:group_detail', group_id=group.id)
            except Course.DoesNotExist:
                messages.error(request, 'Выбранный курс не найден')
            except (ValueError, TypeError) as e:
                messages.error(request, f'Ошибка в данных: {str(e)}')

    context = {
        'courses': courses,
        'instructors': instructors,
    }
    return render(request, 'backoffice/group_create.html', context)


@manager_required
def group_edit(request, group_id):
    """Редактирование настроек группы (только для менеджеров)"""
    from content.models import Course
    from account.models import User

    group = get_object_or_404(Group, id=group_id)
    courses = Course.objects.filter(is_active=True).order_by('title')
    instructors = User.objects.filter(role__in=['instructor', 'super_instructor']).order_by('last_name', 'first_name')
    current_instructor_ids = list(
        group.instructors.filter(is_active=True).values_list('instructor_id', flat=True)
    )

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_paid = request.POST.get('is_paid') == 'on'
        deadline_date = request.POST.get('deadline_date') or None
        final_exam_date = request.POST.get('final_exam_date') or None
        final_exam_start_time = request.POST.get('final_exam_start_time') or None
        final_exam_end_time = request.POST.get('final_exam_end_time') or None
        max_students = request.POST.get('max_students', 0)
        is_active = request.POST.get('is_active') == 'on'
        instructor_ids = request.POST.getlist('instructors')

        if not name:
            messages.error(request, 'Название группы обязательно')
        else:
            try:
                group.name = name
                group.description = description
                # is_default не меняется — только через Django admin
                group.is_paid = is_paid
                # deadline_type и deadline_days не меняются — управляются через Django admin
                if deadline_date:
                    from django.utils.dateparse import parse_datetime
                    group.deadline_date = parse_datetime(deadline_date)
                else:
                    group.deadline_date = None

                group.final_exam_date = final_exam_date or None
                group.final_exam_start_time = final_exam_start_time or None
                group.final_exam_end_time = final_exam_end_time or None
                group.max_students = int(max_students) if max_students else 0
                group.is_active = is_active
                group.save()

                # Синхронизировать инструкторов
                new_ids = set(int(i) for i in instructor_ids)
                old_ids = set(current_instructor_ids)

                # Удалить убранных
                GroupInstructor.objects.filter(group=group).exclude(instructor_id__in=new_ids).delete()

                # Добавить новых
                for instructor_id in new_ids - old_ids:
                    GroupInstructor.objects.create(
                        group=group,
                        instructor_id=instructor_id,
                    )

                messages.success(request, f'Настройки группы "{group.name}" обновлены!')
                return redirect('backoffice:group_detail', group_id=group.id)
            except (ValueError, TypeError) as e:
                messages.error(request, f'Ошибка в данных: {str(e)}')

    context = {
        'group': group,
        'courses': courses,
        'instructors': instructors,
        'current_instructor_ids': current_instructor_ids,
    }
    return render(request, 'backoffice/group_edit.html', context)


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
    if status_filter == 'passed':
        filtered_attempts = attempts.filter(
            status='completed',
            score_percentage__gte=F('quiz__passing_score')
        ).order_by('-started_at')
    elif status_filter == 'failed':
        filtered_attempts = attempts.filter(
            status='completed',
            score_percentage__lt=F('quiz__passing_score')
        ).order_by('-started_at')
    else:
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

    user = request.user

    # Получаем enrollment студента для этого курса
    enrollment = CourseEnrollment.objects.filter(
        user=attempt.user,
        course=attempt.quiz.lesson.module.course,
    ).select_related('group').first()

    # Проверка доступа для обычного инструктора
    if not user.is_super_instructor():
        accessible_groups = user.get_accessible_groups()

        if not enrollment or enrollment.group not in accessible_groups:
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
        'enrollment': enrollment,
    }

    return render(request, 'backoffice/quiz_attempt_detail.html', context)


@instructor_required
def export_quiz_attempt_pdf(request, attempt_id):
    """Скачать результат попытки теста в PDF"""

    from quizzes.models import QuizAttempt
    from exports.services import QuizResultPDFService

    attempt = get_object_or_404(
        QuizAttempt.objects.select_related(
            'quiz__lesson__module__course',
            'user'
        ).filter(status__in=['completed', 'timeout']),
        id=attempt_id,
    )

    user = request.user

    # Проверка доступа для обычного инструктора
    if not user.is_super_instructor():
        enrollment = CourseEnrollment.objects.filter(
            user=attempt.user,
            course=attempt.quiz.lesson.module.course,
        ).select_related('group').first()

        accessible_groups = user.get_accessible_groups()

        if not enrollment or enrollment.group not in accessible_groups:
            messages.error(request, 'У вас нет доступа к этой попытке')
            return redirect('backoffice:quiz_attempts_list')

    service = QuizResultPDFService()

    try:
        pdf_content = service.generate(attempt)
    except Exception as e:
        messages.error(request, f'Ошибка генерации PDF: {str(e)}')
        return redirect('backoffice:quiz_attempt_detail', attempt_id=attempt_id)

    student_name = attempt.user.get_full_name().replace(' ', '_')
    lesson_title = attempt.quiz.lesson.title.replace(' ', '_')[:30]
    filename = f"quiz_{student_name}_{lesson_title}.pdf"

    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


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


@backoffice_required
def graduates_list(request):
    """Список выпускников (для менеджеров и супер-инструкторов)"""

    user = request.user

    # Проверка доступа - только супер-инструктор и менеджеры
    if not (user.is_super_instructor() or user.is_manager() or user.is_super_manager()):
        messages.error(request, 'Доступ к выпускникам только для супер-инструкторов и менеджеров')
        return redirect('backoffice:dashboard')

    # Фильтры
    status_filter = request.GET.get('status', 'pending')
    group_filter = request.GET.get('group', '')
    course_filter = request.GET.get('course', '')

    # Базовый queryset
    graduates = Graduate.objects.select_related(
        'user',
        'course',
        'group',
        'graduated_by'
    )

    # Применяем фильтры
    if status_filter:
        graduates = graduates.filter(status=status_filter)

    if group_filter:
        graduates = graduates.filter(group_id=group_filter)

    if course_filter:
        graduates = graduates.filter(course_id=course_filter)

    graduates = graduates.order_by('-completed_at')

    # Статистика
    all_graduates = Graduate.objects.all()

    stats = {
        'pending': all_graduates.filter(status='pending').count(),
        'graduated': all_graduates.filter(status='graduated').count(),
        'rejected': all_graduates.filter(status='rejected').count(),
    }

    # Списки для фильтров
    from content.models import Course
    groups = Group.objects.filter(is_active=True)
    courses = Course.objects.filter(is_active=True)

    context = {
        'graduates': graduates,
        'status_filter': status_filter,
        'group_filter': group_filter,
        'course_filter': course_filter,
        'stats': stats,
        'groups': groups,
        'courses': courses,
    }

    return render(request, 'backoffice/graduates_list.html', context)

@backoffice_required
def graduate_detail(request, graduate_id):
    """Детали выпускника"""

    graduate = get_object_or_404(Graduate, id=graduate_id)

    # Проверка доступа
    user = request.user

    # Проверка доступа - только супер-инструктор и менеджеры
    if not (user.is_super_instructor() or user.is_manager() or user.is_super_manager()):
        messages.error(request, 'Доступ к выпускникам только для супер-инструкторов и менеджеров')
        return redirect('backoffice:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Выпустить студента
        if action == 'approve':
            if graduate.status != 'pending':
                messages.error(request, 'Можно выпустить только студента со статусом "Ожидает выпуска"')
            else:
                graduate.approve_graduation(request.user)
                messages.success(request, f'🎓 Студент {graduate.user.get_full_name()} выпущен! Сертификат генерируется...')
                return redirect('backoffice:graduates_list')

        # Отклонить
        elif action == 'reject':
            reason = request.POST.get('reason', '')
            if graduate.status != 'pending':
                messages.error(request, 'Можно отклонить только студента со статусом "Ожидает выпуска"')
            else:
                graduate.reject_graduation(request.user, reason)
                messages.warning(request, f'Студент {graduate.user.get_full_name()} отклонен')
                return redirect('backoffice:graduates_list')

    # Попытки тестов
    quiz_attempts = graduate.get_quiz_attempts_summary()

    context = {
        'graduate': graduate,
        'quiz_attempts': quiz_attempts,
    }

    return render(request, 'backoffice/graduate_detail.html', context)

@backoffice_required
def graduates_bulk_action(request):
    """Массовые действия с выпускниками"""

    if request.method != 'POST':
        return redirect('backoffice:graduates_list')

    action = request.POST.get('action')
    graduate_ids = request.POST.getlist('graduate_ids')

    if not graduate_ids:
        messages.error(request, 'Не выбраны выпускники')
        return redirect('backoffice:graduates_list')

    graduates = Graduate.objects.filter(id__in=graduate_ids)

    # Проверка доступа
    user = request.user
    # Проверка доступа - только супер-инструктор и менеджеры
    if not (user.is_super_instructor() or user.is_manager() or user.is_super_manager()):
        messages.error(request, 'Доступ к выпускникам только для супер-инструкторов и менеджеров')
        return redirect('backoffice:dashboard')

    if action == 'approve':
        # Массовый выпуск
        count = 0

        for graduate in graduates.filter(status='pending'):
            graduate.approve_graduation(request.user)
            count += 1

        if count:
            messages.success(request, f'🎓 Выпущено студентов: {count}. Сертификаты генерируются в фоне...')
        else:
            messages.warning(request, 'Нет студентов для выпуска')

    elif action == 'reject':
        # Массовое отклонение
        count = 0
        for graduate in graduates.filter(status='pending'):
            graduate.reject_graduation(request.user)
            count += 1

        if count > 0:
            messages.warning(request, f'Отклонено студентов: {count}')

    return redirect('backoffice:graduates_list')


from dossier.models import StudentDossier, InstructorDossier


@backoffice_required
def student_dossiers_list(request):
    """Список досье студентов"""

    user = request.user

    # Проверка доступа - только супер-менеджер и супер-инструктор
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    # Фильтры
    search = request.GET.get('search', '')
    course_filter = request.GET.get('course', '')

    dossiers = StudentDossier.objects.all()

    if search:
        dossiers = dossiers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(iin__icontains=search) |
            Q(certificate_number__icontains=search)
        )

    if course_filter:
        dossiers = dossiers.filter(course_title__icontains=course_filter)

    dossiers = dossiers.order_by('-graduated_at')

    # Статистика
    stats = {
        'total': StudentDossier.objects.count(),
    }

    context = {
        'dossiers': dossiers,
        'search': search,
        'course_filter': course_filter,
        'stats': stats,
    }

    return render(request, 'backoffice/student_dossiers_list.html', context)


@backoffice_required
def student_dossier_detail(request, dossier_id):
    """Детали досье студента"""

    user = request.user

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    dossier = get_object_or_404(StudentDossier, id=dossier_id)

    context = {
        'dossier': dossier,
    }

    return render(request, 'backoffice/student_dossier_detail.html', context)


@backoffice_required
def instructor_dossiers_list(request):
    """Список досье инструкторов"""

    user = request.user

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    search = request.GET.get('search', '')

    dossiers = InstructorDossier.objects.all()

    if search:
        dossiers = dossiers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    dossiers = dossiers.order_by('-total_graduates')

    # Статистика
    stats = {
        'total': InstructorDossier.objects.count(),
    }

    context = {
        'dossiers': dossiers,
        'search': search,
        'stats': stats,
    }

    return render(request, 'backoffice/instructor_dossiers_list.html', context)


@backoffice_required
def instructor_dossier_detail(request, dossier_id):
    """Детали досье инструктора"""

    user = request.user

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    dossier = get_object_or_404(InstructorDossier, id=dossier_id)

    # Обновить досье при просмотре
    if dossier.user:
        from dossier.services import DossierService
        dossier = DossierService.create_or_update_instructor_dossier(dossier.user)

    context = {
        'dossier': dossier,
    }

    return render(request, 'backoffice/instructor_dossier_detail.html', context)


def backoffice_login(request):
    """Страница входа в backoffice"""

    # Если уже залогинен — редирект
    if request.user.is_authenticated:
        if request.user.is_backoffice_user():
            return redirect('backoffice:dashboard')
        else:
            messages.error(request, 'У вас нет доступа к backoffice')
            return redirect('backoffice:login')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_backoffice_user():
                login(request, user)
                from account.models import UserActivityLog
                UserActivityLog.log(request, user, 'login')
                next_url = request.GET.get('next', 'backoffice:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'У вас нет доступа к backoffice. Только для сотрудников.')
        else:
            messages.error(request, 'Неверный email или пароль')

    return render(request, 'backoffice/login.html')


@backoffice_required
def export_dossier_quiz_pdf(request, dossier_id, quiz_index):
    """Экспорт результатов теста из досье в PDF"""

    from dossier.models import StudentDossier
    from exports.services import QuizResultPDFService

    user = request.user

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    dossier = get_object_or_404(StudentDossier, id=dossier_id)

    # Генерация PDF
    service = QuizResultPDFService()

    try:
        pdf_content = service.generate_from_dossier(dossier, quiz_index)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('backoffice:student_dossier_detail', dossier_id=dossier_id)
    except Exception as e:
        messages.error(request, f'Ошибка генерации PDF: {str(e)}')
        return redirect('backoffice:student_dossier_detail', dossier_id=dossier_id)

    # Имя файла
    student_name = dossier.get_full_name().replace(' ', '_')
    quiz_data = dossier.quizzes_history[quiz_index]
    lesson_title = quiz_data.get('lesson_title', 'test').replace(' ', '_')[:30]
    filename = f"quiz_{student_name}_{lesson_title}.pdf"

    from django.http import HttpResponse
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@backoffice_required
def export_dossier_certificate_pdf(request, dossier_id, with_stamp=False):
    """Скачать сертификат из досье"""

    from dossier.models import StudentDossier

    user = request.user

    # Проверка доступа
    if not (user.is_super_instructor() or user.is_super_manager()):
        messages.error(request, 'Доступ к досье только для супер-менеджеров и супер-инструкторов')
        return redirect('backoffice:dashboard')

    dossier = get_object_or_404(StudentDossier, id=dossier_id)

    # Получаем сертификат через graduate
    if not dossier.graduate or not hasattr(dossier.graduate, 'certificate'):
        messages.error(request, 'Сертификат не найден')
        return redirect('backoffice:student_dossier_detail', dossier_id=dossier_id)

    certificate = dossier.graduate.certificate

    if certificate.status != 'ready':
        messages.warning(request, 'Сертификат ещё генерируется, попробуйте позже')
        return redirect('backoffice:student_dossier_detail', dossier_id=dossier_id)

    # Выбираем файл
    if with_stamp:
        file_field = certificate.file_with_stamp
        suffix = 'с_печатью'
    else:
        file_field = certificate.file_without_stamp
        suffix = 'без_печати'

    if not file_field:
        messages.error(request, 'Файл сертификата не найден')
        return redirect('backoffice:student_dossier_detail', dossier_id=dossier_id)

    # Отдаём файл
    from django.http import FileResponse

    filename = f"certificate_{dossier.get_full_name().replace(' ', '_')}_{suffix}.pdf"

    response = FileResponse(file_field.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@backoffice_required
def export_dossier_certificate_no_stamp(request, dossier_id):
    """Скачать сертификат без печати"""
    return export_dossier_certificate_pdf(request, dossier_id, with_stamp=False)


@backoffice_required
def export_dossier_certificate_with_stamp(request, dossier_id):
    """Скачать сертификат с печатью"""
    return export_dossier_certificate_pdf(request, dossier_id, with_stamp=True)

def backoffice_logout(request):
    """Выход из backoffice"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('backoffice:login')