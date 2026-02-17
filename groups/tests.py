from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from account.models import User
from content.models import Course, Module, Lesson
from groups.models import Group, GroupMembership
from progress.models import CourseEnrollment, LessonProgress


class GroupTestBase(TestCase):
    """Общие фикстуры для тестов groups."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            iin='123456789012',
            first_name='Test',
            last_name='Student',
        )
        self.user2 = User.objects.create_user(
            email='student2@test.com',
            password='testpass123',
            iin='123456789013',
            first_name='Test2',
            last_name='Student2',
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
            max_students=0,
            is_active=True,
        )


# ─── Group.is_full() ───────────────────────────────────────────────

class GroupIsFullTest(GroupTestBase):

    def test_unlimited_always_false(self):
        """max_students=0 → is_full() всегда False."""
        self.group.add_student(self.user)
        self.assertFalse(self.group.is_full())

    def test_at_limit(self):
        """max_students=1, один студент → is_full() True."""
        self.group.max_students = 1
        self.group.save()
        self.group.add_student(self.user)
        self.assertTrue(self.group.is_full())

    def test_below_limit(self):
        """max_students=2, один студент → is_full() False."""
        self.group.max_students = 2
        self.group.save()
        self.group.add_student(self.user)
        self.assertFalse(self.group.is_full())

    def test_ignores_inactive_memberships(self):
        """Неактивные членства не считаются."""
        self.group.max_students = 1
        self.group.save()
        GroupMembership.objects.create(
            group=self.group, user=self.user, is_active=False,
        )
        self.assertFalse(self.group.is_full())


# ─── Group.calculate_personal_deadline() ────────────────────────────

class GroupCalculatePersonalDeadlineTest(GroupTestBase):

    def test_personal_days(self):
        """personal_days + deadline_days=90 → now + 90 дней."""
        deadline = self.group.calculate_personal_deadline()
        expected = timezone.now() + timedelta(days=90)
        self.assertAlmostEqual(
            deadline.timestamp(), expected.timestamp(), delta=5,
        )

    def test_personal_days_zero_returns_none(self):
        """deadline_days=0 → None (бессрочно)."""
        self.group.deadline_days = 0
        self.group.save()
        self.assertIsNone(self.group.calculate_personal_deadline())

    def test_fixed_date(self):
        """fixed_date → возвращает deadline_date."""
        fixed = timezone.now() + timedelta(days=30)
        self.group.deadline_type = 'fixed_date'
        self.group.deadline_date = fixed
        self.group.save()
        self.assertEqual(self.group.calculate_personal_deadline(), fixed)

    def test_fixed_date_none(self):
        """fixed_date без deadline_date → None."""
        self.group.deadline_type = 'fixed_date'
        self.group.deadline_date = None
        self.group.save()
        self.assertIsNone(self.group.calculate_personal_deadline())


# ─── Group.add_student() ───────────────────────────────────────────

class GroupAddStudentTest(GroupTestBase):

    def test_success(self):
        success, msg = self.group.add_student(self.user)
        self.assertTrue(success)
        self.assertEqual(msg, 'Студент добавлен')
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, user=self.user, is_active=True,
            ).exists()
        )

    def test_already_in_group(self):
        self.group.add_student(self.user)
        success, msg = self.group.add_student(self.user)
        self.assertFalse(success)
        self.assertIn('уже в группе', msg)

    def test_group_full(self):
        self.group.max_students = 1
        self.group.save()
        self.group.add_student(self.user)
        success, msg = self.group.add_student(self.user2)
        self.assertFalse(success)
        self.assertIn('заполнена', msg.lower())

    def test_sets_personal_deadline(self):
        self.group.add_student(self.user)
        m = GroupMembership.objects.get(group=self.group, user=self.user)
        expected = timezone.now() + timedelta(days=90)
        self.assertAlmostEqual(
            m.personal_deadline_at.timestamp(), expected.timestamp(), delta=5,
        )

    def test_referral_flag(self):
        self.group.add_student(self.user, enrolled_via_referral=True)
        m = GroupMembership.objects.get(group=self.group, user=self.user)
        self.assertTrue(m.enrolled_via_referral)


# ─── Group.remove_student() ────────────────────────────────────────

class GroupRemoveStudentTest(GroupTestBase):

    def test_success(self):
        self.group.add_student(self.user)
        success, msg = self.group.remove_student(self.user)
        self.assertTrue(success)
        m = GroupMembership.objects.get(group=self.group, user=self.user)
        self.assertFalse(m.is_active)
        self.assertIsNotNone(m.left_at)

    def test_not_in_group(self):
        success, msg = self.group.remove_student(self.user)
        self.assertFalse(success)

    def test_syncs_enrollment(self):
        self.group.add_student(self.user)
        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        self.assertTrue(enrollment.is_active)
        self.group.remove_student(self.user)
        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_active)

    def test_already_inactive(self):
        self.group.add_student(self.user)
        self.group.remove_student(self.user)
        success, _ = self.group.remove_student(self.user)
        self.assertFalse(success)


# ─── Сигнал auto_enroll_on_membership_create ───────────────────────

class GroupMembershipSignalTest(GroupTestBase):

    def test_creates_enrollment(self):
        """Создание membership → автоматически создаётся CourseEnrollment."""
        self.group.add_student(self.user)
        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.group, self.group)

    def test_creates_lesson_progress_for_all_lessons(self):
        """Создаётся LessonProgress для каждого урока курса."""
        self.group.add_student(self.user)
        count = LessonProgress.objects.filter(
            user=self.user, lesson__module__course=self.course,
        ).count()
        self.assertEqual(count, 3)

    def test_skips_inactive_membership(self):
        """Неактивное membership не создаёт enrollment."""
        GroupMembership.objects.create(
            group=self.group, user=self.user, is_active=False,
        )
        self.assertFalse(
            CourseEnrollment.objects.filter(
                user=self.user, course=self.course,
            ).exists()
        )

    def test_reactivates_inactive_enrollment(self):
        """Если enrollment неактивен → реактивируется."""
        # Создаём и деактивируем
        self.group.add_student(self.user)
        self.group.remove_student(self.user)
        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        self.assertFalse(enrollment.is_active)

        # Повторно добавляем
        self.group.add_student(self.user)
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.is_active)

    def test_reactivation_resets_progress(self):
        """При реактивации после деактивации прогресс сбрасывается."""
        self.group.add_student(self.user)

        # Помечаем урок завершённым
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.is_completed = True
        lp.completed_at = timezone.now()
        lp.save()

        # Деактивируем
        m = GroupMembership.objects.get(
            group=self.group, user=self.user, is_active=True,
        )
        m.is_active = False
        m.left_at = timezone.now()
        m.save()

        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        enrollment.is_active = False
        enrollment.save()

        # Повторно добавляем — прогресс сбросится
        self.group.add_student(self.user)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percentage, 0)
        self.assertEqual(enrollment.completed_lessons_count, 0)

    def test_reactivation_no_reset_if_graduated(self):
        """Если студент уже выпускник — прогресс НЕ сбрасывается."""
        from graduates.models import Graduate

        self.group.add_student(self.user)

        # Создаём запись Graduate
        Graduate.objects.create(
            user=self.user,
            course=self.course,
            group=self.group,
            status='graduated',
        )

        # Помечаем урок завершённым и обновляем enrollment
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        lp.is_completed = True
        lp.completed_at = timezone.now()
        lp.save()

        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        enrollment.completed_lessons_count = 1
        enrollment.progress_percentage = 33
        enrollment.save()

        # Деактивируем
        m = GroupMembership.objects.get(
            group=self.group, user=self.user, is_active=True,
        )
        m.is_active = False
        m.left_at = timezone.now()
        m.save()
        enrollment.is_active = False
        enrollment.save()

        # Повторно добавляем — прогресс должен остаться
        self.group.add_student(self.user)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.completed_lessons_count, 1)

    def test_first_lesson_available_at_set(self):
        """Первый урок (requires_previous_completion=False) доступен сразу."""
        self.group.add_student(self.user)
        lp = LessonProgress.objects.get(user=self.user, lesson=self.lesson1)
        self.assertIsNotNone(lp.available_at)
        self.assertTrue(lp.is_available())


# ─── Group.deactivate_expired_memberships() ────────────────────────

class GroupDeactivateExpiredMembershipsTest(GroupTestBase):

    def test_deactivates_expired(self):
        """Членство с истёкшим дедлайном деактивируется."""
        self.group.add_student(self.user)
        m = GroupMembership.objects.get(
            group=self.group, user=self.user, is_active=True,
        )
        m.personal_deadline_at = timezone.now() - timedelta(days=1)
        m.save()

        count = Group.deactivate_expired_memberships()
        self.assertEqual(count, 1)
        m.refresh_from_db()
        self.assertFalse(m.is_active)

    def test_skips_future_deadline(self):
        """Членство с будущим дедлайном остаётся активным."""
        self.group.add_student(self.user)
        count = Group.deactivate_expired_memberships()
        self.assertEqual(count, 0)

    def test_skips_null_deadline(self):
        """Членство без дедлайна не деактивируется."""
        self.group.deadline_days = 0
        self.group.save()
        self.group.add_student(self.user)
        count = Group.deactivate_expired_memberships()
        self.assertEqual(count, 0)

    def test_syncs_enrollment_after_deactivation(self):
        """После деактивации enrollment тоже деактивируется."""
        self.group.add_student(self.user)
        m = GroupMembership.objects.get(
            group=self.group, user=self.user, is_active=True,
        )
        m.personal_deadline_at = timezone.now() - timedelta(days=1)
        m.save()

        Group.deactivate_expired_memberships()

        enrollment = CourseEnrollment.objects.get(
            user=self.user, course=self.course,
        )
        self.assertFalse(enrollment.is_active)
