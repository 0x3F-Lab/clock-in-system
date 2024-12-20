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
      $.get(`${clockedStateUrl}${userId}/`, function (data) {
        clockedIn = data.clocked_in; // Update clockedIn state
        updateClockButtonState(); // Update the button state
      });

    } else {
      // If no valid user is selected, disable the clock button
      $("#clockButton").prop("disabled", true);
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
    alert("AA");
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
      success: function() {
          clockedIn = true;
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
        const totalMinutes = data.shift_length_mins
        console.log(totalMinutes)

        // Update left panel
        timer.textContent = "Worked: 0H 0M";
        $("#totalTime").text(`${Math.floor(totalMinutes / 60)}H ${totalMinutes % 60}M`);
        $("#totalDeliveries").text(deliveries);

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



/////// HELPER FUNCTIONS ///////

// Adjust Deliveries Count
function adjustDeliveries(amount) {
  if (clockedIn) {
    const $deliveriesCount = $("#deliveriesCount");

    const current = parseInt($deliveriesCount.textContent, 10);
    $deliveriesCount.textContent = Math.max(0, current + amount);
  }
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
