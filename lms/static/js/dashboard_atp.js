// load course status
var course_status = {
  start_courses:false,
  progress_courses:false,
  end_courses:false
}

var course_category = '';

function tma_show_more() {
 $('.tuto_action').click(function(){
  if($('#atp_tuto_arrow_up').hasClass('arrow-right')) {
   $('#atp_tuto_arrow_up').removeClass('arrow-right');
   $('#atp_tuto_arrow_up').addClass('arrow-bottom');
  }else if($('#atp_tuto_arrow_up').hasClass('arrow-bottom')) {
   $('#atp_tuto_arrow_up').removeClass('arrow-bottom');
   $('#atp_tuto_arrow_up').addClass('arrow-right');
  }
  var speed = 1800;
  $('#dashboard_tuto_atp').slideToggle(speed);

  if($(this).find('.arrow-top').length != 0) {
    $('html, body').animate( { scrollTop: $('#dashboard_header_atp').offset().top -= 148 }, speed );
  }
 })
 $('.atp_dashboard_active_course').click(function(){
  var text = $(this).text();
  var cible = $(this).data('cible');
  var key = cible.replace('_atp','');
  var _status = $(this).data('status');
  var _cible = '#'+cible;
  var _courses = courses_atp[key];

  if(text.indexOf('+') != -1) {
    // re render courses
    course_status[key] = true;
    render_course_cards(_courses,_cible,course_status[key],_status,course_category);
    text = text.replace('+','-');
  }else{
    course_status[key] = false;
    render_course_cards(_courses,_cible,course_status[key],_status,course_category);
    text = text.replace('-','+');
  }
  $(this).text(text);
 })
}

$('#categories_menu').find('div').click(function(){
  var This = $(this);
  This.parent().hide();
  var data = This.data('location').replace(/ /g,'').toLowerCase();

  if(data == 'all') {
    course_category = '';
    $('#categories_menu').find('div').removeClass('display_button');
  }else{
    $('#categories_menu').find('div').each(function(){
      var That = $(this);
      if(That.data('location') != 'all') {
        That.addClass('display_button');
      }
    })
    course_category = data;
  }
  render_course_cards(courses_atp.progress_courses,progress_cible,course_status.progress_courses,"cours",course_category);
  render_course_cards(courses_atp.start_courses,start_cible,course_status.start_courses,"invite",course_category);
  render_course_cards(courses_atp.end_courses,end_cible,course_status.end_courses,"finish",course_category);
  $('html, body').animate( { scrollTop: $('#dashboard_course_in_progress_atp').offset().top -= 148 }, 750 );
  return false;
})

function intervalDetectHeight() {
  var height = 0;
  $('.atp_course_title').attr('style','');
  $('.atp_course_title').find('span').each(function(){
   var h = $(this).height();
   h = parseInt(h);
   if(h > height) {
    height = h;
   }
  })
  $('.atp_course_title').css('height',height+'px');
}
$(document).ready(function(){
 tma_show_more();
 intervalDetectHeight();
})
$('.atp_course_listing').on('change',function(){
 intervalDetectHeight();
})
$(window).resize(function(){
 intervalDetectHeight();
})


function add_class() {
  var Width = window.screen.width;
  if(Width <= 1600) {
    $( ".atp_course_item:nth-child(4)" ).addClass('atp_hide_cards');
  }else{
    $( ".atp_course_item:nth-child(4)" ).removeClass('atp_hide_cards');
  }
  if(Width <= 1196) {
    $( ".atp_course_item:nth-child(3)" ).addClass('atp_hide_cards');
  }else{
    $( ".atp_course_item:nth-child(3)" ).removeClass('atp_hide_cards');
  }
  if(Width <= 814) {
    $( ".atp_course_item:nth-child(2)" ).addClass('atp_hide_cards');
  }else{
    $( ".atp_course_item:nth-child(2)" ).removeClass('atp_hide_cards');
  }
  $('.atp_dashboard_active_course').each(function(){
      var _s = $(this).text().substring(0,1);
      if(_s == '-') {
        $(this).parent().find('.atp_hide_cards').show();
      }else{
        $(this).parent().find('.atp_hide_cards').attr('style','');
      }
  })
}

function template_course_card(atp_course_word,atp_course_link,img_src,course_id,categ_lower,categ,course_progression,picto_dure,duration,required,picto_obiligatoire,display_name_with_default,_end_add,_img_data) {
  if(categ.toLowerCase()=="fundamental" ||categ.toLowerCase()=="fundamentals"){
    categ=wording_fundamental;
  }
  else if(categ.toLowerCase()=="our solutions"){
    categ=wording_oursolutions;
  }
  else if(categ.toLowerCase()=="sales approach"){
    categ=wording_businessapproach;
  }
  else if(categ.toLowerCase()=="regulatory"){
    categ=wording_regulatory;
  }
  else if(categ.toLowerCase()=="soft skills"){
    categ=wording_softskills;
  }
  else if(categ.toLowerCase()=="expert"){
    categ=wording_expert;
  }


  var template = '<li class="atp_course_item" data-categ="'+categ_lower+'"><div class="atp_course_image"><span class="cateogry_text">'+categ+'</span><a href="/courses/'+course_id+'/courseware/"><img src="'+img_src+'" /><div class="img_'+categ_lower+'"></div></a></div><div class="progress_bar_status_up"><div class="progress_bar_status primary-color-bg" style="width:'+course_progression+'%;"></div></div><div class="atp_course_info"><div class="atp_course_duration"><div class="inside_atp_left"><img src="'+picto_dure+'" class="svg"/><span>'+duration+'</span><div style="display:block;clear:left;height:0px;"></div></div></div><div class="atp_course_dificulties"><div class="inside_atp"><span>'+required+'</span><img src="'+picto_obiligatoire+'" class="svg"/><div style="display:block;clear:left;height:0px;"></div></div></div></div><div class="atp_course_title primary-color-text"><span>'+display_name_with_default+'</span></div>'+_end_add+'<div class="atp_course_picto">'+_img_data+'</div><div class="atp_course_link"><a href="'+atp_course_link+'"class="primary-color-bg">'+atp_course_word+'</a></div></li>';
  return template
}

