// Function to show notifications
function showNotification(message, type = "info") {
  const iconMap = {
    success: "fa-circle-check",
    danger: "fa-circle-exclamation",
    warning: "fa-triangle-exclamation",
    info: "fa-circle-info",
  };

  // Set type to the default if given improper type
  if (!["success", "danger", "warning", "info"].includes(type.toLocaleLowerCase())) {
    type = "info";
  }

  // Make the notification
  const notification = $(`
    <div class="toast align-items-center bg-${type.toLowerCase()}-subtle border-0 rounded-3 show my-2 p-1 text-dark" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-body">
        <div class="d-flex flex-row align-items-center gap-4">
          <span><i class="fa-solid ${iconMap[type.toLowerCase()]} fa-lg"></i></span>
          <div class="d-flex flex-grow-1 align-items-center justify-content-between w-100">
            <span class="fw-semibold">${message}</span>
            <button type="button" class="btn-close btn-close ms-2" data-bs-dismiss="toast" aria-label="Close"></button>
          </div>
        </div>
      </div>
    </div>
  `);

  // Append the notification to the container
  $('#notification-container').append(notification);

  // Remove the notification after 6 seconds
  setTimeout(() => {
    notification.fadeOut(400, () => notification.remove());
  }, 6000);

  // Console logging (only log warning/danger)
  switch (type.toLowerCase()) {
    case "warning":
      console.warn(message);
      break;
    case "danger":
      console.error(message);
      break;
    default:
      break;
  }
}


// Function to handle an API error message -> Returns errorMessage shown
function handleAjaxError(jqXHR, baseMessage = "Failed to complete task", shouldHideSpinner = true) {
  if (shouldHideSpinner) { hideSpinner(); }
  let errorMessage;
  if (jqXHR.status === 500) {
    errorMessage = `${baseMessage} due to internal server errors. Please contact an admin.`;
  } else {
    errorMessage = jqXHR.responseJSON?.Error || `${baseMessage}. Please try again later.`;
  }
  showNotification(errorMessage, "danger");
  return errorMessage
}


// Function to save a single notification which appears on the next page load (or reload) -- ACTIONS NOTIFICATION IF IT CANT SAVE IT
function saveNotificationForReload(message, type = "info", errorNotification = message) {
  try {
    localStorage.setItem("pendingNotification", JSON.stringify({ message, type }));
    return true;

  } catch (e) {
    // Show the notification immediately if it fails to save to ensure the user sees it at one point.
    // Saving can fail when user is in incognito, has turned on higher security, etc.
    console.warn("Failed to save notification in localStorage:", e);
    showNotification(errorNotification, type);
    return false;
  }
}


// Function to retrieve saved notifications and action them
function actionSavedNotifications() {
  try {
    const notifData = localStorage.getItem("pendingNotification");

    if (notifData) {
      const { message, type } = JSON.parse(notifData);
      showNotification(message, type);
      localStorage.removeItem("pendingNotification");
    }
  } catch (e) {
    // Fail silently
  }
}

