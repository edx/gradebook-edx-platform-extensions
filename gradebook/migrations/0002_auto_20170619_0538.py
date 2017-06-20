# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gradebook', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentgradebook',
            name='is_passed',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='studentgradebookhistory',
            name='is_passed',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
