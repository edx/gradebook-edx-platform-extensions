gradebook-edx-platform-extensions
===================

Notice: This repo will be archived in April 2021.
#######

gradebook-edx-platform-extensions (``gradebook``) is a Django application responsible for
calculating and persisting user's grade and proforma grade for a course.
Gradebook application computes user's grades in a course on ``score_changed`` signal of courseware.


Open edX Platform Integration
-----------------------------
1. Update the version of ``gradebook-edx-platform-extensions`` in the appropriate requirements file (e.g. ``requirements/edx/custom.txt``).
2. Add ``gradebook`` to the list of installed apps in ``common.py``.
3. Set these feature flag in ``common.py``

.. code-block:: bash

  'SIGNAL_ON_SCORE_CHANGED': True,
  'STUDENT_GRADEBOOK': True

4. Install gradebook app via requirements file

.. code-block:: bash

  $ pip install -r requirements/edx/custom.txt

5. (Optional) Run tests to make sure gradebook app is integrated:

.. code-block:: bash

   $ python manage.py lms --settings test test gradebook.tests


