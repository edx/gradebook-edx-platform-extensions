"""
Command to update pass status of users in a course
./manage.py lms update_pass_status -c {course_id} --settings=aws
"""
import logging
from optparse import make_option

from django.core.management import BaseCommand

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.keys import CourseKey
from gradebook.models import StudentGradebook

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Updates gradebook entries with pass status of user in the specified course
    """
    help = "Command to update pass status of users in a course"

    def add_arguments(self, parser):
        parser.add_argument(
            "-c",
            "--course_id",
            dest="course_id",
            help="course id to regrade",
            metavar="any/course/id"
        ),

    def handle(self, *args, **options):

        course_id = options.get('course_id')

        users_updated = 0

        course_key = CourseKey.from_string(course_id)
        users = CourseEnrollment.objects.users_enrolled_in(course_key)
        course = modulestore().get_course(course_key, depth=None)

        if course:
            # For each user...
            for user in users:
                is_passed = False
                try:
                    course_grade = CourseGradeFactory().read(user, course)
                    is_passed = course_grade.passed
                    StudentGradebook.objects.filter(user=user, course_id=course_key).update(is_passed=is_passed)
                except Exception as ex:  # pylint: disable=broad-except
                    log.info(
                        "Failed to update pass status for user %s in course %s. Error: %s",
                        user.id, course_key, ex.message
                    )

                users_updated += 1
                log.info(
                    "Gradebook entry updated in Course %s for User id %s with pass status: %s",
                    course.id, user.id, is_passed
                )
        else:
            log.info("Course with course id %s does not exist", course_id)
        log.info("%d users have their pass status updated", users_updated)
