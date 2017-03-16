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
from lms.djangoapps.grades.new.subsection_grade import SubsectionGrade
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
        progress_summary = make_courseware_summary(course_grade.chapter_grades)
        grading_policy = course_descriptor.grading_policy
        grade = grade_summary['percent']
        proforma_grade = calculate_proforma_grade(course_grade, grading_policy)

    progress_summary = get_json_data(progress_summary)
    grade_summary = get_json_data(grade_summary)
    grading_policy = get_json_data(grading_policy)
    gradebook_entry, created = StudentGradebook.objects.get_or_create(
        user=user,
        course_id=course_key,
        defaults={
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
        json_data = json.dumps(obj, cls=GradeJSONEncoder)
    except:
        json_data = {}
    return json_data


def make_courseware_summary(chapter_grades):
    """
    Makes courseware summary dict from chapter grades.
    """
    courseware_summary = []
    for chapter in chapter_grades:
        sub_sections = []
        for sub_section in chapter['sections']:
            sub_sections.append({
                'location': unicode(sub_section.location),
                'display_name': sub_section.display_name,
                'url_name': sub_section.url_name,
                'due': sub_section.due,
                'graded': sub_section.graded,
                'format': sub_section.format,
                'section_total': [
                    sub_section.all_total.earned,
                    sub_section.all_total.possible,
                    sub_section.all_total.graded,
                    sub_section.all_total.attempted,
                ],
                'graded_total': [
                    sub_section.graded_total.earned,
                    sub_section.graded_total.possible,
                    sub_section.graded_total.graded,
                    sub_section.graded_total.attempted,
                ],
            })

        courseware_summary.append({
            'url_name': chapter.get('url_name'),
            'display_name': chapter.get('display_name'),
            'sections': sub_sections,
        })
    return courseware_summary


class GradeJSONEncoder(EdxJSONEncoder):
    """
    Custom JSONEncoder that handles `Location` and `datetime.datetime` objects.

    `Location`s are encoded as their url string form, and `datetime`s as
    ISO date strings
    """
    def default(self, obj):
        if isinstance(obj, SubsectionGrade):
            return obj.dict()
        else:
            return super(EdxJSONEncoder, self).default(obj)


def calculate_proforma_grade(course_grade, grading_policy):
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

    proforma_grade = 0.00
    category_averages = []
    categories_to_estimate = []
    graded_subsections = course_grade.graded_subsections_by_format
    if not graded_subsections:
        # if user has not submitted anything
        return proforma_grade

    for grader in grading_policy['GRADER']:
        category = grader['type']
        categorized_subsections = graded_subsections.get(category, None)
        if categorized_subsections:
            total_item_score = 0.00
            items_considered = 0
            # compute proforma grade for each grade subsection
            for __, subsection_grade in categorized_subsections.iteritems():
                graded_item = subsection_grade.graded_total
                if graded_item.attempted or (subsection_grade.due and subsection_grade.due < timezone.now()):
                    normalized_item_score = graded_item.earned / graded_item.possible
                    total_item_score += normalized_item_score
                    items_considered += 1

            if items_considered:
                category_average_score = total_item_score / items_considered
                category_averages.append(category_average_score)
                category_weight = grader['weight']
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
