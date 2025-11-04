$(document).ready(function() {
  $("#generatePDFBtn").on("click", function() {
    window.open(window.djangoURLs.generateEmptyPDF, "_blank");
  });
});