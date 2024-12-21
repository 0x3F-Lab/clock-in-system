let clockedIn = false; // Track clock-in state

$(document).ready(function() {
  // Access Django-generated URLs
	const listEmployeesUrl = window.djangoUrls.listEmployees;
	const clockedStateUrl = window.djangoUrls.clockedState;
	const clockInUrl = window.djangoUrls.clockIn;
	const clockOutUrl = window.djangoUrls.clockOut;

  // Populate dropdown menu (done only once)
  populateDropDownMenu(listEmployeesUrl);

  // Handle user updating drop down menu
  handleDropDownMenu(clockedStateUrl);

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

function populateDropDownMenu(listEmployeesUrl) {
  $.get(listEmployeesUrl, function(data) {
    data.forEach(employee => {
      $("#userDropdown").append(new Option(employee[1], employee[0]));
    });
  });
}


// To handle any changes with the drop down menu
function handleDropDownMenu(clockedStateUrl) {
  $("#userDropdown").change(function () {
    const userId = $(this).val(); // Get the selected user ID

    if (userId) {
      // Enable the clock button and check clocked-in state
      $("#clockButton").prop("disabled", false); // Enable clock button

      // Get clocked info from API
      $.get(`${clockedStateUrl}${userId}/`, function (data) {
        clockedIn = data.clocked_in; // Update clockedIn state
        updateClockButtonState(); // Update the button state
        updateShiftInfo(startTime=data.login_time); // Update shift info with start time (if clocked in)
      });

    } else {
      // If no valid user is selected, disable the clock button and delivery buttons
      $("#clockButton").prop("disabled", true);
      $("#minusButton").prop("disabled", true);
      $("#plusButton").prop("disabled", true);
    }
  });
}


// Update clock button state based on clockedIn
function updateClockButtonState() {
  if (clockedIn) {
    $("#clockButton").text("Clock Out");
    $("#clockButton").css("background-color", "red");
    $("#minusButton").prop("disabled", false);
    $("#plusButton").prop("disabled", false);
  } else {
    $("#clockButton").text("Clock In");
    $("#clockButton").css("background-color", "green");
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
  const userId = $("#userDropdown").val();
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
      url: `${clockInUrl}${userId}/`,
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
      }
    });
  } else {
    // Clocking out
    $.ajax({
      url: `${clockOutUrl}${userId}/`,
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

  if (shiftLengthMins) {
    const hours = Math.floor(shiftLengthMins / 60);
    const mins = shiftLengthMins % 60;
    $shiftInfo.append(`<p>Shift Length:${hours ? ` ${hours} Hour(s)` : ""} ${mins ? `${mins} Minutes` : ""}</p>`);
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
        }
      );
    });
  } else {
    alert("Geolocation is not supported by your browser. Cannot clock in.");
    return null;
  }
}
