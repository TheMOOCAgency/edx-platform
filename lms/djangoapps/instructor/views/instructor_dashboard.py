"""
Instructor Dashboard Views
"""

import logging
import datetime
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
import uuid
import pytz
import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST,require_GET
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from edxmako.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.http import Http404, HttpResponseServerError,HttpResponse
from django.conf import settings
from util.json_request import JsonResponse
from mock import patch

from openedx.core.lib.xblock_utils import wrap_xblock
from openedx.core.lib.url_utils import quote_slashes
from xmodule.html_module import HtmlDescriptor
from xmodule.modulestore.django import modulestore
from xmodule.tabs import CourseTab
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from courseware.access import has_access
from courseware.courses import get_course_by_id, get_studio_url
from django_comment_client.utils import has_forum_access
from django_comment_common.models import FORUM_ROLE_ADMINISTRATOR
from openedx.core.djangoapps.course_groups.cohorts import get_course_cohorts, is_course_cohorted, DEFAULT_COHORT_NAME
from student.models import CourseEnrollment,User,CourseEnrollment,CourseEnrollmentAllowed,UserPreprofile
from shoppingcart.models import Coupon, PaidCourseRegistration, CourseRegCodeItem
from course_modes.models import CourseMode, CourseModesArchive
from student.roles import CourseFinanceAdminRole, CourseSalesAdminRole
from certificates.models import (
    CertificateGenerationConfiguration,
    CertificateWhitelist,
    GeneratedCertificate,
    CertificateStatuses,
    CertificateGenerationHistory,
    CertificateInvalidation,
)
from certificates import api as certs_api
from bulk_email.models import BulkEmailFlag

from class_dashboard.dashboard_data import get_section_display_name, get_array_section_has_problem
from .tools import get_units_with_due_date, title_or_url
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

from openedx.core.djangolib.markup import HTML, Text
#GEOFFREY
from course_progress.helpers import get_overall_progress
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from courseware.courses import get_course_by_id
from django.db import connection,connections
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from course_progress.helpers import get_overall_progress
from lms.djangoapps.grades.new.course_grade import CourseGradeFactory
#GEOFFREY 2
from courseware.models import StudentModule
from course_api.blocks.api import get_blocks
from course_api.blocks.views import BlocksInCourseView,BlocksView

from django.db.models import Q

from lms.djangoapps.tma_grade_tracking.models import dashboardStats
from xlwt import *
import os
#GEOFFREY
log = logging.getLogger(__name__)
from pprint import pformat

#AGATHE
from course_progress.helpers import get_overall_progress
from course_progress.models import StudentCourseProgress


class InstructorDashboardTab(CourseTab):
    """
    Defines the Instructor Dashboard view type that is shown as a course tab.
    """

    type = "instructor"
    title = ugettext_noop('Instructor')
    view_name = "instructor_dashboard"
    is_dynamic = True    # The "Instructor" tab is instead dynamically added when it is enabled

    @classmethod
    def is_enabled(cls, course, user=None):
        """
        Returns true if the specified user has staff access.
        """
        return bool(user and has_access(user, 'staff', course, course.id))


