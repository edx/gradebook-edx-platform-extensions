"""
Utils methods for gradebook app
"""
import json

from django.db import transaction
from django.utils.decorators import method_decorator

from xmodule.modulestore import EdxJSONEncoder
from xmodule.modulestore.django import modulestore
from course_blocks.api import get_course_blocks
from courseware import grades
from courseware.courses import get_course
from gradebook.models import StudentGradebook


@method_decorator(transaction.non_atomic_requests)
def generate_user_gradebook(course_key, user):
    """
    Recalculates the specified user's gradebook entry
    """
    with modulestore().bulk_operations(course_key):
        course_descriptor = get_course(course_key, depth=None)
        course_structure = get_course_blocks(user, course_descriptor.location)
        progress_summary = grades.progress_summary(user, course_descriptor, course_structure)
        grade_summary = grades.grade(user, course_descriptor, course_structure)
        grading_policy = course_descriptor.grading_policy
        grade = grade_summary['percent']
        proforma_grade = grades.calculate_proforma_grade(grade_summary, grading_policy)

    gradebook_entry, created = StudentGradebook.objects.get_or_create(user=user, course_id=course_key,
                                                                      defaults={'grade': grade,
                                                                                'proforma_grade': proforma_grade,
                                                                                'progress_summary': json.dumps
                                                                                (progress_summary, cls=EdxJSONEncoder),
                                                                                'grade_summary': json.dumps
                                                                                (grade_summary, cls=EdxJSONEncoder),
                                                                                'grading_policy': json.dumps
                                                                                (grading_policy, cls=EdxJSONEncoder)})
    if gradebook_entry.grade != grade:
        gradebook_entry.grade = grade
        gradebook_entry.proforma_grade = proforma_grade
        gradebook_entry.progress_summary = json.dumps(progress_summary, cls=EdxJSONEncoder)
        gradebook_entry.grade_summary = json.dumps(grade_summary, cls=EdxJSONEncoder)
        gradebook_entry.grading_policy = json.dumps(grading_policy, cls=EdxJSONEncoder)
        gradebook_entry.save()

    return gradebook_entry
