# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0010_auto_20170612_0918'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreprofile',
            name='first_name',
            field=models.CharField(db_index=True, max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='userpreprofile',
            name='last_name',
            field=models.CharField(db_index=True, max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='userpreprofile',
            name='uuid',
            field=models.CharField(db_index=True, max_length=255, blank=True),
        ),
    ]
