from django.core.management.base import BaseCommand

from content.models import VideoLesson


class Command(BaseCommand):
    help = 'Синхронизация длительности видео из Vimeo API для всех VideoLesson'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что изменится, без сохранения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        videos = VideoLesson.objects.select_related('lesson').all()

        self.stdout.write(f'Всего видео-уроков: {videos.count()}')
        if dry_run:
            self.stdout.write(self.style.WARNING('Режим dry-run: изменения НЕ сохраняются'))
        self.stdout.write('')

        updated = 0
        unchanged = 0
        errors = 0

        for v in videos:
            duration = v._fetch_vimeo_duration()

            if duration is None:
                self.stdout.write(self.style.ERROR(
                    f'  ERROR | {v.lesson.title} | Vimeo: {v.vimeo_video_id}'
                ))
                errors += 1
                continue

            old = v.video_duration
            if old != duration:
                if not dry_run:
                    VideoLesson.objects.filter(pk=v.pk).update(video_duration=duration)
                self.stdout.write(self.style.SUCCESS(
                    f'  UPDATED | {v.lesson.title} | {old}s -> {duration}s'
                ))
                updated += 1
            else:
                self.stdout.write(f'  OK | {v.lesson.title} | {duration}s')
                unchanged += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Обновлено: {updated}'))
        self.stdout.write(f'Без изменений: {unchanged}')
        if errors:
            self.stdout.write(self.style.ERROR(f'Ошибок: {errors}'))
