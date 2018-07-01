$(document).ready(function(){
    var css = `* {
     transition-property: none !important;
     -o-transition-property: none !important;
     -moz-transition-property: none !important;
     -ms-transition-property: none !important;
     -webkit-transition-property: none !important;

     transform: none !important;
     -o-transform: none !important;
     -moz-transform: none !important;
     -ms-transform: none !important;
     -webkit-transform: none !important;

     animation: none !important;
     -o-animation: none !important;
     -moz-animation: none !important;
     -ms-animation: none !important;
     -webkit-animation: none !important;
    }`,
    head = document.head || document.getElementsByTagName('head')[0],
    style = document.createElement('style');

    style.type = 'text/css';
    style.appendChild(document.createTextNode(css));
    head.appendChild(style);
});