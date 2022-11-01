/* ~/.jupyter/custom/custom.js */
/*
define(['base/js/events'], function(events) {
  events.on('app_initialized.NotebookApp', function () {
    console.log('custom.js: hiding header and toolbar');
    $('#header-container').toggle();
    $('.header-bar').toggle();
    $('div#maintoolbar').toggle();
    events.trigger('resize-header.Page');
  });
});
*/

Jupyter.notebook.events.one('kernel_ready.Kernel', () => {
    console.log('custom.js: hiding header and toolbar');
    $('#header-container').toggle();
    $('.header-bar').toggle();
    $('div#maintoolbar').toggle();
    events.trigger('resize-header.Page');
});

