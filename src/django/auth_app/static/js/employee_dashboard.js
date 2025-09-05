$(document).ready(function() {
  // Attach event to update clocked state & shift history whenever selected store changes
  $('#storeSelectDropdown').on('change', function() {
    initEveryoneSwitchForSelectedStore(); // <--- ADDED
    updateClockedState();
    updateStoreInformation();
    updateShiftRosterAndHistory(new Date().toLocaleDateString('sv-SE'));
  });

  // NEW: When "Everyone" switch toggles, reload roster for the current week
  $('#viewEveryoneSwitch').on('change', function () {
    const weekNow = $('#schedule-week-title').data('week-start-date')
      ? new Date($('#schedule-week-title').data('week-start-date')).toLocaleDateString('sv-SE')
      : new Date().toLocaleDateString('sv-SE');
    updateShiftRosterAndHistory(weekNow);
  });

  // Handle deliveries adjustment
  handleDeliveryAdjustment();

  // Handle week switching on the roster dash
  handleWeekSwitching();

  // Handle shift modal (further info + cover requests)
  handleShiftModal();

  // Attach event to clock in/out submission to actually request the API
  $('#clockingButton').on('click', () => {
    clockInOutUser();
  });

  // Initial state & history set
  initEveryoneSwitchForSelectedStore(); // <--- ADDED
  updateClockedState();
  updateStoreInformation();
  updateShiftRosterAndHistory(new Date().toLocaleDateString('sv-SE'));

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
      .removeClass("btn-clock-in")
      .addClass("btn-clock-out")
      .attr('data-clocking-action', 'clockout');
    $("#minusButton").removeClass('disabled');
    $("#plusButton").removeClass('disabled');
    $('#deliveries').prop('disabled', false);
  } else {
    $("#clockingButton")
      .text("Clock In")
      .removeClass("btn-clock-out")
      .addClass("btn-clock-in")
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
      xhrFields: { withCredentials: true },
      headers: { 'X-CSRFToken': getCSRFToken() },
      contentType: 'application/json',
      data: JSON.stringify({
        store_id: getSelectedStoreID(),
        location_latitude: userLat,
        location_longitude: userLong,
      }),
      success: function(response) {
        hideSpinner();
        showNotification("Successfully clocked in.", "success");

        // Update the clocked state and subsequently the clocking buttons
        updateClockedState();
        updateShiftHistory();
      },
      error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to clock in"); }
    });

  } else {
    $.ajax({
      url: `${window.djangoURLs.clockOut}`,
      type: "PUT",
      xhrFields: { withCredentials: true },
      headers: { 'X-CSRFToken': getCSRFToken() },
      contentType: 'application/json',
      data: JSON.stringify({
        store_id: getSelectedStoreID(),
        location_latitude: userLat,
        location_longitude: userLong,
        deliveries: deliveries,
      }),
      success: function(response) {
        hideSpinner();
        showNotification("Successfully clocked out.", "success");

        // Update the clocked state and subsequently the clocking buttons
        updateClockedState();
        updateShiftHistory();
      },
      error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to clock out"); }
    });
  }
}


//////////////////////// SHIFT HISTORY & SHIFT ROSTER HANDLING //////////////////////////////

function handleWeekSwitching() {
    // --- Shift Previous Week --- 
    $('#previous-week-btn').on('click', function(e) {
        e.preventDefault();
        const previousWeek = $(this).data('week');
        if (isNonEmpty(previousWeek)) { updateShiftRosterAndHistory(previousWeek); }
    });

    // --- Shift Next Week ---
    $('#next-week-btn').on('click', function(e) {
        e.preventDefault();
        const nextWeek = $(this).data('week');
        if (isNonEmpty(nextWeek)) { updateShiftRosterAndHistory(nextWeek); }
    });
}


