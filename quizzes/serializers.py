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
    """Подробная информация о тесте"""

    questions = serializers.SerializerMethodField()
    questions_count = serializers.IntegerField(source='get_questions_count', read_only=True)
    total_points = serializers.IntegerField(source='get_total_points', read_only=True)
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
        """Получить вопросы с учетом перемешивания"""

        # Проверяем есть ли предопределенный порядок из контекста
        questions = self.context.get('questions')

        if questions is None:
            # Если порядка нет - берем из базы
            questions = list(obj.questions.all().order_by('order'))

            # Перемешиваем если нужно
            if obj.shuffle_questions:
                random.shuffle(questions)

        # Сериализуем вопросы
        serialized_questions = []
        for question in questions:
            # Получаем ответы
            answers = list(question.answers.all().order_by('order'))

            # Перемешиваем ответы если нужно
            if obj.shuffle_answers:
                random.shuffle(answers)

            # Сохраняем порядок ответов для этого вопроса
            answers_order = [a.id for a in answers]

            question_data = QuizQuestionSerializer(question).data
            question_data['answers'] = QuizAnswerSerializer(answers, many=True).data
            question_data['answers_order'] = answers_order  # ← ДОБАВЛЯЕМ ПОРЯДОК

            serialized_questions.append(question_data)

        return serialized_questions

    def get_can_attempt(self, obj):
        """Может ли пользователь пройти тест"""
        user = self.context.get('request').user
        can_attempt, message = obj.can_user_attempt(user)
        return {
            'allowed': can_attempt,
            'message': message
        }

    def get_user_attempts_count(self, obj):
        """Количество попыток пользователя"""
        user = self.context.get('request').user
        return obj.attempts.filter(user=user).count()

    def get_best_score(self, obj):
        """Лучший результат пользователя"""
        user = self.context.get('request').user
        best_attempt = obj.attempts.filter(
            user=user,
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