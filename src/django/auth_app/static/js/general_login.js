$(document).ready(function() {
  handleGlobalPinVerification();
});

function handleGlobalPinVerification() {
  const pinModal = new bootstrap.Modal($('#globalPinModal'));

  $("#employee-login-btn").click(function() {
    pinModal.show();
  });

  $("#submit-pin").click(function() {
    const enteredPin = $("#pin-input").val();

    $.ajax({
      url: window.djangoURLs.verifyGlobalPin,
      type: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken') // Include CSRF token
      },
      data: {
          pin: enteredPin,
      },
      success: function(response) {
          window.location.href = "/employee_dashboard/";
      },
      error: function(jqXHR, textStatus, errorThrown) {
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to authorise due to internal errors. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to authorise. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });
  });
}