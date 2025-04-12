let clockedIn = false; // Track clock-in state
let userSelected = false; // Track when the user selects an employee


$(document).ready(function() {
  // Access Django-generated URLs
	const listEmployeeNamesURL = window.djangoURLs.listEmployeeNames;
	const clockedStateURL = window.djangoURLs.clockedState;
	const clockInURL = window.djangoURLs.clockIn;
	const clockOutURL = window.djangoURLs.clockOut;
  const changePinURL = window.djangoURLs.changePin;

  if (listEmployeeNamesURL === undefined || clockedStateURL === undefined || clockInURL === undefined || clockOutURL === undefined) {
    console.error("API URLs are not set correctly.");
  }

  // Disable buttons until they are required
  $("#clockButton").prop("disabled", true);
  $("#minusButton").prop("disabled", true);
  $("#plusButton").prop("disabled", true);

  // Populate the modal user list
  populateModalUserList(listEmployeeNamesURL);

  // Handle user selection modal
  handleUserSelectionModal(clockedStateURL);

  // Handle deliveries adjustment
  handleDeliveryAdjustments();

  // Handle user changing pin
  handleChangePin(listEmployeeNamesURL, changePinURL);

  // Focus on PIN input when the PIN modal is shown
  $("#authPinModal").on("shown.bs.modal", function () {
    $("#authPinInput").trigger("focus");
  });

  // Remove focus from PIN input when the PIN modal is hidden
  $("#authPinModal").on("hidden.bs.modal", function () {
    $("#authPinInput").blur();
  });

  // Add listener for when clock in/out button is clicked
  $("#clockButton").click(async function() {
    const pin = await requestPin(); // Get the PIN from the user
    if (pin) {
      toggleClock(clockInURL, clockOutURL, pin); // Pass the PIN to toggleClock
    }
  });

  // Start Updating Local Time
	setInterval(updateLocalTime, 1000);
})



////// FUNCTIONS //////

// Populate the modal with the user list
function populateModalUserList(listEmployeeNamesURL) {
  $.get(listEmployeeNamesURL, function (data) {
      const $userList = $("#userList");
      data.forEach(employee => {
          $userList.append(`<li class="list-group-item list-group-item-action" data-id="${employee[0]}">${employee[1]}</li>`);
      });

  }).fail(function (jqXHR) {
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to load employee list due to internal server error. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to load employee list. Please try again.";
      }
      showNotification(errorMessage, "danger");
  });
}


// Handle user selection from the modal
function handleUserSelectionModal(clockedStateURL) {
  // Open modal on "Select User" button click
  $("#selectUserButton").click(function () {
      const userModal = new bootstrap.Modal(document.getElementById("userModal"));
      userModal.show();
  });

  // Handle user selection from the list
  $("#userList").on("click", "li", function () {
      const userID = $(this).data("id");
      const userName = $(this).text();

      // Update UI with selected user
      $("#selectedEmployee")
        .text(userName)
        .data("id", userID)
        .attr("data-id", userID); // Also add it to the DOM

      // Fetch clocked-in state for the selected user (and updates buttons)
      fetchClockedState(clockedStateURL, userID);

      // Update selected state
      userSelected = true

      // Close the modal
      const userModal = bootstrap.Modal.getInstance(document.getElementById("userModal"));
      userModal.hide();
  });

  // Focus on search input when the user selection modal is shown
  $("#userModal").on("shown.bs.modal", function () {
    $("#userSearchBar").trigger("focus");
  });

  // Remove focus from search input when the user selection modal is hidden
  $("#userModal").on("hidden.bs.modal", function () {
    $("#userSearchBar").blur();
  });

  // Search functionality in the modal
  $("#userSearchBar").on("input", function () {
      const searchTerm = $(this).val().toLowerCase();
      const $userList = $("#userList");
      const users = $userList.children();

      users.each(function () {
          const $user = $(this);
          $user.toggle($user.text().toLowerCase().includes(searchTerm));
      });
  });
}


// Fetch clocked-in state for a user
function fetchClockedState(clockedStateURL, userID) {
  if (userID) {
      $.get(`${clockedStateURL}${userID}/`, function (data) {
          clockedIn = data.clocked_in;

          // Update buttons and info
          updateClockButtonState();
          updateShiftInfo(data.login_time);

      }).fail(function (jqXHR) {
          // Extract the error message from the API response if available
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to retrieve clocked-in state due to internal server error. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to retrieve clocked-in state. Please try again.";
          }
          showNotification(errorMessage, "danger");
      });
  }
}