def show_analytics_dashboard_message(course_key):
    """
    Defines whether or not the analytics dashboard URL should be displayed.

    Arguments:
        course_key (CourseLocator): The course locator to display the analytics dashboard message on.
    """
    if hasattr(course_key, 'ccx'):
        ccx_analytics_enabled = settings.FEATURES.get('ENABLE_CCX_ANALYTICS_DASHBOARD_URL', False)
        return settings.ANALYTICS_DASHBOARD_URL and ccx_analytics_enabled

    return settings.ANALYTICS_DASHBOARD_URL


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def instructor_dashboard_2(request, course_id):
    """ Display the instructor dashboard for a course. """
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError:
        log.error(u"Unable to find course with course key %s while loading the Instructor Dashboard.", course_id)
        return HttpResponseServerError()

    course = get_course_by_id(course_key, depth=0)

    access = {
        'admin': request.user.is_staff,
        'instructor': bool(has_access(request.user, 'instructor', course)),
        'finance_admin': CourseFinanceAdminRole(course_key).has_user(request.user),
        'sales_admin': CourseSalesAdminRole(course_key).has_user(request.user),
        'staff': bool(has_access(request.user, 'staff', course)),
        'forum_admin': has_forum_access(request.user, course_key, FORUM_ROLE_ADMINISTRATOR),
    }

    if not access['staff']:
        raise Http404()

    is_white_label = CourseMode.is_white_label(course_key)

    reports_enabled = configuration_helpers.get_value('SHOW_ECOMMERCE_REPORTS', False)

    sections = [
        _section_course_info(course, access),
        _section_membership(course, access, is_white_label),
        _section_cohort_management(course, access),
        _section_student_admin(course, access),
        _section_data_download(course, access),
    ]

    analytics_dashboard_message = None
    if show_analytics_dashboard_message(course_key):
        # Construct a URL to the external analytics dashboard
        analytics_dashboard_url = '{0}/courses/{1}'.format(settings.ANALYTICS_DASHBOARD_URL, unicode(course_key))
        link_start = HTML("<a href=\"{}\" target=\"_blank\">").format(analytics_dashboard_url)
        analytics_dashboard_message = _(
            "To gain insights into student enrollment and participation {link_start}"
            "visit {analytics_dashboard_name}, our new course analytics product{link_end}."
        )
        analytics_dashboard_message = Text(analytics_dashboard_message).format(
            link_start=link_start, link_end=HTML("</a>"), analytics_dashboard_name=settings.ANALYTICS_DASHBOARD_NAME)

        # Temporarily show the "Analytics" section until we have a better way of linking to Insights
        sections.append(_section_analytics(course, access))

    # Check if there is corresponding entry in the CourseMode Table related to the Instructor Dashboard course
    course_mode_has_price = False
    paid_modes = CourseMode.paid_modes_for_course(course_key)
    if len(paid_modes) == 1:
        course_mode_has_price = True
    elif len(paid_modes) > 1:
        log.error(
            u"Course %s has %s course modes with payment options. Course must only have "
            u"one paid course mode to enable eCommerce options.",
            unicode(course_key), len(paid_modes)
        )

    if settings.FEATURES.get('INDIVIDUAL_DUE_DATES') and access['instructor']:
        sections.insert(3, _section_extensions(course))

    # Gate access to course email by feature flag & by course-specific authorization
    if BulkEmailFlag.feature_enabled(course_key):
        sections.append(_section_send_email(course, access))

    # Gate access to Metrics tab by featue flag and staff authorization
    if settings.FEATURES['CLASS_DASHBOARD'] and access['staff']:
        sections.append(_section_metrics(course, access))

    # Gate access to Ecommerce tab
    if course_mode_has_price and (access['finance_admin'] or access['sales_admin']):
        sections.append(_section_e_commerce(course, access, paid_modes[0], is_white_label, reports_enabled))

    # Gate access to Special Exam tab depending if either timed exams or proctored exams
    # are enabled in the course

    # NOTE: For now, if we only have procotred exams enabled, then only platform Staff
    # (user.is_staff) will be able to view the special exams tab. This may
    # change in the future
    can_see_special_exams = (
        ((course.enable_proctored_exams and request.user.is_staff) or course.enable_timed_exams) and
        settings.FEATURES.get('ENABLE_SPECIAL_EXAMS', False)
    )
    if can_see_special_exams:
        sections.append(_section_special_exams(course, access))

    # Certificates panel
    # This is used to generate example certificates
    # and enable self-generated certificates for a course.
    # Note: This is hidden for all CCXs
    certs_enabled = CertificateGenerationConfiguration.current().enabled and not hasattr(course_key, 'ccx')
    if certs_enabled and access['admin']:
        sections.append(_section_certificates(course))

    disable_buttons = not _is_small_course(course_key)

    certificate_white_list = CertificateWhitelist.get_certificate_white_list(course_key)
    generate_certificate_exceptions_url = reverse(  # pylint: disable=invalid-name
        'generate_certificate_exceptions',
        kwargs={'course_id': unicode(course_key), 'generate_for': ''}
    )
    generate_bulk_certificate_exceptions_url = reverse(  # pylint: disable=invalid-name
        'generate_bulk_certificate_exceptions',
        kwargs={'course_id': unicode(course_key)}
    )
    certificate_exception_view_url = reverse(
        'certificate_exception_view',
        kwargs={'course_id': unicode(course_key)}
    )

    certificate_invalidation_view_url = reverse(  # pylint: disable=invalid-name
        'certificate_invalidation_view',
        kwargs={'course_id': unicode(course_key)}
    )

    certificate_invalidations = CertificateInvalidation.get_certificate_invalidations(course_key)

    context = {
        'course': course,
        'studio_url': get_studio_url(course, 'course'),
        'sections': sections,
        'disable_buttons': disable_buttons,
        'analytics_dashboard_message': analytics_dashboard_message,
        'certificate_white_list': certificate_white_list,
        'certificate_invalidations': certificate_invalidations,
        'generate_certificate_exceptions_url': generate_certificate_exceptions_url,
        'generate_bulk_certificate_exceptions_url': generate_bulk_certificate_exceptions_url,
        'certificate_exception_view_url': certificate_exception_view_url,
        'certificate_invalidation_view_url': certificate_invalidation_view_url,
    }

    return render_to_response('instructor/instructor_dashboard_2/instructor_dashboard_2.html', context)


## Section functions starting with _section return a dictionary of section data.

## The dictionary must include at least {
##     'section_key': 'circus_expo'
##     'section_display_name': 'Circus Expo'
## }

## section_key will be used as a css attribute, javascript tie-in, and template import filename.
## section_display_name will be used to generate link titles in the nav bar.


def _section_e_commerce(course, access, paid_mode, coupons_enabled, reports_enabled):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id
    coupons = Coupon.objects.filter(course_id=course_key).order_by('-is_active')
    course_price = paid_mode.min_price

    total_amount = None
    if access['finance_admin']:
        single_purchase_total = PaidCourseRegistration.get_total_amount_of_purchased_item(course_key)
        bulk_purchase_total = CourseRegCodeItem.get_total_amount_of_purchased_item(course_key)
        total_amount = single_purchase_total + bulk_purchase_total

    section_data = {
        'section_key': 'e-commerce',
        'section_display_name': _('E-Commerce'),
        'access': access,
        'course_id': unicode(course_key),
        'currency_symbol': settings.PAID_COURSE_REGISTRATION_CURRENCY[1],
        'ajax_remove_coupon_url': reverse('remove_coupon', kwargs={'course_id': unicode(course_key)}),
        'ajax_get_coupon_info': reverse('get_coupon_info', kwargs={'course_id': unicode(course_key)}),
        'get_user_invoice_preference_url': reverse('get_user_invoice_preference', kwargs={'course_id': unicode(course_key)}),
        'sale_validation_url': reverse('sale_validation', kwargs={'course_id': unicode(course_key)}),
        'ajax_update_coupon': reverse('update_coupon', kwargs={'course_id': unicode(course_key)}),
        'ajax_add_coupon': reverse('add_coupon', kwargs={'course_id': unicode(course_key)}),
        'get_sale_records_url': reverse('get_sale_records', kwargs={'course_id': unicode(course_key)}),
        'get_sale_order_records_url': reverse('get_sale_order_records', kwargs={'course_id': unicode(course_key)}),
        'instructor_url': reverse('instructor_dashboard', kwargs={'course_id': unicode(course_key)}),
        'get_registration_code_csv_url': reverse('get_registration_codes', kwargs={'course_id': unicode(course_key)}),
        'generate_registration_code_csv_url': reverse('generate_registration_codes', kwargs={'course_id': unicode(course_key)}),
        'active_registration_code_csv_url': reverse('active_registration_codes', kwargs={'course_id': unicode(course_key)}),
        'spent_registration_code_csv_url': reverse('spent_registration_codes', kwargs={'course_id': unicode(course_key)}),
        'set_course_mode_url': reverse('set_course_mode_price', kwargs={'course_id': unicode(course_key)}),
        'download_coupon_codes_url': reverse('get_coupon_codes', kwargs={'course_id': unicode(course_key)}),
        'enrollment_report_url': reverse('get_enrollment_report', kwargs={'course_id': unicode(course_key)}),
        'exec_summary_report_url': reverse('get_exec_summary_report', kwargs={'course_id': unicode(course_key)}),
        'list_financial_report_downloads_url': reverse('list_financial_report_downloads',
                                                       kwargs={'course_id': unicode(course_key)}),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': unicode(course_key)}),
        'look_up_registration_code': reverse('look_up_registration_code', kwargs={'course_id': unicode(course_key)}),
        'coupons': coupons,
        'sales_admin': access['sales_admin'],
        'coupons_enabled': coupons_enabled,
        'reports_enabled': reports_enabled,
        'course_price': course_price,
        'total_amount': total_amount
    }
    return section_data


