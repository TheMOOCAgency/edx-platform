#!/usr/bin/env python
# -*- coding: utf-8 -*-

from weasyprint import HTML
import codecs
from django.template import Context, Template
import cStringIO as StringIO
from xhtml2pdf import pisa
from django.http import HttpResponse
from cgi import escape
from edxmako.shortcuts import render_to_response,render_to_string
from django.views.generic import TemplateView
import datetime

from textwrap import wrap

import requests

import logging
log = logging.getLogger(__name__)

#LO UPDATE GENERATE PDF
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import img2pdf
import os
from resizeimage import resizeimage
import urllib, cStringIO

def hex_to_rgb (hex) :
    couleur = hex.lstrip("#")
    couleur_rgb = tuple(int(couleur[i:i+2], 16) for i in (0, 2 ,4))
    return couleur_rgb

def generate_html(user,score,course_img_path,template_path,course_title,categorie,certif_img_path,logo_path,amundi_academy,lang,user_name, primary_color, secondary_color):
    font_main = ImageFont.truetype("/edx/var/edxapp/media/certificates/OpenSans-Regular.ttf",12,  encoding="utf-8")
    font_big = ImageFont.truetype("/edx/var/edxapp/media/certificates/OpenSans-Bold.ttf",15,  encoding="utf-8")

    marge_haute=30
    marge_laterale=40
    marge_espacement=20
    marge_espacement_large=30
    main_color=(19, 33, 73)
    second_color=(0, 180, 234)
    gold=(221, 157, 58)
    date = str(datetime.datetime.today().strftime('%d/%m/%Y'))

    #Traduction
    traductions={
    "fr":{
        "date_title":u"Date",
        "score_title":u"Score",
        "category_label":u"Catégorie",
        "fundamentals":u"fondamentaux",
        "fundamental":u"fondamentaux",
        "sales approach":u"démarche commerciale",
        "our solutions":u"nos solutions",
        "regulatory":u"réglementaire",
        "phrase":u"Le certificat de réussite du module de formation sur",
        "phrase2":u"est décerné à",
        "soft skills":"démarche commerciale",
        "expert":"experts",
        },
    "de":{
        "date_title":u"Datum",
        "score_title":u"Ergebnis",
        "category_label":u"Kategorie",
        "fundamentals":u"grundlagen",
        "fundamental":u"grundlagen",
        "sales approach":u"vertriebsansatz",
        "our solutions":u"unsere lösungen",
        "regulatory":u"vorschriften",
        "phrase":u"Das Leistungszertifikat für",
        "phrase2":u"gehört zu",
        "soft skills":"Kommerzieller Ansatz",
        "expert":"experten",
        },
    "it":{
        "date_title":"Data",
        "score_title":"Punteggio",
        "category_label":"Categoria",
        "fundamentals":"Le basi",
        "fundamental":"Le basi",
        "sales approach":"Approccio commerciale",
        "our solutions":"Le nostre soluzioni",
        "regulatory":"Normativo",
        "phrase":u"il certificato di conseguimento per",
        "phrase2":u"è attribuito a",
        "soft skills":"Approccio commerciale",
        "expert":"esperti",
        },
    "en":{
        "date_title":"Date",
        "score_title":"Score",
        "category_label":"Category",
        "fundamentals":"fundamentals",
        "fundamental":"fundamental",
        "sales approach":"sales approach",
        "our solutions":"our solutions",
        "regulatory":"regulatory",
        "phrase":"The certificate of achievement for",
        "phrase2":"is attributed to",
        "soft skills":"soft skills",
        "expert":"expert",
    },
    "cs":{
        "date_title":u"Datum",
        "score_title":u"Skóre",
        "category_label":u"Kategorie",
        "fundamentals":u"Obecné základy",
        "fundamental":u"Obecné základy",
        "sales approach":u"Prodejní přístup",
        "our solutions":u"Základní řešení",
        "regulatory":u"Regulace",
        "phrase":u"Osvědčení o úspěšném absolvování vzdělávacího kurzu:",
        "phrase2":u"pro",
        "soft skills":u"Prodejní dovednosti",
        "expert":u"Doplňková řešení",
    },
    "nl":{
        "date_title":u"Datum",
        "score_title":u"Score",
        "category_label":u"Categorie",
        "fundamentals":u"Basiskennis",
        "fundamental":u"Basiskennis",
        "sales approach":u"Zakelijke aanpak",
        "our solutions":u"Onze oplossingen",
        "regulatory":u"Regelgeving",
        "phrase":u"Het certificaat van voltooiing wordt",
        "phrase2":u"toegekend aan",
        "soft skills":"soft skills",
        "expert":"expert",
    },
    "ro":{
        "date_title":u"Data",
        "score_title":u"scorul",
        "category_label":u"Categoria",
        "fundamentals":u"Principii Fundamentale",
        "fundamental":u"Principii Fundamentale",
        "sales approach":u"abordarea de vanzare",
        "our solutions":u"Solutiile noastre",
        "regulatory":u"cerinte legale",
        "phrase":u"Certificatul pentru",
        "phrase2":u"este atribuit ",
        "soft skills":"abilitati moi",
        "expert":"expert",
    },
    "hu":{
        "date_title":u"Dátum",
        "score_title":u"Összpontszámod",
        "category_label":u"Kategória",
        "fundamentals":u"Alapvetõ ismeretek",
        "fundamental":u"Alapvetõ ismeretek",
        "sales approach":u"Értékesítési megközelítés",
        "our solutions":u"Megoldásaink",
        "regulatory":u"Szabályozói",
        "phrase":u"Ezen igazolás bizonyítja, hogy a",
        "phrase2":u"tréninget teljesítette",
        "soft skills":u"soft skills",
        "expert":u"expert",
    }
    }

    if not lang in traductions :
        lang="en"
    date_title=traductions[lang]['date_title']
    score_title=traductions[lang]['score_title']
    category_label=traductions[lang]['category_label']
    category_type = traductions[lang][categorie.lower()]
    phrase=traductions[lang]['phrase']
    phrase2=traductions[lang]['phrase2']




    #Couleurs
    if primary_color :
        if "#" in primary_color:
            try :
                main_color = hex_to_rgb(primary_color)
            except :
                main_color = (19, 33, 73)
    else :
        main_color = (19, 33, 73)

    if secondary_color :
        if "#" in secondary_color:
            try :
                second_color = hex_to_rgb(secondary_color)
                gold=second_color
            except :
                second_color=(0, 180, 234)
    else :
        second_color=(0, 180, 234)


    background = Image.new('RGBA', (595,865), (255, 255, 255, 255))
    background_largeur, background_hauteur=background.size

    logo=Image.open('/edx/var/edxapp'+logo_path).convert("RGBA")
    try:
        logo=resizeimage.resize_height(logo, 70)
    except:
	pass
    logo_largeur, logo_hauteur=logo.size

    #Positionnement bloc logo
    if amundi_academy!='':
        amundi=Image.open('/edx/var/edxapp'+amundi_academy)
        try:
            amundi=resizeimage.resize_height(amundi, 50)
        except:
            pass
        amundi_largeur, amundi_hauteur=amundi.size
        px_logo=(marge_laterale)
        py_logo=marge_haute
        px_amundi=(background_largeur-amundi_largeur-marge_laterale)
        py_amundi=marge_haute+((logo_hauteur-amundi_hauteur)/2)
        background.paste(logo, (px_logo,py_logo), mask=logo)
        background.paste(amundi, (px_amundi,py_amundi))
    else:
        px_logo=(background_largeur - logo_largeur)/2
        py_logo=marge_haute
        background.paste(logo, (px_logo,py_logo), mask=logo)
        amundi_hauteur=60


    #TEXTES
    draw= ImageDraw.Draw(background)

    py_logo=py_logo+amundi_hauteur
    #Titre cours
    array_of_strings = wrap(course_title, 60)
    for parts in array_of_strings:
        py_logo=py_logo+20
        course1_largeur, course1_hauteur = draw.textsize(parts, font=font_big)
        px_course1=(background_largeur-course1_largeur)/2
        draw.text((px_course1,py_logo),parts,main_color,font=font_big)

    #Image course

    #file_cours = cStringIO.StringIO(urllib.urlopen(course_img_path).read())
    #image_cours=Image.open(file_cours, 'r')
    #use requests geoffrey fix
    response_img = requests.get(course_img_path, stream=True)
    response_img.raw.decode_content = True
    log.info("atp_certificates.utils course_img get requests status code : ".format(response_img.status_code))
    image_cours=Image.open(response_img.raw)
    try:
        image_cours=resizeimage.resize_width(image_cours, 300)
    except:
	pass
    imgc_largeur, imgc_hauteur= image_cours.size
    px_imgc=(background_largeur-imgc_largeur)/2
    py_imgc=(py_logo+30+course1_hauteur+marge_espacement)
    background.paste(image_cours, (px_imgc,py_imgc))

    #Date
    px_date=marge_laterale
    py_date=py_imgc+imgc_hauteur+marge_espacement

    draw.text((px_date+10,py_date),date_title,gold,font=font_big)
    draw.text((px_date,py_date+30),date,main_color,font=font_main)

    #score title
    score_largeur, score_hauteur = draw.textsize(score_title, font_big)
    px_score=(background_largeur-score_largeur)/2
    py_score=py_date
    draw.text((px_score,py_score), score_title, gold, font_big)

    # score result
    score_largeur, score_hauteur = draw.textsize(score, font_big)
    px_score=(background_largeur-score_largeur)/2
    py_score=py_date
    draw.text((px_score,py_score+30), score, main_color, font_big)

    #Category
    category_largeur, category_hauteur = draw.textsize(category_label, font=font_big)
    px_category=(background_largeur-category_largeur-marge_laterale)
    py_category=py_date
    draw.text((px_category,py_category),category_label,gold,font=font_big)

    #Category label
    category_largeur2, category_hauteur2 = draw.textsize(category_type, font=font_main)
    px_category2=px_category+((category_largeur-category_largeur2)/2)
    draw.text((px_category2,py_category+30),category_type.capitalize(),main_color,font=font_main)

    #Declaration
    p1_largeur, p1_hauteur = draw.textsize(phrase, font=font_big)
    px_p1=(background_largeur-p1_largeur)/2
    py_p1=py_score+score_hauteur+30+marge_espacement_large
    draw.text((px_p1,py_p1),phrase,main_color,font=font_big)

    #Ecriture course title
    #course title use
    array_of_strings = wrap(course_title, 60)
    for parts in array_of_strings:
        py_p1=py_p1+20
        course2_largeur, course2_hauteur = draw.textsize(parts, font=font_big)
        px_course2=(background_largeur-course2_largeur)/2
        draw.text((px_course2,py_p1),parts,main_color,font=font_big)

    #Ecriture est décerné à
    p2_largeur, p2_hauteur = draw.textsize(phrase2, font=font_big)
    px_p2=(background_largeur-p2_largeur)/2
    py_p2=py_p1+30
    draw.text((px_p2,py_p2),phrase2,main_color,font=font_big)

    #Ecriture user name
    user_largeur, user_hauteur = draw.textsize(user_name, font=font_big)
    px_user=(background_largeur-user_largeur)/2
    py_user=py_p2+p2_hauteur+30
    draw.text((px_user,py_user),user_name,second_color,font=font_big)

    #Tampon certificat
    tampon=Image.open('/edx/var/edxapp/media/certificates/images/tampon.jpg')
    tampon=resizeimage.resize_height(tampon, 180)
    tampon_largeur, tampon_hauteur= tampon.size
    px_tampon=(background_largeur-tampon_largeur)/2
    py_tampon=(background_hauteur-tampon_hauteur-marge_espacement)
    background.paste(tampon, (px_tampon,py_tampon))




    background.save('/edx/var/edxapp/media/certificates/Export_Attestation_Amundi.png')
    pdf_bytes = img2pdf.convert('/edx/var/edxapp/media/certificates/Export_Attestation_Amundi.png')
    pdf_name = "certificat_{}.pdf".format(user)
    content_type = 'application/pdf'
    response = HttpResponse(pdf_bytes, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(pdf_name)
    os.remove('/edx/var/edxapp/media/certificates/Export_Attestation_Amundi.png')
    return response
