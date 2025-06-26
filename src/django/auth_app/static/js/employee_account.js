$(document).ready(function() {

  // Add tooltip to user pin
  $('[data-bs-toggle="tooltip"]').tooltip();

  // Open edit modal when clicking on edit button
  $('#updateAccInfoBtn').on('click', () => {
    openEditModal();
  });

  // Open edit password modal when clicking on edit pass button at bottom
  $('#updateAccPassBtn').on('click', () => {
    openEditPassModal();
  });

  // When submitting account infromation modal, send info to API
  $('#editModalSubmit').on('click', function (e) {
    e.preventDefault();
    submitAccountInfoModal();
  });
  
  // When submitting password edit modal, send pass to API
  $('#editPassModalSubmit').on('click', function (e) {
    e.preventDefault();
    submitAccountPassModal();
  });

});

//////////////////////// ACOUNT INFORMATION HANDLING ////////////////////////////////

function openEditModal() {
  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function openEditPassModal() {
  const editPassModal = new bootstrap.Modal(document.getElementById("editPassModal"));
  editPassModal.show();
}


function submitAccountInfoModal() {
  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.modifyAccountInfo}`,
    type: "POST",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },
    contentType: 'application/json',
    data: JSON.stringify({
      first_name: $('#editFirstName').val(),
      last_name: $('#editLastName').val(),
      phone: $('#editPhone').val(),
    }),

    success: function(response) {
      hideSpinner();
      const editModal = new bootstrap.Modal(document.getElementById("editModal"));
      editModal.hide();
      const saved = saveNotificationForReload("Successfully updated account information.", "success", "Successfully updated account information. Please reload the page to see changes.");
      if (saved) {location.reload();}
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();
      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to update account information due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to update account information. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


function submitAccountPassModal() {
  // Ensure fields are set
  if (!$('#editOldPass').val() || !$('#editNewPass').val() || !$('#editNewPassCopy').val()) {
    $('#editPassModalGlobalFieldsWarning').removeClass('d-none');
    return;
  } else {
    $('#editPassModalGlobalFieldsWarning').addClass('d-none');
  }

  // Ensure the new password and copy is exactly the same.
  if ($('#editNewPass').val() !== $('#editNewPassCopy').val()) {
    $('#repeatPassWarning').removeClass('d-none');
    return;
  } else {
    $('#repeatPassWarning').addClass('d-none');
  }

  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.modifyAccountPass}`,
    type: "PUT",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },
    contentType: 'application/json',
    data: JSON.stringify({
      old_pass: $('#editOldPass').val(),
      new_pass: $('#editNewPass').val(),
    }),

    success: function(response) {
      hideSpinner();

      // Remove old errors/field data
      $('.editPassFieldError').remove();
      $('#editOldPass').val("");
      $('#editNewPass').val("");
      $('#editNewPassCopy').val("");

      const editPassModal = bootstrap.Modal.getInstance(document.getElementById("editPassModal"));
      editPassModal.hide();
      const saved = saveNotificationForReload("Successfully updated account password. Please login again.", "success", "Successfully updated account password. Please login again.");
      if (saved) {location.href = window.djangoURLs.login;}
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();
      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to update account password due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to update account password. Please try again.";
      }

      // Remove old field errors
      $('.editPassFieldError').remove();

      // Add field errors
      $.each(jqXHR.responseJSON?.field_errors?.old_pass || [], function (index, err) {
        $('#editOldPass').after(`<div class="editPassFieldError field-error mt-1">${err}</div>`);
      });
      $.each(jqXHR.responseJSON?.field_errors?.new_pass || [], function (index, err) {
        $('#editNewPass').after(`<div class="editPassFieldError field-error mt-1">${err}</div>`);
      });

      showNotification(errorMessage, "danger");
    }
  });
}
