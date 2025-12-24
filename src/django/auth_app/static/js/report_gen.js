$(document).ready(function () {
    // SHIFT LOG REPORT
    $("#openShiftLogModal").on("click", openShiftLogModal);
    $("#shiftLogReportForm").on("submit", generateShiftLogReport);

    // ACCOUNT SUMMARY REPORT
    $("#openAccountSummaryModal").on("click", openAccountSummaryModal);
    $("#accountSummaryForm").on("submit", generateAccountSummaryReport);

    // ROSTER REPORT
    $("#openWeeklyRosterModal").on("click", openWeeklyRosterModal);
    $("#weeklyRosterGenerateBtn").on("click", generateWeeklyRosterReport);

    // Add page reloader to force reload after period of inactivity
    setupVisibilityReload(30); // 30 minutes
});

// Will open the file AND download
function openPDFBlob(blob, filename) {
    const file = new Blob([blob], { type: "application/pdf" });
    const url = URL.createObjectURL(file);

    // Open for preview
    window.open(url, "_blank");

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;  
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// SHIFT LOG REPORT HANDLER
function openShiftLogModal() {
    const modal = new bootstrap.Modal(document.getElementById("shiftLogsModal"));
    modal.show();
}

function generateShiftLogReport(e) {
    e.preventDefault();

    const storeId = getSelectedStoreID();
    const start   = $("#startDate").val();
    const end     = $("#endDate").val();
    const filter  = $("#filterNames").val().trim();
    const onlyPublicHol  = $("#onlyPublicHol").is(":checked");
    const minHours = $("#minHours").val() || "";
    const minDeliveries = $("#minDeliveries").val() || "";


    const sortBy = $("#sortBy").val();
    const sortDesc = $("#sortDesc").is(":checked") ? "true" : "false";

    if (!storeId || !start || !end) {
        showNotification("Please select store, start and end date.", "danger");
        return;
    }

    showSpinner();

    $.ajax({
        url: window.djangoURLs.generateShiftReport,
        method: "GET",
        xhrFields: { responseType: "blob", withCredentials: true },
        headers: {
            'X-CSRFToken': getCSRFToken(), // Include CSRF token
        }, 
        data: {
            store_id: storeId,
            start: start,
            end: end,
            filter: filter,
            only_pub: onlyPublicHol,
            min_hours: minHours,
            min_deliveries: minDeliveries,
            sort_by: sortBy,
            sort_desc: sortDesc
        },
        success: function(blob) {
            hideSpinner();
            openPDFBlob(blob, "shift_logs_report.pdf");

        },
        error: function(xhr) {
            hideSpinner();
            showErrorMessage(xhr.status);
        }
    });
}



// ACCOUNT SUMMARY REPORT HANDLER

function openAccountSummaryModal() {
    const modal = new bootstrap.Modal(document.getElementById("accountSummaryModal"));
    modal.show();
}

function generateAccountSummaryReport(e) {
    e.preventDefault();

    const storeId     = getSelectedStoreID();
    const start       = $("#summaryStartDate").val();
    const end         = $("#summaryEndDate").val();

    const ignoreHours = $("#summaryIgnoreNoHours").is(":checked");
    const minHours    = $("#summaryMinHours").val() || "";
    const minDeliveries = $("#summaryMinDeliveries").val() || "";

    const sortBy      = $("#summarySortBy").val();
    const sortDesc    = $("#summarySortDesc").is(":checked");

    const filterNames = $("#summaryFilterNames").val().trim();

    if (!storeId || !start || !end) {
        showNotification("Please select store, start date and end date.", "danger");
        return;
    }

    showSpinner();

    $.ajax({
        url: window.djangoURLs.generateAccountSummaryPDF,
        method: "GET",
        xhrFields: { responseType: "blob", withCredentials: true },
        headers: { "X-CSRFToken": getCSRFToken() },

        data: {
            store_id: storeId,
            start: start,
            end: end,
            ignore_no_hours: ignoreHours,
            min_hours: minHours,
            min_deliveries: minDeliveries,
            sort_by: sortBy,
            sort_desc: sortDesc,
            filter: filterNames
        },

        success: function (blob) {
            hideSpinner();
            openPDFBlob(blob, "account_summary_report.pdf");
        },

        error: function (xhr) {
            hideSpinner();
            if (xhr.status === 422) {
                showNotification("There exists unapproved shift exceptions for the period. Please resolve them first.", "Danger")
            } else {
                showErrorMessage(xhr.status);
            }
            
        }
    });
}

// Error notifications
function showErrorMessage(status) {
    let message;
    switch (status) {
        case 400:
            message = "Invalid input. Please check the inputs.";
            break;
        case 403:
            message = "You are not authorised to generate this report.";
            break;
        case 413:
            message = "Date range exceeds 4 months. Please reduce the time frame."
            break;
        case 417:
            message = "Cannot exceed 10 reports generated per hour. Try again later."
            break;
        case 418:
            message = "End date cannot be before start date.";
            break;
        case 404:
            message = "Store not found";
            break;
        case 500:
            message = "Internal server error. Please try again later.";
            break;
        default:
            message = "Failed to generate report. Please try again. If issue persists, contact an admin";
            break;
    }
    showNotification(message, "danger");
}

// ROSTER REPORT HANDLER

function loadWeeklyRosterRoles() {
    let storeId = getSelectedStoreID();
    if (!storeId) return;

    $.ajax({
        url: `${window.djangoURLs.listStoreRoles}${storeId}/`,
        method: "GET",
        xhrFields: { withCredentials: true },
        headers: { "X-CSRFToken": getCSRFToken() },

        success: function(resp) {
            const $roleList = $("#weeklyRosterRoles");
            $roleList.empty();

            if (resp.data && resp.data.length > 0) {
                resp.data.forEach(role => {
                    $roleList.append(`
                        <label class="list-group-item d-flex align-items-center">
                            <input class="form-check-input me-2 roster-role-checkbox" 
                                type="checkbox" 
                                value="${role.id}"
                                data-role-name="${role.name}">
                            ${role.name}
                        </label>
                    `);
                });
            } else {
                $roleList.append(`<option disabled>No roles found</option>`);
            }
        },

        error: function(xhr) {
            hideSpinner();
            showErrorMessage(xhr.status);
        }
    });

}


function openWeeklyRosterModal() {
    loadWeeklyRosterRoles();
    const modal = new bootstrap.Modal(document.getElementById("weeklyRosterModal"));
    modal.show();
}


function generateWeeklyRosterReport() {
    let storeId = getSelectedStoreID();
    let week = $("#weeklyRosterWeek").val();
    let filterNames = $("#weeklyRosterFilterNames").val();
    let hideResigned = $("#weeklyRosterHideResigned").is(":checked");
    let selectedRoles = $(".roster-role-checkbox:checked").map(function () {return $(this).data("role-name");}).get();

    if (!storeId || !week) {
        showNotification("Please select store and week.", "danger");
        return;
    }

    showSpinner();

    $.ajax({
        url: window.djangoURLs.generateWeeklyRosterPDF,
        method: "GET",
        xhrFields: { responseType: "blob", withCredentials: true },
        headers: {
            'X-CSRFToken': getCSRFToken(), // Include CSRF token
        },
        data: {
            store_id: storeId,
            week: week,
            filter: filterNames,
            hide_resigned: hideResigned,
            roles: selectedRoles.join(",")
        },
        success: function(blob) {
            hideSpinner();
            openPDFBlob(blob, "weekly_roster_report.pdf");
        },
        error: function(xhr) {
            hideSpinner();
            showErrorMessage(xhr.status);
        }
    });
}