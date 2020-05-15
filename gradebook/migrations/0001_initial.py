# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
from opaque_keys.edx.django.models import CourseKeyField
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
                ('course_id', CourseKeyField(db_index=True, max_length=255, blank=True)),
                ('grade', models.FloatField(db_index=True)),
                ('proforma_grade', models.FloatField()),
                ('progress_summary', models.TextField(blank=True)),
                ('grade_summary', models.TextField()),
                ('grading_policy', models.TextField()),
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
                ('course_id', CourseKeyField(db_index=True, max_length=255, blank=True)),
                ('grade', models.FloatField()),
                ('proforma_grade', models.FloatField()),
                ('progress_summary', models.TextField(blank=True)),
                ('grade_summary', models.TextField()),
                ('grading_policy', models.TextField()),
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
