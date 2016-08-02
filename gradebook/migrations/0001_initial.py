# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
import xmodule_django.models
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGradebook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(db_index=True, max_length=255, blank=True)),
                ('grade', models.FloatField(db_index=True)),
                ('proforma_grade', models.FloatField()),
                ('progress_summary', models.TextField(blank=True)),
                ('grade_summary', models.TextField(blank=True)),
                ('grading_policy', models.TextField(blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False, db_index=True)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False, db_index=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='StudentGradebookHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('course_id', xmodule_django.models.CourseKeyField(db_index=True, max_length=255, blank=True)),
                ('grade', models.FloatField()),
                ('proforma_grade', models.FloatField()),
                ('progress_summary', models.TextField(blank=True)),
                ('grade_summary', models.TextField(blank=True)),
                ('grading_policy', models.TextField(blank=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterUniqueTogether(
            name='studentgradebook',
            unique_together=set([('user', 'course_id')]),
        ),
    ]
