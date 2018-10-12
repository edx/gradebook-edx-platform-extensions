"""
Django database models supporting the gradebook app
"""
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Avg, Max, Min, Count, F, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from model_utils.fields import AutoCreatedField, AutoLastModifiedField

from model_utils.models import TimeStampedModel
from student.models import CourseEnrollment
from openedx.core.djangoapps.xmodule_django.models import CourseKeyField


class StudentGradebook(models.Model):
    """
    StudentGradebook is essentially a container used to cache calculated
    grades (see courseware.grades.grade), which can be an expensive operation.
    """
    user = models.ForeignKey(User, db_index=True)
    course_id = CourseKeyField(db_index=True, max_length=255, blank=True)
    grade = models.FloatField(db_index=True)
    proforma_grade = models.FloatField()
    progress_summary = models.TextField(blank=True)
    grade_summary = models.TextField()
    grading_policy = models.TextField()
    is_passed = models.BooleanField(db_index=True, default=False)
    # We can't use TimeStampedModel here because those fields are not indexed.
    created = AutoCreatedField(_('created'), db_index=True)
    modified = AutoLastModifiedField(_('modified'), db_index=True)

    class Meta(object):
        """
        Meta information for this Django model
        """
        unique_together = (('user', 'course_id'),)

    @classmethod
    def generate_leaderboard(
            cls,
            course_key,
            user_id=None,
            group_ids=None,
            count=3,
            exclude_users=None,
            cohort_user_ids=None,
    ):
        """
        Assembles a data set representing the Top N users, by grade, for a given course.
        Optionally provide a user_id to include user-specific info.  For example, you
        may want to view the Top 5 users, but also need the data for the logged-in user
        who may actually be currently located in position #10.

        data = {
            'course_avg': 0.873,
            'queryset': [
                {'id': 123, 'username': 'testuser1', 'title', 'Engineer', 'profile_image_uploaded_at': '2014-01-15 06:27:54', 'grade': 0.92, 'created': '2014-01-15 06:27:54'},
                {'id': 983, 'username': 'testuser2', 'title', 'Analyst', 'profile_image_uploaded_at': '2014-01-15 06:27:54', 'grade': 0.91, 'created': '2014-06-27 01:15:54'},
                {'id': 246, 'username': 'testuser3', 'title', 'Product Owner', 'profile_image_uploaded_at': '2014-01-15 06:27:54', 'grade': 0.90, 'created': '2014-03-19 04:54:54'},
                {'id': 357, 'username': 'testuser4', 'title', 'Director', 'profile_image_uploaded_at': '2014-01-15 06:27:54', 'grade': 0.89, 'created': '2014-12-01 08:38:54'},
            ]
            ### IF USER ID SPECIFIED (in this case user_id=246) ###
            'user_position': 4,
            'user_grade': 0.89
        }

        If there is a discrepancy between the number of gradebook entries and the overall number of enrolled
        users (excluding any users who should be excluded), then we modify the course average to account for
        those users who currently lack gradebook entries.  We assume zero grades for these users because they
        have not yet submitted a response to a scored assessment which means no grade has been calculated.
        """
        exclude_users = exclude_users or []
        data = {}
        data['course_avg'] = 0
        data['course_max'] = 0
        data['course_min'] = 0
        data['course_count'] = 0
        data['enrollment_count'] = 0
        data['queryset'] = []

        total_users_qs = CourseEnrollment.objects.users_enrolled_in(course_key).exclude(id__in=exclude_users)
        if cohort_user_ids:
            total_users_qs = total_users_qs.filter(id__in=cohort_user_ids)
        total_user_count = total_users_qs.count()
        data['enrollment_count'] = total_user_count

        if total_user_count:
            # Generate the base data set we're going to work with
            queryset = StudentGradebook.objects.select_related('user')\
                .filter(course_id__exact=course_key, user__is_active=True, user__courseenrollment__is_active=True,
                        user__courseenrollment__course_id__exact=course_key).exclude(user__id__in=exclude_users)

            if cohort_user_ids:
                queryset = queryset.filter(user_id__in=cohort_user_ids)

            aggregates = queryset.aggregate(Avg('grade'), Max('grade'), Min('grade'), Count('user'))
            gradebook_user_count = aggregates['user__count']

            if gradebook_user_count:
                # Calculate the class average
                course_avg = aggregates['grade__avg']
                if course_avg is not None:
                    # Take into account any ungraded students (assumes zeros for grades...)
                    course_avg = course_avg / total_user_count * gradebook_user_count

                    # Fill up the response container
                    data['course_avg'] = float("{0:.3f}".format(course_avg))
                    data['course_max'] = aggregates['grade__max']
                    data['course_min'] = aggregates['grade__min']
                    data['course_count'] = gradebook_user_count

                if group_ids:
                    queryset = queryset.filter(user__groups__in=group_ids).distinct()

                # Construct the leaderboard as a queryset
                data['queryset'] = queryset.values(
                    'user__id',
                    'user__username',
                    'user__profile__title',
                    'user__profile__profile_image_uploaded_at',
                    'grade',
                    'modified')\
                    .order_by('-grade', 'modified')[:count]
                # If a user_id value was provided, we need to provide some additional user-specific data to the caller
                if user_id:
                    result = cls.get_user_position(
                        course_key,
                        user_id,
                        exclude_users=exclude_users,
                        group_ids=group_ids,
                    )
                    data.update(result)

        return data

    @classmethod
    def get_user_position(cls, course_key, user_id, exclude_users=None, group_ids=None):
        """
        Helper method to return the user's position in the leaderboard for Proficiency
        """
        exclude_users = exclude_users or []
        data = {'user_position': 0, 'user_grade': 0}
        user_grade = 0
        users_above = 0
        user_time_scored = timezone.now()
        try:
            user_queryset = StudentGradebook.objects.get(course_id__exact=course_key, user__id=user_id)
        except StudentGradebook.DoesNotExist:
            user_queryset = None

        if user_queryset:
            user_grade = user_queryset.grade
            user_time_scored = user_queryset.created

        queryset = StudentGradebook.objects.select_related('user').filter(
            course_id__exact=course_key,
            user__is_active=True,
            user__courseenrollment__is_active=True,
            user__courseenrollment__course_id__exact=course_key
        ).exclude(
            user__in=exclude_users
        )

        if group_ids:
            queryset = queryset.filter(user__groups__in=group_ids).distinct()

        users_above = queryset.filter(
            Q(grade__gt=user_grade) |
            Q(grade=user_grade, modified__lt=user_time_scored)
        ).count()

        data['user_position'] = users_above + 1
        data['user_grade'] = user_grade

        return data

    @classmethod
    def course_grade_avg(cls, course_key, exclude_users=None, org_ids=None, group_ids=None, cohort_user_ids=None):
        """
        Returns course grade average
        """
        course_avg = 0.0
        exclude_users = exclude_users or []
        total_users_qs = CourseEnrollment.objects.users_enrolled_in(course_key).exclude(id__in=exclude_users)
        if org_ids:
            total_users_qs = total_users_qs.filter(organizations__in=org_ids)
        if group_ids:
            total_users_qs = total_users_qs.filter(groups__in=group_ids).distinct()
        if cohort_user_ids:
            total_users_qs = total_users_qs.filter(id__in=cohort_user_ids)
        total_user_count = total_users_qs.count()

        if total_user_count:
            # Generate the base data set we're going to work with
            queryset = StudentGradebook.objects.select_related('user')\
                .filter(course_id__exact=course_key, user__is_active=True, user__courseenrollment__is_active=True,
                        user__courseenrollment__course_id__exact=course_key).exclude(user__id__in=exclude_users)
            if org_ids:
                queryset = queryset.filter(user__organizations__in=org_ids)
            if group_ids:
                queryset = queryset.filter(user__groups__in=group_ids)
            aggregates = queryset.aggregate(Avg('grade'), Count('user'))
            gradebook_user_count = aggregates['user__count']

            if gradebook_user_count:
                # Calculate the class average
                course_avg = aggregates['grade__avg']
                if course_avg is not None:
                    # Take into account any ungraded students (assumes zeros for grades...)
                    course_avg = course_avg / total_user_count * gradebook_user_count
                    course_avg = float("{0:.3f}".format(course_avg))
        return course_avg

    @classmethod
    def get_user_grade(cls, course_key, user_id):
        """
        returns the user's grade
        """
        user_grade = 0.0
        try:
            user_queryset = StudentGradebook.objects.get(course_id__exact=course_key, user__id=user_id)
            return user_queryset.grade
        except StudentGradebook.DoesNotExist:
            return user_grade

    @classmethod
    def get_num_users_completed(cls, course_key, exclude_users=None, org_ids=None, group_ids=None):
        """
        Returns count of users those who completed given course.
        """
        exclude_users = exclude_users or []
        grade_complete_match_range = getattr(settings, 'GRADEBOOK_GRADE_COMPLETE_PROFORMA_MATCH_RANGE', 0.01)
        queryset = cls.objects.filter(
            course_id__exact=course_key,
            user__is_active=True,
            user__courseenrollment__is_active=True,
            user__courseenrollment__course_id__exact=course_key,
            proforma_grade__lte=F('grade') + grade_complete_match_range,
            proforma_grade__gt=0
        ).exclude(user__id__in=exclude_users)
        if org_ids:
            queryset = queryset.filter(user__organizations__in=org_ids)
        if group_ids:
            queryset = queryset.filter(user__groups__in=group_ids)

        return queryset.distinct().count()

    @classmethod
    def get_passed_users_gradebook(cls, course_key, exclude_users=None, org_ids=None, group_ids=None):
        """
        Return users gradebook who passed given course.
        """
        exclude_users = exclude_users or []
        queryset = StudentGradebook.objects.select_related('user').filter(
            course_id__exact=course_key,
            user__is_active=True,
            user__courseenrollment__is_active=True,
            user__courseenrollment__course_id__exact=course_key,
            is_passed=True
        ).exclude(user__id__in=exclude_users)
        if org_ids:
            queryset = queryset.filter(user__organizations__in=org_ids)
        if group_ids:
            queryset = queryset.filter(user__groups__in=group_ids)

        return queryset


