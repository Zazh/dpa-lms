from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Avg, F

from graduates.models import Graduate
from quizzes.models import QuizAttempt


class Command(BaseCommand):
    help = 'Пересчитать итоговые оценки выпускников (только сданные попытки)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без сохранения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        graduates = Graduate.objects.all()
        updated = 0

        for graduate in graduates:
            passed_attempts = QuizAttempt.objects.filter(
                user=graduate.user,
                quiz__lesson__module__course=graduate.course,
                status='completed',
                score_percentage__gte=F('quiz__passing_score'),
            )

            new_score = passed_attempts.aggregate(
                Avg('score_percentage')
            )['score_percentage__avg']

            old_score = graduate.final_score

            if old_score != new_score:
                self.stdout.write(
                    f'{graduate.user.email} | '
                    f'{graduate.course.title} | '
                    f'{old_score}% -> {round(new_score, 2)}%'
                )
                if not dry_run:
                    graduate.final_score = new_score
                    graduate.average_quiz_score = new_score
                    graduate.save(update_fields=['final_score', 'average_quiz_score'])
                updated += 1

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Пересчитано: {updated} из {graduates.count()}'
        ))