def _section_special_exams(course, access):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id

    section_data = {
        'section_key': 'special_exams',
        'section_display_name': _('Special Exams'),
        'access': access,
        'course_id': unicode(course_key)
    }
    return section_data


def _section_certificates(course):
    """Section information for the certificates panel.

    The certificates panel allows global staff to generate
    example certificates and enable self-generated certificates
    for a course.

    Arguments:
        course (Course)

    Returns:
        dict

    """
    example_cert_status = None
    html_cert_enabled = certs_api.has_html_certificates_enabled(course.id, course)
    if html_cert_enabled:
        can_enable_for_course = True
    else:
        example_cert_status = certs_api.example_certificates_status(course.id)

        # Allow the user to enable self-generated certificates for students
        # *only* once a set of example certificates has been successfully generated.
        # If certificates have been misconfigured for the course (for example, if
        # the PDF template hasn't been uploaded yet), then we don't want
        # to turn on self-generated certificates for students!
        can_enable_for_course = (
            example_cert_status is not None and
            all(
                cert_status['status'] == 'success'
                for cert_status in example_cert_status
            )
        )
    instructor_generation_enabled = settings.FEATURES.get('CERTIFICATES_INSTRUCTOR_GENERATION', False)
    certificate_statuses_with_count = {
        certificate['status']: certificate['count']
        for certificate in GeneratedCertificate.get_unique_statuses(course_key=course.id)
    }

    return {
        'section_key': 'certificates',
        'section_display_name': _('Certificates'),
        'example_certificate_status': example_cert_status,
        'can_enable_for_course': can_enable_for_course,
        'enabled_for_course': certs_api.cert_generation_enabled(course.id),
        'is_self_paced': course.self_paced,
        'instructor_generation_enabled': instructor_generation_enabled,
        'html_cert_enabled': html_cert_enabled,
        'active_certificate': certs_api.get_active_web_certificate(course),
        'certificate_statuses_with_count': certificate_statuses_with_count,
        'status': CertificateStatuses,
        'certificate_generation_history':
            CertificateGenerationHistory.objects.filter(course_id=course.id).order_by("-created"),
        'urls': {
            'generate_example_certificates': reverse(
                'generate_example_certificates',
                kwargs={'course_id': course.id}
            ),
            'enable_certificate_generation': reverse(
                'enable_certificate_generation',
                kwargs={'course_id': course.id}
            ),
            'start_certificate_generation': reverse(
                'start_certificate_generation',
                kwargs={'course_id': course.id}
            ),
            'start_certificate_regeneration': reverse(
                'start_certificate_regeneration',
                kwargs={'course_id': course.id}
            ),
            'list_instructor_tasks_url': reverse(
                'list_instructor_tasks',
                kwargs={'course_id': course.id}
            ),
        }
    }


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_POST
@login_required
def set_course_mode_price(request, course_id):
    """
    set the new course price and add new entry in the CourseModesArchive Table
    """
    try:
        course_price = int(request.POST['course_price'])
    except ValueError:
        return JsonResponse(
            {'message': _("Please Enter the numeric value for the course price")},
            status=400)  # status code 400: Bad Request

    currency = request.POST['currency']
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)

    course_honor_mode = CourseMode.objects.filter(mode_slug='honor', course_id=course_key)
    if not course_honor_mode:
        return JsonResponse(
            {'message': _("CourseMode with the mode slug({mode_slug}) DoesNotExist").format(mode_slug='honor')},
            status=400)  # status code 400: Bad Request

    CourseModesArchive.objects.create(
        course_id=course_id, mode_slug='honor', mode_display_name='Honor Code Certificate',
        min_price=course_honor_mode[0].min_price, currency=course_honor_mode[0].currency,
        expiration_datetime=datetime.datetime.now(pytz.utc), expiration_date=datetime.date.today()
    )
    course_honor_mode.update(
        min_price=course_price,
        currency=currency
    )
    return JsonResponse({'message': _("CourseMode price updated successfully")})


