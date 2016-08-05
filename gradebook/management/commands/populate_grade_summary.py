"""
One-time data migration script -- shouldn't need to run it again
"""
import json
import logging
from optparse import make_option

from django.core.management import BaseCommand

from courseware import grades
from gradebook.models import StudentGradebook
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from xmodule.modulestore import EdxJSONEncoder
from util.request import RequestMockWithoutMiddleware
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Creates (or updates) gradebook entries for the specified course or all courses
    """
    help = "Command to populate gradebook grade summary"

    option_list = BaseCommand.option_list + (
        make_option(
            "-c",
            "--course_id",
            dest="course_id",
            help="course id to fix",
            metavar="any/course/id"
        ),
    )

    def handle(self, *args, **options):

        course_id = options.get('course_id')
        course_ids = []

        if course_id:
            course_ids.append(course_id)
        else:
            course_ids = StudentGradebook.objects.filter(grade_summary='').values_list('course_id', flat=True)

        for course_id in course_ids:
            course_key = CourseKey.from_string(course_id)
            users = CourseEnrollment.objects.users_enrolled_in(course_key)
            course = modulestore().get_course(course_key, depth=None)
            if course:
                # For each user...
                for user in users:
                    request = RequestMockWithoutMiddleware().get('/')
                    request.user = user
                    grade_data = grades.grade(user, request, course)
                    grade = grade_data['percent']
                    grading_policy = course.grading_policy
                    proforma_grade = grades.calculate_proforma_grade(grade_data, grading_policy)
                    progress_summary = grades.progress_summary(user, request, course, locators_as_strings=True)
                    try:
                        gradebook_entry = StudentGradebook.objects.get(user=user, course_id=course.id)
                        if not gradebook_entry.grade_summary:
                            gradebook_entry.grade = grade
                            gradebook_entry.proforma_grade = proforma_grade
                            gradebook_entry.progress_summary = json.dumps(progress_summary, cls=EdxJSONEncoder)
                            gradebook_entry.grade_summary = json.dumps(grade_data, cls=EdxJSONEncoder)
                            gradebook_entry.grading_policy = json.dumps(grading_policy, cls=EdxJSONEncoder)
                            gradebook_entry.save()
                    except StudentGradebook.DoesNotExist:
                       pass

                    log_msg = 'Gradebook entry created -- Course: {}, User: {}  (grade: {}, proforma_grade: {})'.format(course.id, user.id, grade, proforma_grade)
                    log.info(log_msg)
