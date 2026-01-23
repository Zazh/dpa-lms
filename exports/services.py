"""
Сервисы для генерации PDF документов
"""
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


class PDFGenerator:
    """Базовый генератор PDF"""

    def __init__(self):
        self.font_config = FontConfiguration()

    def generate_from_template(
        self,
        template_name: str,
        context: dict,
        css_files: list[str] = None
    ) -> bytes:
        """
        Генерирует PDF из Django шаблона

        Args:
            template_name: путь к шаблону
            context: контекст для рендеринга
            css_files: список путей к CSS файлам (относительно static)

        Returns:
            bytes: PDF документ
        """
        html_string = render_to_string(template_name, context)
        html = HTML(string=html_string)

        stylesheets = []
        if css_files:
            for css_path in css_files:
                absolute_path = finders.find(css_path)
                if absolute_path:
                    stylesheets.append(
                        CSS(filename=absolute_path, font_config=self.font_config)
                    )

        return html.write_pdf(
            stylesheets=stylesheets,
            font_config=self.font_config
        )


class QuizResultPDFService:
    """Сервис генерации PDF для результатов тестов"""

    CSS_FILES = [
        'exports/css/quiz_result.css',
    ]

    def __init__(self):
        self.generator = PDFGenerator()

    def generate(self, attempt) -> bytes:
        """
        Генерирует PDF с результатами теста

        Args:
            attempt: QuizAttempt instance

        Returns:
            bytes: PDF документ
        """
        responses = attempt.responses.select_related(
            'question'
        ).prefetch_related(
            'selected_answers',
            'question__answers'
        ).order_by('question__order')

        total_questions = responses.count()
        correct_answers = sum(1 for r in responses if r.is_correct)

        context = {
            'attempt': attempt,
            'quiz': attempt.quiz,
            'student': attempt.user,
            'course': attempt.quiz.lesson.module.course,
            'responses': responses,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'passed': attempt.score_percentage >= attempt.quiz.passing_score,
        }

        return self.generator.generate_from_template(
            'exports/quiz_result.html',
            context,
            css_files=self.CSS_FILES
        )

    def generate_from_dossier(self, dossier, quiz_index: int) -> bytes:
        """
        Генерирует PDF с результатами теста из данных досье

        Args:
            dossier: StudentDossier instance
            quiz_index: индекс теста в quizzes_history

        Returns:
            bytes: PDF документ
        """
        quizzes = dossier.quizzes_history

        if not quizzes or quiz_index >= len(quizzes):
            raise ValueError('Тест не найден в досье')

        quiz_data = quizzes[quiz_index]

        context = {
            'attempt': {
                'attempt_number': quiz_data.get('attempt_number', 1),
                'score_percentage': quiz_data.get('score_percentage', 0),
                'completed_at': quiz_data.get('completed_at', ''),
            },
            'quiz': {
                'lesson': {'title': quiz_data.get('lesson_title', '')},
                'passing_score': quiz_data.get('passing_score', 70),
            },
            'student': {
                'get_full_name': dossier.get_full_name(),
            },
            'course': {
                'title': dossier.course_title,
            },
            'responses': self._convert_questions_to_responses(quiz_data.get('questions', [])),
            'total_questions': len(quiz_data.get('questions', [])),
            'correct_answers': sum(1 for q in quiz_data.get('questions', []) if q.get('is_correct')),
            'passed': quiz_data.get('passed', False),
            'from_dossier': True,
        }

        return self.generator.generate_from_template(
            'exports/quiz_result.html',
            context,
            css_files=self.CSS_FILES
        )

    def _convert_questions_to_responses(self, questions: list) -> list:
        """Конвертирует формат вопросов из досье в формат для шаблона"""
        responses = []

        for q in questions:
            responses.append({
                'is_correct': q.get('is_correct', False),
                'question': {
                    'question_text': q.get('question_text', ''),
                },
                'user_answers': q.get('user_answers', []),
                'correct_answers': q.get('correct_answers', []),
                'points_earned': q.get('points_earned', 0),
                'max_points': q.get('max_points', 1),
            })

        return responses


class CertificatePDFService:
    """Сервис генерации сертификатов в PDF"""

    CSS_FILES = [
        'exports/css/certificate.css',
    ]

    def __init__(self):
        self.generator = PDFGenerator()

    def generate(self, graduate, with_stamp: bool = False) -> bytes:
        """
        Генерирует PDF сертификат из Graduate

        Args:
            graduate: Graduate instance
            with_stamp: добавить печать

        Returns:
            bytes: PDF документ
        """
        context = {
            'student_name': graduate.user.get_full_name(),
            'course_title': graduate.course.title,
            'certificate_number': graduate.certificate.number if hasattr(graduate, 'certificate') and graduate.certificate else '',
            'completed_at': graduate.completed_at,
            'group_name': graduate.group.name if graduate.group else '',
            'with_stamp': with_stamp,
        }

        return self.generator.generate_from_template(
            'exports/certificate.html',
            context,
            css_files=self.CSS_FILES
        )

    def generate_from_certificate(self, certificate, with_stamp: bool = False) -> bytes:
        """
        Генерирует PDF из модели Certificate

        Args:
            certificate: Certificate instance
            with_stamp: добавить печать

        Returns:
            bytes: PDF документ
        """
        context = {
            'student_name': certificate.holder_name,
            'course_title': certificate.course_title,
            'certificate_number': certificate.number,
            'completed_at': certificate.issued_at,
            'group_name': certificate.group_name,
            'with_stamp': with_stamp,
        }

        return self.generator.generate_from_template(
            'exports/certificate.html',
            context,
            css_files=self.CSS_FILES
        )

    def generate_from_dossier(self, dossier, with_stamp: bool = False) -> bytes:
        """
        Генерирует PDF сертификат из данных досье

        Args:
            dossier: StudentDossier instance
            with_stamp: добавить печать

        Returns:
            bytes: PDF документ
        """
        context = {
            'student_name': dossier.get_full_name(),
            'course_title': dossier.course_title,
            'certificate_number': dossier.certificate_number,
            'completed_at': dossier.completed_at,
            'group_name': dossier.group_name,
            'with_stamp': with_stamp,
            'from_dossier': True,
        }

        return self.generator.generate_from_template(
            'exports/certificate.html',
            context,
            css_files=self.CSS_FILES
        )