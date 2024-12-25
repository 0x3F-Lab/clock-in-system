let clockedIn = false; // Track clock-in state
let userSelected = false; // Track when the user selects an employee


$(document).ready(function() {
  // Access Django-generated URLs
	const listEmployeesUrl = window.djangoUrls.listEmployees;
	const clockedStateUrl = window.djangoUrls.clockedState;
	const clockInUrl = window.djangoUrls.clockIn;
	const clockOutUrl = window.djangoUrls.clockOut;

  // Disable buttons until they are required
  $("#clockButton").prop("disabled", true);
  $("#minusButton").prop("disabled", true);
  $("#plusButton").prop("disabled", true);

  // Populate the modal user list
  populateModalUserList(listEmployeesUrl);

  // Handle user selection modal
  handleUserSelectionModal(clockedStateUrl);

  // Handle deliveries adjustment
  handleDeliveryAdjustments();

  // Add listener for when clock in/out button is clicked
  $("#clockButton").click(function() {
    toggleClock(clockInUrl, clockOutUrl);
  });

  // Start Updating Local Time
	setInterval(updateLocalTime, 1000);
})



////// FUNCTIONS //////

// Populate the modal with the user list
function populateModalUserList(listEmployeesUrl) {
  $.get(listEmployeesUrl, function (data) {
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
function handleUserSelectionModal(clockedStateUrl) {
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
      fetchClockedState(clockedStateUrl, userID);

      // Update selected state
      userSelected = true

      // Close the modal
      const userModal = bootstrap.Modal.getInstance(document.getElementById("userModal"));
      userModal.hide();
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
function fetchClockedState(clockedStateUrl, userID) {
  if (userID) {
      $.get(`${clockedStateUrl}${userID}/`, function (data) {
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
async function toggleClock(clockInUrl, clockOutUrl) {
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
      url: `${clockInUrl}${userID}/`,
      type: "PUT",
      contentType: "application/json",
      headers: {
        'X-CSRFToken': csrftoken // Include CSRF token
      },
      data: JSON.stringify({
        location_latitude: userLat,
        location_longitude: userLon,
      }),

      success: function(data) {
          clockedIn = true;

          // Update shift info
          updateShiftInfo(startTime=data.login_time);

          updateClockButtonState();
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
      url: `${clockOutUrl}${userID}/`,
      type: "PUT",
      contentType: "application/json",
      headers: {
        'X-CSRFToken': csrftoken // Include CSRF token
      },
      data: JSON.stringify({
        location_latitude: userLat,
        location_longitude: userLon,
        deliveries: deliveries,
      }),

      success: function(data) {
        clockedIn = false;

        // Update shift info
        updateShiftInfo(startTime=data.login_time, endTime=data.logout_time, shiftLengthMins=data.shift_length_mins, deliveryCount=data.deliveries);

        $("#deliveriesCount").text("0"); // Reset deliveries after clock out
        updateClockButtonState();
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



/////// HELPER FUNCTIONS ///////


// Format time function
function formatTime(text) {
  if (!text) { return ""; }

  const date = new Date(text);
  const options = { hour: 'numeric', minute: 'numeric', hour12: true };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}


// Get the required cookie from document
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}


// Get the location data of the user
async function getLocationData() {
  if ('geolocation' in navigator) {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const userLat = position.coords.latitude;
          const userLon = position.coords.longitude;

          resolve([userLat, userLon]);
        },
        (error) => {
          console.error("Geolocation error:", error);
          alert("Unable to get your location. Cannot clock in.");
          reject(null);
        },
        {
          enableHighAccuracy: true,  // Request high accuracy
          timeout: 5000,             // Timeout after 5 seconds
          maximumAge: 0              // Do not use cached location
        }
      );
    });
  } else {
    alert("Geolocation is not supported by your browser. Cannot clock in.");
    return null;
  }
}
