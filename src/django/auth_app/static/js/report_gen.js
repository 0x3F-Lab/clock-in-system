// DOCUMENT READY

$(document).ready(function () {

    // SHIFT LOG REPORT
    $("#openShiftLogModal").on("click", openShiftLogModal);
    $("#shiftLogReportForm").on("submit", generateShiftLogReport);

    // ACCOUNT SUMMARY REPORT
    $("#openAccountSummaryModal").on("click", openAccountSummaryModal);
    $("#summaryGenerateBtn").on("click", generateAccountSummaryReport);

    // ROSTER REPORT
    $("#openWeeklyRosterModal").on("click", openWeeklyRosterModal);
    $("#weeklyRosterGenerateBtn").on("click", generateWeeklyRosterReport);

});

function openPDFBlob(blob, filename) {
    const file = new Blob([blob], { type: "application/pdf" });
    const url  = URL.createObjectURL(file);

    const viewer = window.open(url, "_blank");

    if (viewer) {
        viewer.document.title = filename;
    }

    setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// SHIFT LOG REPORT HANDLER

function openShiftLogModal() {
    const modal = new bootstrap.Modal(document.getElementById("shiftLogsModal"));
    modal.show();
}

function generateShiftLogReport(e) {
    e.preventDefault();

    let storeId = getSelectedStoreID();
    let start   = $("#startDate").val();
    let end     = $("#endDate").val();
    let filter  = $("#filterNames").val().trim();
    let onlyUnfinished = $("#onlyUnfinished").is(":checked");
    let onlyPublicHol  = $("#onlyPublicHol").is(":checked");

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
            only_unfinished: onlyUnfinished,
            only_pub: onlyPublicHol
        },
        success: function(blob) {
            hideSpinner();
            openPDFBlob(blob, "shift_logs_report.pdf");

        },
        error: function(xhr) {
            handleAjaxError(xhr, "Failed to generate report");
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

    let storeId     = getSelectedStoreID();
    let start       = $("#summaryStartDate").val();
    let end         = $("#summaryEndDate").val();
    let ignoreHours = $("#summaryIgnoreNoHours").is(":checked");
    let filterNames = $("#summaryFilterNames").val();

    if (!storeId || !start || !end) {
        showNotification("Please select store, start date and end date.", "danger");
        return;
    }

    showSpinner();

    $.ajax({
        url: window.djangoURLs.generateAccountSummaryPDF,
        method: "GET",
        xhrFields: { responseType: "blob", withCredentials: true },
        headers: {
            'X-CSRFToken': getCSRFToken(), // Include CSRF token
        },
        data: {
            store_id: storeId,
            start: start,
            end: end,
            ignore_no_hours: ignoreHours,
            filter: filterNames
        },
        success: function(blob) {
            hideSpinner();

            const file = new Blob([blob], { type: "application/pdf" });
            const url  = URL.createObjectURL(file);

            window.open(url, "_blank");

            setTimeout(() => URL.revokeObjectURL(url), 2000);

        },
        error: function(xhr) {
            handleAjaxError(xhr, "Failed to generate account summary report");
        }
    });
}

// ROSTER REPORT HANDLER

function openWeeklyRosterModal() {
    const modal = new bootstrap.Modal(document.getElementById("weeklyRosterModal"));
    modal.show();
}

function generateWeeklyRosterReport() {
    let storeId = getSelectedStoreID();
    let week = $("#weeklyRosterWeek").val();
    let filterNames = $("#weeklyRosterFilterNames").val();
    let hideResigned = $("#weeklyRosterHideResigned").is(":checked");

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
            hide_resigned: hideResigned
        },
        success: function(blob) {
            hideSpinner();

            const pdf = new Blob([blob], { type: "application/pdf" });
            const url = URL.createObjectURL(pdf);

            window.open(url, "_blank");

            setTimeout(() => URL.revokeObjectURL(url), 2000);
        },
        error: function(xhr) {
            handleAjaxError(xhr, "Failed to generate roster report.");
        }
    });
}