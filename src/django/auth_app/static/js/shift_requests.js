$(document).ready(function() {
    // --- Initialize all event handlers ---
    handleViewTypeSwitching();
    setupActionButtons();

    // Activate the pagination system (set the update function)
    handlePagination({updateFunc: updateRequestsList});

    // --- INITIAL LOAD ---
    updateRequestsList();

    // Add page reloader to force reload after period of inactivity
    setupVisibilityReload(45); // 45 minutes
});


function updateRequestsList() {
    showSpinner();

    const container = $(`#requests-list`);
    const listUrl = `${window.djangoURLs.listShiftRequests}?type=${container.attr('data-type')}&offset=${getPaginationOffset()}&limit=${getPaginationLimit()}`;

    $.ajax({
        url: listUrl,
        method: 'GET',
        xhrFields: { withCredentials: true },
        headers: { 'X-CSRFToken': getCSRFToken() },
        success: function(data) {
            container.empty();
            $('#requests-list-count').text(data.total);

            if (data.requests && data.requests.length > 0) {
                data.requests.forEach(req => {
                    // Pass the whole data object to the renderer
                    container.append(renderRequestCard(req));
                });
            } else {
                const msg = container.attr('data-type') === "history" ? "You have no past shift requests. Any new handled requests will appear here." : "You're all caught up. There are no shift requests for this cetegory.";
                container.html(`
                  <div class="list-group-item list-group-item-action flex-column align-items-start p-3 bg-light text-muted">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                      <h5 class="mb-1">
                        <i class="fas fa-bell-slash me-2"></i>No Shift Requests
                      </h5>
                    </div>
                    <small class="mt-2">${msg}</small>
                  </div>
                  `);
            }

            // Set pagination values
            setPaginationValues(data.offset, data.total);
            hideSpinner();
        },
        error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to load shift requests"); },
    });
}


function renderRequestCard(req) {
    let actionsHtml = '';

    // Determine which action buttons to show
    if (req.status === 'pending') {
        if (req.is_request_owner) {
            actionsHtml = `<button class="btn btn-sm btn-outline-danger cancel-request-btn action-btn d-none" data-req-id="${req.id}">Cancel</button>`;
        } else { // It's an incoming request for me to accept
            actionsHtml = `<button class="btn btn-sm btn-outline-success accept-request-btn action-btn d-none" data-req-id="${req.id}">Accept</button>`;
            if (req.type === "swap_request") { actionsHtml += `<button class="btn btn-sm btn-outline-danger reject-request-btn action-btn d-none" data-req-id="${req.id}">Reject</button>`; }
            if (req.is_store_manager) { actionsHtml += `<button class="btn btn-sm btn-outline-danger cancel-request-btn action-btn d-none" data-req-id="${req.id}">Cancel</button>`; }
        }
    } else if (req.status === 'accepted') {
        if (req.is_store_manager) {
            actionsHtml = `
                <button class="btn btn-sm btn-outline-success approve-request-btn action-btn d-none" data-req-id="${req.id}">Approve</button>
                <button class="btn btn-sm btn-outline-danger reject-request-btn action-btn d-none" data-req-id="${req.id}">Reject</button>`;
        } else {
             actionsHtml = `<div class="btn btn-sm btn-outline-danger disabled">Awaiting Manager Approval</div>`;
        }
    }
    
    const cardTitle = req.type === 'cover_request' ? `Store-Wide Cover Request` : (req.type === 'swap_request' ? `Swap Request` : `Store-Wide Shift Bid`);
    const target = req.target_name ? req.target_name : `Employees of ${req.store_code}`;
    const status = req.status.replace('_', ' ').toUpperCase();
    const badgeColour = status === "PENDING"
        ? "bg-info"
        : status === "ACCEPTED"
            ? "bg-warning"
            : status === "APPROVED"
                ? "bg-success"
                : "bg-danger" // Rejected/Cancelled

    return `
      <div class="bg-light list-group-item list-group-item-action flex-column align-items-start p-3 collapsed cursor-pointer"
          id="req-${req.id}"
          data-bs-toggle="collapse"
          data-bs-target="#req-info-${req.id}"
          aria-expanded="false"
          aria-controls="req-info-${req.id}">
        <div class="d-flex justify-content-between align-items-start">
          <div class="d-flex w-100 justify-content-between align-items-start">
            <div>
              <h5 class="card-title">
                <span class="${badgeColour} badge me-2">${status}</span>
                <b>[<code>${req.store_code}</code>] ${cardTitle}</b>
              </h5>
              <p class="text-muted my-1"><small><strong>From:</strong> ${req.requester_name} → <strong>To:</strong> ${target}</small></p>
            </div>
            <div class="text-end d-flex flex-column align-items-end">
              <small class="text-muted mb-1">Created: ${formatDateTimeFull(req.created_at)}</small>
              <div class="d-flex gap-2 mt-1">
                ${actionsHtml}
              </div>
            </div>
          </div>
        </div>
        
        <div class="collapse mt-3" id="req-info-${req.id}">
          <div class="card card-body bg-light text-dark">
            <strong>Shift Details:</strong>
            <span>🏬 ${req.store_code}<span>
            <span>📅 ${formatDateTimeFull(req.shift_date, false)}</span>
            <span>🕒 ${req.shift_start_time} - ${req.shift_end_time} [${req.shift_length_hr} Hours]</span>
            <span>👤 ${req.shift_role_name ? req.shift_role_name : "None"}</span>
            <div class="mt-2">
              <strong>Shift Comment:</strong>
              <div>${req.shift_comment ? req.shift_comment : "No Comment"}</div>
            </div>
            <hr>
            Request was last updated at: ${formatDateTimeFull(req.updated_at)}
          </div>
        </div>
      </div>`;
}

