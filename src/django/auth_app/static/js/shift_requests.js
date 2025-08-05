$(document).ready(function() {
    // --- Initialize all event handlers ---
    setupSidebarNavigation();
    setupActionButtons();

    // --- INITIAL LOAD ---
    // Trigger a click on the default tab to load the initial view
    $('#notification-page-btn').trigger('click'); 
});

//  map sidebar buttons to their content and API view type.
const viewConfig = {
    'notification-page-btn': { contentId: 'my-requests', viewType: 'my_requests' },
    'read-notification-page-btn': { contentId: 'incoming-requests', viewType: 'incoming' },
    'sent-notification-page-btn': { contentId: 'manager-approval', viewType: 'approval' },
    'send-msg-page-btn': { contentId: 'shift-pool', viewType: 'pool' },
    'settings-page-btn': { contentId: 'request-history', viewType: 'history' }
};

let currentViewType = 'my_requests'; // Store the API view type

/**
 * The master function to fetch and display a list of shift requests.
 * @param {string} viewType - The type of view to render (e.g., 'my_requests').
 * @param {string} contentId - The ID of the div to render the content into.
 */
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
                    container.append(renderRequestCard(req, viewType));
                });
            } else {
                container.html('<div class="panel rounded shadow p-4 text-center"><p class="m-0">No requests found.</p></div>');
            }
        },
        error: function(jqXHR) {
            handleAjaxError(jqXHR, "Failed to load shift requests");
        },
        complete: function() {
            hideSpinner();
        }
    });
}

/**
 * Builds the HTML for a single shift request card, showing the correct actions.
 * @param {object} req - The shift request data object from the API.
 * @param {string} viewType - The current view type to determine which actions to show.
 * @returns {string} The HTML string for the card.
 */
function renderRequestCard(req, viewType) {
    let actionsHtml = '';

    if (req.status === 'pending') {
        if (viewType === 'my_requests' || (req.is_manager && viewType !== 'pool')) {
            actionsHtml = `<button class="btn btn-sm btn-outline-danger cancel-request-btn action-btn" data-req-id="${req.id}">Cancel</button>`;
        } else if (viewType === 'incoming' || viewType === 'pool') {
            actionsHtml = `<button class="btn btn-sm btn-success accept-request-btn action-btn" data-req-id="${req.id}">Accept</button>`;
        }
    } else if (req.status === 'accepted' && req.is_manager) {
        actionsHtml = `
            <button class="btn btn-sm btn-success approve-request-btn action-btn" data-req-id="${req.id}">Approve</button>
            <button class="btn btn-sm btn-warning reject-request-btn action-btn ms-2" data-req-id="${req.id}">Reject</button>`;
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
        
        currentViewType = config.viewType;
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



