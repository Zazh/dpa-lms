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