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

// Enable "Clock In" button when a user is selected
userDropdown.addEventListener("change", () => {
    if (userDropdown.value) {
        clockButton.disabled = false; // Enable the clock button
    }
});

// Toggle Clock In/Clock Out
function toggleClock() {
    if (!clockedIn) {
        // Clocking in
        clockedIn = true;
        startTime = new Date();
        clockButton.textContent = "Clock Out";
        clockButton.style.backgroundColor = "red";
        deliveriesCount.textContent = "0"; // Reset deliveries
        minusButton.disabled = false;
        plusButton.disabled = false;

        intervalId = setInterval(updateTimer, 1000); // Start timer
    } else {
        // Clocking out
        clockedIn = false;
        clearInterval(intervalId); // Stop timer
        const endTime = new Date();
        const totalMinutes = Math.round((endTime - startTime) / 60000);

        clockButton.textContent = "Clock In";
        clockButton.style.backgroundColor = "green";
        minusButton.disabled = true;
        plusButton.disabled = true;

        // Update left panel
        timer.textContent = "Worked: 0H 0M";
        totalTimeDisplay.textContent = `${Math.floor(totalMinutes / 60)}H ${totalMinutes % 60}M`;
        totalDeliveriesDisplay.textContent = deliveriesCount.textContent;

        deliveriesCount.textContent = "0"; // Reset deliveries after clock out
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