// Function to setup ability for page to RELOAD after set period of inactivity
function setupVisibilityReload(maxIdleMinutes) {
  let lastHiddenTime = null;

  $(document).on("visibilitychange", function () {
    if (document.hidden) {
      // Store the time when the tab was hidden
      lastHiddenTime = Date.now();

    } else {
      // Tab has become visible again
      if (lastHiddenTime) {
        const now = Date.now();
        const minutesAway = (now - lastHiddenTime) / 1000 / 60;

        if (minutesAway > maxIdleMinutes) {
          location.href = location.href;
        }
      }
      lastHiddenTime = null; // Reset after checking
    }
  });
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


// Get CSRF Token (allow for the method to change when using secure cookies...)
function getCSRFToken() {
  const token = $('meta[name="csrf-token"]').attr('content')
  if (!token) {
    console.error("CSRF token was not loaded on this page correctly. Please contact an admin for further assistance.")
  }

  // Return regardless
  return token
}


function ensureSafeInt(val, min, max) {
  // Parse the int to ensure its an int
  val = parseInt(val, 10);

  // Ensure the int is within range
  if (min != null) {
    min = parseInt(min, 10);
    val = Math.max(val, min)
  }
  
  if (max != null) {
    max = parseInt(max, 10);
    val = Math.min(val, max)
  }

  return val
}


function ensureSafeFloat(val, min, max) {
  // Parse the number to ensure its an int
  val = parseFloat(val);

  // Ensure the number is within range
  if (min != null) {
    min = parseFloat(min);
    val = Math.max(val, min)
  }
  
  if (max != null) {
    max = parseFloat(max);
    val = Math.min(val, max)
  }

  return val
}


function isNonEmpty(val) {
  return val !== null && val !== undefined && val !== "";
}


function formatToDatetimeLocal(dateStr) {
  if (!dateStr) return "";
  // Expecting "DD/MM/YYYY HH:MM"
  const [datePart, timePart] = dateStr.split(" ");
  const [day, month, year] = datePart.split("/");
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${timePart}`;
}

// Format to YYYY-MM-DD for input[type="date"]
function formatDateForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };


function getFullDayName(dateString) {
  if (!dateString) return "";
  return new Date(dateString).toLocaleDateString('en-US', {weekday: 'long', timeZone: 'UTC'});
}

function getShortDate(dateString) {
  if (!dateString) return "";
  return new Date(dateString).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
}

function getMonday(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1 - day); // If Sunday, go back 6 days; else subtract (day - 1)
  d.setDate(d.getDate() + diff);
  return d;
}


////////////// SPINNER /////////////////////

// Ensure global variable to ensure spinner timeout can be adjusted
let spinnerTimeout;
let isSpinnerActive = false;

// Hide / show progress spinner
function showSpinner(delay = 150) {
  if (isSpinnerActive) return; // Do nothing if already active
  clearTimeout(spinnerTimeout); // Prevent any previous timers

  spinnerTimeout = setTimeout(() => {
    $('#spinnerContainer').removeClass('d-none').stop(true, true).fadeIn(300);
    isSpinnerActive = true;
  }, delay);
}

function hideSpinner() {
  clearTimeout(spinnerTimeout); // Cancel pending show

  $('#spinnerContainer').stop(true, true).fadeOut(300, function () {
    $(this).addClass('d-none');
    isSpinnerActive = false;
  });
}


//////// HANDLE PASSWORD FIELD SHOWING ////////

$(document).on('click', '.toggle-password', function () {
  const $btn = $(this);
  const $input = $btn.closest(".position-relative").find("input");
  const isPassword = $input.attr("type") === "password";
  const $icon = $btn.find("i");

  $input.attr("type", isPassword ? "text" : "password");
  $icon.toggleClass("fa-eye fa-eye-slash");
});


////// PAGINATION CONTROLLER FUNCTIONS //////


function handlePagination(config) {
  const { updateFunc } = config;

  $('#prevPageBtn').on('click', function () {
    const newOffset = $(this).attr('data-offset');
    $('#paginationVariables').attr('data-future-offset', newOffset);
    updateFunc();
  });

  $('#nextPageBtn').on('click', function () {
    const newOffset = $(this).attr('data-offset');
    $('#paginationVariables').attr('data-future-offset', newOffset);
    updateFunc();
  });

  // For clicking any specific page number (done so that it dynamically adjusts when they're added/removed)
  $(document).on('click', 'li.page-item button', function () {
    const newOffset = $(this).attr('data-offset');
    $('#paginationVariables').attr('data-future-offset', newOffset);
    updateFunc();
  });

  $('#pageLimitInput').on('change', () => {
    resetPaginationValues();
    updateFunc(); // Refresh the table with new limit
  });
}


function resetPaginationValues() {
  // DOESNT CALL THE UPDATE FUNCTION -- MUST BE DONE MANUALLY!
  $('#paginationVariables').attr('data-future-offset', 0); // Reset offset to start
}


function updatePaginationPageButtons() {
  const totCount = ensureSafeInt($('#paginationVariables').attr('data-count'), 0, null);
  const offset = ensureSafeInt($('#paginationVariables').attr('data-offset'), 0, Math.max(totCount - 1, 0)); // Limit offset to max total-1 (or 0 if total=0)
  const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
  const totalPages = Math.max(Math.ceil(totCount / pageLimit), 1); // Ensure there is at least 1 page (even if totCount=0)
  const currentPage = Math.floor(offset / pageLimit) + 1;

  // Get the list of page numbers that need to be made into buttons using the window size for dynamic sizing
  const maxPageBtns = window.innerWidth < 576 ? 5 :
                    window.innerWidth < 768 ? 7 :
                    window.innerWidth < 992 ? 9 : 11;
  const pages = getPaginationPages(currentPage, totalPages, maxPageBtns);

  const paginationList = $('#paginationList');
  paginationList.find('li.page-number').remove(); // Remove previous page buttons

  const nextBtn = $('#nextPageBtn').closest('li');
  const prevBtn = $('#prevPageBtn').closest('li');

  // Insert page buttons between prev and next
  pages.forEach(page => {
    const pageItem = $('<li>').addClass('page-item page-number');

    // If the page indicator is meerely a break (i.e ...)
    if (page === '...') {
      pageItem.addClass('disabled').append(`<span class="page-link">…</span>`);

    } else {
      pageItem.append(
        $('<button>')
          .addClass('page-link')
          .attr('data-offset', `${(page - 1) * pageLimit}`)
          .text(page)
      );

      // If its the current page, ensure its marked as active
      if (page === currentPage) {
        pageItem.addClass('active');
      }
    }

    // Add the single page button
    pageItem.insertBefore(nextBtn);
  });

  // Update prev/next button states
  if (currentPage === 1) {
    prevBtn.find('button').addClass('disabled');
  } else {
    const newOffset = ensureSafeInt(((currentPage - 1) * pageLimit) - pageLimit, 0, totCount-1); // Ensure offset is within possible limits and take off page limit as offset indexes at 0 comparatively to pages which start at 1
    prevBtn.find('button').removeClass('disabled').attr('data-offset', `${newOffset}`);
  }

  if (currentPage === totalPages) {
    nextBtn.find('button').addClass('disabled');
  } else {
    const newOffset = ensureSafeInt(((currentPage + 1) * pageLimit) - pageLimit, 0, totCount-1); // Ensure offset is within possible limits
    nextBtn.find('button').removeClass('disabled').attr('data-offset', `${newOffset}`);
  }
}


function getPaginationPages(currentPage, totalPages, size = 7) {
  const pages = [];

  // Ensure minimum of 5 for proper ellipsis logic
  size = Math.max(size, 5); 

  // Simple case of having less pages than room given for page buttons
  if (totalPages <= size) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const half = Math.floor(size / 2);

  // Near start
  if (currentPage <= half + 1) {
    const end = size - 2;
    for (let i = 1; i <= end; i++) pages.push(i);
    pages.push('...', totalPages);
    return pages;
  }

  // Near end
  if (currentPage >= totalPages - half) {
    pages.push(1, '...');
    for (let i = totalPages - (size - 3); i <= totalPages; i++) {
      pages.push(i);
    }
    return pages;
  }

  // Middle range
  pages.push(1, '...');
  const sideCount = Math.floor((size - 4) / 2);
  for (let i = currentPage - sideCount; i <= currentPage + sideCount; i++) {
    pages.push(i);
  }
  pages.push('...', totalPages);
  return pages;
}



function getPaginationOffset() {
  // Ensure number is an int and within range
  const totCount = ensureSafeInt($('#paginationVariables').attr('data-count'), 0, null);
  const currOffset = ensureSafeInt($('#paginationVariables').attr('data-future-offset'), 0, totCount-1);
  return currOffset
}


function getPaginationLimit() {
  // Ensure number is an int and within range
  const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
  return pageLimit
}


function setPaginationValues(offset, totalCount) {
  totalCount = ensureSafeInt(totalCount, 0, null);
  
  if (totalCount != null) {
    offset = ensureSafeInt(offset, 0, totalCount-1);
    $('#paginationVariables').attr('data-count', totalCount);

  } else {
    offset = ensureSafeInt(offset, 0, null);
  }

  if (offset != null) { // If offset was given in request response
    $('#paginationVariables').attr('data-offset', offset);
  }

  // Update the button controls
  updatePaginationPageButtons();
}


///////////////////// STORE SELECTION PANEL COMPONENT FUNCTIONS /////////////////////////

function getSelectedStoreID() {
  const storeID = $('#storeSelectDropdown').val();

  // Return null if storeID is empty, null, or undefined
  if (!storeID || storeID.trim() === "") {
    return null;
  }

  // Return as an int for easy use
  return parseInt(storeID.trim(), 10);
}


/////////////////// LOCATION FUNCTION FOR CLOCKING IN/OUT /////////////////////////////

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
          maximumAge: 30000          // Allow cached location up to 30s old
        }
      );
    });
  } else {
    showNotification("Geolocation is not supported by your browser. Cannot clock in/out.");
    return null;
  }
}