function updateShiftRosterAndHistory(week) {
  $('#schedule-container').empty();
  
  if (getSelectedStoreID() == null) {
    showNotification("Cannot update roster table due to not having selected a store.", "danger");
    $('#schedule-container').html(`
      <div class="d-flex flex-row gap-3 justify-content-around align-items-center bg-danger text-white text-center rounded p-2 w-100 mb-2">
        <div><i class="fas fa-circle-exclamation"></i></div>
        <div>
          <p class="m-0">Error loading roster. Please try again later.</p>
        </div>
      </div>`);
    return;
  }

  // Load the base week headers
  showSpinner();
  scheduleAddBaseDayDiv(week);

  // LOAD PAST ACTIVITIES (WORKED SHIFTS)
  $.ajax({
    url: `${window.djangoURLs.listUserActivities}?store_id=${getSelectedStoreID()}&week=${week}`,
    type: "GET",
    xhrFields: {withCredentials: true},
    headers: {'X-CSRFToken': getCSRFToken()},
    success: function(response) {
      $.each(response.activities || {}, function (date, activities) {
        activities.forEach(activity => {
          const duration = activity.logout_time_str
            ? calculateDuration(activity.login_time_str, activity.logout_time_str)
            : "N/A";

          // Decide background colour based on priority highest to lowest (not finished [green], has been modified by manager [red], is public holiday [blue], then [white])
          const background = !activity.logout_time_str ? 'bg-success-subtle' : (activity.is_modified ? 'bg-danger-subtle' : (activity.is_public_holiday ? 'bg-info-subtle' : 'bg-light'));
          const card = `
            <div class="shift-item position-relative text-dark ${background}">
              <div><strong>${activity.store_code}</strong></div>
              <div class="shift-item-details">
                <span>🕒 ${activity.login_time_str} – ${activity.logout_time_str ? activity.logout_time_str : 'N/A'}</span>
                <span>⌛ ${duration}</span>
                ${activity.deliveries ? `<span>🚚 ${activity.deliveries}</span>` : ''}
                ${activity.is_public_holiday ? '<span>✅ <em>Public Holiday</em></span>' : ''}
              </div>
            </div>`;

          const $roster = $(`#roster-${date}`);
          $roster.find('.default-no-schedule').remove(); // Remove placeholder if exists
          $roster.append(card);
        });
      });
    },
    error: function(jqXHR, textStatus, errorThrown) {
      $('#schedule-container').html(`
        <div class="d-flex flex-row gap-3 justify-content-around align-items-center bg-danger text-white text-center rounded p-2 w-100 mb-2">
          <div><i class="fas fa-circle-exclamation"></i></div>
          <div>
            <p class="m-0">Error loading past shifts. Please try again later.</p>
          </div>
        </div>`);
      handleAjaxError(jqXHR, "Failed to load past shifts in this week");
      return;
    }
  });

  // --- Build query params (add get_all when "Everyone" is checked)
const everyone = $('#viewEveryoneSwitch').is(':checked');
const params = new URLSearchParams({ week });
if (everyone) {
  params.set('get_all', 'true');
  params.set('legacy', 'true'); 
}
  // LOAD ROSTERED SHIFTS
  $.ajax({
    url: `${window.djangoURLs.listStoreShifts}${getSelectedStoreID()}/?${params.toString()}`,
    method: 'GET',
    xhrFields: {withCredentials: true},
    headers: {'X-CSRFToken': getCSRFToken()},
    success: function(data) {
      $.each(data.schedule || {}, function (dayDate, dayShifts) {
        let shiftsHtml = '';
        if (dayShifts && dayShifts.length > 0) {
          dayShifts.forEach(shift => {
            const borderColor = shift.role_colour || '#adb5bd'; 
            const duration = calculateDuration(shift.start_time, shift.end_time);

            // Build the HTML with the new color logic.
            shiftsHtml += `
              <div class="shift-item shift-item-action position-relative cursor-pointer" style="border-left: 8px solid ${borderColor}; background-color: #f8f9fa;" data-shift-id="${shift.id}">
                ${shift.has_comment ? '<span class="danger-tooltip-icon position-absolute p-1" data-bs-toggle="tooltip" title="This shift has a comment">C</span>' : ''}
                <div class="shift-item-employee">${shift.role_name ? shift.role_name : 'No Role'}</div>
                <div class="shift-item-details">
                  <span>🕒 ${shift.start_time} – ${shift.end_time}</span>
                  <span>⌛ ${duration}</span>
                </div>
              </div>`;
          });
        }
        const $roster = $(`#roster-${dayDate}`);
        if (shiftsHtml !== '') { $roster.find('.default-no-schedule').remove(); } // Remove placeholder if exists
        $roster.append(shiftsHtml);
      });

      $('#previous-week-btn').data('week', data.prev_week);
      $('#next-week-btn').data('week', data.next_week);
    },
    error: function(jqXHR, textStatus, errorThrown) {
      $('#schedule-container').html(`
        <div class="d-flex flex-row gap-3 justify-content-around align-items-center bg-danger text-white text-center rounded p-2 w-100 mb-2">
          <div><i class="fas fa-circle-exclamation"></i></div>
          <div>
            <p class="m-0">Error loading roster. Please try again later.</p>
          </div>
        </div>`);
      handleAjaxError(jqXHR, "Failed to load the roster week");
      return;
    }
  });

  $('[data-bs-toggle="tooltip"]').tooltip(); // Enable tooltips
  hideSpinner();
}


