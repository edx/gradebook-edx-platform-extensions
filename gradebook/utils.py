"""
Utils methods for gradebook app
"""
import json

from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator

from xmodule.modulestore import EdxJSONEncoder
from xmodule.modulestore.django import modulestore
from lms.djangoapps.grades.new.course_grade import CourseGradeFactory
from courseware.courses import get_course
from gradebook.models import StudentGradebook


@method_decorator(transaction.non_atomic_requests)
def generate_user_gradebook(course_key, user):
    """
    Recalculates the specified user's gradebook entry
    """
    with modulestore().bulk_operations(course_key):
        course_descriptor = get_course(course_key, depth=None)
        course_grade = CourseGradeFactory().create(user, course_descriptor)
        grade_summary = course_grade.summary
        progress_summary = course_grade.chapter_grades
        grading_policy = course_descriptor.grading_policy
        grade = grade_summary['percent']
        proforma_grade = calculate_proforma_grade(grade_summary, grading_policy)

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


def calculate_proforma_grade(grade_summary, grading_policy):
    """
    Calculates a projected (proforma) final grade based on the current state
    of grades using the provided grading policy.  Categories equate to grading policy
    'types' and have values such as 'Homework', 'Lab', 'MidtermExam', and 'FinalExam'
    We invert the concepts here and use the category weights as the possible scores by
    assuming that the weights total 100 percent.  So, if a Homework category is worth 15
    percent of your overall grade, and you have currently scored 70 percent for that
    category, the normalized score for the Homework category is 0.105.  Note that
    we do not take into account dropped assignments/scores, such as lowest-two homeworks.
    After all scored categories are processed we apply the average category score to any
    unscored categories using the value as a projection of the user's performance in each category.
    Example:
        - Scored Category: Homework,    Weight: 15%, Totaled Score: 70%,  Normalized Score: 0.105
        - Scored Category: MidtermExam, Weight: 30%, Totaled Score: 80%,  Normalized Score: 0.240
        - Scored Category: Final Exam,  Weight: 40%, Totaled Score: 95%,  Normalized Score: 0.380
        - Average Category Score: (70 + 80 + 95) / 3 = 81.7
        - Unscored Category: Lab,       Weight: 15%, Totaled Score: 81.7%, Normalized Score: 0.123
        - Proforma Grade = 0.105 + 0.240 + 0.380 + 0.123 = 0.8475  (84.8%)
    """
    grade_breakdown = grade_summary['grade_breakdown']
    proforma_grade = 0.00
    totaled_scores = grade_summary['totaled_scores']
    category_averages = []
    categories_to_estimate = []
    for grade_category, value in grade_breakdown.items():
        # from nose.tools import set_trace;
        # set_trace()

        category = value['category']
        #category = grade_category['category']
        item_scores = totaled_scores.get(category)
        if item_scores is not None and len(item_scores):
            total_item_score = 0.00
            items_considered = 0
            for item_score in item_scores:
                if item_score.earned or (item_score.due and item_score.due < timezone.now()):
                    normalized_item_score = item_score.earned / item_score.possible
                    total_item_score += normalized_item_score
                    items_considered += 1
            if total_item_score:
                category_average_score = total_item_score / items_considered
                category_averages.append(category_average_score)
                category_policy = next((policy for policy in grading_policy['GRADER'] if policy['type'] == category), None)
                category_weight = category_policy['weight']
                category_grade = category_average_score * category_weight
                proforma_grade += category_grade
            else:
                categories_to_estimate.append(category)
        else:
            categories_to_estimate.append(category)
    assumed_category_average = sum(category_averages) / len(category_averages) if len(category_averages) > 0 else 0
    for category in categories_to_estimate:
        category_policy = next((policy for policy in grading_policy['GRADER'] if policy['type'] == category), None)
        category_weight = category_policy['weight']
        category_grade = assumed_category_average * category_weight
        proforma_grade += category_grade
    return proforma_grade
