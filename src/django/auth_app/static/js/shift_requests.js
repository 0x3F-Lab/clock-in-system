$(document).ready(function() {
    // --- Initialize all event handlers ---
    setupSidebarNavigation();
    setupActionButtons();

    // --- INITIAL LOAD ---
    $('#pending-requests-btn').trigger('click'); 
});

const viewConfig = {
    'pending-requests-btn': { contentId: 'pending-requests', viewType: 'pending' },
    'active-requests-btn': { contentId: 'active-requests', viewType: 'active' },
    'manager-approval-btn': { contentId: 'manager-approval', viewType: 'approval' },
    'history-btn': { contentId: 'history', viewType: 'history' }
};

function fetchAndRenderRequests(viewType, contentId) {
    showSpinner();
    const listUrl = `${window.djangoURLs.listShiftRequests}?view=${viewType}`;

    $.ajax({
        url: listUrl,
        method: 'GET',
        xhrFields: { withCredentials: true },
        headers: { 'X-CSRFToken': getCSRFToken() },
        success: function(data) {
            const container = $(`#${contentId}`);
            container.empty();

            if (data.requests && data.requests.length > 0) {
                data.requests.forEach(req => {
                    // Pass the whole data object to the renderer
                    container.append(renderRequestCard(req, req.current_user_id, req.is_manager));
                });
            } else {
                container.html('<div class="panel rounded shadow p-4 text-center"><p class="m-0">No requests found.</p></div>');
            }
        },
        error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to load shift requests"); },
        complete: function() { hideSpinner(); }
    });
}


function renderRequestCard(req, currentUserId, isManager) {
    let actionsHtml = '';
    const isMyRequest = currentUserId === req.requester_id;

    // Determine which action buttons to show
    if (req.status === 'pending') {
        if (isMyRequest) {
            actionsHtml = `<button class="btn btn-sm btn-outline-danger cancel-request-btn action-btn" data-req-id="${req.id}">Cancel</button>`;
        } else { // It's an incoming request for me to accept
            actionsHtml = `<button class="btn btn-sm btn-success accept-request-btn action-btn" data-req-id="${req.id}">Accept</button>`;
        }
    } else if (req.status === 'accepted') {
        if (isManager) {
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

function setupSidebarNavigation() {
    $('.list-group-item').on('click', function() {
        const $this = $(this);
        if ($this.hasClass('active')) return;

        const buttonId = $this.attr('id');
        const config = viewConfig[buttonId];
        if (!config) return;

        $('.list-group-item').removeClass('active');
        $this.addClass('active');

        $('.col-md-9').hide();
        $(`#${config.contentId}`).show();
        
        fetchAndRenderRequests(config.viewType, config.contentId);
    });
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
                hideSpinner();
            }
        });
    });
}


