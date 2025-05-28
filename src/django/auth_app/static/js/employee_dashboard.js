$(document).ready(function() {
  // Initial state & history set
  updateClockedState();
  updateShiftHistory();

  // Attach event to update clocked state & shift history whenever selected store changes
  $('#storeSelectDropdown').on('change', function() {
    updateClockedState();
    updateShiftHistory();
  });

  // Handle deliveries adjustment
  handleDeliveryAdjustment();

  // Attach event to clock in/out submission to actually request the API
  $('#clockingButton').on('click', () => {
    clockInOutUser();
  });

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

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(30); // 30 minutes
});


function handleDeliveryAdjustment() {
  const $input = $('#deliveries');

  $('#plusButton').on('click', function (e) {
    e.preventDefault();
    const curr = parseInt($input.val(), 10) || 0;
    $input.val(curr + 1);
    if (curr == 0) {
      $('#minusButton').removeClass('disabled');
    }
  });

  $('#minusButton').on('click', function (e) {
    e.preventDefault();
    const curr = parseInt($input.val(), 10) || 0;
    if (curr > 0) {
      $input.val(curr - 1);
    }
    if (curr == 1) {
      $('#minusButton').addClass('disabled');
    }
  });

  // Handle minus button disabling
  $('#deliveries').on('input', function () {
    if ($(this).val() > 0) {
      $('#minusButton').removeClass('disabled');

    } else{
      $('#minusButton').addClass('disabled');
    }
  });

  // Disable button on first load if the input field is default 0
  if ((parseInt($input.val(), 10) || 0) == 0) {
    $('#minusButton').addClass('disabled'); 
  }
}