def _section_course_info(course, access):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id

    section_data = {
        'section_key': 'course_info',
        'section_display_name': _('Course Info'),
        'access': access,
        'course_id': course_key,
        'course_display_name': course.display_name,
        'has_started': course.has_started(),
        'has_ended': course.has_ended(),
        'start_date': course.start,
        'end_date': course.end,
        'num_sections': len(course.children),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': unicode(course_key)}),
    }

    if settings.FEATURES.get('DISPLAY_ANALYTICS_ENROLLMENTS'):
        section_data['enrollment_count'] = CourseEnrollment.objects.enrollment_counts(course_key)

    if show_analytics_dashboard_message(course_key):
        #  dashboard_link is already made safe in _get_dashboard_link
        dashboard_link = _get_dashboard_link(course_key)
        #  so we can use Text() here so it's not double-escaped and rendering HTML on the front-end
        message = Text(_("Enrollment data is now available in {dashboard_link}.")).format(dashboard_link=dashboard_link)
        section_data['enrollment_message'] = message

    if settings.FEATURES.get('ENABLE_SYSADMIN_DASHBOARD'):
        section_data['detailed_gitlogs_url'] = reverse('gitlogs_detail', kwargs={'course_id': unicode(course_key)})

    try:
        sorted_cutoffs = sorted(course.grade_cutoffs.items(), key=lambda i: i[1], reverse=True)
        advance = lambda memo, (letter, score): "{}: {}, ".format(letter, score) + memo
        section_data['grade_cutoffs'] = reduce(advance, sorted_cutoffs, "")[:-2]
    except Exception:  # pylint: disable=broad-except
        section_data['grade_cutoffs'] = "Not Available"

    try:
        section_data['course_errors'] = [(escape(a), '') for (a, _unused) in modulestore().get_course_errors(course.id)]
    except Exception:  # pylint: disable=broad-except
        section_data['course_errors'] = [('Error fetching errors', '')]

    return section_data


def _section_membership(course, access, is_white_label):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id
    ccx_enabled = settings.FEATURES.get('CUSTOM_COURSES_EDX', False) and course.enable_ccx
    section_data = {
        'section_key': 'membership',
        'section_display_name': _('Membership'),
        'access': access,
        'ccx_is_enabled': ccx_enabled,
        'is_white_label': is_white_label,
        'enroll_button_url': reverse('students_update_enrollment', kwargs={'course_id': unicode(course_key)}),
        'unenroll_button_url': reverse('students_update_enrollment', kwargs={'course_id': unicode(course_key)}),
        'upload_student_csv_button_url': reverse('register_and_enroll_students', kwargs={'course_id': unicode(course_key)}),
        'modify_beta_testers_button_url': reverse('bulk_beta_modify_access', kwargs={'course_id': unicode(course_key)}),
        'list_course_role_members_url': reverse('list_course_role_members', kwargs={'course_id': unicode(course_key)}),
        'modify_access_url': reverse('modify_access', kwargs={'course_id': unicode(course_key)}),
        'list_forum_members_url': reverse('list_forum_members', kwargs={'course_id': unicode(course_key)}),
        'update_forum_role_membership_url': reverse('update_forum_role_membership', kwargs={'course_id': unicode(course_key)}),
    }
    return section_data


def _section_cohort_management(course, access):
    """ Provide data for the corresponding cohort management section """
    course_key = course.id
    ccx_enabled = hasattr(course_key, 'ccx')
    section_data = {
        'section_key': 'cohort_management',
        'section_display_name': _('Cohorts'),
        'access': access,
        'ccx_is_enabled': ccx_enabled,
        'course_cohort_settings_url': reverse(
            'course_cohort_settings',
            kwargs={'course_key_string': unicode(course_key)}
        ),
        'cohorts_url': reverse('cohorts', kwargs={'course_key_string': unicode(course_key)}),
        'upload_cohorts_csv_url': reverse('add_users_to_cohorts', kwargs={'course_id': unicode(course_key)}),
        'discussion_topics_url': reverse('cohort_discussion_topics', kwargs={'course_key_string': unicode(course_key)}),
        'verified_track_cohorting_url': reverse(
            'verified_track_cohorting', kwargs={'course_key_string': unicode(course_key)}
        ),
    }
    return section_data


def _is_small_course(course_key):
    """ Compares against MAX_ENROLLMENT_INSTR_BUTTONS to determine if course enrollment is considered small. """
    is_small_course = False
    enrollment_count = CourseEnrollment.objects.num_enrolled_in(course_key)
    max_enrollment_for_buttons = settings.FEATURES.get("MAX_ENROLLMENT_INSTR_BUTTONS")
    if max_enrollment_for_buttons is not None:
        is_small_course = enrollment_count <= max_enrollment_for_buttons
    return is_small_course


def _section_student_admin(course, access):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id
    is_small_course = _is_small_course(course_key)

    section_data = {
        'section_key': 'student_admin',
        'section_display_name': _('Student Admin'),
        'access': access,
        'is_small_course': is_small_course,
        'get_student_progress_url_url': reverse('get_student_progress_url', kwargs={'course_id': unicode(course_key)}),
        'enrollment_url': reverse('students_update_enrollment', kwargs={'course_id': unicode(course_key)}),
        'reset_student_attempts_url': reverse('reset_student_attempts', kwargs={'course_id': unicode(course_key)}),
        'reset_student_attempts_for_entrance_exam_url': reverse(
            'reset_student_attempts_for_entrance_exam',
            kwargs={'course_id': unicode(course_key)},
        ),
        'rescore_problem_url': reverse('rescore_problem', kwargs={'course_id': unicode(course_key)}),
        'rescore_entrance_exam_url': reverse('rescore_entrance_exam', kwargs={'course_id': unicode(course_key)}),
        'student_can_skip_entrance_exam_url': reverse(
            'mark_student_can_skip_entrance_exam',
            kwargs={'course_id': unicode(course_key)},
        ),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': unicode(course_key)}),
        'list_entrace_exam_instructor_tasks_url': reverse('list_entrance_exam_instructor_tasks',
                                                          kwargs={'course_id': unicode(course_key)}),
        'spoc_gradebook_url': reverse('spoc_gradebook', kwargs={'course_id': unicode(course_key)}),
    }
    return section_data


