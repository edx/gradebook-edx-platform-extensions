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
        grade_summary = grades.grade(user, course_descriptor, course_structure)
        grading_policy = course_descriptor.grading_policy
        progress_summary = grades.progress_summary(user, course_descriptor, course_structure)
        grade = grade_summary['percent']
        proforma_grade = grades.calculate_proforma_grade(grade_summary, grading_policy)

    progress_summary = get_json_data(progress_summary)
    grade_summary = get_json_data(grade_summary)
    grading_policy = get_json_data(grading_policy)

    gradebook_entry, created = StudentGradebook.objects.get_or_create(
        user=user, course_id=course_key, defaults={
                'grade': grade,
                'proforma_grade': proforma_grade,
                'progress_summary': progress_summary,
                'grade_summary': grade_summary,
                'grading_policy': grading_policy
            }
    )

    if gradebook_entry.grade != grade:
        gradebook_entry.grade = grade
        gradebook_entry.proforma_grade = proforma_grade
        gradebook_entry.progress_summary = progress_summary
        gradebook_entry.grade_summary = grade_summary
        gradebook_entry.grading_policy = grading_policy
        gradebook_entry.save()

    return gradebook_entry


def get_json_data(obj):
    try:
        json_data = json.dumps(obj, cls=EdxJSONEncoder)
    except:
        json_data = {}
    return json_data
