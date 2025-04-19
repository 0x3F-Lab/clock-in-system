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

// Ensure global variable to ensure spinner timeout can be adjusted
let spinnerTimeout;

// Hide / show progress spinner
function showSpinner(delay = 150) {
  clearTimeout(spinnerTimeout); // Prevent any previous timers

  spinnerTimeout = setTimeout(() => {
    const $spinner = $('#spinnerContainer');
    $spinner.removeClass('d-none').stop(true, true).fadeIn(300);
  }, delay);
}

function hideSpinner() {
  clearTimeout(spinnerTimeout); // Cancel pending show
  const $spinner = $('#spinnerContainer');

  $spinner.stop(true, true).fadeOut(300, function () {
    $(this).addClass('d-none');
  });
}


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
    $('#paginationVariables').attr('data-future-offset', 0); // Reset offset to start
    updateFunc(); // Refresh the table with new limit
  });
}


function updatePaginationPageButtons() {
  const totCount = ensureSafeInt($('#paginationVariables').attr('data-count'), 0, null);
  const offset = ensureSafeInt($('#paginationVariables').attr('data-offset'), 0, totCount - 1);
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
  
  if (totalCount) {
    offset = ensureSafeInt(offset, 0, totalCount-1);
    $('#paginationVariables').attr('data-count', totalCount);

  } else {
    offset = ensureSafeInt(offset, 0, null);
  }

  if (offset || offset == 0) { // If offset was given in request response
    $('#paginationVariables').attr('data-offset', offset);
  }

  // Update the button controls
  updatePaginationPageButtons();
}