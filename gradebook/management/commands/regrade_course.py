"""
Command to regrade users in a course
./manage.py lms regrade_course -c {course_id} --settings=aws
"""
import logging
from optparse import make_option

from django.core.management import BaseCommand

from gradebook.utils import generate_user_gradebook
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Updates gradebook entries for the specified course
    """
    help = "Command to regrade users in a course"

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

        users_regraded = 0

        course_key = CourseKey.from_string(course_id)
        users = CourseEnrollment.objects.users_enrolled_in(course_key)
        course = modulestore().get_course(course_key, depth=None)

        if course:
            # For each user...
            for user in users:
                try:
                    gradebook = generate_user_gradebook(course_key, user)
                except Exception as ex:   # pylint: disable=broad-except
                    log.info(
                        "Failed to update gradeboo for user %s in course %s. Error: %s",
                        user.id, course_key, ex.message
                    )

                users_regraded += 1
                log.info(
                    "Gradebook entry updated in Course %s for User id %s with grade: %s, proforma_grade: %s ",
                    course.id, user.id, gradebook.grade, gradebook.proforma_grade
                )
        else:
            log.info("Course with course id %s does not exist", course_id)
        log.info("%d users regraded", users_regraded)
