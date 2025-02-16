// Track clock-in state and user selection
let clockedIn = false;
let userSelected = false;

$(document).ready(function () {
    // Access Django-generated URLs
    const listEmployeeNamesURL = window.djangoURLs.listEmployeeNames;
    const clockedStateURL = window.djangoURLs.clockedState;
    const clockInURL = window.djangoURLs.clockIn;
    const clockOutURL = window.djangoURLs.clockOut;

    if (!listEmployeeNamesURL || !clockedStateURL || !clockInURL || !clockOutURL) {
        console.error("API URLs are not set correctly.");
    }

    // Disable buttons initially
    $("#clockButton, #minusButton, #plusButton").prop("disabled", true);

    // Initialize UI elements
    populateModalUserList(listEmployeeNamesURL);
    handleUserSelectionModal(clockedStateURL);
    handleDeliveryAdjustments();
    setInterval(updateLocalTime, 1000);

    // Focus on PIN input when modal is shown
    $("#authPinModal").on("shown.bs.modal", function () {
        $("#authPinInput").trigger("focus");
    });
    $("#authPinModal").on("hidden.bs.modal", function () {
        $("#authPinInput").blur();
    });

    // Clock in/out button listener
    $("#clockButton").click(async function () {
        const pin = await requestPin();
        if (pin) {
            toggleClock(clockInURL, clockOutURL, pin);
        }
    });
});

/************ FUNCTIONS ************/

// Populate modal user list
function populateModalUserList(listEmployeeNamesURL) {
    $.get(listEmployeeNamesURL, function (data) {
        const $userList = $("#userList");
        data.forEach(employee => {
            $userList.append(`<li class="list-group-item list-group-item-action" data-id="${employee[0]}">${employee[1]}</li>`);
        });
    }).fail(function (jqXHR) {
        const errorMessage = jqXHR.status === 500
            ? "Failed to load employee list due to internal server error."
            : jqXHR.responseJSON?.Error || "Failed to load employee list.";
        showNotification(errorMessage, "danger");
    });
}

// Handle user selection modal
function handleUserSelectionModal(clockedStateURL) {
    $("#selectUserButton").click(() => {
        new bootstrap.Modal(document.getElementById("userModal")).show();
    });

    $("#userList").on("click", "li", function () {
        const userID = $(this).data("id");
        const userName = $(this).text();

        $("#selectUserButton")
            .text(userName)
            .data("id", userID)
            .attr("data-id", userID);

        fetchClockedState(clockedStateURL, userID);
        userSelected = true;

        bootstrap.Modal.getInstance(document.getElementById("userModal")).hide();
    });
}

// Fetch and update clocked-in state
function fetchClockedState(clockedStateURL, userID) {
    if (!userID) return;
    
    $.get(`${clockedStateURL}${userID}/`, function (data) {
        clockedIn = data.clocked_in;
        updateClockButtonState();
        updateShiftInfo(data.login_time);
    }).fail(function (jqXHR) {
        const errorMessage = jqXHR.status === 500
            ? "Failed to retrieve clocked-in state due to internal server error."
            : jqXHR.responseJSON?.Error || "Failed to retrieve clocked-in state.";
        showNotification(errorMessage, "danger");
    });
}

// Update clock button state
function updateClockButtonState() {
    $("#clockButton").prop("disabled", false);
    
    if (clockedIn) {
        $("#clockButton").text("Clock Out").removeClass("btn-success").addClass("btn-danger");
        $("#minusButton, #plusButton").prop("disabled", false);
    } else {
        $("#clockButton").text("Clock In").removeClass("btn-danger").addClass("btn-success");
        $("#minusButton, #plusButton").prop("disabled", true);
    }
}

// Handle delivery count adjustments
function handleDeliveryAdjustments() {
    $("#minusButton").click(() => adjustDeliveries(-1));
    $("#plusButton").click(() => adjustDeliveries(1));
}

// Adjust deliveries count
function adjustDeliveries(amount) {
    if (clockedIn) {
        const $deliveriesCount = $("#deliveriesCount");
        const current = parseInt($deliveriesCount.text(), 10) || 0;
        $deliveriesCount.text(Math.max(0, current + amount));
    }
}

// Update shift information
function updateShiftInfo(startTime, endTime, shiftLengthMins, deliveryCount) {
    const $shiftInfo = $("#shiftInfo");
    $shiftInfo.empty();

    if (startTime) $shiftInfo.append(`<p>Start Time: ${formatTime(startTime)}</p>`);
    if (endTime) $shiftInfo.append(`<p>End Time: ${formatTime(endTime)}</p>`);
    if (shiftLengthMins !== undefined) {
        const hours = Math.floor(shiftLengthMins / 60);
        const mins = shiftLengthMins % 60;
        $shiftInfo.append(`<p>Shift Length: ${hours ? ` ${hours} Hours` : ""} ${mins ? `${mins} Minutes` : ""}</p>`);
    }
    if (endTime && deliveryCount !== undefined) {
        $shiftInfo.append(`<p>Deliveries Completed: ${deliveryCount}</p>`);
    }
}

// Update local time display
function updateLocalTime() {
    $("#localTime").text(new Date().toLocaleTimeString());
}

// Format time utility function
function formatTime(text) {
    return text ? new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: 'numeric', hour12: true }).format(new Date(text)) : "";
}

// Request PIN from user
async function requestPin() {
    return new Promise((resolve) => {
        const pinModal = new bootstrap.Modal(document.getElementById("authPinModal"));
        pinModal.show();

        $("#authPinSubmit").off("click").on("click", function () {
            const pin = $("#authPinInput").val().trim();
            pinModal.hide();
            $("#authPinInput").val("");
            resolve(pin || null);
        });

        $("#authPinModal").on("hidden.bs.modal", function () {
            $("#authPinInput").blur();
            resolve(null);
        });
    });
}