function scheduleAddBaseDayDiv(week) {
  const scheduleContainer = $('#schedule-container');
  scheduleContainer.empty(); // Clear existing content

  const weekStart = new Date(week);
  const monday = getMonday(weekStart); // Ensure it's Monday

  for (let i = 0; i < 7; i++) {
    const dayDate = new Date(monday);
    dayDate.setDate(monday.getDate() + i);

    const isoDate = dayDate.toISOString().split('T')[0]; // e.g., "2025-07-01"
    const dayCardHtml = `
      <div class="day-column mb-4">
        <div class="day-header">
          <div class="day-name">${getFullDayName(dayDate)}</div>
          <div class="day-date">${getShortDate(dayDate)}</div>
        </div>
        <div id="roster-${isoDate}" class="shifts-list">
          <div class="default-no-schedule text-center text-white p-3"><small>No shifts</small></div>
        </div>
      </div>`;
    scheduleContainer.append(dayCardHtml);
  }

  $('#schedule-week-title')
    .text(`Week of ${formatWeekTitle(monday)}`)
    .data('week-start-date', monday.toISOString());
}


function handleShiftModal() {
  // CLICK ON SHIFT -> POPULATE MODAL DETAILS AND OPEN IT
  $('#schedule-container').on('click', '.shift-item-action', function() {
    showSpinner();
    const shiftId = $(this).data('shift-id');

    // Get shift info -> ENSURE ITS ALWAYS UP TO DATE
    $.ajax({
      url: `${window.djangoURLs.manageShift}${shiftId}/`,
      method: 'GET',
      headers: { 'X-CSRFToken': getCSRFToken() },
      xhrFields: { withCredentials: true },
      success: function(shiftData) {
        $('#displayShiftId').val(shiftData.id);
        $('#displayShiftDate').text(shiftData.date); 
        $('#displayShiftRole').text(shiftData.role_name || "N/A");
        $('#displayStartTime').text(shiftData.start_time);
        $('#displayEndTime').text(shiftData.end_time);
        $('#displayComment').text(shiftData.comment || "No Comment");

        // Clear selected user (if one was selected before)
        $('#editModalSelectedEmployeeID').val('');
        $("#editModalEmployeeList li").removeClass("active");

        // If role has description, add it
        $('#displayShiftRoleDesc').text('');
        if (shiftData.role_desc) { $('#displayShiftRoleDesc').text(shiftData.role_desc) }
        
        hideSpinner();
        const editModal = new bootstrap.Modal(document.getElementById('editModal'));
        editModal.show();
      },
      error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to get shift information"); }
    });
  });

  // HANDLE EMPLOYEE LIST INPUT/SELECTION
  // Filter list on input
  $("#editModalEmployeeSearchBar").on("input", function() {
      const term = $(this).val().toLowerCase();
      $("#editModalEmployeeList").children("li").each(function() {
          $(this).toggle($(this).text().toLowerCase().includes(term));
      });
  });

  // Click on an employee name to select
  $("#editModalEmployeeList").on("click", "li", function() {
      $("#editModalEmployeeList li").removeClass("active");
      $(this).addClass("active");
      const userId = $(this).data("id");
      $("#editModalSelectedEmployeeID").val(userId);
  });

  // CLICK ON COVER SUBMISSION BUTTON -> SEND TO API
  $('#editModal').on("click", ".cover-btn", function() {
    const method = $(this).data("type").toLowerCase() === "store" ? "POST" : "PATCH";  // 'POST'=store or 'PATCH'=employee
    const shiftId = $('#displayShiftId').val();
    const selectedEmployee = $("#editModalSelectedEmployeeID").val();

    if (method === "PATCH" && !isNonEmpty(selectedEmployee)) {
      showNotification("Please select an employee.", "danger");
      return;
    }
    
    showSpinner();
    $.ajax({
      url: `${window.djangoURLs.requestCover}${shiftId}/`,
      method: method,
      headers: { 'X-CSRFToken': getCSRFToken() },
      xhrFields: { withCredentials: true },
      contentType: 'application/json',
      data: JSON.stringify({ selected_employee_id: $("#editModalSelectedEmployeeID").val() }),
      success: function(resp) {
        hideSpinner();
        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
        showNotification("Successfully requested cover for the shift.", "success");
      },
      error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to request cover"); }
    });
  });
}


