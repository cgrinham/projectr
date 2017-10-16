jQuery(document).ready(function() {
jQuery(function( $ ) {

    $('.delete').on('click', function() {

        image = $(this).parents('.tile').data("image");
        //alert(absimage);


        current_element = $(this).parents('.tile');

        nothing = "nothing";

        jQuery.ajax({
            type: "POST",
            data: {action : "delete", prop1 : image, prop2 : nothing},
            success: function() {
                current_element.css("display", "none");
            }
        });
        return false;
    });

    $('.project').on('click', function() {
        image = $(this).parents('.tile').data("image");


        nothing = "nothing";

        jQuery.ajax({
            type:"POST",
            data: {action: "project", prop1 : image, prop2: nothing},
            success: function() {
                alert("Projecting " + image);
            }
        });

    });

    $('#menubutton').on('click', function(){

        if ($('nav').css('display') === 'none'){
            $('nav').css("display", "block");
        } else {
            $('nav').css("display", "none");
        }
        
    });
    
});

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