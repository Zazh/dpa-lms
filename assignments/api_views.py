from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from progress.models import LessonProgress
from .models import AssignmentLesson, AssignmentSubmission, AssignmentComment
from .serializers import (
    AssignmentSubmissionSerializer,
    AssignmentSubmissionDetailSerializer,
    AssignmentSubmitSerializer,
    CommentCreateSerializer,
    AssignmentCommentSerializer  # ← ДОБАВЛЕНО
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def submit_assignment(request, assignment_id):
    """
    Сдать домашнее задание

    POST /api/assignments/{id}/submit/

    Multipart form-data:
    - submission_text: текст ответа (опционально)
    - submission_file: файл (опционально)
    """
    assignment = get_object_or_404(AssignmentLesson, id=assignment_id)

    # Проверка: зачислен ли на курс
    try:
        lesson_progress = LessonProgress.objects.get(
            user=request.user,
            lesson=assignment.lesson
        )
    except LessonProgress.DoesNotExist:
        return Response(
            {'error': 'Вы не зачислены на этот курс'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Проверка: доступен ли урок
    if not lesson_progress.is_available():
        return Response(
            {'error': 'Урок недоступен'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Проверка: уже завершен?
    if lesson_progress.is_completed:
        return Response(
            {'error': 'Задание уже зачтено'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Проверка: есть ли работа на проверке
    existing_submission = AssignmentSubmission.objects.filter(
        user=request.user,
        assignment=assignment,
        status='in_review'
    ).first()

    if existing_submission:
        return Response(
            {'error': 'У вас уже есть работа на проверке'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Проверка: можно ли пересдать
    last_submission = AssignmentSubmission.objects.filter(
        user=request.user,
        assignment=assignment
    ).order_by('-submission_number').first()

    if last_submission:
        if last_submission.status == 'needs_revision':
            if not assignment.allow_resubmission:
                return Response(
                    {'error': 'Пересдача запрещена'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif last_submission.status in ['in_review', 'passed']:
            return Response(
                {'error': 'Невозможно сдать повторно'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Валидация данных
    serializer = AssignmentSubmitSerializer(
        data=request.data,
        context={'assignment': assignment}
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Определяем номер попытки
    submission_number = 1
    if last_submission:
        submission_number = last_submission.submission_number + 1

    # Создаем сдачу
    submission = AssignmentSubmission.objects.create(
        user=request.user,
        assignment=assignment,
        submission_number=submission_number,
        submission_text=serializer.validated_data.get('submission_text', ''),
        submission_file=serializer.validated_data.get('submission_file'),
        status='in_review'
    )

    return Response({
        'success': True,
        'message': 'Работа отправлена на проверку',
        'submission': AssignmentSubmissionDetailSerializer(
            submission,
            context={'request': request}
        ).data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_submissions(request):
    """
    Получить список своих сдач

    GET /api/assignments/my-submissions/
    """
    submissions = AssignmentSubmission.objects.filter(
        user=request.user
    ).select_related(
        'assignment__lesson',
        'reviewed_by'
    ).order_by('-submitted_at')

    serializer = AssignmentSubmissionSerializer(
        submissions,
        many=True,
        context={'request': request}
    )

    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def submission_detail(request, submission_id):
    """
    Детали конкретной сдачи

    GET /api/assignments/submissions/{id}/
    """
    submission = get_object_or_404(
        AssignmentSubmission,
        id=submission_id,
        user=request.user
    )

    serializer = AssignmentSubmissionDetailSerializer(
        submission,
        context={'request': request}
    )

    # Отметить комментарии как прочитанные
    submission.comments.filter(
        is_read=False
    ).exclude(
        author=request.user
    ).update(is_read=True)

    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request, submission_id):
    """
    Добавить комментарий к сдаче

    POST /api/assignments/submissions/{id}/comment/

    Body:
    {
        "message": "Текст комментария"
    }
    """
    submission = get_object_or_404(
        AssignmentSubmission,
        id=submission_id,
        user=request.user
    )

    serializer = CommentCreateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Создаем комментарий
    comment = AssignmentComment.objects.create(
        submission=submission,
        author=request.user,
        message=serializer.validated_data['message'],
        is_instructor=False
    )

    return Response({
        'success': True,
        'comment': AssignmentCommentSerializer(comment).data
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grade_assignment(request, submission_id):
    """
    Оценить домашнее задание (только преподаватель)

    POST /api/assignments/submissions/{id}/grade/

    Body:
    {
        "status": "passed" | "needs_revision" | "failed",
        "score": 85,  # для passed и failed
        "feedback": "Хорошая работа!"
    }
    """
    print(f"🟢 grade_assignment: START submission_id={submission_id}")

    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    print(f"🟢 Найдена сдача: {submission}")

    # ✅ Проверка прав: только инструктор курса может оценивать
    user = request.user

    # 1. Проверяем что пользователь — инструктор
    if not user.is_instructor():
        return Response(
            {'error': 'Только инструкторы могут оценивать задания'},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. Если не супер-инструктор — проверяем доступ к группе студента
    if not user.is_super_instructor():
        from progress.models import CourseEnrollment

        accessible_groups = user.get_accessible_groups()
        enrollment = CourseEnrollment.objects.filter(
            user=submission.user,
            course=submission.assignment.lesson.module.course,
            group__in=accessible_groups
        ).first()

        if not enrollment:
            return Response(
                {'error': 'У вас нет доступа к этой работе'},
                status=status.HTTP_403_FORBIDDEN
            )

    # Валидация
    status_value = request.data.get('status')
    print(f"🟢 status_value: {status_value}")

    if status_value not in ['passed', 'needs_revision', 'failed']:
        return Response(
            {'error': 'Неверный статус'},
            status=status.HTTP_400_BAD_REQUEST
        )

    feedback = request.data.get('feedback', '')
    score = request.data.get('score')
    print(f"🟢 score: {score}, feedback: {feedback[:50] if feedback else 'нет'}")

    # Применяем оценку
    if status_value == 'passed':
        if score is None:
            return Response(
                {'error': 'Укажите балл'},
                status=status.HTTP_400_BAD_REQUEST
            )
        print(f"🟢 Вызываем mark_passed()")
        submission.mark_passed(request.user, score, feedback)
        print(f"🟢 mark_passed() завершен")
        message = 'Работа зачтена'

    elif status_value == 'needs_revision':
        print(f"🟢 Вызываем mark_needs_revision()")
        submission.mark_needs_revision(request.user, feedback)
        print(f"🟢 mark_needs_revision() завершен")
        message = 'Отправлено на доработку'

    else:  # failed
        score = score or 0
        print(f"🟢 Вызываем mark_failed()")
        submission.mark_failed(request.user, feedback, score)
        print(f"🟢 mark_failed() завершен")
        message = 'Работа не зачтена'

    print(f"🟢 grade_assignment: END")

    return Response({
        'success': True,
        'message': message,
        'submission': AssignmentSubmissionDetailSerializer(
            submission,
            context={'request': request}
        ).data
    })