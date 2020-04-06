# -*- coding: utf-8 -*-

import errno
import os
import re
import logging
import json
import requests

from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, QueryDict
from django.views.generic import View
from django.contrib.sites.models import Site
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.conf import settings
from edxmako.shortcuts import render_to_response, render_to_string
from util.json_request import  JsonResponse, JsonResponseBadRequest
from util.views import require_global_staff

from django.contrib.auth.models import User

from organizations.models import Organization
from microsite_configuration.models import (
    Microsite,
    MicrositeOrganizationMapping,
    MicrositeTemplate,

)
from .models import MicrositeDetail , MicrositeAdminManager
from .libs import copydirectorykut,microsite_staff
import unicodedata
from distutils.dir_util import copy_tree




log = logging.getLogger(__name__)



class microsite_manager():
    def __init__(self):
        self.logo = None
        self.logo_couleur = None
        self.microsite_name = None
        self.primary_color = None
        self.secondary_color = None
        self.third_color = None
        self.third_bg_color = None
        self.white_or_color_logo = None
        self.language = None
        self.contact_address = None
        self.amundi_brand = None
        self.disclaimer=None
        self.trademark=None

    #CHECK ALL ELEMENTS AND CREATE MICROSITE
    def remove_accents(self, input_str):
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

    def create(self,request):
        logo_couleur_ext = request.FILES.get('logo_couleur').name.split('.')[1]

        #SAVE MICROSITE DETAILS TO DISPLAY IN LIST BACK
        microsite_details = {}
        microsite_details['name'] = request.POST['display_name']
        microsite_details['name'] = microsite_details['name'].lower()
        microsite_details['primary_color'] = request.POST['primary_color']
        microsite_details['color'] = '#000000'
        microsite_details['secondary_color'] = request.POST['secondary_color']
        microsite_details['third_color'] = request.POST['third_color']
        microsite_details['third_bg_color'] = request.POST['third_bg_color']
        microsite_details['white_or_color_logo'] = request.POST['white_or_color_logo']
        microsite_details['logo'] = 'logo_couleur.'+logo_couleur_ext
        microsite_details['language_code'] = request.POST['language']

        details_status = MicrositeDetail.save_details(microsite_details)

        log.info(u'microsite_manager.create start')
        context = {
            "mode":"create",
            "status":False
        }
        require_keys = [
            'display_name','logo','primary_color',
            'secondary_color','third_color','third_bg_color','white_or_color_logo','language',
            'logo_couleur', 'contact_address', 'amundi_brand'
        ]
        if request.method == 'POST':
            #CHECK ALL REQUIRED ELEMENTS ARE SENT BY POST
            _ensure = True
            for key,value in request.POST.items():
                log.info(u'microsite_manager.create key:{},value:{}'.format(str(key),str(value)))
                if not key in require_keys or not value:
                    _ensure = False
            for key,value in request.FILES.items():
                log.info(u'microsite_manager.create key:{},value:{}'.format(str(key),str(value)))
                if not key in require_keys or not value:
                    _ensure = False

            #IF REQUEST POST IS OK
            if _ensure:
                log.info(u'microsite_manager.create _ensure')
                log.info(u'request.POST : {}'.format(str(request.POST.__dict__)))
                log.info(u'request.FILES : {}'.format(str(request.FILES.__dict__)))
                #add request values to class attributes
                self.add(
                    microsite_name=request.POST.get('display_name'),
                    logo=request.FILES.get('logo'),
                    logo_couleur=request.FILES.get('logo_couleur'),
                    primary_color=request.POST.get('primary_color'),
                    secondary_color=request.POST.get('secondary_color'),
                    third_color=request.POST.get('third_color'),
                    third_bg_color=request.POST.get('third_bg_color'),
                    white_or_color_logo=request.POST.get('white_or_color_logo'),
                    language = request.POST.get('language'),
                    contact_address = request.POST.get('contact_address'),
                    amundi_brand = request.POST.get('amundi_brand'),
                    disclaimer=request.POST.get('disclaimer'),
                    trademark=request.POST.get('trademark')
                )

                #microsite values to sql db
                # Set the mother domain name
                mother_domain = settings.LMS_BASE

                #set cookie domain
                cookie_domain = '.' + mother_domain

                # Create site
                site_name = self.microsite_name + '.' + mother_domain
                log.info(u'microsite_manager.create site')
                site, created = Site.objects.get_or_create(
                    domain=site_name,
                    name=self.microsite_name.capitalize()
                )
                # Create microsite using Database backend
                log.info(u'microsite_manager.create microsite')
                microsite = Microsite.objects.create(
                    site=site,
                    key=self.microsite_name,

                    values = {
                     "domain_prefix":self.microsite_name,
                     "university":self.microsite_name,
                     "platform_name":self.microsite_name,
                     "logo":"/media/microsite/"+self.microsite_name+"/images/"+self.logo.name,
                     "logo_couleur":"/media/microsite/"+self.microsite_name+"/images/"+self.logo_couleur.name,
                     "ENABLE_MKTG_SITE":False,
                     "SITE_NAME":site_name,
                     "course_org_filter":self.microsite_name,
                     "course_about_show_social_links":False,
                     "css_overrides_file":"/media/microsite/"+self.microsite_name+"/css/style.css",
                     "css_overrides_nav":"/media/microsite/"+self.microsite_name+"/css/nav.css",
                     "css_overrides_dashboard":"/media/microsite/"+self.microsite_name+"/css/dashboard.css",
                     "css_overrides_course_about":"/media/microsite/"+self.microsite_name+"/css/course_about.css",
                     "css_overrides_courseware":"/media/microsite/"+self.microsite_name+"/css/courseware.css",
                     "css_overrides_stat_dashboard":"/media/microsite/"+self.microsite_name+"/css/stat_dashboard.css",
                     "css_overrides_footer":"/media/microsite/"+self.microsite_name+"/css/footer.css",
                     "css_overrides_main":"/media/microsite/"+self.microsite_name+"/css/main.css",
                     "primary_color":self.primary_color,
                     "secondary_color":self.secondary_color,
                     "third_color":self.third_color,
                     "third_bg_color":self.third_bg_color,
                     "white_or_color_logo":self.white_or_color_logo,
                     "show_partners":False,
                     "show_homepage_promo_video":False,
                     "course_index_overlay_text":"Bienvenue sur "+self.microsite_name,
                     "homepage_overlay_html":"<h1>"+self.microsite_name+"</h1>",
                     "ENABLE_THIRD_PARTY_AUTH":True,
                     "ALLOW_AUTOMATED_SIGNUPS":True,
                     "ALWAYS_REDIRECT_HOMEPAGE_TO_DASHBOARD_FOR_AUTHENTICATED_USER":True,
                     "course_email_from_addr":"ne-pas-repondre@themoocagency.com",
                     "SESSION_COOKIE_DOMAIN":cookie_domain,
                     "language_code":self.language,
                     "contact_address":self.contact_address,
                     "amundi_brand":self.amundi_brand,
                     "disclaimer":self.disclaimer,
                     "trademark":self.trademark
                     }
                )

                # Create organization
                log.info(u'microsite_manager.create organization')
                organization, created = Organization.objects.get_or_create(
                    name=self.microsite_name,
                    short_name=self.microsite_name,
                    active=True
                )
                # Create organization - microstite mapping
                log.info(u'microsite_manager.create organization_microsite_mapping')
                organization_microsite_mapping = MicrositeOrganizationMapping.objects.create(
                    organization=organization.name,
                    microsite=microsite
                )
                #add static values
                log.info(u'microsite_manager.create add_static_values')
                _static = self.add_static_values()
                context["status"] = _static
                context["url"] = '/home'

        return JsonResponse(context)

    #CHECK FORMAT ADD MICROSITE ATTRIBUTES (colors etc...) to self attributes
    def add(self,microsite_name=None,logo=None,logo_couleur=None,bg_img=None,primary_color=None,secondary_color=None,third_color=None,third_bg_color=None,white_or_color_logo=None,language=None,contact_address=None, amundi_brand=None, disclaimer=None, trademark=None):
        log.info(u'microsite_manager.add start')

        valid_ext = ['jpg','jpeg','png']
        valid_ico = ['jpg','jpeg','png','ico']

        #erase all accents and spaces in file names
        if logo is not None:
            logo.name=self.remove_accents(logo.name)
            logo.name=logo.name.replace(' ', '_')
        if logo_couleur is not None:
            logo_couleur.name=self.remove_accents(logo_couleur.name)
            logo_couleur.name=logo_couleur.name.replace(' ', '_')

        #ensure logo formatis valid
        if logo is not None:
            l_ext = logo.name.split('.')[1]
            log.info(u'microsite_manager.add logo name : {}'.format(str(logo.name)))
            if l_ext.lower() in valid_ext:
                log.info(u'microsite_manager.add logo ext : {}'.format(str(l_ext)))
                logo.name = "logo.{}".format(l_ext)
                self.logo = logo
        #ensure logo_couleur is valid
        if logo_couleur is not None:
            lcouleur_ext = logo_couleur.name.split('.')[1]
            log.info(u'microsite_manager.add logo_couleur name : {}'.format(str(logo_couleur.name)))
            if lcouleur_ext.lower() in valid_ext:
                log.info(u'microsite_manager.add logo_couleur ext : {}'.format(str(lcouleur_ext)))
                logo_couleur.name = "logo_couleur.{}".format(lcouleur_ext)
                self.logo_couleur = logo_couleur

        if microsite_name !='':
            self.microsite_name = microsite_name
        if language !='':
            self.language = language
        if primary_color!='':
            self.primary_color = primary_color
        if secondary_color!='':
            self.secondary_color = secondary_color
        if third_color!='':
            self.third_color = third_color
        if third_bg_color!='':
            self.third_bg_color = third_bg_color
        if white_or_color_logo!='':
            self.white_or_color_logo = white_or_color_logo
        if contact_address!='':
            self.contact_address=contact_address
        if amundi_brand!='':
            if amundi_brand=="false" :
                self.amundi_brand=False
            if amundi_brand =="true":
                self.amundi_brand=True
        if trademark!='':
            self.trademark=trademark
        else :
            self.trademark=''
        if disclaimer!='' and disclaimer is not None:
            self.disclaimer=disclaimer
        else :
            self.disclaimer=''

    #DISPLAY MICROSITE DATA AND MANAGE IT
    def manage_microsite_data(self, request, microsite_id=None):
        microsite_details = MicrositeDetail.objects.get(id=microsite_id)
        microsite_name = microsite_details.name
        microsite = Microsite.objects.get(key=microsite_name)
        microsite_value = microsite.values
        lang_key = 0
        logo_key = 0
        primary_key = 0
        secondary_key = 0
        third_key = 0
        third_bg_key = 0
        white_or_color_logo_key = 0
        i = 0
        for n in microsite_value:
            if n == 'language_code':
                lang_key = i
            if n == 'logo':
                logo_key = i
            if n == 'primary_color':
                primary_key = i
            if n == 'secondary_color':
                secondary_key = i
            if n == 'third_color':
                third_key = i
            if n == 'third_bg_color':
                third_bg_key = i
            if n == 'white_or_color_logo':
                white_or_color_logo_key = i
            if n == 'logo_couleur':
                logo_couleur_key = i
            if n == 'amundi_brand':
                amundi_brand_key = i
            if n == 'contact_address':
                contact_address_key = i
            if n == 'disclaimer':
                disclaimer_key = i
            if n == 'trademark':
                trademark_key = i
            i = i + 1

        context = {}
        context['key'] = microsite_name
        context['primary_color'] = microsite_value.values()[primary_key]
        context['secondary_color'] = microsite_value.values()[secondary_key]
        context['third_color'] = microsite_value.values()[third_key]
        context['third_bg_color'] = microsite_value.values()[third_bg_key]
        context['white_or_color_logo'] = microsite_value.values()[white_or_color_logo_key]
        context['logo_site'] = microsite_value.values()[logo_key]
        try:
            context['logo_couleur'] = microsite_value.values()[logo_couleur_key]
        except:
            context['logo_couleur'] ='';
        try:
            context['amundi_brand'] = microsite_value.values()[amundi_brand_key]
        except:
            context['amundi_brand'] ='';
        try:
            context['contact_address'] = microsite_value.values()[contact_address_key]
        except:
            context['contact_address'] ='';
        try:
            context['disclaimer'] = microsite_value.values()[disclaimer_key]
        except:
            context['disclaimer'] ='';
        try:
            context['trademark'] = microsite_value.values()[trademark_key]
        except:
            context['trademark'] ='';
        context['language_code'] = microsite_value.values()[lang_key]
        context['microsite_value'] = microsite_value
        context['microsite_admin'] = self.get_microsite_admin_manager(microsite)
        return render_to_response('update-microsite.html',context)

    #UPDATE MICROSITE DATA
    def update_microsite_data(self,request, microsite_id=None):
        if request.method == 'POST':
            log.info(u'microsite_manager.update_static microsite_id : {} user_email = {}'.format(str(microsite_id),str(request.user.email)))

            user_email = request.user.email

            #GET CURRENT SITE INFORMATONS
            microsite_details = MicrositeDetail.objects.get(id=microsite_id)
            _cur_microsite = Microsite.objects.get(key=microsite_details.name)

            #UPDATE CLASS PROPERTIES WITH NEW VALUES IF ANY
            self.add(
                microsite_name=microsite_details.name,
                logo=request.FILES.get('logo'),
                logo_couleur=request.FILES.get('logo_couleur'),
                primary_color=request.POST.get('primary_color'),
                secondary_color=request.POST.get('secondary_color'),
                third_color=request.POST.get('third_color'),
                third_bg_color=request.POST.get('third_bg_color'),
                white_or_color_logo=request.POST.get('white_or_color_logo'),
                language = request.POST.get('language'),
                contact_address = request.POST.get('contact_address'),
                amundi_brand = request.POST.get('amundi_brand'),
                disclaimer=request.POST.get('disclaimer'),
                trademark=request.POST.get('trademark')
            )

            #SAVE NEW STATIC FILES (IMAGES LOGO)
            _static = self.add_static_values(_cur_microsite)
            log.info(u'microsite_manager.update_static _static : {}'.format(str(_static)))

            #UPDATE MICROSITEDETAILS TABLE WITH NEW INFOS
            if self.logo_couleur is not None:
                microsite_details.logo=self.logo_couleur.name
            microsite_details.name=self.microsite_name.lower()
            microsite_details.language_code=self.language
            microsite_details.primary_color=self.primary_color
            microsite_details.secondary_color=self.secondary_color
            microsite_details.third_color=self.third_color
            microsite_details.third_bg_color=self.third_bg_color
            microsite_details.white_or_color_logo=self.white_or_color_logo

            details_status = microsite_details.save()


            #UPDATE MICROSITE OBJECT WITH NEW INFO
            values = _cur_microsite.values
            q = {}
            i = 0
            for n in values:
                q[n] = values.values()[i]
                i = i + 1
            for key,value in _static.items():
                if key != 'status':
                    q[key] = value
            _cur_microsite.values = q
            _cur_microsite.save()
            return JsonResponse(_static)

    #SAVE IMAGES (logo etc...) / COPY TEMPLATE FILES / ADAPT CSS FILES
    def add_static_values(self, _cur_microsite=None):
        log.info(u'microsite_manager.add_static_values start')
        if self.microsite_name is None:
            raise TypeError

        #where template css is stored
        microsite_path = "/edx/app/edxapp/themes/atp_theme/cms/templates/microsite_manager/"
        css_template_path = microsite_path+'css/'

        #where microsite files will be stored
        static_path = "/edx/var/edxapp/media/microsite/{}/".format(self.microsite_name.lower())
        image_path = static_path+'images/'
        css_path = static_path+'css'

        #SAVE LOGO IMG
        if self.logo is not None:
            logo_path = image_path+self.logo.name
            try:
                os.makedirs(os.path.dirname(logo_path))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
            try:
                with open(logo_path, 'wb+') as destination:
                    for chunk in self.logo.chunks():
                        destination.write(chunk)
            except:
                pass

        #SAVE LOGO_COULEUR IMG
        if self.logo_couleur is not None:
            logo_couleur_path = image_path+self.logo_couleur.name
            try:
                os.makedirs(os.path.dirname(logo_couleur_path))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
            try:
                with open(logo_couleur_path, 'wb+') as destination:
                    for chunk in self.logo_couleur.chunks():
                        destination.write(chunk)
            except:
                pass

        #Replace missing values for colors replacement and final context
        if _cur_microsite is not None:
            microsite_value = _cur_microsite.__dict__['values']
            if self.primary_color is None :
                self.primary_color = microsite_value['primary_color'].encode('utf-8')
            if self.secondary_color is None :
                self.secondary_color = microsite_value['secondary_color'].encode('utf-8')
            if self.third_color is None :
                self.third_color = microsite_value['third_color'].encode('utf-8')
            if self.third_bg_color is None :
                self.third_bg_color = microsite_value['third_bg_color'].encode('utf-8')
            if self.white_or_color_logo is None :
                self.white_or_color_logo = microsite_value['white_or_color_logo'].encode('utf-8')
            if self.language is None :
                self.language = microsite_value['language_code'].encode('utf-8')
            if self.contact_address is None :
                self.contact_address = microsite_value['contact_address'].encode('utf-8')
            if self.amundi_brand is None :
                self.amundi_brand = microsite_value['amundi_brand'].encode('utf-8')
            if self.disclaimer is None :
                self.disclaimer = microsite_value['disclaimer'].encode('utf-8')
            if self.trademark is None :
                self.trademark = microsite_value['trademark'].encode('utf-8')

        #REPLACE COLORS IN CSS FILES
        if self.primary_color is not None and self.secondary_color is not None and self.third_color is not None and self.third_bg_color is not None:
            dict_change = {
                '!atp_primary_color': self.primary_color,
                '!atp_secondary_color': self.secondary_color,
                '!atp_third_color': self.third_color,
                '!atp_third_bg_color': self.third_bg_color,
                '!font_family_atp': 'mywebfont'
            }

            #create media/microsite/self.microsite/css folder
            if not os.path.exists(css_path):
                os.makedirs(css_path)
            #copy template css file to static folder
            copy_tree(css_template_path,css_path)
            _css_files = os.listdir(css_path)
            #for each css file
            for n in _css_files:
                if '.css' in n:
                    log.info(u'microsite_manager.css file : {}'.format(str(n)))
                    _file = open(css_path+'/'+n,'r')
                    _content = _file.read()
                    _file.close()
                    #change css file attributes with custom value
                    for key,value in dict_change.items():
                        log.info(u'microsite_manager.dict_change key : {}'.format(str(key)))
                        log.info(u'microsite_manager.dict_change value : {}'.format(str(value)))
                        log.info(u'microsite_manager.dict_change _content : {}'.format(str(n)))
                        _content = _content.replace(key,value)
                    _file = open(css_path+'/'+n,'w')
                    _file.write(_content)
                    _file.close()
            log.info(u'microsite_manager.add_static_values end')

            context = {
                'status':True,
                'primary_color':self.primary_color,
                'secondary_color':self.secondary_color,
                'third_color':self.third_color,
                'third_bg_color':self.third_bg_color,
                'white_or_color_logo':self.white_or_color_logo,
                'contact_address':self.contact_address,
                'amundi_brand':self.amundi_brand,
                'disclaimer':self.disclaimer,
                'trademark':self.trademark
            }
            if self.logo is not None:
                context['logo']=format(logo_path.replace("/edx/var/edxapp",""))
            else:
                context['logo']=microsite_value['logo'].encode('utf-8')
            if self.logo_couleur is not None:
                context['logo_couleur']=format(logo_couleur_path.replace("/edx/var/edxapp",""))
            else:
                context['logo_couleur']=microsite_value['logo_couleur'].encode('utf-8')
            return context
        else:
            return True



    #
    def get_microsite_admin_manager(self, microsite):
        context = {}
        try:
            microsite_manager = MicrositeAdminManager.objects.all().filter(microsite=microsite)
            users = []
            for n in microsite_manager:
                try:
                    user_id = n.user_id
                    user = User.objects.get(id=user_id)
                    email = user.email
                    q = {}
                    q['user_id'] = int(user_id)
                    q['email'] = email
                    users.append(q)
                except:
                    test = None
            context['users_admin'] = users
            context['status'] = True
        except:
            context['status'] = False

        return context

    #
    def microsite_admin_manager(self, request, microsite_key):
        #get request methods
        methods = request.method
        #if REQUEST GET
        context = {}
        if methods == 'POST':
            email = request.POST['data']
            check_user = True
            check_microsite = True
            user = None
            microsite = None
            try:
                user = User.objects.get(email=email)
            except:
                check_user = False
                context['user'] = 'email invalide'
            try:
                microsite = Microsite.objects.get(key=microsite_key)
            except:
                check_microsite = False
                context['microsite'] = 'microsite invalide'

            if check_user and check_microsite:

                check_microsite = True
                try:
                    MicrositeAdminManager.objects.get(user=user)
                    context['microsite_admin'] = False
                except:
                    check_microsite = False

                if not check_microsite:
                    #try:
                    microsite_admin_manager = MicrositeAdminManager.objects.create(user=user,microsite=microsite)
                    microsite_admin_manager.save()
                    context['microsite_admin'] = True
                    context['user_id'] = user.id
                    context['user_email'] = user.email
                    """
                    except:
                        context['microsite_admin'] = False
                    """

        if methods == 'DELETE':
            request.META['REQUEST_METHOD'] = 'DELETE'
            request.DELETE = QueryDict(request.body)
            user_id = request.DELETE['data']
            check_user = True
            check_microsite = True
            user = None
            microsite = None
            context['user_id'] = user_id
            try:
                user = User.objects.get(pk=user_id)
            except:
                check_user = False
                context['user'] = 'user invalide'
            try:
                microsite = Microsite.objects.get(key=microsite_key)
            except:
                check_microsite = False
                context['microsite'] = 'microsite invalide'

            if check_user and check_microsite:

                check_microsite = True
                try:
                    MicrositeAdminManager.objects.get(user=user,microsite=microsite).delete()
                    context['delete'] = True
                except:
                    context['delete'] = False
        context['methods'] = methods
        return JsonResponse({'context':context})
