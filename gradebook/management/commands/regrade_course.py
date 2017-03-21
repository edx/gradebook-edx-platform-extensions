"""
Command to regrade users in a course
./manage.py lms regrade_course -c {course_id} --settings=aws
"""
import json
import logging
from optparse import make_option

from django.core.management import BaseCommand

from courseware import grades
from course_blocks.api import get_course_blocks
from gradebook.models import StudentGradebook
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from xmodule.modulestore import EdxJSONEncoder
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Updates gradebook entries for the specified course
    """
    help = "Command to regrade users in a course"

    option_list = BaseCommand.option_list + (
        make_option(
            "-c",
            "--course_id",
            dest="course_id",
            help="course id to regrade",
            metavar="any/course/id"
        ),
    )

    def handle(self, *args, **options):

        course_id = options.get('course_id')

        users_regraded = 0

        course_key = CourseKey.from_string(course_id)
        users = CourseEnrollment.objects.users_enrolled_in(course_key)
        course = modulestore().get_course(course_key, depth=None)

        if course:
            # For each user...
            for user in users:
                course_structure = get_course_blocks(user, course.location)
                grade_summary = grades.grade(user, course, course_structure)
                grading_policy = course.grading_policy
                progress_summary = grades.progress_summary(user, course, course_structure)
                grade = grade_summary['percent']
                proforma_grade = grades.calculate_proforma_grade(grade_summary, grading_policy)
                try:
                    gradebook_entry = StudentGradebook.objects.get(user=user, course_id=course.id)
                    gradebook_entry.grade = grade
                    gradebook_entry.proforma_grade = proforma_grade
                    gradebook_entry.progress_summary = json.dumps(progress_summary, cls=EdxJSONEncoder)
                    gradebook_entry.grade_summary = json.dumps(grade_summary, cls=EdxJSONEncoder)
                    gradebook_entry.grading_policy = json.dumps(grading_policy, cls=EdxJSONEncoder)
                    gradebook_entry.save()
                except StudentGradebook.DoesNotExist:
                    pass

                users_regraded += 1
                log.info(
                    "Gradebook entry updated in Course %s for User id %s with grade: %s, proforma_grade: %s ",
                    course.id, user.id, grade, proforma_grade
                )
        else:
            log.info("Course with course id %s does not exist", course_id)
        log.info("%d users regraded", users_regraded)
