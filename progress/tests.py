from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from account.models import User
from content.models import Course, Module, Lesson
from groups.models import Group
from progress.models import CourseEnrollment, LessonProgress


class ProgressTestBase(TestCase):
    """
    Общие фикстуры. Создаёт user, course, module, 3 lessons, group.
    Добавляет студента в группу (сигнал создаёт enrollment + lesson progress).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            iin='123456789012',
            first_name='Test',
            last_name='Student',
        )
        self.manager = User.objects.create_user(
            email='manager@test.com',
            password='testpass123',
            iin='123456789099',
            first_name='Manager',
            last_name='User',
            role='manager',
        )
        self.course = Course.objects.create(title='Test Course')
        self.module = Module.objects.create(
            course=self.course, title='Module 1', order=0,
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module, title='Lesson 1', lesson_type='text', order=0,
            requires_previous_completion=False,
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module, title='Lesson 2', lesson_type='text', order=1,
            access_delay_hours=0,
        )
        self.lesson3 = Lesson.objects.create(
            module=self.module, title='Lesson 3', lesson_type='text', order=2,
            access_delay_hours=0,
        )
        self.group = Group.objects.create(
            course=self.course,
            name='Test Group',
            deadline_type='personal_days',
            deadline_days=90,
            max_students=0,
            is_active=True,
        )
        # Сигнал создаст enrollment + lesson progress
        self.group.add_student(self.user)
        self.enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )


# ─── CourseEnrollment.calculate_progress() ─────────────────────────

class CourseEnrollmentCalculateProgressTest(ProgressTestBase):

    def test_zero_completed(self):
        """0 из 3 уроков → 0%."""
        self.enrollment.calculate_progress()
        self.assertEqual(self.enrollment.progress_percentage, 0)
        self.assertEqual(self.enrollment.completed_lessons_count, 0)

    def test_partial(self):
        """1 из 3 уроков → ~33.33%."""
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.is_completed = True
        lp.completed_at = timezone.now()
        lp.save()

        self.enrollment.calculate_progress()
        self.assertAlmostEqual(
            float(self.enrollment.progress_percentage), 33.33, places=1,
        )
        self.assertEqual(self.enrollment.completed_lessons_count, 1)

    def test_all_completed(self):
        """3 из 3 уроков → 100%."""
        for lesson in [self.lesson1, self.lesson2, self.lesson3]:
            lp = LessonProgress.objects.get(user=self.user, lesson=lesson)
            lp.is_completed = True
            lp.completed_at = timezone.now()
            lp.save()

        self.enrollment.calculate_progress()
        self.assertEqual(float(self.enrollment.progress_percentage), 100.0)
        self.assertEqual(self.enrollment.completed_lessons_count, 3)

    def test_no_lessons_in_course(self):
        """Курс без уроков → 0%."""
        empty_course = Course.objects.create(title='Empty Course')
        Module.objects.create(course=empty_course, title='Empty Module', order=0)
        empty_group = Group.objects.create(
            course=empty_course, name='Empty Group',
            deadline_type='personal_days', deadline_days=90,
        )
        empty_group.add_student(self.user)
        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=empty_course,
        )
        enrollment.calculate_progress()
        self.assertEqual(enrollment.progress_percentage, 0)
        self.assertEqual(enrollment.completed_lessons_count, 0)


# ─── CourseEnrollment.reset_progress() ─────────────────────────────

class CourseEnrollmentResetProgressTest(ProgressTestBase):

    def test_clears_lesson_progress(self):
        """После reset_progress LessonProgress удалён."""
        self.enrollment.reset_progress()
        count = LessonProgress.objects.filter(
            user=self.user, lesson__module__course=self.course,
        ).count()
        self.assertEqual(count, 0)

    def test_clears_counters(self):
        """Счётчики enrollment сбрасываются."""
        self.enrollment.progress_percentage = 50
        self.enrollment.completed_lessons_count = 2
        self.enrollment.last_activity_at = timezone.now()
        self.enrollment.save()

        self.enrollment.reset_progress()
        self.assertEqual(self.enrollment.progress_percentage, 0)
        self.assertEqual(self.enrollment.completed_lessons_count, 0)
        self.assertIsNone(self.enrollment.last_activity_at)

    def test_clears_quiz_attempts(self):
        """QuizAttempt для курса удаляются при reset."""
        from quizzes.models import QuizLesson, QuizAttempt

        quiz_lesson = Lesson.objects.create(
            module=self.module, title='Quiz Lesson', lesson_type='quiz', order=3,
        )
        quiz = QuizLesson.objects.create(
            lesson=quiz_lesson, passing_score=70,
        )
        QuizAttempt.objects.create(
            user=self.user, quiz=quiz, status='completed',
            score_percentage=80,
        )

        self.enrollment.reset_progress()
        self.assertEqual(
            QuizAttempt.objects.filter(
                user=self.user,
                quiz__lesson__module__course=self.course,
            ).count(),
            0,
        )


# ─── CourseEnrollment access ───────────────────────────────────────

class CourseEnrollmentAccessTest(ProgressTestBase):

    def test_has_access_with_active_membership(self):
        self.assertTrue(self.enrollment.has_access())

    def test_has_access_without_membership(self):
        self.group.remove_student(self.user)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.has_access())

    def test_has_access_no_group(self):
        self.enrollment.group = None
        self.enrollment.save()
        self.assertFalse(self.enrollment.has_access())

    def test_sync_active_status_deactivates(self):
        self.group.remove_student(self.user)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_active)


# ─── LessonProgress.mark_completed() ──────────────────────────────

class LessonProgressMarkCompletedTest(ProgressTestBase):

    def test_sets_fields(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.mark_completed()
        self.assertTrue(lp.is_completed)
        self.assertIsNotNone(lp.completed_at)

    def test_updates_enrollment_progress(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.mark_completed()
        self.enrollment.refresh_from_db()
        self.assertAlmostEqual(
            float(self.enrollment.progress_percentage), 33.33, places=1,
        )

    def test_with_completion_data(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.mark_completed(completion_data={'score': 95})
        self.assertEqual(lp.completion_data['score'], 95)

    def test_idempotent(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.mark_completed()
        first_completed_at = lp.completed_at

        lp.mark_completed()
        self.assertEqual(lp.completed_at, first_completed_at)

    def test_updates_next_lesson_available_at(self):
        """После завершения lesson1, lesson2 становится доступен."""
        lp1 = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp2 = LessonProgress.objects.get(user=self.user, lesson=self.lesson2)

        # До завершения lesson1 — lesson2 недоступен
        self.assertFalse(lp2.is_available())

        lp1.mark_completed()
        lp2.refresh_from_db()
        self.assertTrue(lp2.is_available())

    @patch('notifications.services.NotificationService.notify_graduation')
    def test_100_percent_creates_graduate(self, mock_notify):
        """При 100% прогрессе создаётся Graduate."""
        from graduates.models import Graduate

        for lesson in [self.lesson1, self.lesson2, self.lesson3]:
            lp = LessonProgress.objects.get(user=self.user, lesson=lesson)
            lp.mark_completed()

        self.assertTrue(
            Graduate.objects.filter(
                user=self.user, course=self.course, status='pending',
            ).exists()
        )

    @patch('notifications.services.NotificationService.notify_graduation')
    def test_100_percent_deactivates_enrollment(self, mock_notify):
        """При 100% enrollment деактивируется."""
        for lesson in [self.lesson1, self.lesson2, self.lesson3]:
            lp = LessonProgress.objects.get(user=self.user, lesson=lesson)
            lp.mark_completed()

        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_active)


# ─── LessonProgress availability ──────────────────────────────────

class LessonProgressAvailabilityTest(ProgressTestBase):

    def test_first_lesson_always_available(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        self.assertTrue(lp.is_available())

    def test_second_lesson_unavailable_before_first(self):
        lp2 = LessonProgress.objects.get(user=self.user, lesson=self.lesson2)
        self.assertFalse(lp2.is_available())

    def test_second_lesson_available_after_first_completed(self):
        lp1 = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp1.mark_completed()
        lp2 = LessonProgress.objects.get(user=self.user, lesson=self.lesson2)
        lp2.refresh_from_db()
        self.assertTrue(lp2.is_available())

    def test_delay_makes_unavailable(self):
        """Урок с access_delay_hours=24 недоступен сразу после prev."""
        self.lesson2.access_delay_hours = 24
        self.lesson2.save()

        lp1 = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp1.mark_completed()

        lp2 = LessonProgress.objects.get(user=self.user, lesson=self.lesson2)
        lp2.refresh_from_db()
        self.assertFalse(lp2.is_available())

    def test_completed_lesson_always_available(self):
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.is_completed = True
        lp.completed_at = timezone.now()
        lp.available_at = None
        lp.save()
        self.assertTrue(lp.is_available())
