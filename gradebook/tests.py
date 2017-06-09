# pylint: disable=E1101
"""
Run these tests @ Devstack:
    paver test_system -s lms --test_id=lms/djangoapps/gradebook/tests.py
"""
from mock import MagicMock, patch
import json
from datetime import datetime

from django.utils.timezone import UTC
from django.conf import settings
from django.test.utils import override_settings

from student.tests.factories import UserFactory, AdminFactory
from courseware.tests.factories import StaffFactory

from gradebook.models import StudentGradebook, StudentGradebookHistory
from util.signals import course_deleted

from edx_notifications.lib.consumer import get_notifications_count_for_user
from edx_notifications.startup import initialize as initialize_notifications
from edx_solutions_api_integration.test_utils import (
    CourseGradingMixin,
    SignalDisconnectTestMixin,
    make_non_atomic,
)
from xmodule.modulestore.tests.django_utils import (
    ModuleStoreTestCase,
    TEST_DATA_SPLIT_MODULESTORE
)


class GradebookTests(SignalDisconnectTestMixin, CourseGradingMixin, ModuleStoreTestCase):
    """ Test suite for Student Gradebook """

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        super(GradebookTests, self).setUp()
        self.test_server_prefix = 'https://testserver'
        self.user = UserFactory()
        self.score = 0.75

    def _get_homework_grade_summary(self):
        """
        returns grade summary for homework assignment
        """
        return {
            "category": "Homework",
            "percent": 0.25,
            "detail": "Homework = 25.00% of a possible 50.00%",
        }

    def _get_midterm_grade_summary(self):
        """
        returns grade summary for midterm assignment
        """
        return {
            "category": "Midterm Exam",
            "percent": 0.5,
            "detail": "Midterm Exam = 50.00% of a possible 50.00%",
        }

    def _get_homework_summary(self, course, attempted=False):
        return {
            u'url_name': u'Sequence_2',
            u'display_name': u'Sequence 2',
            u'location': 'block-v1:{org}+{num}+{run}+type@sequential+block@Sequence_2'.format(
                org=course.org,
                num=course.number,
                run=course.id.run,
            ),
            u'graded': True,
            u'format': u'Homework',
            u'due': None,
            u'section_total': [0.5, 1.0, False, attempted],
            u'graded_total': [0.5, 1.0, True, attempted]
        }

    def _get_midterm_summary(self, course, attempted=False):
        return {
            u'url_name': u'Sequence_3',
            u'display_name': u'Sequence 3',
            u'location': 'block-v1:{org}+{num}+{run}+type@sequential+block@Sequence_3'.format(
                org=course.org,
                num=course.number,
                run=course.id.run,
            ),
            u'graded': True,
            u'format': u'Midterm Exam',
            u'due': None,
            u'section_total': [1.0, 1.0, False, attempted],
            u'graded_total': [1.0, 1.0, True, attempted]
        }

    def _assert_valid_gradebook_on_course(self, course):
        """
        Asserts user has a valid grade book
        """
        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        gradebook = StudentGradebook.objects.get(user=self.user, course_id=course.id)
        self.assertEqual(gradebook.grade, 0.25)
        self.assertEqual(gradebook.proforma_grade, 0.5)

        self.assertIn(
            json.dumps(self._get_homework_summary(course, attempted=True)),
            gradebook.progress_summary
        )
        self.assertIn(json.dumps(self._get_homework_grade_summary()), gradebook.grade_summary)
        self.assertEquals(json.loads(gradebook.grading_policy), course.grading_policy)

        module = self.get_module_for_user(self.user, course, course.midterm_assignment)
        grade_dict = {'value': 1, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        gradebook = StudentGradebook.objects.get(user=self.user, course_id=course.id)
        self.assertEqual(gradebook.grade, 0.75)
        self.assertEqual(gradebook.proforma_grade, 0.75)
        self.assertIn(
            json.dumps(self._get_midterm_summary(course, attempted=True)),
            gradebook.progress_summary
        )
        self.assertIn(json.dumps(self._get_midterm_grade_summary()), gradebook.grade_summary)
        self.assertEquals(json.loads(gradebook.grading_policy), course.grading_policy)

        gradebook = StudentGradebook.objects.all()
        self.assertEqual(len(gradebook), 1)

        history = StudentGradebookHistory.objects.all()
        self.assertEqual(len(history), 2)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_receiver_on_score_changed(self):
        course = self.setup_course_with_grading()
        self._assert_valid_gradebook_on_course(course)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True,
        'ENABLE_NOTIFICATIONS': True
    })
    @make_non_atomic
    def test_notifications_publishing(self):
        initialize_notifications()

        # assert user has no notifications
        self.assertEqual(get_notifications_count_for_user(self.user.id), 0)

        course = self.setup_course_with_grading()
        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        # user should have had a notification published as he/her is now in the
        # leaderboard
        self.assertEqual(get_notifications_count_for_user(self.user.id), 1)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_open_course(self):
        course = self.setup_course_with_grading(
            start=datetime(2010, 1, 1, tzinfo=UTC()),
            end=datetime(3000, 1, 1, tzinfo=UTC()),
        )
        self._assert_valid_gradebook_on_course(course)


    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_not_yet_started_course(self):
        course = self.setup_course_with_grading(
            start=datetime(3000, 1, 1, tzinfo=UTC()),
            end=datetime(3000, 1, 1, tzinfo=UTC()),
        )
        self._assert_valid_gradebook_on_course(course)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_closed_course_student(self):
        course = self.setup_course_with_grading(
            start=datetime(2010, 1, 1, tzinfo=UTC()),
            end=datetime(2011, 1, 1, tzinfo=UTC()),
        )
        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        with self.assertRaises(StudentGradebook.DoesNotExist):
            __ = StudentGradebook.objects.get(user=self.user, course_id=course.id)

        gradebook = StudentGradebook.objects.all()
        self.assertEqual(len(gradebook), 0)

        history = StudentGradebookHistory.objects.all()
        self.assertEqual(len(history), 0)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_closed_course_admin(self):
        """
        Users marked as Admin should be able to submit grade events to a closed course
        """
        self.user = AdminFactory()
        course = self.setup_course_with_grading(
            start=datetime(2010, 1, 1, tzinfo=UTC()),
            end=datetime(2011, 1, 1, tzinfo=UTC()),
        )
        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        with self.assertRaises(StudentGradebook.DoesNotExist):
            __ = StudentGradebook.objects.get(user=self.user, course_id=course.id)

        gradebook = StudentGradebook.objects.all()
        self.assertEqual(len(gradebook), 0)

        history = StudentGradebookHistory.objects.all()
        self.assertEqual(len(history), 0)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_closed_course_staff(self):
        """
        Users marked as course staff should be able to submit grade events to a closed course
        """
        course = self.setup_course_with_grading(
            start=datetime(2010, 1, 1, tzinfo=UTC()),
            end=datetime(2011, 1, 1, tzinfo=UTC()),
        )
        self.user = StaffFactory(course_key=course.id)
        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        with self.assertRaises(StudentGradebook.DoesNotExist):
            __ = StudentGradebook.objects.get(user=self.user, course_id=course.id)

        gradebook = StudentGradebook.objects.all()
        self.assertEqual(len(gradebook), 0)

        history = StudentGradebookHistory.objects.all()
        self.assertEqual(len(history), 0)

    def test_update_user_gradebook_task_arguments(self):
        """
        Tests update_user_gradebook task is called with appropriate arguments
        """
        course = self.setup_course_with_grading()
        user = UserFactory()
        module = self.get_module_for_user(user, course, course.homework_assignment)
        grade_dict = {'value': 0.75, 'max_value': 1, 'user_id': user.id}
        with patch('gradebook.signals.update_user_gradebook.delay') as mock_task:
            module.system.publish(module, 'grade', grade_dict)
            mock_task.assert_called_with(unicode(course.id), user.id)

    @patch.dict(settings.FEATURES, {
        'ALLOW_STUDENT_STATE_UPDATES_ON_CLOSED_COURSE': False,
        'SIGNAL_ON_SCORE_CHANGED': True
    })
    @make_non_atomic
    def test_receiver_on_course_deleted(self):
        course = self.setup_course_with_grading()
        self._assert_valid_gradebook_on_course(course)

        course_deleted.send(sender=None, course_key=course.id)
        with self.assertRaises(StudentGradebook.DoesNotExist):
            gradebook = StudentGradebook.objects.get(user=self.user, course_id=course.id)

        gradebook = StudentGradebook.objects.all()
        self.assertEqual(len(gradebook), 0)

        history = StudentGradebookHistory.objects.all()
        self.assertEqual(len(history), 0)

    def test_course_passed(self):
        course = self.setup_course_with_grading()
        course2 = self.setup_course_with_grading()

        module = self.get_module_for_user(self.user, course, course.homework_assignment)
        grade_dict = {'value': 0.5, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        gradebook = StudentGradebook.objects.filter(is_passed=True)
        self.assertEqual(len(gradebook), 0)

        history = StudentGradebookHistory.objects.filter(is_passed=True)
        self.assertEqual(len(history), 0)

        module = self.get_module_for_user(self.user, course2, course2.midterm_assignment)
        grade_dict = {'value': 1, 'max_value': 1, 'user_id': self.user.id}
        module.system.publish(module, 'grade', grade_dict)

        gradebook = StudentGradebook.objects.filter(is_passed=True)
        self.assertEqual(len(gradebook), 1)

        gradebook = StudentGradebook.objects.filter(is_passed=True, user=self.user)
        self.assertEqual(len(gradebook), 1)

        history = StudentGradebookHistory.objects.filter(is_passed=True)
        self.assertEqual(len(history), 1)
