from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from progress.models import LessonProgress
from .models import QuizLesson, QuizAttempt, QuizResponse, QuizQuestion
from .serializers import (
    QuizLessonDetailSerializer,
    QuizSubmitSerializer,
    QuizQuestionWithCorrectSerializer,
    QuizAttemptSerializer,
    QuizAnswerWithCorrectSerializer
)


def _format_available_in(available_at):
    """Форматировать время доступности в человекочитаемый вид"""
    if not available_at:
        return None

    delta = available_at - timezone.now()

    if delta.total_seconds() < 0:
        return "доступен сейчас"

    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)

    if hours > 0 and minutes > 0:
        return f"через {hours} ч. {minutes} мин."
    elif hours > 0:
        return f"через {hours} ч."
    else:
        return f"через {minutes} мин."


@api_view(['POST'])
def start_quiz(request, quiz_id):
    """
    Начать попытку прохождения теста

    POST /api/quizzes/{id}/start/
    """
    import random

    quiz = get_object_or_404(QuizLesson, id=quiz_id)

    # Проверка: может ли пользователь начать тест
    can_attempt, message = quiz.can_user_attempt(request.user)
    if not can_attempt:
        return Response(
            {'error': message},
            status=status.HTTP_403_FORBIDDEN
        )

    # Подсчет номера попытки
    attempts_count = quiz.attempts.filter(user=request.user).count()
    attempt_number = attempts_count + 1

    # Получаем вопросы
    questions = list(quiz.questions.all().order_by('order'))

    # Перемешиваем вопросы если нужно
    if quiz.shuffle_questions:
        random.shuffle(questions)

    # Сохраняем порядок вопросов
    questions_order = [q.id for q in questions]

    # Создание попытки с сохраненным порядком
    attempt = QuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        attempt_number=attempt_number,
        status='in_progress',
        questions_order=questions_order  # ← СОХРАНЯЕМ ПОРЯДОК
    )

    # Возвращаем информацию о попытке и вопросы
    return Response({
        'attempt_id': attempt.id,
        'attempt_number': attempt.attempt_number,
        'started_at': attempt.started_at,
        'time_limit_minutes': quiz.time_limit_minutes,
        'quiz': QuizLessonDetailSerializer(quiz, context={'request': request, 'questions': questions}).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, attempt_id):
    """
    Отправить ответы и завершить тест

    POST /api/quizzes/attempts/{id}/submit/

    Body:
    {
        "answers": [
            {"question_id": 1, "answer_ids": [2]},
            {"question_id": 2, "answer_ids": [1, 3]}
        ]
    }
    """
    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        user=request.user
    )

    # Проверка: попытка еще в процессе?
    if attempt.status != 'in_progress':
        return Response(
            {'error': 'Попытка уже завершена'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Валидация данных
    serializer = QuizSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    answers_data = serializer.validated_data['answers']

    # Обработка ответов в транзакции
    with transaction.atomic():
        correct_count = 0
        total_questions = len(answers_data)

        for answer_data in answers_data:
            question_id = answer_data['question_id']
            answer_ids = answer_data['answer_ids']

            # Получаем вопрос
            question = get_object_or_404(
                QuizQuestion,
                id=question_id,
                quiz=attempt.quiz
            )

            # Получаем ответы в том порядке, как они были показаны
            # (из клиента должен прийти порядок, или восстанавливаем из attempt)
            answers = list(question.answers.all().order_by('order'))

            # Если тест перемешивает ответы - используем порядок из attempt
            if attempt.quiz.shuffle_answers:
                # Порядок должен быть сохранен на клиенте и прислан с ответом
                # Или мы можем восстановить его из предыдущего шага
                answers_order = answer_data.get('answers_order', [a.id for a in answers])
            else:
                answers_order = [a.id for a in answers]

            # Создаем ответ пользователя
            response = QuizResponse.objects.create(
                attempt=attempt,
                question=question,
                answers_order=answers_order  # ← СОХРАНЯЕМ ПОРЯДОК
            )

            # Добавляем выбранные ответы
            response.selected_answers.set(answer_ids)

            # Проверяем правильность и начисляем баллы
            response.check_answer()

            if response.is_correct:
                correct_count += 1

        # Завершаем попытку
        attempt.complete()

        # Проверка: пройден ли тест
        passed = attempt.is_passed()

        # Подготовка результата
        result_data = {
            'success': True,
            'passed': passed,
            'score': attempt.score_percentage,
            'passing_score': attempt.quiz.passing_score,
            'correct_answers': correct_count,
            'total_questions': total_questions,
            'attempt_number': attempt.attempt_number
        }

        # Если тест пройден - обновляем прогресс урока
        if passed:
            from progress.models import CourseEnrollment

            # ИСПРАВЛЕНО: get_or_create вместо get
            lesson_progress, created = LessonProgress.objects.get_or_create(
                user=request.user,
                lesson=attempt.quiz.lesson,
                defaults={'is_completed': False}
            )

            # Завершаем урок с данными о тесте
            lesson_progress.mark_completed({
                'quiz_score': attempt.score_percentage,
                'quiz_attempt': attempt.attempt_number
            })

            # Получаем enrollment и курс
            course = lesson_progress.lesson.module.course
            enrollment = CourseEnrollment.objects.get(
                user=request.user,
                course=course
            )

            # Подсчитываем прогресс
            total_lessons = course.get_lessons_count()
            completed_lessons = LessonProgress.objects.filter(
                user=request.user,
                lesson__module__course=course,
                is_completed=True
            ).count()

            percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

            # Добавляем прогресс курса
            course_progress_data = {
                'percentage': round(percentage, 2),
                'completed_lessons': completed_lessons,
                'total_lessons': total_lessons
            }
            result_data['course_progress'] = course_progress_data

            # Получаем следующий урок
            next_lesson = lesson_progress.lesson.get_next_lesson()

            # Добавляем следующий урок
            if next_lesson:
                next_lesson_progress, created = LessonProgress.objects.get_or_create(
                    user=request.user,
                    lesson=next_lesson
                )

                # ВСЕГДА пересчитываем доступность после завершения предыдущего
                next_lesson_progress.calculate_available_at()

                # Форматируем время доступности
                available_in = _format_available_in(next_lesson_progress.available_at)

                result_data['next_lesson'] = {
                    'id': next_lesson.id,
                    'title': next_lesson.title,
                    'type': next_lesson.lesson_type,
                    'is_available': next_lesson_progress.is_available(),
                    'available_in': available_in
                }

        # Показываем правильные ответы если включено
        if attempt.quiz.show_correct_answers:
            questions_with_answers = []

            # Используем сохраненный порядок вопросов
            questions_ids = attempt.questions_order if attempt.questions_order else []

            if questions_ids:
                # Восстанавливаем порядок вопросов как при прохождении
                responses_dict = {r.question_id: r for r in attempt.responses.all()}

                for question_id in questions_ids:
                    response = responses_dict.get(question_id)
                    if not response:
                        continue

                    question = response.question
                    question_data = QuizQuestionWithCorrectSerializer(question).data

                    # Используем сохраненный порядок ответов
                    if response.answers_order:
                        # Восстанавливаем порядок ответов
                        answers_dict = {a.id: a for a in question.answers.all()}
                        ordered_answers = []
                        for answer_id in response.answers_order:
                            if answer_id in answers_dict:
                                ordered_answers.append(answers_dict[answer_id])

                        question_data['answers'] = QuizAnswerWithCorrectSerializer(ordered_answers, many=True).data

                    question_data['user_selected_ids'] = list(
                        response.selected_answers.values_list('id', flat=True)
                    )
                    question_data['is_correct'] = response.is_correct
                    question_data['points_earned'] = response.points_earned
                    questions_with_answers.append(question_data)
            else:
                # Fallback: старый способ (для старых попыток без сохраненного порядка)
                for response in attempt.responses.all():
                    question_data = QuizQuestionWithCorrectSerializer(response.question).data
                    question_data['user_selected_ids'] = list(
                        response.selected_answers.values_list('id', flat=True)
                    )
                    question_data['is_correct'] = response.is_correct
                    question_data['points_earned'] = response.points_earned
                    questions_with_answers.append(question_data)

            result_data['questions'] = questions_with_answers

        return Response(result_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_quiz_attempts(request):
    """
    Получить историю попыток пользователя

    GET /api/quizzes/attempts/
    """
    attempts = QuizAttempt.objects.filter(
        user=request.user
    ).select_related('quiz__lesson').order_by('-started_at')

    serializer = QuizAttemptSerializer(attempts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quiz_attempt_detail(request, attempt_id):
    """
    Детали конкретной попытки с правильными ответами

    GET /api/quizzes/attempts/{id}/
    """
    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        user=request.user
    )

    # Только для завершенных попыток
    if attempt.status != 'completed':
        return Response(
            {'error': 'Попытка еще не завершена'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Только если показ правильных ответов включен
    if not attempt.quiz.show_correct_answers:
        return Response(
            {'error': 'Просмотр правильных ответов отключен'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Формируем детали с сохраненным порядком
    questions_with_answers = []

    # Используем сохраненный порядок вопросов
    questions_ids = attempt.questions_order if attempt.questions_order else []

    if questions_ids:
        responses_dict = {r.question_id: r for r in attempt.responses.all()}

        for question_id in questions_ids:
            response = responses_dict.get(question_id)
            if not response:
                continue

            question = response.question
            question_data = QuizQuestionWithCorrectSerializer(question).data

            # Используем сохраненный порядок ответов
            if response.answers_order:
                answers_dict = {a.id: a for a in question.answers.all()}
                ordered_answers = []
                for answer_id in response.answers_order:
                    if answer_id in answers_dict:
                        ordered_answers.append(answers_dict[answer_id])

                question_data['answers'] = QuizAnswerWithCorrectSerializer(ordered_answers, many=True).data

            question_data['user_selected_ids'] = list(
                response.selected_answers.values_list('id', flat=True)
            )
            question_data['is_correct'] = response.is_correct
            question_data['points_earned'] = response.points_earned
            questions_with_answers.append(question_data)
    else:
        # Fallback для старых попыток
        for response in attempt.responses.all():
            question_data = QuizQuestionWithCorrectSerializer(response.question).data
            question_data['user_selected_ids'] = list(
                response.selected_answers.values_list('id', flat=True)
            )
            question_data['is_correct'] = response.is_correct
            question_data['points_earned'] = response.points_earned
            questions_with_answers.append(question_data)

    return Response({
        'attempt': QuizAttemptSerializer(attempt).data,
        'passed': attempt.is_passed(),
        'questions': questions_with_answers
    })