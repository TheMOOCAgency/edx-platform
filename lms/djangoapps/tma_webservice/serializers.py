
"""
Student Data API Serializers.
"""

import urllib
import logging
import datetime

from django.core.urlresolvers import reverse
from rest_framework import serializers


from student.roles import CourseStaffRole
from student.views import get_course_enrollments
from student.models import (CourseEnrollment)
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from courseware.courses import get_course_by_id
from course_progress.helpers import get_overall_progress
from openedx.core.djangoapps.models.course_details import CourseDetails
from lms.djangoapps.grades.new.course_grade import CourseGradeFactory
from cms.djangoapps.microsite_manager.models import MicrositeAdminManager
from microsite_configuration.models import Microsite
from student.models import CourseEnrollmentAllowed, UserPreprofile
from django.contrib.auth.models import User



class StudentSerializer(serializers.Serializer):
    student_info = serializers.SerializerMethodField()

    def get_student_info(self, email):
        if User.objects.filter(email=email).exists() :
            student=User.objects.get(email=email)
            # List of courses user is enrolled to
            org_filter_out_set = ''
            course_org_filter = ''
            course_enrollments = list(get_course_enrollments(student, course_org_filter, org_filter_out_set))

            #last login data_email
            last_login_brut = str(student.last_login)
            last_login = last_login_brut.split('.')

            #Check if microsite admin
            if MicrositeAdminManager.objects.filter(user=student).exists():
                check_admin_microsite = True
                microsite_key = MicrositeAdminManager.objects.get(user=student).microsite_id
                microsite_admin_org = Microsite.objects.get(pk=microsite_key).key
            else :
                check_admin_microsite = False

            #Check wich course invited first
            if CourseEnrollment.objects.filter(user=student).exists():
                course_id=CourseEnrollment.objects.filter(user=student).order_by('-created')[0].course_id
                user_org=str(course_id).split('+')[0].replace("course-v1:","")
            else :
                user_org="No organization found for user"

            #Course counters
            compteur_progress = 0
            compteur_finish = 0
            compteur_start = 0
            compteur_certified=0

            progress_courses = []
            finish_courses = []
            start_courses = []
            certified_courses = []

            _now = int(datetime.datetime.now().strftime("%s"))

            if len(course_enrollments) > 0:
              #For each course user is enrolled to
              for dashboard_index, enrollment in enumerate(course_enrollments):
                course_id = enrollment.course_overview.id
                user_id = student.id
                course_tma = get_course_by_id(enrollment.course_id)
                try:
                    course_grade_factory = CourseGradeFactory().create(student, course_tma)
                    passed = course_grade_factory.passed
                    percent = course_grade_factory.percent
                except:
                    passed = False
                    percent = 0
                course_progression = get_overall_progress(user_id,course_id)
                try:
                    _end = int(enrollment.course_overview.end.strftime("%s"))
                except:
                    _end = 0
                _progress = True
                if _end > 0 and _end < _now:
                    _progress = False

                #storing student results for this class
                q={}
                q['passed'] = passed
                q['percent'] = float(int(percent * 1000)/10)
                q['course_id'] = str(enrollment.course_id)
                q['duration'] = CourseDetails.fetch(enrollment.course_id).effort
                q['required'] = course_tma.is_required_atp
                q['content_data'] = course_tma.content_data
                q['category'] = course_tma.categ
                q['display_name_with_default'] = enrollment.course_overview.display_name_with_default
                q['course_progression'] = course_progression

                if passed :
                    compteur_certified+=1
                    certified_courses.append(q)
                if course_progression > 0 and course_progression < 100 and not passed and _progress:
                    compteur_progress+=1
                    progress_courses.append(q)
                elif ( course_progression == 100 or not _progress ) and passed:
                    compteur_finish+=1
                    finish_courses.append(q)
                elif ( course_progression == 100 or not _progress ) and not passed:
                    compteur_progress+=1
                    progress_courses.append(q)
                elif course_progression == 0 and _progress:
                    compteur_start+=1
                    start_courses.append(q)

            #Candidate status
            if student.is_staff :
                status = "Staff"
            elif check_admin_microsite :
                status = "Admin Microsite"
            else :
                status = "Student"


            context = {
                'student_id' : student.id,
                'status' : status,
                'student_mail' : student.email,
                'student_name' : student.first_name+" "+student.last_name,
                'progress_courses' : compteur_progress,
                #'progress_courses': progress_courses,
                'finished_courses' : compteur_finish,
                #'finish_courses': finish_courses,
                'started_courses':compteur_start,
                #'start_courses':start_courses,
                'certified_courses': compteur_certified,
                #'certified_course' : certified_courses,
                'user_org' : user_org,
                'last login' : last_login[0]

            }
            if check_admin_microsite :
                context['microsite_admin_org'] = microsite_admin_org

        else :
            if UserPreprofile.objects.filter(email=email).exists():
                user=UserPreprofile.objects.get(email=email)
                if CourseEnrollmentAllowed.objects.filter(email=email).exists():
                    profile=CourseEnrollmentAllowed.objects.filter(email=email).order_by('-created')
                    course_id=profile[0].course_id
                    user_org=str(course_id).split('+')[0].replace("course-v1:","")
                else :
                    user_org = "No organization found for user"

                context={
                    'student_mail' : email,
                    'student_name' : user.first_name+" "+user.last_name,
                    'status' : "User preregistered on platform",
                    'user_org':user_org
                }
            else :
                context={
                    'student_mail' : email,
                    'status' : "Unknown user",
                }

        return context