function svg_load() {
jQuery('img.svg').each(function(){
    var $img = jQuery(this);
    var imgID = $img.attr('id');
    var imgClass = $img.attr('class');
    var imgURL = $img.attr('src');
    jQuery.get(imgURL, function(data) {
        // Get the SVG tag, ignore the rest
        var $svg = jQuery(data).find('svg');
        // Add replaced image's ID to the new SVG
        if(typeof imgID !== 'undefined') {
            $svg = $svg.attr('id', imgID);
        }
        // Add replaced image's classes to the new SVG
        if(typeof imgClass !== 'undefined') {
            $svg = $svg.attr('class', imgClass+' replaced-svg');
        }
        // Remove any invalid XML tags as per http://validator.w3.org
        $svg = $svg.removeAttr('xmlns:a');
        // Replace image with new SVG
        $img.replaceWith($svg);

    }, 'xml');
});
$('img.svg').show();
}



function course_card(categ,course_id,img_src,course_progression,duration,required,display_name_with_default,content_data,percent,passed,atp_rank,cible) {

  var _img_data = "";
  var _end_add = "";

  if(content_data.document_pdf){
    _img_data = _img_data+'<img src="'+picto_pdf+'" class="svg"/>'
  }
  if(content_data.webzine){
    _img_data = _img_data+'<img src="'+picto_webzine+'" class="svg"/>'
  }
  if(content_data.quiz){
    _img_data = _img_data+'<img src="'+picto_quiz+'" class="svg"/>'
  }
  if(content_data.video){
    _img_data = _img_data+'<img src="'+picto_video+'" class="svg"/>'
  }
  if(content_data.serious_game){
    _img_data = _img_data+'<img src="'+picto_serious_game+'" class="svg"/>'
  }
  if(content_data.text_image){
    _img_data = _img_data+'<img src="'+picto_teste_images+'" class="svg"/>'
  }
  if(content_data.simulation_investissement){
    _img_data = _img_data+'<img src="'+picto_simulation_inv+'" class="svg"/>'
  }

  if(required) {
    required = wording_mandatory;
  }else{
    required = wording_optional;
  }

  if(percent.toString().indexOf('.') == -1) {
    percent=percent+'.0'
  }

  var categ_lower = categ.replace(/ /g,'').toLowerCase();
  var atp_course_link = '';
  var atp_course_word = '';

  if(atp_rank == "cours") {
     atp_course_link = '/courses/'+course_id+'/courseware/';
     atp_course_word = '<span class="proceed">'+wording_proceed+'</span>';
     if(!passed && course_progression==100){
      _end_add = '<div class="atp_course_progress"><img src="'+picto_error+'" class="validate_img"/><span class="validate" style="color:rgb(220,158,41);">'+wording_notvalidated+' '+percent+'%</span></div>';
     }
     else{
       _end_add = '<div style="min-height:30px;" class="atp_course_progress"></div>';
     }
  }else if(atp_rank == "invite") {
     atp_course_link = '/courses/'+course_id+'/about';
     atp_course_word = '<span class="more_info">'+wording_morinfo+'</span>';
  }else if(atp_rank == "finish") {
     atp_course_link = '/courses/'+course_id+'/about';
     atp_course_word = '<span class="more_info">'+wording_morinfo+'</span>';
     if(passed) {
      _end_add = '<div class="atp_course_progress"><img src="'+picto_success+'" class="validate_img"/><span class="is_green validate"> '+wording_validated+' '+percent+'%</span></div>';
     }else{
      _end_add = '<div class="atp_course_progress"><img src="'+picto_error+'" class="validate_img"/><span class="validate" style="color:rgb(220,158,41);"> '+wording_notvalidated+' '+percent+'%</span></div>';
     }
  }

  var course_card_template = template_course_card(
    atp_course_word,
    atp_course_link,
    img_src,
    course_id,
    categ_lower,
    categ,course_progression,
    picto_dure,duration,
    required,picto_obiligatoire,
    display_name_with_default,
    _end_add,_img_data
  );

  $(cible).append(course_card_template);
  ////////////////////////////////////// XITI ///////////////////
  $('.proceed').parent('a.primary-color-bg').each(function(){
    $(this).attr('onclick','followClickEvents(this,\'courseware\',\'action\')');
  });
  $('.more_info').parent('a.primary-color-bg').each(function(){
    $(this).attr('onclick','followClickEvents(this,\'course_about\',\'action\')');
  });
}
