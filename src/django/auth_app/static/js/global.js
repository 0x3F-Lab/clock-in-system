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
        <div class="d-flex gap-4">
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
  if (min) {
    min = parseInt(min, 10);
    val = Math.max(val, min)
  }
  
  if (max) {
    max = parseInt(max, 10);
    val = Math.min(val, max)
  }

  return val
}


function formatToDatetimeLocal(dateStr) {
  if (!dateStr) return "";
  // Expecting "DD/MM/YYYY HH:MM"
  const [datePart, timePart] = dateStr.split(" ");
  const [day, month, year] = datePart.split("/");
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${timePart}`;
}


// Hide / show progress spinner
function showSpinner(delay = 150) {
  // Start a timer but don’t show the spinner yet
  spinnerTimeout = setTimeout(() => {
    // Remove the d-none class to ensure it's not hidden
    $('#spinnerContainer').removeClass('d-none');
    $('#spinnerContainer').fadeIn(300);  // Fade in over 300ms
  }, delay);
}

function hideSpinner() {
  clearTimeout(spinnerTimeout); // Prevent spinner from showing if it's still waiting
  $('#spinnerContainer').fadeOut(300, function() {
    // After fading out, hide the spinner completely
    $(this).addClass('d-none');
  });
}


////// PAGINATION CONTROLLER FUNCTIONS //////


function handlePagination(config) {
  const { updateFunc } = config;

  $('#firstPageBtn').on('click', () => {
    $('#paginationOffset').attr('data-future-offset', 0);
    updateFunc();
  });

  $('#prevPageBtn').on('click', () => {
    const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
    const currOffset = ensureSafeInt($('#paginationOffset').attr('data-offset'), 0, totCount-1);
    const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
    $('#paginationOffset').attr('data-future-offset', (currOffset - pageLimit));
    updateFunc();
  });

  $('#nextPageBtn').on('click', () => {
    const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
    const currOffset = ensureSafeInt($('#paginationOffset').attr('data-offset'), 0, totCount-1);
    const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
    const newOffset = Math.min(currOffset + pageLimit, totCount - 1);
    $('#paginationOffset').attr('data-future-offset', newOffset);
    updateFunc();
  });

  $('#lastPageBtn').on('click', () => {
    const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
    const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
    const lastOffset = Math.floor((totCount - 1) / pageLimit) * pageLimit;
    $('#paginationOffset').attr('data-future-offset', lastOffset);
    updateFunc();
  });

  $('#pageInput').on('change', function () {
    const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
    const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
    const totalPages = Math.ceil(totCount / pageLimit);

    // Update input in case it's out of bounds
    const requestedPage = ensureSafeInt($(this).val(), 1, totalPages);
    $(this).val(requestedPage);
  
    const newOffset = (requestedPage - 1) * pageLimit;
    $('#paginationOffset').attr('data-future-offset', newOffset);
    updateFunc();
  });

  $('#pageLimitInput').on('change', () => {
      $('#paginationOffset').attr('data-future-offset', 0); // Reset offset to start
      updateFunc(); // Refresh the table with new limit
  });
}


function getPaginationOffset() {
  // Ensure number is an int and within range
  const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
  const currOffset = ensureSafeInt($('#paginationOffset').attr('data-future-offset'), 0, totCount-1);
  return currOffset
}


function getPaginationLimit() {
  // Ensure number is an int and within range
  const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
  return pageLimit
}


function setPaginationValues(offset, totalCount) {
  totalCount = ensureSafeInt(totalCount, 0, null);
  
  if (totalCount) {
    offset = ensureSafeInt(offset, 0, totalCount-1);
    $('#paginationTotalItemsCount').attr('data-count', totalCount);

  } else {
    offset = ensureSafeInt(offset, 0, null);
  }

  if (offset || offset == 0) { // If offset was given in request response
    $('#paginationOffset').attr('data-offset', offset);
  }

  // Set max page count (USE PAGE VALUES IN CASE ONE OF THE TWO VALUES WERENT PROVIDED)
  const pageTotCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
  const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);
  $('#pageCount').text(Math.ceil(pageTotCount / pageLimit));

  // Update current page count
  const currOffset = ensureSafeInt($('#paginationOffset').attr('data-offset'), 0, pageTotCount-1);
  const pageNum = Math.ceil(currOffset/pageLimit) + 1; // Counting is offset by 1 compared to indexation (starts at 0)
  $('#pageInput').val(pageNum);

  // Update the button controls
  updatePaginationButtonControls();
}


function updatePaginationButtonControls() {
  const totCount = ensureSafeInt($('#paginationTotalItemsCount').attr('data-count'), 0, null);
  const offset = ensureSafeInt($('#paginationOffset').attr('data-offset'), 0, totCount-1);
  const pageLimit = ensureSafeInt($('#pageLimitInput').val(), 1, null);

  // Check if first/back buttons can be enabled/disabled
  if (offset > 0) {
    $('#firstPageBtn').prop('disabled', false);
    $('#prevPageBtn').prop('disabled', false);

  } else {
    $('#firstPageBtn').prop('disabled', true);
    $('#prevPageBtn').prop('disabled', true);
  }

  // Check if next/last buttons can be enabled/disabled
  if (offset + pageLimit < totCount) {
    $('#nextPageBtn').prop('disabled', false);
    $('#lastPageBtn').prop('disabled', false);

  } else {
    $('#nextPageBtn').prop('disabled', true);
    $('#lastPageBtn').prop('disabled', true);
  }

  // Check if the manual page navigator (input) can be enabled/disabled
  if (totCount > pageLimit) {
    $('#pageInput').prop('disabled', false);

  } else {
    $('#pageInput').prop('disabled', true);
  }
}