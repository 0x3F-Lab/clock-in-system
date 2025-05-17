$(document).ready(function () {
  // Handle button(s) to mark a notification as read (dismiss it)
  handleNotificationMarkAsRead();

  // Function to handle submisison of notification messages (page form)
  handleNotificationSubmission();

  // Function to handle switching between the multiple pages on the notification page (i.e. seeing notifications to sending notifications)
  handleNotificationPageSwitching();
});


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


function handleNotificationOpen() {
  // Listen for any collapse being shown
  $('.collapse').on('show.bs.collapse', function () {
    const notifId = $(this).attr('id').split('-')[1];
    $(`[data-id="${notifId}"]`).removeClass('d-none');
  });

  // Hide the button when the collapse is closed
  $('.collapse').on('hide.bs.collapse', function () {
    const notifId = $(this).attr('id').split('-')[1];
    $(`[data-id="${notifId}"]`).addClass('d-none');
  });
}


function handleNotificationMarkAsRead() {
  // Listen for any collapse being shown
  $('.collapse').on('show.bs.collapse', function () {
    const notifId = $(this).attr('id').split('-')[1];
    $(`[data-id="${notifId}"]`).removeClass('d-none');
  });

  // Hide the button when the collapse is closed
  $('.collapse').on('hide.bs.collapse', function () {
    const notifId = $(this).attr('id').split('-')[1];
    $(`[data-id="${notifId}"]`).addClass('d-none');
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