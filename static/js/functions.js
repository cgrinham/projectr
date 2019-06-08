jQuery(document).ready(function() {
jQuery(function( $ ) {

    $('#displayswitch').on('click', function(){
        if ($('#displayslist').css('display') === 'none'){
            $('#displayslist').slideDown();
        } else {
            $('#displayslist').slideUp();
        }
    })

    $('.project').on('click', function() {
        currentTile = $(this).parents('.tile')
        image = currentTile.data("image");

        nothing = "nothing";

        jQuery.ajax({
            type:"POST",
            data: {action: "project", prop1 : image, prop2: nothing},
            success: function() {
                $('.tile').removeClass('active');
                currentTile.addClass('active');
            }
        });
    });

    $('.sync').on('click', function() {
        display = $(this).data("display");


        nothing = "nothing";

        jQuery.ajax({
            type:"POST",
            data: {action: "sync", prop1 : display, prop2: nothing},
            success: function() {
                //alert("Projecting " + image);
            }
        });
    });



    $('.menubutton').on('click', function(){

        if ($('nav').css('display') === 'none'){
            $('#title').css("visibility", "hidden");
            $('nav').slideDown();
            $('body').css("overflow", "hidden");
        } else {
            $('nav').slideUp(function(){
                $('#title').css("visibility", "visible");
            });
            $('body').css("overflow", "visible");
        }
        
    });

    $('.slideshow').on('click', function(){
        if ($('.slideshowcheck').css('display') === 'none'){
            $('.slideshowcheck').css('display', "block");
            $('.delete').css('display', "none");
            $('.project').css('display', "none");
            $('.rename').css('display', "none");
            $('.slideshow-project').css('display', "block");
        } else {
            $('.slideshowcheck').css('display', "none");
            $('.delete').css('display', "block");
            $('.project').css('display', "block");
            $('.rename').css('display', "block");
            $('.slideshow-project').css('display', "none");
        }
    });

    $('.shutdownsubmit').on('click', function(){
        choice = $(this).data('choice');
        $('#choice').val(choice);
        $('#shutdownform').submit();
    });
    
}); // END JQUERY

});

/*
$("id-" + image).attr("src", "../" + absimage + "?" + d.getTime());

jQuery(document).ready(function() {
jQuery(".button").click(function() {
        var input_string = $$("input#textfield").val();
        jQuery.ajax({
                type: "POST",
                data: {textfield : input_string},
                success: function(data) {
                jQuery('#foo').html(data).hide().fadeIn(1500);
                },
                });
        return false;
        });
});*/