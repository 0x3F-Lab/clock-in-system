let clockedIn = false;
let userSelected = false;

$(document).ready(function () {
    // Access Django-generated URLs
    const listEmployeeNamesURL = window.djangoURLs.listEmployeeNames;
    const clockedStateURL = window.djangoURLs.clockedState;
    const clockInURL = window.djangoURLs.clockIn;
    const clockOutURL = window.djangoURLs.clockOut;

    // Check if required URLs are defined
    if (!listEmployeeNamesURL || !clockedStateURL || !clockInURL || !clockOutURL) {
        console.error("API URLs are not set correctly.");
    }

    // Disable buttons initially
    $("#clockButton").prop("disabled", true);
    $("#minusButton").prop("disabled", true);
    $("#plusButton").prop("disabled", true);

    // Initialize UI elements
    populateModalUserList(listEmployeeNamesURL);
    handleUserSelectionModal(clockedStateURL);
    handleDeliveryAdjustments();

    // PIN modal focus and blur events
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

    // Update local time every second
    setInterval(updateLocalTime, 1000);
});

/************ FUNCTIONS ************/

/* Populate the modal with the user list */
function populateModalUserList(listEmployeeNamesURL) {
    $.get(listEmployeeNamesURL, function (data) {
        const $userList = $("#userList");
        data.forEach(employee => {
            $userList.append(
                `<li class="list-group-item list-group-item-action" data-id="${employee[0]}">${employee[1]}</li>`
            );
        });
    }).fail(function (jqXHR) {
        let errorMessage;
        if (jqXHR.status === 500) {
            errorMessage = "Failed to load employee list due to internal server error. Please try again.";
        } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to load employee list. Please try again.";
        }
        showNotification(errorMessage, "danger");
    });
}

/* Handle user selection from the modal */
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

        $("#selectUserButton")
            .text(userName)
            .data("id", userID)
            .attr("data-id", userID);

        fetchClockedState(clockedStateURL, userID);

        userSelected = true;

        const userModal = bootstrap.Modal.getInstance(document.getElementById("userModal"));
        userModal.hide();
    });

    // Focus management for user selection modal
    $("#userModal").on("shown.bs.modal", function () {
        $("#userSearchBar").trigger("focus");
    });
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

/* Fetch the clocked-in state for a user */
function fetchClockedState(clockedStateURL, userID) {
    if (userID) {
        $.get(`${clockedStateURL}${userID}/`, function (data) {
            clockedIn = data.clocked_in;
            updateClockButtonState();
            updateShiftInfo(data.login_time);
        }).fail(function (jqXHR) {
            let errorMessage;
            if (jqXHR.status === 500) {
                errorMessage = "Failed to retrieve clocked-in state due to internal server error. Please try again.";
            } else {
                errorMessage = jqXHR.responseJSON?.Error || "Failed to retrieve clocked-in state. Please try again.";
            }
            showNotification(errorMessage, "danger");
        });
    }
}

/* Update the clock button state based on clockedIn */
function updateClockButtonState() {
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

/* Handle delivery count adjustments */
function handleDeliveryAdjustments() {
    $("#minusButton").click(function () {
        adjustDeliveries(-1);
    });
    $("#plusButton").click(function () {
        adjustDeliveries(1);
    });
}

/* Toggle clock in/out */
async function toggleClock(clockInURL, clockOutURL, pin) {
    // Ensure an employee is selected
    const userID = $("#selectUserButton").data("id");
    if (!userID) {
        showNotification("Please select an employee first.", "warning");
        return;
    }

    const deliveries = parseInt(deliveriesCount.textContent, 10);
    const csrftoken = getCookie("csrftoken");

    // Get location data
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
                "X-CSRFToken": csrftoken
            },
            data: JSON.stringify({
                location_latitude: userLat,
                location_longitude: userLon,
                pin: pin
            }),
            success: function (data) {
                clockedIn = true;
                updateShiftInfo((startTime = data.login_time));
                updateClockButtonState();
                showNotification("Successfully clocked in.", "success");
            },
            error: function (jqXHR) {
                let errorMessage;
                if (jqXHR.status === 500) {
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
                "X-CSRFToken": csrftoken
            },
            data: JSON.stringify({
                location_latitude: userLat,
                location_longitude: userLon,
                deliveries: deliveries,
                pin: pin
            }),
            success: function (data) {
                clockedIn = false;
                updateShiftInfo(
                    (startTime = data.login_time),
                    (endTime = data.logout_time),
                    (shiftLengthMins = data.shift_length_mins),
                    (deliveryCount = data.deliveries)
                );
                $("#deliveriesCount").text("0");
                updateClockButtonState();
                showNotification("Successfully clocked out.", "success");
            },
            error: function (jqXHR) {
                let errorMessage;
                if (jqXHR.status === 500) {
                    errorMessage = "Failed to clock out due to internal server errors. Please try again.";
                } else {
                    errorMessage = jqXHR.responseJSON?.Error || "Failed to clock out. Please try again.";
                }
                showNotification(errorMessage, "danger");
            }
        });
    }
}