class StudentGradebookHistory(TimeStampedModel):
    """
    A running audit trail for the StudentGradebook model.  Listens for
    post_save events and creates/stores copies of gradebook entries.
    """
    user = models.ForeignKey(User, db_index=True)
    course_id = CourseKeyField(db_index=True, max_length=255, blank=True)
    grade = models.FloatField()
    proforma_grade = models.FloatField()
    progress_summary = models.TextField(blank=True)
    grade_summary = models.TextField()
    grading_policy = models.TextField()
    is_passed = models.BooleanField(db_index=True, default=False)

    @receiver(post_save, sender=StudentGradebook)
    def save_history(sender, instance, **kwargs):  # pylint: disable=no-self-argument, unused-argument
        """
        Event hook for creating gradebook entry copies
        """
        history_entries = StudentGradebookHistory.objects.filter(user=instance.user, course_id=instance.course_id)
        latest_history_entry = None
        if len(history_entries):
            latest_history_entry = history_entries[0]

        create_history_entry = False
        if latest_history_entry is not None:
            if (
                latest_history_entry.grade != instance.grade or
                latest_history_entry.proforma_grade != instance.proforma_grade or
                latest_history_entry.progress_summary != instance.progress_summary or
                latest_history_entry.grade_summary != instance.grade_summary or
                latest_history_entry.grading_policy != instance.grading_policy or
                latest_history_entry.is_passed != instance.is_passed
            ):
                create_history_entry = True
        else:
            create_history_entry = True

        if create_history_entry:
            new_history_entry = StudentGradebookHistory(
                user=instance.user,
                course_id=instance.course_id,
                grade=instance.grade,
                proforma_grade=instance.proforma_grade,
                progress_summary=instance.progress_summary,
                grade_summary=instance.grade_summary,
                grading_policy=instance.grading_policy,
                is_passed=instance.is_passed
            )
            new_history_entry.save()
