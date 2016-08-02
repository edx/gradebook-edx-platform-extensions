"""
app configuration
"""
from django.apps import AppConfig


class SolutionsAppGradebookConfig(AppConfig):

    name = 'gradebook'
    verbose_name = 'gradebook app'

    def ready(self):

        # import signal handlers
        import gradebook.signals  # pylint: disable=unused-import
