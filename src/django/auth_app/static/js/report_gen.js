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

// SHIFT LOG REPORT HANDLER

function openShiftLogModal() {
    const modal = new bootstrap.Modal(document.getElementById("shiftLogsModal"));
    modal.show();
}

function generateShiftLogReport(e) {
    e.preventDefault();

    // Get store from selector
    let storeId = getSelectedStoreID();
    let start   = $("#startDate").val();
    let end     = $("#endDate").val();
    let filter  = $("#filterNames").val().trim();
    let onlyUnfinished = $("#onlyUnfinished").is(":checked");
    let onlyPublicHol  = $("#onlyPublicHol").is(":checked");

    if (!storeId || !start || !end) {
        showNotification("Please select store, start date and end date.", "danger");
        return;
    }

    const params = new URLSearchParams({
        store_id: storeId,
        start: start,
        end: end,
        only_unfinished: onlyUnfinished,
        only_pub: onlyPublicHol,
        filter: filter
    });

    window.open(`${window.djangoURLs.generateShiftReport}?${params.toString()}`, "_blank");
}



// ACCOUNT SUMMARY REPORT HANDLER

function openAccountSummaryModal() {
    const modal = new bootstrap.Modal(document.getElementById("accountSummaryModal"));
    modal.show();
}

function generateAccountSummaryReport() {
    let start       = $("#summaryStartDate").val();
    let end         = $("#summaryEndDate").val();
    let ignoreHours = $("#summaryIgnoreNoHours").is(":checked");
    let filterNames = $("#summaryFilterNames").val();
    let storeId     = getSelectedStoreID();

    if (!storeId || !start || !end) {
        showNotification("Please select store, start date and end date.", "danger");
        return;
    }

    let url = `${window.djangoURLs.generateAccountSummaryPDF}?store_id=${storeId}`
            + `&start=${start}&end=${end}`
            + `&ignore_no_hours=${ignoreHours}`
            + `&filter=${encodeURIComponent(filterNames)}`;

    window.open(url, "_blank");
}

// ROSTER REPORT HANDLER

function openWeeklyRosterModal() {
    const modal = new bootstrap.Modal(document.getElementById("weeklyRosterModal"));
    modal.show();
}

function generateWeeklyRosterReport() {
    let storeId     = getSelectedStoreID();
    let week        = $("#weeklyRosterWeek").val();
    let filterNames = $("#weeklyRosterFilterNames").val();
    let hideResigned = $("#weeklyRosterHideResigned").is(":checked");

    if (!storeId || !week) {
        showNotification("Please select store and week.", "danger");
        return;
    }

    let url =
        `${window.djangoURLs.generateWeeklyRosterPDF}?store_id=${storeId}` +
        `&week=${encodeURIComponent(week)}` +
        `&filter=${encodeURIComponent(filterNames)}` +
        `&hide_resigned=${hideResigned}`;

    window.open(url, "_blank");
}