def _section_extensions(course):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'extensions',
        'section_display_name': _('Extensions'),
        'units_with_due_dates': [(title_or_url(unit), unicode(unit.location))
                                 for unit in get_units_with_due_date(course)],
        'change_due_date_url': reverse('change_due_date', kwargs={'course_id': unicode(course.id)}),
        'reset_due_date_url': reverse('reset_due_date', kwargs={'course_id': unicode(course.id)}),
        'show_unit_extensions_url': reverse('show_unit_extensions', kwargs={'course_id': unicode(course.id)}),
        'show_student_extensions_url': reverse('show_student_extensions', kwargs={'course_id': unicode(course.id)}),
    }
    return section_data


def _section_data_download(course, access):
    """ Provide data for the corresponding dashboard section """
    course_key = course.id

    show_proctored_report_button = (
        settings.FEATURES.get('ENABLE_SPECIAL_EXAMS', False) and
        course.enable_proctored_exams
    )

    section_data = {
        'section_key': 'data_download',
        'section_display_name': _('Data Download'),
        'access': access,
        'show_generate_proctored_exam_report_button': show_proctored_report_button,
        'get_problem_responses_url': reverse('get_problem_responses', kwargs={'course_id': unicode(course_key)}),
        'get_grading_config_url': reverse('get_grading_config', kwargs={'course_id': unicode(course_key)}),
        'get_students_features_url': reverse('get_students_features', kwargs={'course_id': unicode(course_key)}),
        'get_issued_certificates_url': reverse(
            'get_issued_certificates', kwargs={'course_id': unicode(course_key)}
        ),
        'get_students_who_may_enroll_url': reverse(
            'get_students_who_may_enroll', kwargs={'course_id': unicode(course_key)}
        ),
        'get_anon_ids_url': reverse('get_anon_ids', kwargs={'course_id': unicode(course_key)}),
        'list_proctored_results_url': reverse('get_proctored_exam_results', kwargs={'course_id': unicode(course_key)}),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': unicode(course_key)}),
        'list_report_downloads_url': reverse('list_report_downloads', kwargs={'course_id': unicode(course_key)}),
        'calculate_grades_csv_url': reverse('calculate_grades_csv', kwargs={'course_id': unicode(course_key)}),
        'problem_grade_report_url': reverse('problem_grade_report', kwargs={'course_id': unicode(course_key)}),
        'course_has_survey': True if course.course_survey_name else False,
        'course_survey_results_url': reverse('get_course_survey_results', kwargs={'course_id': unicode(course_key)}),
        'export_ora2_data_url': reverse('export_ora2_data', kwargs={'course_id': unicode(course_key)}),
    }
    return section_data


def null_applicable_aside_types(block):  # pylint: disable=unused-argument
    """
    get_aside method for monkey-patching into applicable_aside_types
    while rendering an HtmlDescriptor for email text editing. This returns
    an empty list.
    """
    return []


def _section_send_email(course, access):
    """ Provide data for the corresponding bulk email section """
    course_key = course.id

    # Monkey-patch applicable_aside_types to return no asides for the duration of this render
    with patch.object(course.runtime, 'applicable_aside_types', null_applicable_aside_types):
        # This HtmlDescriptor is only being used to generate a nice text editor.
        html_module = HtmlDescriptor(
            course.system,
            DictFieldData({'data': ''}),
            ScopeIds(None, None, None, course_key.make_usage_key('html', 'fake'))
        )
        fragment = course.system.render(html_module, 'studio_view')
    fragment = wrap_xblock(
        'LmsRuntime', html_module, 'studio_view', fragment, None,
        extra_data={"course-id": unicode(course_key)},
        usage_id_serializer=lambda usage_id: quote_slashes(unicode(usage_id)),
        # Generate a new request_token here at random, because this module isn't connected to any other
        # xblock rendering.
        request_token=uuid.uuid1().get_hex()
    )
    cohorts = []
    if is_course_cohorted(course_key):
        cohorts = get_course_cohorts(course)
    email_editor = fragment.content
    section_data = {
        'section_key': 'send_email',
        'section_display_name': _('Email'),
        'access': access,
        'send_email': reverse('send_email', kwargs={'course_id': unicode(course_key)}),
        'editor': email_editor,
        'cohorts': cohorts,
        'default_cohort_name': DEFAULT_COHORT_NAME,
        'list_instructor_tasks_url': reverse(
            'list_instructor_tasks', kwargs={'course_id': unicode(course_key)}
        ),
        'email_background_tasks_url': reverse(
            'list_background_email_tasks', kwargs={'course_id': unicode(course_key)}
        ),
        'email_content_history_url': reverse(
            'list_email_content', kwargs={'course_id': unicode(course_key)}
        ),
    }
    return section_data


def _get_dashboard_link(course_key):
    """ Construct a URL to the external analytics dashboard """
    analytics_dashboard_url = '{0}/courses/{1}'.format(settings.ANALYTICS_DASHBOARD_URL, unicode(course_key))
    link = HTML(u"<a href=\"{0}\" target=\"_blank\">{1}</a>").format(
        analytics_dashboard_url, settings.ANALYTICS_DASHBOARD_NAME
    )
    return link


def _section_analytics(course, access):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'instructor_analytics',
        'section_display_name': _('Analytics'),
        'access': access,
        'course_id': unicode(course.id),
    }
    return section_data


def _section_metrics(course, access):
    """Provide data for the corresponding dashboard section """
    course_key = course.id
    section_data = {
        'section_key': 'metrics',
        'section_display_name': _('Metrics'),
        'access': access,
        'course_id': unicode(course_key),
        'sub_section_display_name': get_section_display_name(course_key),
        'section_has_problem': get_array_section_has_problem(course_key),
        'get_students_opened_subsection_url': reverse('get_students_opened_subsection'),
        'get_students_problem_grades_url': reverse('get_students_problem_grades'),
        'post_metrics_data_csv_url': reverse('post_metrics_data_csv'),
    }
    return section_data


