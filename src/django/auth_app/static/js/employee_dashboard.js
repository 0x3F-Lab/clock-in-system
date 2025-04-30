$(document).ready(function() {
  // Attach event to update clocked state whenever selected store changes
  $('#storeSelectDropdown').on('change', function() {
    updateClockedState();
  });

  // Update store selection component
  populateStoreSelection();

  // Handle deliveries adjustment
  handleDeliveryAdjustment();

  // Attach event to clock in/out submission to actually request the API
  $('#clockingButton').on('click', () => {
    clockInOutUser();
  });
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
    url: `${window.djangoURLs.clockedState}`,
    type: "GET",
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },
    data: {
      store_id: getSelectedStoreID(),
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


//////////////////////////// HELPER FUNCTIONS ///////////////////////////////////////


// Format time function
function formatTime(text) {
  if (!text) { return ""; }

  const date = new Date(text);
  const options = { hour: 'numeric', minute: 'numeric', hour12: true };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}