function updateClockedState() {
  // Remove Clocked In Info if it exists
  $('#clockedInInfoDiv').empty();

  if (getSelectedStoreID() === null) {
    showNotification("Cannot update clocked state due to not having selected a store.", "danger");
    return;
  }

  $.ajax({
    url: `${window.djangoURLs.clockedState}?store_id=${getSelectedStoreID()}`,
    type: "GET",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(response) {
      // Update the clocking in/out button based on response
      updateClockButtonState(response.clocked_in);

      // Add the clockin information if the user is clocked in
      if (response.clocked_in) {
        updateClockinInformation(response.login_time, response.login_timestamp);
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to load clocked state for selected store due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to load clocked state for selected store. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


// Update clock button state based on API response
function updateClockButtonState(clockedIn) {
  // Assume starting from disabled state going into enabled state (cant go backwards)
  $("#clockingButton").prop("disabled", false);

  if (clockedIn) {
    $("#clockingButton")
      .text("Clock Out")
      .removeClass("btn-success")
      .addClass("btn-danger")
      .attr('data-clocking-action', 'clockout');
    $("#minusButton").removeClass('disabled');
    $("#plusButton").removeClass('disabled');
    $('#deliveries').prop('disabled', false);
  } else {
    $("#clockingButton")
      .text("Clock In")
      .removeClass("btn-danger")
      .addClass("btn-success")
      .attr('data-clocking-action', 'clockin');
    $("#minusButton").addClass('disabled');
    $("#plusButton").addClass('disabled');
    $('#deliveries').prop('disabled', true); // Also disable the input field
  }
}


function updateClockinInformation(login_time, login_timestamp) {
  $infoDiv = $('#clockedInInfoDiv');

  // Append the times
  $infoDiv.append(`<div>Registered Start Time: ${formatTime(login_timestamp)}</div>`);
  $infoDiv.append(`<div>Actual Start Time: ${formatTime(login_time)}</div>`);
}


async function clockInOutUser() {
  // Show the spinner to indicate the page is waiting for informaiton
  showSpinner();

  const clockingIn = ($("#clockingButton").attr('data-clocking-action')?.toLowerCase() === 'clockin')
  const deliveries = ensureSafeInt($('#deliveries').val(), 0, null);
  $('#deliveries').val(deliveries); // Update value if its not safe

  // Get location data using the helper function
  const locationData = await getLocationData();
  
  if (!locationData) {
    hideSpinner();
    return;
  }

  const [userLat, userLong] = locationData;

  if (clockingIn) {
    $.ajax({
      url: `${window.djangoURLs.clockIn}`,
      type: "PUT",
      xhrFields: {
        withCredentials: true
      },
      headers: {
        'X-CSRFToken': getCSRFToken(), // Include CSRF token
      },
      contentType: 'application/json',
      data: JSON.stringify({
        store_id: getSelectedStoreID(),
        location_latitude: userLat,
        location_longitude: userLong,
      }),
  
      success: function(response) {
        hideSpinner();

        // Update the clocked state and subsequently the clocking buttons
        updateClockedState();
        updateShiftHistory();
        showNotification("Successfully clocked in.");
      },
  
      error: function(jqXHR, textStatus, errorThrown) {
        hideSpinner();
        // Extract the error message from the API response if available
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to clock in due to internal server errors. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to clock in. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });

  } else {
    $.ajax({
      url: `${window.djangoURLs.clockOut}`,
      type: "PUT",
      xhrFields: {
        withCredentials: true
      },
      headers: {
        'X-CSRFToken': getCSRFToken(), // Include CSRF token
      },
      contentType: 'application/json',
      data: JSON.stringify({
        store_id: getSelectedStoreID(),
        location_latitude: userLat,
        location_longitude: userLong,
        deliveries: deliveries,
      }),
  
      success: function(response) {
        hideSpinner();

        // Update the clocked state and subsequently the clocking buttons
        updateClockedState();
        showNotification("Successfully clocked out.");
      },
  
      error: function(jqXHR, textStatus, errorThrown) {
        hideSpinner();
        // Extract the error message from the API response if available
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to clock out due to internal server errors. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to clock out. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });
  }
}


//////////////////////// SHIFT HISTORY & SHIFT ROSTER HANDLING //////////////////////////////

function updateShiftHistory() {
  $('#shiftHistoryContainer').empty();

  if (getSelectedStoreID() === null) {
    showNotification("Cannot update shift history due to not having selected a store.", "danger");
    $('#shiftHistoryContainer').append('<div class="rounded bg-danger-subtle text-dark p-4">Failed to load shifts.</div>');
    return;
  }

  $.ajax({
    url: `${window.djangoURLs.listRecentShifts}?store_id=${getSelectedStoreID()}`,
    type: "GET",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(response) {
      if (response.length === 0) {
        $('#shiftHistoryContainer').append('<div class="rounded bg-danger-subtle text-dark p-4">No shifts found within last 7 days.</div>');
        return;
      }

      response.forEach(shift => {
        const loginDate = new Date(shift.login_time);
        const logoutDate = shift.logout_time ? new Date(shift.logout_time) : null;

        const dateStr = loginDate.toLocaleDateString('en-GB'); // DD/MM/YYYY
        const loginTimeStr = loginDate.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        const logoutTimeStr = logoutDate
          ? logoutDate.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
          : "N/A";

        // Decide background colour based on priority highest to lowest (not finished [green], has been modified by manager [red], is public holiday [blue], then [white])
        const background = !logoutDate ? 'bg-success-subtle' : (shift.is_modified ? 'bg-danger-subtle' : (shift.is_public_holiday ? 'bg-info-subtle' : 'bg-light'));
        const deliveriesDiv = shift.deliveries ? `<div><i class="fas fa-truck me-2"></i>${shift.deliveries}</div>` : ''

        const card = `
          <div class="p-3 m-2 rounded ${background} shadow-sm text-center" style="min-width: 220px;">
            <div><strong>${shift.store_code}</strong></div>
            <div>${shift.is_public_holiday ? `<em>${dateStr}</em>` : dateStr}</div>
            <div><span class="fw-medium">Start:</span> ${loginTimeStr}</div>
            <div><span class="fw-medium">End:</span> ${logoutTimeStr}</div>
            ${deliveriesDiv}
          </div>
        `;

        $('#shiftHistoryContainer').append(card);
      });
    },

    error: function(jqXHR, textStatus, errorThrown) {
      $('#shiftHistoryContainer').append('<div class="rounded bg-danger-subtle text-dark p-4">Failed to load shifts.</div>');
      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to get shift history for selected store due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to get shift history for selected store. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


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


//////////////////////////// HELPER FUNCTIONS ///////////////////////////////////////


// Format time function
function formatTime(text) {
  if (!text) { return ""; }

  const date = new Date(text);
  const options = { hour: 'numeric', minute: 'numeric', hour12: true };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}