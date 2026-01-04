import logging
from django.utils import timezone
from django.db.models import Avg, Count

from .models import StudentDossier, InstructorDossier

logger = logging.getLogger(__name__)


class DossierService:
    """Сервис для создания и обновления досье"""

    @classmethod
    def create_student_dossier(cls, graduate):
        """
        Создать досье студента при выпуске.

        Args:
            graduate: объект Graduate

        Returns:
            StudentDossier или None
        """
        # Проверяем что досье еще не создано
        if hasattr(graduate, 'dossier') and graduate.dossier:
            logger.info(f"Досье для {graduate.user.email} уже существует")
            return graduate.dossier

        user = graduate.user
        course = graduate.course
        group = graduate.group

        # Получаем инструктора группы
        instructor_name = ''
        instructor_email = ''
        if group:
            instructor = cls._get_group_instructor(group)
            if instructor:
                instructor_name = instructor.get_full_name()
                instructor_email = instructor.email

        # Если инструктор группы не найден — берём того, кто проверял ДЗ
        if not instructor_name:
            from assignments.models import AssignmentSubmission
            last_reviewed = AssignmentSubmission.objects.filter(
                user=user,
                assignment__lesson__module__course=course,
                reviewed_by__isnull=False
            ).select_related('reviewed_by').order_by('-reviewed_at').first()

            if last_reviewed and last_reviewed.reviewed_by:
                instructor_name = last_reviewed.reviewed_by.get_full_name()
                instructor_email = last_reviewed.reviewed_by.email

        # Получаем enrollment для даты зачисления
        from progress.models import CourseEnrollment
        try:
            enrollment = CourseEnrollment.objects.get(user=user, course=course)
            enrolled_at = enrollment.enrolled_at
        except CourseEnrollment.DoesNotExist:
            enrolled_at = graduate.completed_at

        # Собираем историю уроков
        lessons_history = cls._collect_lessons_history(user, course)

        # Собираем историю модулей
        modules_history = cls._collect_modules_history(user, course)

        # Собираем историю тестов
        quizzes_history = cls._collect_quizzes_history(user, course)

        # Собираем историю ДЗ
        assignments_history = cls._collect_assignments_history(user, course)

        # Создаем досье
        dossier = StudentDossier.objects.create(
            user=user,
            graduate=graduate,

            # Личные данные
            first_name=user.first_name,
            last_name=user.last_name,
            middle_name=getattr(user, 'middle_name', '') or '',
            email=user.email,
            iin=user.iin,
            phone=getattr(user, 'phone', '') or '',

            # Обучение
            course_title=course.title,
            course_label=getattr(course, 'label', '') or '',
            group_name=group.name if group else 'Без группы',
            instructor_name=instructor_name,
            instructor_email=instructor_email,

            # Сертификат
            certificate_number=graduate.certificate_number,
            certificate_file=graduate.certificate_file,

            # Даты
            enrolled_at=enrolled_at,
            completed_at=graduate.completed_at,
            graduated_at=graduate.graduated_at,

            # Результаты
            final_score=graduate.final_score,
            total_lessons_completed=graduate.total_lessons_completed,
            total_study_days=graduate.total_study_days,
            average_quiz_score=graduate.average_quiz_score,

            # JSON архивы
            lessons_history=lessons_history,
            modules_history=modules_history,
            quizzes_history=quizzes_history,
            assignments_history=assignments_history,
        )

        logger.info(f"✅ Создано досье студента: {dossier}")
        return dossier

    @classmethod
    def _get_group_instructor(cls, group):
        """Получить инструктора группы"""
        from groups.models import GroupInstructor

        # 1. Проверяем GroupInstructor (назначенные через админку)
        group_instructor = GroupInstructor.objects.filter(
            group=group,
            is_active=True
        ).select_related('instructor').first()

        if group_instructor:
            return group_instructor.instructor

        # 2. Проверяем assigned_instructors (старый механизм)
        instructor = group.assigned_instructors.first()
        if instructor:
            return instructor

        return None

    @classmethod
    def _collect_lessons_history(cls, user, course):
        """Собрать историю прохождения уроков"""
        from progress.models import LessonProgress

        lessons = []
        progresses = LessonProgress.objects.filter(
            user=user,
            lesson__module__course=course,
            is_completed=True
        ).select_related('lesson', 'lesson__module').order_by(
            'lesson__module__order', 'lesson__order'
        )

        for progress in progresses:
            lessons.append({
                'lesson_id': progress.lesson.id,
                'lesson_title': progress.lesson.title,
                'lesson_type': progress.lesson.lesson_type,
                'module_title': progress.lesson.module.title,
                'module_order': progress.lesson.module.order,
                'lesson_order': progress.lesson.order,
                'started_at': progress.started_at.isoformat() if progress.started_at else None,
                'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            })

        return lessons

    @classmethod
    def _collect_modules_history(cls, user, course):
        """Собрать историю завершения модулей"""
        from content.models import Module
        from progress.models import LessonProgress

        modules = []
        course_modules = Module.objects.filter(course=course).order_by('order')

        for module in course_modules:
            # Получаем последний завершенный урок модуля
            last_lesson = LessonProgress.objects.filter(
                user=user,
                lesson__module=module,
                is_completed=True
            ).order_by('-completed_at').first()

            if last_lesson:
                total_lessons = module.lessons.count()
                completed_lessons = LessonProgress.objects.filter(
                    user=user,
                    lesson__module=module,
                    is_completed=True
                ).count()

                modules.append({
                    'module_id': module.id,
                    'module_title': module.title,
                    'module_order': module.order,
                    'total_lessons': total_lessons,
                    'completed_lessons': completed_lessons,
                    'completed_at': last_lesson.completed_at.isoformat() if last_lesson.completed_at else None,
                })

        return modules

    @classmethod
    def _collect_quizzes_history(cls, user, course):
        """Собрать историю тестов с ответами"""
        from quizzes.models import QuizAttempt

        quizzes = []
        attempts = QuizAttempt.objects.filter(
            user=user,
            quiz__lesson__module__course=course,
            status='completed'
        ).select_related(
            'quiz', 'quiz__lesson'
        ).prefetch_related(
            'responses', 'responses__question', 'responses__selected_answers'
        ).order_by('quiz__lesson__order', 'attempt_number')

        for attempt in attempts:
            questions_data = []

            for response in attempt.responses.all():
                question = response.question

                # Собираем выбранные ответы
                selected = [a.answer_text for a in response.selected_answers.all()]

                # Собираем правильные ответы
                correct = [a.answer_text for a in question.answers.filter(is_correct=True)]

                questions_data.append({
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'user_answers': selected,
                    'correct_answers': correct,
                    'is_correct': response.is_correct,
                    'points_earned': response.points_earned,
                    'max_points': question.points,
                })

            quizzes.append({
                'quiz_id': attempt.quiz.id,
                'lesson_title': attempt.quiz.lesson.title,
                'attempt_number': attempt.attempt_number,
                'score_percentage': float(attempt.score_percentage) if attempt.score_percentage else 0,
                'passed': attempt.is_passed(),
                'passing_score': attempt.quiz.passing_score,
                'started_at': attempt.started_at.isoformat() if attempt.started_at else None,
                'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                'questions': questions_data,
            })

        return quizzes

    @classmethod
    def _collect_assignments_history(cls, user, course):
        """Собрать историю ДЗ (без комментариев)"""
        from assignments.models import AssignmentSubmission

        assignments = []
        submissions = AssignmentSubmission.objects.filter(
            user=user,
            assignment__lesson__module__course=course
        ).select_related(
            'assignment', 'assignment__lesson', 'reviewed_by'
        ).order_by('assignment__lesson__order', 'submission_number')

        for submission in submissions:
            assignment = submission.assignment

            assignments.append({
                'assignment_id': assignment.id,
                'lesson_title': assignment.lesson.title,
                'submission_number': submission.submission_number,
                'status': submission.status,
                'score': submission.score,
                'max_score': assignment.max_score,
                'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
                'reviewed_at': submission.reviewed_at.isoformat() if submission.reviewed_at else None,
                'reviewer_name': submission.reviewed_by.get_full_name() if submission.reviewed_by else None,
                'student_answer': submission.submission_text or '',
                'student_file': submission.submission_file.url if submission.submission_file else None,
                'instructor_feedback': submission.feedback or '',
            })

        return assignments

    # === INSTRUCTOR DOSSIER ===

    @classmethod
    def create_or_update_instructor_dossier(cls, user):
        """
        Создать или обновить досье инструктора.

        Args:
            user: объект User с ролью instructor/super_instructor

        Returns:
            InstructorDossier
        """
        from assignments.models import AssignmentSubmission
        from groups.models import Group
        from graduates.models import Graduate

        # Получаем или создаем досье
        dossier, created = InstructorDossier.objects.get_or_create(
            user=user,
            defaults={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'middle_name': getattr(user, 'middle_name', '') or '',
                'email': user.email,
                'phone': getattr(user, 'phone', '') or '',
                'role': user.role,
                'role_assigned_at': timezone.now(),
                'registered_at': user.date_joined,
            }
        )

        # Обновляем личные данные
        dossier.first_name = user.first_name
        dossier.last_name = user.last_name
        dossier.middle_name = getattr(user, 'middle_name', '') or ''
        dossier.email = user.email
        dossier.phone = getattr(user, 'phone', '') or ''
        dossier.role = user.role

        # Статистика по группам
        assigned_groups = user.assigned_groups.all()
        dossier.total_groups_led = assigned_groups.count()

        # Статистика по студентам
        from groups.models import GroupMembership
        total_students = GroupMembership.objects.filter(
            group__in=assigned_groups
        ).values('user').distinct().count()
        dossier.total_students_taught = total_students

        # Статистика по выпускникам
        total_graduates = Graduate.objects.filter(
            group__in=assigned_groups,
            status='graduated'
        ).count()
        dossier.total_graduates = total_graduates

        # Статистика по ДЗ
        reviews = AssignmentSubmission.objects.filter(reviewed_by=user)
        dossier.total_assignments_reviewed = reviews.count()
        dossier.total_assignments_passed = reviews.filter(status='passed').count()
        dossier.total_assignments_rejected = reviews.filter(status='needs_revision').count()

        # Средняя оценка
        avg_score = reviews.filter(score__isnull=False).aggregate(Avg('score'))
        dossier.average_score_given = avg_score['score__avg'] or 0

        # История групп
        groups_history = []
        for group in assigned_groups:
            students_count = GroupMembership.objects.filter(group=group).count()
            graduates_count = Graduate.objects.filter(group=group, status='graduated').count()

            groups_history.append({
                'group_id': group.id,
                'group_name': group.name,
                'course_title': group.course.title if group.course else '',
                'students_count': students_count,
                'graduates_count': graduates_count,
                'created_at': group.created_at.isoformat() if group.created_at else None,
            })

        dossier.groups_history = groups_history

        # Сводка проверок по месяцам
        from django.db.models.functions import TruncMonth
        reviews_by_month = reviews.annotate(
            month=TruncMonth('reviewed_at')
        ).values('month').annotate(count=Count('id')).order_by('-month')[:12]

        dossier.reviews_summary = {
            'by_month': [
                {
                    'month': r['month'].isoformat() if r['month'] else None,
                    'count': r['count']
                }
                for r in reviews_by_month
            ]
        }

        dossier.save()

        action = "Создано" if created else "Обновлено"
        logger.info(f"✅ {action} досье инструктора: {dossier}")

        return dossier

    @classmethod
    def update_all_instructor_dossiers(cls):
        """Обновить досье всех инструкторов (для cron job)"""
        from account.models import User

        instructors = User.objects.filter(
            role__in=['instructor', 'super_instructor']
        )

        count = 0
        for instructor in instructors:
            cls.create_or_update_instructor_dossier(instructor)
            count += 1

        logger.info(f"✅ Обновлено досье инструкторов: {count}")
        return count