function updateStoreInformation() {
    const $employeeSelect = $("#editModalEmployeeList");
    $employeeSelect.empty();

    // Fetch employees names
    $.ajax({
        url: `${window.djangoURLs.listStoreEmployeeNames}?store_id=${getSelectedStoreID()}&only_active=true`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},

        success: function(response) {
            const employeeList = response.names;

            if (Array.isArray(employeeList) && employeeList.length > 0) {
                employeeList.forEach(employee => {
                    $employeeSelect.append(
                        `<li class="list-group-item cursor-pointer" data-id="${employee.id}">${employee.name}</li>`
                    );
                });
            } else {
                $employeeSelect.append('<option value="">No Employees available</option>');
                showNotification("There are no employees associated to the selected store.", "danger");
            }
        },

        error: function(jqXHR, textStatus, errorThrown) {
            handleAjaxError(jqXHR, "Failed to load employee names", false);
            $employeeSelect.append('<option value="">Error getting employees</option>');
        }
    });
}


// --- Everyone toggle helpers (ADD THIS) --------------------------------------
// Read server-rendered {store_id: boolean} from <script id="store-perms">
const STORE_PERMS = (() => {
  try { return JSON.parse(document.getElementById('store-perms')?.textContent || '{}'); }
  catch { return {}; }
})();

// Enable/disable the "Everyone" switch for the currently selected store
function initEveryoneSwitchForSelectedStore() {
  const id = getSelectedStoreID();
  const key = id != null ? String(id) : null; // keys from json_script are strings
  const allowed = key && Object.prototype.hasOwnProperty.call(STORE_PERMS, key) ? !!STORE_PERMS[key] : false;

  const $sw = $('#viewEveryoneSwitch');
  $sw.prop('checked', false);        // reset when store changes
  $sw.prop('disabled', !allowed);    // enable only if allowed
}
// -----------------------------------------------------------------------------

//////////////////////////// HELPER FUNCTIONS ///////////////////////////////////////


// Format time function
function formatTime(text) {
  if (!text) { return ""; }

  const date = new Date(text);
  const options = { hour: 'numeric', minute: 'numeric', hour12: true };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}

function formatWeekTitle(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
}

function calculateDuration(startTime, endTime) {
    // Create date objects to calculate the difference. Date itself doesn't matter.
    const start = new Date(`01/01/2000 ${startTime}`);
    let end = new Date(`01/01/2000 ${endTime}`);

    // Handle overnight shifts
    if (end < start) {
        end.setDate(end.getDate() + 1);
    }
    
    let diffMs = end - start;
    const hours = Math.floor(diffMs / 3600000);
    const minutes = Math.floor((diffMs % 3600000) / 60000);

    return `${hours}h ${minutes}m`;
}