# GEOFFREY STAT DASHBOARD
# GEOFFREY STAT DASHBOARD
# GEOFFREY STAT DASHBOARD
# GEOFFREY STAT DASHBOARD

@login_required
def stat_dashboard(request, course_id):
    #GET course_key
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    course_key_modulestore = CourseKey.from_string(course_id)
    #course_module
    course_module = modulestore().get_course(course_key, depth=0)
    #course cutoff
    course_cutoff = course_module.grade_cutoffs['Pass']
    #GET COURSE
    course = get_course_by_id(course_key)
    #overview
    overview = CourseOverview.get_from_id(course_key)
    #Get all course-enrollment
    row = User.objects.raw('SELECT a.id ,a.email FROM auth_user a,student_courseenrollment b WHERE a.id=b.user_id AND b.course_id=%s' ,[course_id])
    invite = CourseEnrollmentAllowed.objects.all().filter(course_id=course_key)
    participant_list = []
    all_user = 0
    for _user in row:
        participant_list.append(_user.email)
        all_user = all_user + 1
    for _u in invite:
        if not str(_u.email) in str(participant_list):
            all_user = all_user + 1
    #number of user who started the course
    user_course_started = 0
    #number of users who completed the entire quiz
    users_completed_quiz = 0
    #count passed
    num_passed = 0
    #add course average grade
    course_average_grade = 0
    course_average_grade_global = 0
    #number of user who finished the course
    user_finished = 0
    # Users who completed the quiz entirely
    user_completed_quiz = 0
    user_completed_quiz_list = []
    #course_structure
    course_structure = get_course_structure(request,course_id)
    course_usage_key = modulestore().make_course_usage_key(course_key)
    blocks = get_blocks(request,course_usage_key,depth='all',requested_fields=['display_name','children'])

    # Users who completed the quiz (overall_progress equals 100.0 only if user completed the quiz)
    for user in row:
        overall_progress = get_overall_progress(user.id, course_key)
        if overall_progress == 100.0:
            users_completed_quiz = users_completed_quiz + 1
            user_completed_quiz_list.append(user.username)

    # connect mongodb return values:
    mongo_persist = dashboardStats()
    collection = mongo_persist.connect()
    find_mongo_persist_course = mongo_persist.find_by_course_id(collection,course_id)
    for n in row:
        user_id = n.id
        users = User.objects.get(pk=user_id)

    try:
        users_info = find_mongo_persist_course['users_info']
        for key, value in users_info.iteritems():
            #log.info("user_info key:"+pformat(key)+" value"+pformat(value))
            _passed = value['passed']
            _percent = value['percent']
            user_course_started = user_course_started + 1
            # Average grade of all users who completed the quiz
            _username = value['username']
            if _username in user_completed_quiz_list:
                course_average_grade_global = course_average_grade_global + (_percent * 100)
            # Average grade of users who passed the quiz
            if _passed:
                course_average_grade = course_average_grade + (_percent * 100)
                user_finished = user_finished + 1
                if _percent >= course_cutoff:
                    num_passed = num_passed + 1
    except:
        pass

    #return context
    if user_finished != 0:
        final_course_average_grade = round((course_average_grade / user_finished),1)
    else :
        final_course_average_grade=0.0

    if users_completed_quiz !=0:
        course_average_grade_global = round((course_average_grade_global / users_completed_quiz), 1)
    else :
        course_average_grade_global=0.0

    #store problems components order
    problem_components=[]
    for chapter in course_structure:
      for section in chapter['children']:
        for vertical in section['children']:
          for component in vertical['children']:
            if 'problem' in str(component):
              problem_components.append(str(component))

    context = {
     "course_id":course_id,
     "course":course,
     "row":row,
     'course_module':course_module,
     "all_user":all_user,
     "num_passed":num_passed,
     "user_course_started":user_course_started,
     'course_average_grade':final_course_average_grade,
     'course_average_grade_global': course_average_grade_global,
     'user_finished':user_finished,
     'course_structure':course_structure,
     'overview':overview,
     'language_course':get_course_langue(course.language),
     'problem_components':problem_components
    }

    return render_to_response('courseware/stat.html', context)

@ensure_csrf_cookie
@login_required
def get_dashboard_username(request,course_id,email):
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    row = User.objects.raw('SELECT a.id,a.email,a.first_name,a.last_name FROM auth_user a,student_courseenrollment b WHERE a.id=b.user_id AND b.course_id=%s' ,[course_id])
    emails = []
    email = str(email).lower()
    for n in row:
        low = [
            n.email.lower(),
            n.first_name.lower(),
            n.last_name.lower()
        ]
        if email in str(low).lower():
            q = {
                "values" : [
                    n.email,
                    n.first_name,
                    n.last_name
                ],
                "id":n.email
            }
            emails.append(q)
    response = JsonResponse({
            "usernames":emails,
            "email":email
        })

    return response

