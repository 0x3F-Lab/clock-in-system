$(document).ready(function() {
    // --- Initialize all event handlers ---
    handleViewTypeSwitching();
    setupActionButtons();

    // Activate the pagination system (set the update function)
    handlePagination({updateFunc: updateRequestsList});

    // --- INITIAL LOAD ---
    updateRequestsList();
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
                container.html('<div class="panel rounded shadow p-4 text-center"><p class="m-0">No requests found.</p></div>');
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
            actionsHtml = `<button class="btn btn-sm btn-outline-danger cancel-request-btn action-btn" data-req-id="${req.id}">Cancel</button>`;
        } else { // It's an incoming request for me to accept
            actionsHtml = `<button class="btn btn-sm btn-success accept-request-btn action-btn" data-req-id="${req.id}">Accept</button>`;
            if (req.target_user_id || req.is_store_manager) {
                actionsHtml += `<button class="btn btn-sm btn-warning reject-request-btn action-btn ms-2" data-req-id="${req.id}">Reject</button>`;
            }
        }
    } else if (req.status === 'accepted') {
        if (req.is_store_manager) {
            actionsHtml = `
                <button class="btn btn-sm btn-success approve-request-btn action-btn" data-req-id="${req.id}">Approve</button>
                <button class="btn btn-sm btn-warning reject-request-btn action-btn ms-2" data-req-id="${req.id}">Reject</button>`;
        } else {
             actionsHtml = `<span>Awaiting Manager Approval</span>`;
        }
    }
    
    const cardHeader = req.type === 'cover_request' ? `Cover Request for ${req.store_name}` : `Swap Request`;
    const targetInfo = req.target_name ? `<p class="card-text mb-1"><small>To: <strong>${req.target_name}</strong></small></p>` : '';
    const statusBadge = `<span class="badge bg-info text-dark">${req.status.replace('_', ' ').toUpperCase()}</span>`;

    return `
        <div class="panel rounded shadow p-4 mb-4">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h5 class="card-title">${cardHeader}</h5>
                    <p class="card-text mb-1"><small>From: <strong>${req.requester_name}</strong></small></p>
                    ${targetInfo}
                </div>
                ${statusBadge}
            </div>
            <hr>
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>Shift Details:</strong><br>
                    <span>📅 ${req.shift_date}</span><br>
                    <span>🕒 ${req.shift_start_time} - ${req.shift_end_time}</span>
                    ${req.shift_role_name ? `<span><br>👤 ${req.shift_role_name}</span>` : ''}
                </div>
                <div class="actions">${actionsHtml}</div>
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
    $(document).on('click', '.action-btn', function() {
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
                showNotification("Request updated successfully.", "success");
                $('.list-group-item.active').trigger('click');
            },
            error: function(jqXHR) {
                handleAjaxError(jqXHR, "Failed to update request");
            }
        });
    });
}


