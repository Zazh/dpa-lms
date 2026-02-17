from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from account.models import User
from content.models import Course, Module, Lesson
from groups.models import Group
from progress.models import CourseEnrollment, LessonProgress
from graduates.models import Graduate


class GraduateTestBase(TestCase):
    """
    Общие фикстуры. Создаёт user, manager, course, module, 3 lessons, group.
    Зачисляет студента через add_student (сигнал создаёт enrollment + progress).
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
        )
        self.lesson3 = Lesson.objects.create(
            module=self.module, title='Lesson 3', lesson_type='text', order=2,
        )
        self.group = Group.objects.create(
            course=self.course,
            name='Test Group',
            deadline_type='personal_days',
            deadline_days=90,
        )
        self.group.add_student(self.user)
        self.enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )


# ─── Graduate.create_from_enrollment() ─────────────────────────────

class GraduateCreateFromEnrollmentTest(GraduateTestBase):

    def test_success(self):
        """Создаёт Graduate со status='pending'."""
        graduate = Graduate.create_from_enrollment(self.enrollment)
        self.assertIsNotNone(graduate)
        self.assertEqual(graduate.status, 'pending')
        self.assertEqual(graduate.user, self.user)
        self.assertEqual(graduate.course, self.course)
        self.assertEqual(graduate.group, self.group)

    def test_calculates_study_days(self):
        """total_study_days = разница между enrolled_at и now."""
        graduate = Graduate.create_from_enrollment(self.enrollment)
        expected_days = (timezone.now() - self.enrollment.enrolled_at).days
        self.assertEqual(graduate.total_study_days, expected_days)

    def test_calculates_avg_quiz_score(self):
        """Средний балл из QuizAttempt."""
        from quizzes.models import QuizLesson, QuizAttempt

        quiz_lesson = Lesson.objects.create(
            module=self.module, title='Quiz', lesson_type='quiz', order=3,
        )
        quiz = QuizLesson.objects.create(lesson=quiz_lesson, passing_score=70)
        QuizAttempt.objects.create(
            user=self.user, quiz=quiz, status='completed',
            score_percentage=80,
        )
        QuizAttempt.objects.create(
            user=self.user, quiz=quiz, status='completed',
            score_percentage=60, attempt_number=2,
        )

        graduate = Graduate.create_from_enrollment(self.enrollment)
        self.assertAlmostEqual(float(graduate.average_quiz_score), 70.0, places=1)

    def test_no_quizzes_zero_score(self):
        """Без тестов average_quiz_score = 0."""
        graduate = Graduate.create_from_enrollment(self.enrollment)
        self.assertEqual(float(graduate.average_quiz_score), 0)

    def test_duplicate_returns_none(self):
        """Повторный вызов возвращает None."""
        Graduate.create_from_enrollment(self.enrollment)
        result = Graduate.create_from_enrollment(self.enrollment)
        self.assertIsNone(result)


# ─── Graduate.approve_graduation() ─────────────────────────────────

class GraduateApproveGraduationTest(GraduateTestBase):

    def _create_pending_graduate(self):
        return Graduate.objects.create(
            user=self.user,
            course=self.course,
            group=self.group,
            status='pending',
        )

    def _make_certificate(self, graduate):
        from certificates.models import Certificate
        return Certificate.objects.create(
            user=self.user,
            graduate=graduate,
            course=self.course,
            number=f'TEST-{graduate.id}',
            issued_at=timezone.now().date(),
        )

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_approve_sets_status(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        """Status → 'graduated', graduated_at и graduated_by установлены."""
        graduate = self._create_pending_graduate()
        mock_cert.return_value = self._make_certificate(graduate)

        result = graduate.approve_graduation(self.manager)

        self.assertTrue(result)
        graduate.refresh_from_db()
        self.assertEqual(graduate.status, 'graduated')
        self.assertIsNotNone(graduate.graduated_at)
        self.assertEqual(graduate.graduated_by, self.manager)

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_approve_calls_certificate_service(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        graduate = self._create_pending_graduate()
        mock_cert.return_value = self._make_certificate(graduate)

        graduate.approve_graduation(self.manager)

        mock_cert.assert_called_once_with(graduate)

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_approve_calls_dossier_service(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        graduate = self._create_pending_graduate()
        mock_cert.return_value = self._make_certificate(graduate)

        graduate.approve_graduation(self.manager)

        mock_dossier.assert_called_once_with(graduate)

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_approve_triggers_pdf_task(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        graduate = self._create_pending_graduate()
        cert = self._make_certificate(graduate)
        mock_cert.return_value = cert

        graduate.approve_graduation(self.manager)

        mock_pdf.assert_called_once_with(cert.id)

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_approve_returns_false_if_not_pending(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        graduate = self._create_pending_graduate()
        graduate.status = 'graduated'
        graduate.save()

        result = graduate.approve_graduation(self.manager)

        self.assertFalse(result)
        mock_cert.assert_not_called()


# ─── Graduate.reject_graduation() ──────────────────────────────────

class GraduateRejectGraduationTest(GraduateTestBase):

    def _create_pending_graduate(self):
        return Graduate.objects.create(
            user=self.user,
            course=self.course,
            group=self.group,
            status='pending',
        )

    def _make_certificate(self, graduate):
        from certificates.models import Certificate
        return Certificate.objects.create(
            user=self.user,
            graduate=graduate,
            course=self.course,
            number=f'TEST-R-{graduate.id}',
            certificate_type='attended',
            issued_at=timezone.now().date(),
        )

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_reject_sets_status(self, mock_cert, mock_pdf):
        graduate = self._create_pending_graduate()
        mock_cert.return_value = self._make_certificate(graduate)

        result = graduate.reject_graduation(self.manager)

        self.assertTrue(result)
        graduate.refresh_from_db()
        self.assertEqual(graduate.status, 'rejected')
        self.assertIsNotNone(graduate.graduated_at)
        self.assertEqual(graduate.graduated_by, self.manager)

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_reject_creates_attended_certificate(self, mock_cert, mock_pdf):
        graduate = self._create_pending_graduate()
        mock_cert.return_value = self._make_certificate(graduate)

        graduate.reject_graduation(self.manager)

        mock_cert.assert_called_once_with(graduate, certificate_type='attended')

    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_reject_skips_certificate_when_flag_false(self, mock_cert):
        graduate = self._create_pending_graduate()

        graduate.reject_graduation(self.manager, create_attended_certificate=False)

        mock_cert.assert_not_called()

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_reject_returns_false_if_not_pending(self, mock_cert, mock_pdf):
        graduate = self._create_pending_graduate()
        graduate.status = 'graduated'
        graduate.save()

        result = graduate.reject_graduation(self.manager)

        self.assertFalse(result)
        mock_cert.assert_not_called()


# ─── End-to-end ────────────────────────────────────────────────────

class GraduateEndToEndTest(GraduateTestBase):

    @patch('certificates.tasks.generate_certificate_pdf.delay')
    @patch('notifications.services.NotificationService.notify_graduation')
    @patch('dossier.services.DossierService.create_student_dossier')
    @patch('certificates.services.CertificateService.create_from_graduate')
    def test_full_flow(self, mock_cert, mock_dossier, mock_notify, mock_pdf):
        """Полный цикл: enrollment → mark_completed → graduate → approve."""
        from certificates.models import Certificate

        def create_cert(graduate, **kwargs):
            return Certificate.objects.create(
                user=graduate.user,
                graduate=graduate,
                course=graduate.course,
                number=f'TEST-E2E-{graduate.id}',
                issued_at=timezone.now().date(),
            )
        mock_cert.side_effect = create_cert

        # 1. Завершаем все уроки
        for lesson in [self.lesson1, self.lesson2, self.lesson3]:
            lp = LessonProgress.objects.get(user=self.user, lesson=lesson)
            lp.mark_completed()

        # 2. Graduate создан автоматически
        graduate = Graduate.objects.get(
            user=self.user, course=self.course,
        )
        self.assertEqual(graduate.status, 'pending')

        # 3. Менеджер одобряет выпуск
        result = graduate.approve_graduation(self.manager)
        self.assertTrue(result)

        graduate.refresh_from_db()
        self.assertEqual(graduate.status, 'graduated')
        mock_cert.assert_called_once()
        mock_dossier.assert_called_once()
        mock_pdf.assert_called_once()
