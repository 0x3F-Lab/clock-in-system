let clockedIn = false; // Track clock-in state
let startTime = null; // Store clock-in start time
let intervalId = null; // Interval for timer

const clockButton = document.getElementById("clockButton");
const deliveriesCount = document.getElementById("deliveriesCount");
const minusButton = document.getElementById("minusButton");
const plusButton = document.getElementById("plusButton");
const timer = document.getElementById("timer");
const totalTimeDisplay = document.getElementById("totalTime");
const totalDeliveriesDisplay = document.getElementById("totalDeliveries");
const localTimeDisplay = document.getElementById("localTime");
const userDropdown = document.getElementById("userDropdown");

// Access Django-generated URLs
const listEmployeesUrl = window.djangoUrls.listEmployees;
const clockedStateUrl = window.djangoUrls.clockedState;
const clockInUrl = window.djangoUrls.clockIn;
const clockOutUrl = window.djangoUrls.clockOut;

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

const csrftoken = getCookie('csrftoken');

// Fetch employees and populate dropdown
function fetchEmployees() {
    $.get(listEmployeesUrl, function(data) {
        data.forEach(employee => {
            $("#userDropdown").append(new Option(employee[1], employee[0]));
        });
    });
}

// Fetch clocked state when user is selected
$("#userDropdown").change(function() {
    const userId = $(this).val();
    if (userId) {
        $.get(`${clockedStateUrl}${userId}/`, function(data) {
            clockedIn = data.clocked_in;
            clockButton.disabled = false;
            updateClockButtonState();
        });
    }
});

// Update clock button state based on clockedIn
function updateClockButtonState() {
    if (clockedIn) {
        clockButton.textContent = "Clock Out";
        clockButton.style.backgroundColor = "red";
        minusButton.disabled = false;
        plusButton.disabled = false;
    } else {
        clockButton.textContent = "Clock In";
        clockButton.style.backgroundColor = "green";
        minusButton.disabled = true;
        plusButton.disabled = true;
    }
}

// Toggle Clock In/Clock Out
function toggleClock() {
    const userId = $("#userDropdown").val();
    const deliveries = parseInt(deliveriesCount.textContent, 10);

    if (!clockedIn) {
        // Clocking in
        $.ajax({
            url: `${clockInUrl}${userId}/`,
            type: "PUT",
            contentType: "application/json",
            headers: {
                'X-CSRFToken': csrftoken // Include CSRF token
            },
            success: function() {
                  clockedIn = true;
                  startTime = new Date();
                  updateClockButtonState();
                  intervalId = setInterval(updateTimer, 1000); // Start timer
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
            data: JSON.stringify({ deliveries: deliveries }),
            success: function() {
                clockedIn = false;
                clearInterval(intervalId); // Stop timer
                const endTime = new Date();
                const totalMinutes = Math.round((endTime - startTime) / 60000);

                // Update left panel
                timer.textContent = "Worked: 0H 0M";
                totalTimeDisplay.textContent = `${Math.floor(totalMinutes / 60)}H ${totalMinutes % 60}M`;
                totalDeliveriesDisplay.textContent = deliveries;

                deliveriesCount.textContent = "0"; // Reset deliveries after clock out
                updateClockButtonState();
            }
        });
    }
}

// Update Timer
function updateTimer() {
    const now = new Date();
    const elapsedMinutes = Math.round((now - startTime) / 60000);
    const hours = Math.floor(elapsedMinutes / 60);
    const minutes = elapsedMinutes % 60;

    timer.textContent = `Worked: ${hours}H ${minutes}M`;
}

// Update Local Time
function updateLocalTime() {
    const now = new Date();
    localTimeDisplay.textContent = now.toLocaleTimeString();
}

// Adjust Deliveries Count
function adjustDeliveries(amount) {
    if (clockedIn) {
        const current = parseInt(deliveriesCount.textContent, 10);
        deliveriesCount.textContent = Math.max(0, current + amount);
    }
}

// Attach Event Listeners
clockButton.addEventListener("click", toggleClock);
minusButton.addEventListener("click", () => adjustDeliveries(-1));
plusButton.addEventListener("click", () => adjustDeliveries(1));

// Start Updating Local Time
setInterval(updateLocalTime, 1000);

// Fetch employees on load
fetchEmployees();
