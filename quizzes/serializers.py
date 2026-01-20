from rest_framework import serializers
from .models import QuizLesson, QuizQuestion, QuizAnswer, QuizAttempt, QuizResponse
import random


class QuizAnswerSerializer(serializers.ModelSerializer):
    """Сериализатор для вариантов ответов (БЕЗ is_correct)"""

    class Meta:
        model = QuizAnswer
        fields = ['id', 'answer_text', 'order']


class QuizAnswerWithCorrectSerializer(serializers.ModelSerializer):
    """Сериализатор с правильными ответами (после завершения)"""

    class Meta:
        model = QuizAnswer
        fields = ['id', 'answer_text', 'is_correct', 'order']


class QuizQuestionSerializer(serializers.ModelSerializer):
    """Сериализатор для вопросов теста (БЕЗ правильных ответов)"""

    answers = serializers.SerializerMethodField()

    class Meta:
        model = QuizQuestion
        fields = [
            'id',
            'question_type',
            'question_text',
            'points',
            'order',
            'answers'
        ]

    def get_answers(self, obj):
        """Получить варианты ответов (БЕЗ is_correct)"""
        answers = obj.answers.all().order_by('order')

        # Перемешивание если включено
        quiz = obj.quiz
        if quiz.shuffle_answers:
            answers = list(answers)
            random.shuffle(answers)

        return QuizAnswerSerializer(answers, many=True).data


class QuizQuestionWithCorrectSerializer(serializers.ModelSerializer):
    """Вопросы с правильными ответами (после завершения)"""

    answers = QuizAnswerWithCorrectSerializer(many=True, read_only=True)
    user_selected_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    class Meta:
        model = QuizQuestion
        fields = [
            'id',
            'question_type',
            'question_text',
            'explanation',
            'points',
            'order',
            'answers',
            'user_selected_ids'  # ID ответов которые выбрал пользователь
        ]