// Update clock button state based on clockedIn
function updateClockButtonState() {
  // Assume starting from disabled state going into enabled state (cant go backwards)
  $("#clockButton").prop("disabled", false);

  if (clockedIn) {
    $("#clockButton")
      .text("Clock Out")
      .removeClass("btn-success")
      .addClass("btn-danger");
    $("#minusButton").prop("disabled", false);
    $("#plusButton").prop("disabled", false);
  } else {
    $("#clockButton")
      .text("Clock In")
      .removeClass("btn-danger")
      .addClass("btn-success");
    $("#minusButton").prop("disabled", true);
    $("#plusButton").prop("disabled", true);
  }
}


// Handle updates to 
function handleDeliveryAdjustments() {
	$("#minusButton").click(function() {
    adjustDeliveries(-1)}
  );
	$("#plusButton").click(function() {
    adjustDeliveries(1)
  });
}


// Toggle Clock In/Clock Out
async function toggleClock(clockInURL, clockOutURL, pin) {
  // Ensure cant clock in/out until an employee is selected
  if (!userSelected) { return; }

  const userID = $("#selectedEmployee").data("id");
  const deliveries = parseInt(deliveriesCount.textContent, 10);
  const csrftoken = getCookie('csrftoken');

  // Get location data using the helper function
  const locationData = await getLocationData();
  
  if (!locationData) {
    return;
  }

  const [userLat, userLon] = locationData;

  if (!clockedIn) {
    // Clocking in
    $.ajax({
      url: `${clockInURL}${userID}/`,
      type: "PUT",
      contentType: "application/json",
      headers: {
        'X-CSRFToken': csrftoken // Include CSRF token
      },
      data: JSON.stringify({
        location_latitude: userLat,
        location_longitude: userLon,
        pin: pin,
      }),

      success: function(data) {
          clockedIn = true;

          // Update shift info
          updateShiftInfo(startTime=data.login_time);

          updateClockButtonState();
          showNotification("Successfully clocked in.", "success");
      },

      error: function(jqXHR, textStatus, errorThrown) {
        // Extract the error message from the API response if available
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to clock in due to internal server error. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to clock in. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });

  } else {
    // Clocking out
    $.ajax({
      url: `${clockOutURL}${userID}/`,
      type: "PUT",
      contentType: "application/json",
      headers: {
        'X-CSRFToken': csrftoken // Include CSRF token
      },
      data: JSON.stringify({
        location_latitude: userLat,
        location_longitude: userLon,
        deliveries: deliveries,
        pin: pin,
      }),

      success: function(data) {
        clockedIn = false;

        // Update shift info
        updateShiftInfo(startTime=data.login_time, endTime=data.logout_time, shiftLengthMins=data.shift_length_mins, deliveryCount=data.deliveries);

        $("#deliveriesCount").text("0"); // Reset deliveries after clock out
        updateClockButtonState();
        showNotification("Successfully clocked out.", "success");
      },

      error: function(jqXHR, textStatus, errorThrown) {
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


// Request PIN from the user
async function requestPin() {
  return new Promise((resolve) => {
      const pinModalElement = document.getElementById("authPinModal");
      const pinModal = new bootstrap.Modal(pinModalElement);
      pinModal.show();

      // Handle PIN submission
      $("#authPinSubmit").off("click").on("click", async function () {
          const pin = $("#authPinInput").val().trim();

          // Close the modal after the user enters a PIN
          pinModal.hide();

          // Clear the input field for future use
          $("#authPinInput").val("");

          if (pin) {
            //const hashedPin = await hashString(pin);
            resolve(pin); // Resolve the promise with the PIN
          } else {
            resolve(null); // Resolve with null if no PIN was entered
          }
      });

      // Optionally handle PIN modal dismissal without entering a PIN
      $("#authPinModal").on("hidden.bs.modal", function () {
          $("#authPinInput").blur(); // Take focus off PIN input
          resolve(null); // Resolve with null if the modal is dismissed
      });
  });
}


// Update Local Time
function updateLocalTime() {
  const now = new Date();
  $("#localTime").text(now.toLocaleTimeString());
}


// Add shift info
function updateShiftInfo(startTime, endTime, shiftLengthMins, deliveryCount) {
  const $shiftInfo = $("#shiftInfo")

  // Clear previous shift info
  $shiftInfo.empty();

  // Create new <p> elements and append them with the respective text
  if (startTime) { $shiftInfo.append(`<p>Start Time: ${formatTime(startTime)}</p>`); }
  if (endTime) { $shiftInfo.append(`<p>End Time: ${formatTime(endTime)}</p>`); }

  if (shiftLengthMins || shiftLengthMins == 0) {
    const hours = Math.floor(shiftLengthMins / 60);
    const mins = shiftLengthMins % 60;
    $shiftInfo.append(`<p>Shift Length:${hours ? ` ${hours} Hours` : ""} ${mins ? (`${mins} Minutes`) : (hours ? "" : `${mins} Minutes`)}</p>`);
  }

  // Only add delivery count IF they have finished the shift
  if (endTime && deliveryCount !== undefined) { $shiftInfo.append(`<p>Deliveries Completed: ${deliveryCount}</p>`); }
}


// Adjust Deliveries Count
function adjustDeliveries(amount) {
  if (clockedIn) {
    const $deliveriesCount = $("#deliveriesCount");

    // Convert to int
    const current = parseInt($deliveriesCount.text(), 10) || 0; // Returns 0 if it fails

    // Ensure new amount is no less than zero
    $deliveriesCount.text(Math.max(0, current + amount));
  }
}


// Change user pin
function handleChangePin(listEmployeeNamesURL, changePinURL) {
  // When modal is about to be shown, populate employee list
  $("#changePinModal").on("show.bs.modal", function() {
    // Clear any previous data
    $("#changePinUserList").empty();
    $("#changePinSearchBar").val("");
    $("#changePinSelectedUserID").val("");
    $("#currentPin").val("");
    $("#newPin").val("");
    $("#confirmNewPin").val("");

    // Fetch the employees listEmployeeNames endpoint
    $.get(listEmployeeNamesURL, function(data) {
      // data might be [[1, "John Smith"], [2, "Jane Doe"]], etc.
      data.forEach(emp => {
        const userId = emp[0];
        const fullName = emp[1];
        $("#changePinUserList").append(`
          <li
            class="list-group-item"
            data-id="${userId}"
            style="cursor: pointer;"
          >
            ${fullName}
          </li>
        `);
      });
    })
    .fail(function(xhr) {
      showNotification("Failed to load employee list.", "danger");
      console.error(xhr);
    });
  });

  // Filter list on input
  $("#changePinSearchBar").on("input", function() {
    const term = $(this).val().toLowerCase();
    $("#changePinUserList").children("li").each(function() {
      $(this).toggle($(this).text().toLowerCase().includes(term));
    });
  });

  // Click on an employee name to select
  $("#changePinUserList").on("click", "li", function() {
    $("#changePinUserList li").removeClass("active");
    $(this).addClass("active");
    const userId = $(this).data("id");
    $("#changePinSelectedUserID").val(userId);
  });

  // Submit button
  $("#submitChangePin").on("click", function() {
    const userID = $("#changePinSelectedUserID").val();
    const currentPin = $("#currentPin").val().trim();
    const newPin = $("#newPin").val().trim();
    const confirmNewPin = $("#confirmNewPin").val().trim();

    if (!userID) {
      showNotification("Please select your name from the list.", "danger");
      return;
    }
    if (!currentPin || !newPin || !confirmNewPin) {
      showNotification("All pin fields are required.", "danger");
      return;
    }
    if (newPin !== confirmNewPin) {
      showNotification("New pin and confirmation do not match.", "danger");
      return;
    }

    const csrftoken = getCookie('csrftoken');

    // POST to your "change pin" endpoint
    $.ajax({
      url: `${changePinURL}${userID}/`,
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken
      },
      data: {
        current_pin: currentPin,
        new_pin: newPin
      },
      success: function(response) {
        if (response.success) {
          showNotification(response.message, "success");
          $("#changePinModal").modal("hide");
        } else {
          showNotification(response.message, "danger");
        }
      },
      error: function(jqXHR, textStatus, errorThrown) {
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to change pin due to internal error. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to change pin. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });
  });
}



/////// HELPER FUNCTIONS ///////


// Format time function
function formatTime(text) {
  if (!text) { return ""; }

  const date = new Date(text);
  const options = { hour: 'numeric', minute: 'numeric', hour12: true };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}


// Get the location data of the user
async function getLocationData() {
  if ('geolocation' in navigator) {
    // Check geolocation permissions proactively
    const permissionStatus = await navigator.permissions.query({ name: 'geolocation' });
    
    if (permissionStatus.state === 'denied') {
      showNotification("Location access is denied. Please enable it in your browser settings.");
      return null;
    }

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const userLat = position.coords.latitude;
          const userLon = position.coords.longitude;

          resolve([userLat, userLon]);
        },
        (error) => {
          switch (error.code) {
            case error.PERMISSION_DENIED:
              showNotification("Location access is denied. Please enable it in your browser settings.");
              break;
            case error.POSITION_UNAVAILABLE:
              showNotification("Location is unavailable. Please try again later.");
              break;
            case error.TIMEOUT:
              showNotification("Unable to get your location. Please ensure you have a good signal and try again.");
              break;
            default:
              showNotification("An unknown error occurred while retrieving your location.");
          }

          reject(null);
        },
        {
          enableHighAccuracy: true,  // Request high accuracy for mobile users
          timeout: 30000,            // Timeout after 30 seconds
          maximumAge: 45000          // Allow cached location up to 45s old
        }
      );
    });
  } else {
    showNotification("Geolocation is not supported by your browser. Cannot clock in/out.");
    return null;
  }
}