@ensure_csrf_cookie
@login_required
def stat_dashboard_username(request, course_id, email):
    try:
        # get users info
        users = User.objects.get(email=email)
        #user_email
        user_email = users.email
        lvl_1 = ''
        lvl_2 = ''
        lvl_3 = ''
        lvl_4 = ''
        try:
            preprofile = UserPreprofile.objects.get(email=user_email).first()
            lvl_1 = preprofile.level_1
            lvl_2 = preprofile.level_2
            lvl_3 = preprofile.level_3
            lvl_4 = preprofile.level_4
        except:
            pass

        #ordered course
        course_grade = []
        ordered_course_grade=[]
        quiz_order=get_quiz_structure(request, course_id)

        # get user id
        user_id= users.id
        # get course_key from url's param
        course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
        # get course from course_key
        course = get_course_by_id(course_key)
        # get all courses block of the site
        course_block = StudentModule.objects.all().filter(student_id=user_id,course_id=course_key,max_grade__isnull=False)
        # var of grades / course_structure
        course_grade = []
        # get course_users_info
        course_user_info = CourseGradeFactory().create(users, course)
        # user info responses
        user_info = [
        {'Score':str(course_user_info.percent * 100)+'%'},
        {'First_name':users.first_name},
        {'Last_name':users.last_name},
        {'Email':users.email},
        {'Niveau_1':lvl_1},
        {'Niveau_2':lvl_2},
        {'Niveau_3':lvl_3},
        {'Niveau_4':lvl_4}
        ]
        for n in course_block:
            q = {}
            usage_key = n.module_state_key
            block_view = BlocksView()
            block_name = get_blocks(request,usage_key,depth='all',requested_fields=['display_name'])
            root = block_name['root']
            display_name = block_name['blocks'][root]['display_name']
            q['earned'] = n.grade
            q['possible'] = n.max_grade
            q['display_name'] = display_name
            q['root'] = root
            course_grade.append(q)

        #Order blocks
        for id in quiz_order:
            for block in course_grade :
                if block['root']==str(id):
                    ordered_course_grade.append(block)

        return JsonResponse({
                "course_id":course_id,
        		"email":email,
                "user_id":user_id,
                "course_grade": ordered_course_grade,
                "user_info": user_info,
                "quiz_order":quiz_order
            })
    except:
        return JsonResponse({
                "course_id":course_id,
        		"username":username,
                "user_id": '',
                "course_grade": [],
                "user_info": '',
            })


@login_required
def get_course_structure(request, course_id):

    course_key = CourseKey.from_string(course_id)
    course_usage_key = modulestore().make_course_usage_key(course_key)
    blocks = get_blocks(request,course_usage_key,depth='all',requested_fields=['display_name','children'])
    root = blocks['root']
    blocks_overviews = []
    try:
        children = blocks['blocks'][root]['children']
        for z in children:
            q = {}
            child = blocks['blocks'][z]
            q['display_name'] = child['display_name']
            q['id'] = child['id']
            try:
                sub_section = child['children']
                q['children'] = []
                for s in sub_section:
                    sub_ = blocks['blocks'][s]
                    a = {}
                    a['id'] = sub_['id']
                    a['display_name'] = sub_['display_name']
                    vertical = sub_['children']
                    try:
                        a['children'] = []
                        for v in vertical:
                            unit = blocks['blocks'][v]
                            w = {}
                            w['id'] = unit['id']
                            w['display_name'] = unit['display_name']
                            try:
                                w['children'] = unit['children']
                            except:
                                w['children'] = []
                            a['children'].append(w)
                    except:
                        a['children'] = []
                    q['children'].append(a)
            except:
                q['children'] = []
            blocks_overviews.append(q)
    except:
        children = ''
    return blocks_overviews


@ensure_csrf_cookie
@login_required
@require_POST
def get_course_blocks_grade(request,course_id):

    data = json.loads(request.body)
    data_id = data.get('data_id')
    course_block = StudentModule.objects.raw("SELECT id,AVG(grade) AS moyenne,count(id) AS total,MAX(max_grade) AS max_grade,course_id,module_id FROM courseware_studentmodule WHERE course_id = %s AND max_grade IS NOT NULL AND grade <= max_grade GROUP BY module_id", [course_id])
    course_grade = {}
    for n in course_block:
        usage_key = n.module_state_key
        block_view = BlocksView()
        try:
            block_name = get_blocks(request,usage_key,depth='all',requested_fields=['display_name'])
            root = block_name['root']
            for z in data_id:
                if root in z.get('id'):
                    if not root in course_grade:
                        course_grade[root] = {}
                        course_grade[root]['moyenne'] = n.moyenne
                        course_grade[root]['total'] = n.total
                        course_grade[root]['max_grade'] = n.max_grade
                        course_grade[root]['course_id'] = str(n.course_id)
                        course_grade[root]['module_id'] = str(n.module_state_key)
                        course_grade[root]['display_name'] = block_name['blocks'][root]['display_name']
                        course_grade[root]['vertical_name'] = z.get('title')

        except:
            pass

    return JsonResponse({'course_grade':course_grade})

def get_result_page_info(request,course_id):

    response = JsonResponse({
      "course_id":course_id
    })

    return response

