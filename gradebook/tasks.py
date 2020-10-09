"""
This module has implementation of celery tasks for learner gradebook use cases
"""
import json
import logging

from django.contrib.auth.models import User

from celery.task import task  # pylint: disable=import-error,no-name-in-module
from gradebook.utils import generate_user_gradebook
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger('edx.celery.task')


@task(name='lms.djangoapps.gradebook.tasks.update_user_gradebook')
def update_user_gradebook(course_key, user_id):
    """
    Taks to recalculate user's gradebook entry
    """
    if not isinstance(course_key, str):
        raise ValueError('course_key must be a string. {} is not acceptable.'.format(type(course_key)))

    course_key = CourseKey.from_string(course_key)
    try:
        user = User.objects.get(id=user_id)
        generate_user_gradebook(course_key, user)
    except Exception as ex:
        log.exception('An error occurred while generating gradebook: %s', ex.message)
        raise