class QuizLessonDetailSerializer(serializers.ModelSerializer):
    """Подробная информация о тесте - ОПТИМИЗИРОВАНО"""

    questions = serializers.SerializerMethodField()
    questions_count = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    can_attempt = serializers.SerializerMethodField()
    user_attempts_count = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = QuizLesson
        fields = [
            'id',
            'passing_score',
            'max_attempts',
            'retry_delay_hours',
            'time_limit_minutes',
            'show_correct_answers',
            'questions_count',
            'total_points',
            'can_attempt',
            'user_attempts_count',
            'best_score',
            'questions'
        ]

    def get_questions(self, obj):
        """Получить вопросы с учетом перемешивания - ОПТИМИЗИРОВАНО"""

        # Проверяем есть ли предопределенный порядок из контекста
        questions = self.context.get('questions')

        if questions is None:
            # Используем prefetch (без дополнительных запросов!)
            questions = list(obj.questions.all())

            # Перемешиваем если нужно
            if obj.shuffle_questions:
                random.shuffle(questions)

        # Сериализуем вопросы
        serialized_questions = []
        for question in questions:
            # Ответы уже загружены через prefetch!
            answers = list(question.answers.all())

            # Перемешиваем ответы если нужно
            if obj.shuffle_answers:
                random.shuffle(answers)

            # Сохраняем порядок ответов
            answers_order = [a.id for a in answers]

            question_data = {
                'id': question.id,
                'question_type': question.question_type,
                'question_text': question.question_text,
                'points': question.points,
                'order': question.order,
                'answers': QuizAnswerSerializer(answers, many=True).data,
                'answers_order': answers_order
            }

            serialized_questions.append(question_data)

        return serialized_questions

    def get_questions_count(self, obj):
        """Количество вопросов - из prefetch без запроса"""
        return len(list(obj.questions.all()))

    def get_total_points(self, obj):
        """Сумма баллов - из prefetch без запроса"""
        return sum(q.points for q in obj.questions.all())

    def get_can_attempt(self, obj):
        """Может ли пользователь пройти тест"""
        request = self.context.get('request')
        if not request:
            return {'allowed': False, 'message': 'Не авторизован'}

        user = request.user

        # Используем prefetch если есть
        user_attempts = getattr(obj, 'user_attempts_list', None)

        if user_attempts is not None:
            # Логика проверки из prefetch
            attempts_count = len(user_attempts)

            if obj.max_attempts and attempts_count >= obj.max_attempts:
                return {'allowed': False, 'message': f'Достигнут лимит попыток ({obj.max_attempts})'}

            # Проверка задержки между попытками
            if obj.retry_delay_hours and user_attempts:
                from django.utils import timezone
                last_attempt = max(user_attempts, key=lambda a: a.started_at)
                if last_attempt.status == 'completed':
                    time_since = timezone.now() - last_attempt.completed_at
                    hours_passed = time_since.total_seconds() / 3600
                    if hours_passed < obj.retry_delay_hours:
                        remaining = obj.retry_delay_hours - hours_passed
                        return {
                            'allowed': False,
                            'message': f'Повторная попытка доступна через {int(remaining)} ч.'
                        }

            return {'allowed': True, 'message': 'Можно начать тест'}

        # Fallback к стандартному методу
        can_attempt, message = obj.can_user_attempt(user)
        return {'allowed': can_attempt, 'message': message}

    def get_user_attempts_count(self, obj):
        """Количество попыток пользователя - из prefetch"""
        user_attempts = getattr(obj, 'user_attempts_list', None)

        if user_attempts is not None:
            return len(user_attempts)

        # Fallback
        request = self.context.get('request')
        if not request:
            return 0
        return obj.attempts.filter(user=request.user).count()

    def get_best_score(self, obj):
        """Лучший результат пользователя - из prefetch"""
        user_attempts = getattr(obj, 'user_attempts_list', None)

        if user_attempts is not None:
            completed = [a for a in user_attempts if a.status == 'completed']
            if completed:
                best = max(completed, key=lambda a: a.score_percentage)
                return {
                    'score': float(best.score_percentage),
                    'passed': best.is_passed()
                }
            return None

        # Fallback
        request = self.context.get('request')
        if not request:
            return None

        best_attempt = obj.attempts.filter(
            user=request.user,
            status='completed'
        ).order_by('-score_percentage').first()

        if best_attempt:
            return {
                'score': float(best_attempt.score_percentage),
                'passed': best_attempt.is_passed()
            }
        return None


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Сериализатор попытки прохождения"""

    quiz_title = serializers.CharField(source='quiz.lesson.title', read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz_title',
            'attempt_number',
            'status',
            'score_percentage',
            'started_at',
            'completed_at',
            'duration'
        ]

    def get_duration(self, obj):
        """Длительность попытки"""
        seconds = obj.get_duration_seconds()
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return {
            'seconds': int(seconds),
            'formatted': f'{minutes}:{secs:02d}'
        }


class QuizSubmitSerializer(serializers.Serializer):
    """Сериализатор для отправки ответов"""

    answers = serializers.ListField(
        child=serializers.DictField(),
        help_text='[{"question_id": 1, "answer_ids": [2, 3]}]'
    )

    def validate_answers(self, value):
        """Валидация структуры ответов"""
        for answer in value:
            if 'question_id' not in answer:
                raise serializers.ValidationError('Отсутствует question_id')
            if 'answer_ids' not in answer:
                raise serializers.ValidationError('Отсутствует answer_ids')
            if not isinstance(answer['answer_ids'], list):
                raise serializers.ValidationError('answer_ids должен быть массивом')

        return value


class QuizResultSerializer(serializers.Serializer):
    """Результат прохождения теста"""

    success = serializers.BooleanField()
    passed = serializers.BooleanField()
    score = serializers.DecimalField(max_digits=5, decimal_places=2)
    passing_score = serializers.IntegerField()
    correct_answers = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    attempt_number = serializers.IntegerField()

    # Прогресс курса (если тест пройден)
    course_progress = serializers.DictField(required=False)
    next_lesson = serializers.DictField(required=False)

    # Детали ответов (если show_correct_answers = True)
    questions = QuizQuestionWithCorrectSerializer(many=True, required=False)