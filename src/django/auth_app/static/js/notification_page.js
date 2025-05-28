$(document).ready(function () {
  // Handle button(s) to mark a notification as read (dismiss it)
  handleNotificationMarkAsRead();

  // Function to handle switching between the multiple pages on the notification page (i.e. seeing notifications to sending notifications)
  handleNotificationPageSwitching();

  // Handle changing recipient group -> hide/show store field
  $('#id_recipient_group').on('change', () => {
    handleRecipientGroupChange();
  });

  // Initial recipient group update
  handleRecipientGroupChange();

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
  const readNotifPanel = $('#account-read-notifications');
  const sendPanel = $("#send-notification-form");

  const notifButton = $("#notification-page-btn");
  const readNotifButton = $('#read-notification-page-btn')
  const sendButton = $("#send-msg-page-btn");

  notifButton.on("click", function () {
    notifPanel.removeClass("d-none");
    readNotifPanel.addClass("d-none");
    sendPanel.addClass("d-none");

    notifButton.addClass("active");
    readNotifButton.removeClass("active");
    sendButton.removeClass("active");

    try {
      localStorage.setItem("notificationTab", "notifications");
    } catch (e) {
      // Fail silently
    }
  });

  readNotifButton.on("click", function () {
    notifPanel.addClass("d-none");
    readNotifPanel.removeClass("d-none");
    sendPanel.addClass("d-none");

    notifButton.removeClass("active");
    readNotifButton.addClass("active");
    sendButton.removeClass("active");

    try {
      localStorage.setItem("notificationTab", "read_notifications");
    } catch (e) {
      // Fail silently
    }
  });

  sendButton.on("click", function () {
    sendPanel.removeClass("d-none");
    readNotifPanel.addClass("d-none");
    notifPanel.addClass("d-none");

    sendButton.addClass("active");
    readNotifButton.removeClass("active");
    notifButton.removeClass("active");

    try {
      localStorage.setItem("notificationTab", "send");
    } catch (e) {
      // Fail silently
    }
  });

  // Check page's last state on page load to ensure user gets directed to same page
  try {
    const lastTab = localStorage.getItem("notificationTab");
    if (lastTab === "send") {
      sendButton.trigger("click");
    } else if (lastTab === "read_notifications") {
      readNotifButton.trigger("click");
    } else {
      notifButton.trigger("click");
    }
  } catch (e) {
    // Fail silently if localStorage access throws
    notifButton.trigger("click");
  }
}


// Show/hide the store selector based on recipient group
function handleRecipientGroupChange() {
  recipient = $('#id_recipient_group').val()
  if (recipient === "store_managers" || recipient === "store_employees") {
    $('#id_store').closest('.form-group').removeClass('d-none');

  } else {
    $('#id_store').closest('.form-group').addClass('d-none');
  }
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