/* Request PIN from the user */
async function requestPin() {
    return new Promise((resolve) => {
        const pinModalElement = document.getElementById("authPinModal");
        const pinModal = new bootstrap.Modal(pinModalElement);
        pinModal.show();

        // Handle PIN submission
        $("#authPinSubmit")
            .off("click")
            .on("click", async function () {
                const pin = $("#authPinInput").val().trim();
                pinModal.hide();
                $("#authPinInput").val("");
                resolve(pin || null);
            });

        // Handle dismissal without entering a PIN
        $("#authPinModal").on("hidden.bs.modal", function () {
            $("#authPinInput").blur();
            resolve(null);
        });
    });
}

/* Update local time display */
function updateLocalTime() {
    const now = new Date();
    $("#localTime").text(now.toLocaleTimeString());
}

/* Update shift info display */
function updateShiftInfo(startTime, endTime, shiftLengthMins, deliveryCount) {
    const $shiftInfo = $("#shiftInfo");
    $shiftInfo.empty();

    if (startTime) {
        $shiftInfo.append(`<p>Start Time: ${formatTime(startTime)}</p>`);
    }
    if (endTime) {
        $shiftInfo.append(`<p>End Time: ${formatTime(endTime)}</p>`);
    }

    if (shiftLengthMins || shiftLengthMins === 0) {
        const hours = Math.floor(shiftLengthMins / 60);
        const mins = shiftLengthMins % 60;
        $shiftInfo.append(
            `<p>Shift Length:${hours ? ` ${hours} Hours` : ""} ${
                mins ? `${mins} Minutes` : hours ? "" : `${mins} Minutes`
            }</p>`
        );
    }

    // Only add delivery count if the user has finished the shift
    if (endTime && deliveryCount !== undefined) {
        $shiftInfo.append(`<p>Deliveries Completed: ${deliveryCount}</p>`);
    }
}

/* Adjust the deliveries count */
function adjustDeliveries(amount) {
    if (clockedIn) {
        const $deliveriesCount = $("#deliveriesCount");
        const current = parseInt($deliveriesCount.text(), 10) || 0;
        $deliveriesCount.text(Math.max(0, current + amount));
    }
}

/************ HELPER FUNCTIONS ************/

/* Format time string */
function formatTime(text) {
    if (!text) {
        return "";
    }
    const date = new Date(text);
    const options = { hour: "numeric", minute: "numeric", hour12: true };
    return new Intl.DateTimeFormat("en-US", options).format(date);
}

/* Get the location data of the user */
async function getLocationData() {
    if ("geolocation" in navigator) {
        // Check geolocation permissions proactively
        const permissionStatus = await navigator.permissions.query({ name: "geolocation" });

        if (permissionStatus.state === "denied") {
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
                    enableHighAccuracy: true,
                    timeout: 30000,
                    maximumAge: 45000
                }
            );
        });
    } else {
        showNotification("Geolocation is not supported by your browser. Cannot clock in/out.");
        return null;
    }
}
