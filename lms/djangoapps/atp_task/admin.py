"""
Django admin page for bulk email models
"""
from django.contrib import admin

from config_models.admin import ConfigurationModelAdmin

from atp_task.models import tmaTask

class tmaTaskAdmin(admin.ModelAdmin):
    """Admin for tmatasks."""
    list_display = ['task_type','course_id','task_input','task_id','task_state','task_output','requester','created','updated','subtasks']
    search_fields = ['course_id','task_id','task_state','task_output']

    actions = None

admin.site.register(tmaTask, tmaTaskAdmin)
