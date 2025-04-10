function OfficeQuestionBankXBlockAdmin(runtime, element) {
    var handlerUrl = runtime.handlerUrl(element, 'save_question_bank');

    function calcWdith(evt){
        var width = 0;
        if (evt.lengthComputable) {
            var percentComplete = evt.loaded / evt.total;
            width = percentComplete * 100;
        }
        return Math.round(width);

    }

    function setProgressBarWidth(width, text){
        $('.xb-simulation-progress-bar .progress-bar', $(element))
            .prop('aria-valuenow', width)
            .css({
                width: width + '%'
            }).text(text + '(' + width + '%)');
    }

    $('.copy-text').click(function() {
        var copyIcon = $(this);
        var textToCopy = copyIcon.siblings('.text-to-copy').val();
        navigator.clipboard.writeText(textToCopy).then(
            function() {
                copyIcon.toggleClass('fa-copy').toggleClass('fa-check');
            }
        )
    });

    if ($('#xb_field_edit_is_scorable').val() == '1'){
        $(element).find('.scorable').show();
    }else{
        $(element).find('.scorable').hide();
    }

    $('#xb_field_edit_is_scorable').change(function() {
        if($(this).val() == '1') {
            $(element).find('.scorable').show();
        }
        else {
            $(element).find('.scorable').hide();
        }
    });

    $(element).find('.save-button').bind('click', function () {
        var form_data = new FormData();
        var display_name = $(element).find('input[name=xb_display_name]').val();
        var is_scorable = $(element).find('#xb_field_edit_is_scorable').val();
        var weight = $(element).find('input[name=xb_weight]').val();
        var points = $(element).find('input[name=xb_points]').val();
        var state_definitions = $(element).find('#xb_state_definitions').val();
        var simulation_content_path = $(element).find('#xb_existing_content_path').val();
        var simulation_content_bundle = $(element).find('#xb_simulation_file').prop('files')[0];

        form_data.append('simulation_content_bundle', simulation_content_bundle);
        form_data.append('simulation_content_path', simulation_content_path);
        form_data.append('display_name', display_name);
        form_data.append('is_scorable', is_scorable);
        form_data.append('weight', weight);
        form_data.append('points', points);
        form_data.append('state_definitions', state_definitions);

        if ('notify' in runtime) { //xblock workbench runtime does not have `notify` method
            runtime.notify('save', { state: 'start' });
        }        

        $.ajax({
            url: handlerUrl,
            dataType: 'text',
            cache: false,
            contentType: false,
            processData: false,
            data: form_data,
            type: "POST",
            xhr: function () {
                if(simulation_content_bundle !== undefined) {
                    $('.progress-bar-container').show();
                }
                else {
                    $('.progress-bar-container').hide();
                }
                var xhr = new window.XMLHttpRequest();
                xhr.addEventListener("progress", function (evt) {
                    setProgressBarWidth(calcWdith(evt), args.extracting_txt);
                });
                xhr.addEventListener("load", function (evt) {
                    setProgressBarWidth(100, args.uploaded_txt);
                });
                xhr.upload.addEventListener("progress", function (evt) {
                    setProgressBarWidth(calcWdith(evt), args.uploading_txt);
                });
                xhr.upload.addEventListener("load", function (evt) {
                    setProgressBarWidth(50, args.extracting_txt); // xblock handler does not support stream response
                });
                return xhr;
            },
            success: function (response) {
                if ('notify' in runtime) { //xblock workbench runtime does not have `notify` method
                    runtime.notify('save', { state: 'end' });
                }
            }
        });

    });

    $(element).find('.cancel-button').bind('click', function () {
        if ('notify' in runtime) { //xblock workbench runtime does not have `notify` method
            runtime.notify('cancel', {});
        }
    });

    // const getQuestionBankUrl = runtime.handlerUrl(element, "get_question_bank");
    // const saveQuestionBankUrl = runtime.handlerUrl(element, "save_question_bank");

    // $.post(getQuestionBankUrl, JSON.stringify({get: true}))
    // .then(
    //     function(response) {
    //         // Success callback
    //         console.log('Data received:', response);
    //         $("#question-bank-json").val(JSON.stringify(response.questions, null, 4));
    //     },
    //     function(error) {
    //         // Error callback
    //         console.error('Error occurred:', error);
    //     }
    // );

    // $("#save-question-bank").click(() => {
    //     const questions = JSON.parse($("#question-bank-json").val());
    //     $.post(saveQuestionBankUrl, JSON.stringify({ questions }))
    //     .then(
    //         function(response) {
    //             // Success callback
    //             console.log('Data received:', response);
    //             $("#admin-feedback").text(response.message);
    //         },
    //         function(error) {
    //             // Error callback
    //             console.error('Error occurred:', error);
    //         }
    //     );
    // });
}