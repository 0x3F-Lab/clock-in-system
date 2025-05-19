$(document).ready(function () {
  // Handle button(s) to mark a notification as read (dismiss it)
  handleNotificationMarkAsRead();

  // Function to handle submisison of notification messages (page form)
  handleNotificationSubmission();

  // Function to handle switching between the multiple pages on the notification page (i.e. seeing notifications to sending notifications)
  handleNotificationPageSwitching();

  // Handle message field input -> change current characters
  $('#id_message').on('input', () => {
    updateCharCount();
  });

  // Initial char count update
  updateCharCount();
});


function updateCharCount() {
  const max = $('#id_message').attr('maxlength');
  const len = $('#id_message').val().length;
  $('#charCount').text(`${len}/${max} Characters`)
}


function handleNotificationPageSwitching() {
  const notifPanel = $("#account-notifications");
  const sendPanel = $("#send-notification-form");

  const notifButton = $(".list-group-item:contains('Notifications')");
  const sendButton = $(".list-group-item:contains('Send Messages')");

  notifButton.on("click", function () {
    notifPanel.removeClass("d-none");
    sendPanel.addClass("d-none");

    notifButton.addClass("active");
    sendButton.removeClass("active");
  });

  sendButton.on("click", function () {
    sendPanel.removeClass("d-none");
    notifPanel.addClass("d-none");

    sendButton.addClass("active");
    notifButton.removeClass("active");
  });
}


function handleNotificationMarkAsRead() {
  // Listen for any collapse being shown
  $('.collapse').on('show.bs.collapse', function () {
    const notifID = $(this).attr('id').split('-').pop();
    $(`[data-id="${notifID}"]`).removeClass('d-none');
  });

  // Hide the button when the collapse is closed
  $('.collapse').on('hide.bs.collapse', function () {
    const notifID = $(this).attr('id').split('-').pop();
    $(`[data-id="${notifID}"]`).addClass('d-none');
  });

  // Handle user pressing 'Mark as Read'
  $(document).on('click', '.mark-as-read', function () {
    const ID = $(this).data('id');
    markNotificationRead(ID);
  });
}


function handleNotificationSubmission() {
  $("form").on("submit", function (e) {
    e.preventDefault(); // Prevent the default form submit

    const storeID = getSelectedStoreID();

    if (!storeID) {
      showNotification("Please select a store before submitting a message.", "danger");
      return;
    }

    // Set the value of the hidden input
    $(this).find("input[name='store']").val(storeID);

    // Submit the form after setting the store ID
    this.submit(); // Native submit to avoid recursion
  });
}


function markNotificationRead(id) {
  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.markNotificationRead}${id}/`,
    type: "PUT",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(req) {
      hideSpinner();

      // Delete the notification from the page (no need to reload)
      $(`#notif-${id}`).remove();

      // Update the code
      count = ensureSafeInt($('#notification-page-count').html(), 0, null);
      $('#notification-page-count').html(count - 1);

      showNotification("Successfully marked notification as read.", "success");
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to mark notification as read due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to mark notification as read. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}