@ensure_csrf_cookie
@login_required
@require_GET
def get_course_users(request,course_id):

    #Get all course-enrollment
    """
    UserPreprofile
    CourseEnrollment
    CourseEnrollmentAllowed
    """
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    invite = CourseEnrollmentAllowed.objects.all().filter(course_id=course_key)
    enroll = CourseEnrollment.objects.all().filter(course_id=course_key)
    users = []
    for _ui in invite:
        email = _ui.email
        if not str(email) in str(users):
            q = {}
            q['email'] = email
            q['statut'] = 'sent'
            q['Nom'] = ''
            q['Prenom'] = ''
            q['Niveau 1'] = ''
            q['Niveau 2'] = ''
            q['Niveau 3'] = ''
            q['Niveau 4'] = ''
            users.append(q)

    for _ue in enroll:
        try:
            email = User.objects.get(pk=_ue.user_id).email
            if not str(email) in str(users):
                q = {}
                q['email'] = email
                q['statut'] = 'accepted'
                q['Nom'] = ''
                q['Prenom'] = ''
                q['Niveau 1'] = ''
                q['Niveau 2'] = ''
                q['Niveau 3'] = ''
                q['Niveau 4'] = ''
                users.append(q)
            else:
                for user in users:
                    if user['email'] == email:
                        user['statut'] = 'accepted'
        except:
            pass

    for user in users:
        try:
            email = user['email']
            profile = UserPreprofile.objects.get(email=email).first()
            user['Nom'] = profile.last_name
            user['Prenom'] = profile.first_name
            user['Niveau 1'] = profile.level_1
            user['Niveau 2'] = profile.level_2
            user['Niveau 3'] = profile.level_3
            user['Niveau 4'] = profile.level_4
        except:
            pass

    filename = '{}_registered_users.xls'.format(course_id).replace('+','_')
    filepath = '/edx/var/edxapp/'+filename
    HEADERS = (u"Nom",u"Prenom",u"Adresse email",u"Niveau 1",u"Niveau 2",u"Niveau 3",u"Niveau 4",u"Statut")
    wb = Workbook(encoding='utf-8')
    sheet = wb.add_sheet('Users')

    for i, header in enumerate(HEADERS):
        sheet.write(0, i, header)

    j = 0
    for i in range(len(users)):
        j=j+1
        try:
            sheet.write(j, 0, users[i]['Nom'])
        except:
            sheet.write(j, 0, ' ')
        try:
            sheet.write(j, 1, users[i]['Prenom'])
        except:
            sheet.write(j, 1, ' ')
        try:
            sheet.write(j, 2, users[i]['email'])
        except:
            sheet.write(j, 2, ' ')
        try:
            sheet.write(j, 3, users[i]['Niveau 1'])
        except:
            sheet.write(j, 3, ' ')
        try:
            sheet.write(j, 4, users[i]['Niveau 2'])
        except:
            sheet.write(j, 4, ' ')
        try:
            sheet.write(j, 5, users[i]['Niveau 3'])
        except:
            sheet.write(j, 5, ' ')
        try:
            sheet.write(j, 6, users[i]['Niveau 4'])
        except:
            sheet.write(j, 6, ' ')
        try:
            sheet.write(j, 7, users[i]['statut'])
        except:
            sheet.write(j, 7, ' ')

    wb.save(filepath)

    context = {
        'filename':filename,
        'users':str(users)
    }

    return JsonResponse(context)

def download_xls(request,filename):
    full_path = '/edx/var/edxapp/'+filename
    _file = open(full_path,'r')
    _content = _file.read()
    response = HttpResponse(_content, content_type="application/vnd.ms-excel")
    response['Content-Disposition'] = "attachment; filename="+filename
    os.remove(full_path)
    return response

#generate current_course grade reports

@ensure_csrf_cookie
@login_required
@require_GET
def get_course_users_grades(request,course_id):

    # connect mongodb return values:
    mongo_persist = dashboardStats()
    collection = mongo_persist.connect()
    find_mongo_persist_course = mongo_persist.find_by_course_id(collection,course_id)
    # get users saved data
    users_info = find_mongo_persist_course.get('users_info')
    #get users id
    users_id = users_info.keys()
    q = {
        'title': [
            'email','first name','last name'
        ],
        'users': []
    }

    k = 0
    for _user_id in users_id:
        #try:
        current = users_info[_user_id]
        user = User.objects.get(pk=users_info[str(_user_id)]["user_id"])
        percent = str(current["percent"] * 100)+'%'
        summary = current["summary"]["section_breakdown"]
        user_info = {
            'email':user.email,
            'first_name':user.first_name,
            'last_name':user.last_name,
            'percent': percent,
            'grades':[]
        }

        for section in summary:
            if k == 0:
                if not section['label'] in q['title']:
                    q['title'].append(section['label'])
            _section = {
                'label':section['label'],
                'percent':str(section['percent'] * 100)+'%'
            }
            user_info['grades'].append(_section)
        q['users'].append(user_info)

        k = k + 1
        """
        except:
            pass
        """
    if not 'final grade' in q['title']:
        q['title'].append('final grade')
    filename = '{}_grades_reports.xls'.format(course_id).replace('+','_')
    filepath = '/edx/var/edxapp/'+filename
    HEADERS = q['title']
    wb = Workbook(encoding='utf-8')
    sheet = wb.add_sheet('Grades')

    for i, header in enumerate(HEADERS):
        sheet.write(0, i, header)

    j = 0
    for i in range(len(q['users'])):
        j=j+1
        try:
            sheet.write(j, 0, q['users'][i]['email'])
        except:
            sheet.write(j, 0, ' ')
        try:
            sheet.write(j, 1, q['users'][i]['first_name'])
        except:
            sheet.write(j, 1, ' ')
        try:
            sheet.write(j, 2, q['users'][i]['last_name'])
        except:
            sheet.write(j, 2, ' ')
        d = 2
        for grade in q['users'][i]['grades']:
            d = d + 1
            try:
                sheet.write(j, d, grade['percent'])
            except:
                sheet.write(j, d, ' ')
        d = d + 1
        sheet.write(j, d, q['users'][i]['percent'])

    wb.save(filepath)

    context = {
        'filename':filename,
        'course_id':course_id
    }

    return JsonResponse(context)

def download_grades(request,filename):
    full_path = '/edx/var/edxapp/'+filename
    _file = open(full_path,'r')
    _content = _file.read()
    response = HttpResponse(_content, content_type="application/vnd.ms-excel")
    response['Content-Disposition'] = "attachment; filename="+filename
    os.remove(full_path)
    return response

def get_list_lang():
    language_options_tulp=settings.ALL_LANGUAGES
    language_options_dict={}
    for lang, label in language_options_tulp:
        language_options_dict[lang]=label
    return language_options_dict

def get_course_langue(lang_code):
    language_options_dict=get_list_lang()
    course_language=language_options_dict[lang_code]
    return course_language

def get_quiz_structure(request, course_id):
  course_key = CourseKey.from_string(course_id)
  course_usage_key = modulestore().make_course_usage_key(course_key)
  course_blocks = get_blocks(request,course_usage_key,depth='all',requested_fields=['display_name','children'])
  blocks_overviews = []
  quiz_elements=[]
  blocks_list=[]

  for block in course_blocks['blocks'] :
    if course_blocks['blocks'][block].get('children') and "problem" in course_blocks['blocks'][block].get('children')[0]:
      blocks_list=course_blocks['blocks'][block]['children']
  return blocks_list