// --- EVENT HANDLER SETUP FUNCTIONS ---


function handleViewTypeSwitching() {
    $(document).on('click', '.view-type-switch', function () {
        // Ignore clicking on already active button
        if ($(this).hasClass('active')) { return; }

        $(".view-type-switch").removeClass("active");
        $(this).addClass("active");

        type = $(this).attr('data-type');
        $('#requests-list').attr('data-type', type);

        switch (type) {
          case 'active':
            $('#requests-list-type').text('Active');
            break;
          case 'pending':
            $('#requests-list-type').text('Pending');
            break;
          case 'approval':
            $('#requests-list-type').text('Awaiting Approval');
            break;
          case 'history':
            $('#requests-list-type').text('Past');
            break;
        }

        resetPaginationValues();
        updateRequestsList();
    })
}


function setupActionButtons() {
  // Listen for any collapse being shown (request info portion)
  $("#requests-list").on('show.bs.collapse', '.collapse', function () {
    const excepID = $(this).attr('id').split('-').pop();
    $(`[data-req-id="${excepID}"]`).removeClass('d-none');
  });

  // Hide the button when the collapse is closed
  $("#requests-list").on('hide.bs.collapse', '.collapse', function () {
    const excepID = $(this).attr('id').split('-').pop();
    $(`[data-req-id="${excepID}"]`).addClass('d-none');
  });

  $("#requests-list").on('click', '.action-btn', function() {
    const $this = $(this);
    const reqId = $this.data('req-id');
    let method;

    if ($this.hasClass('accept-request-btn')) { method = 'POST'; }
    else if ($this.hasClass('approve-request-btn')) { method = 'PUT'; }
    else if ($this.hasClass('reject-request-btn')) { method = 'PATCH'; }
    else if ($this.hasClass('cancel-request-btn')) { method = 'DELETE'; }
    else { return; }

    showSpinner();
    $.ajax({
        url: `${window.djangoURLs.manageShiftRequest}${reqId}/`,
        method: method,
        xhrFields: { withCredentials: true },
        headers: { 'X-CSRFToken': getCSRFToken() },
        success: function() {
            hideSpinner();
            $(`#req-${reqId}`).addClass('d-none');
            $('#requests-list-count').text(ensureSafeInt($('#requests-list-count').text()) - 1);
            showNotification("Request updated successfully.", "success");
        },
        error: function(jqXHR) {
            handleAjaxError(jqXHR, "Failed to update request");
        }
    });
  });
}


