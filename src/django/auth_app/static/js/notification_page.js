$(document).ready(function () {
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

  handleNotificationCollapse();

  handleNotificationMarkAsRead();
});


function handleNotificationCollapse() {
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


handleNotificationMarkAsRead() {
  a=5
}