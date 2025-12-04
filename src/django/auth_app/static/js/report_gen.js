$(document).ready(function() {
  // open modal
  $("#openShiftLogModal").on("click", () => {
    const modal = new bootstrap.Modal(document.getElementById("shiftLogsModal"));
    modal.show();
  });

  // submit form
  $("#shiftLogReportForm").on("submit", function(e) {
    e.preventDefault();

    const params = new URLSearchParams({
      store_id: $("#storeID").val(),
      start: $("#startDate").val(),
      end: $("#endDate").val(),
      only_unfinished: $("#onlyUnfinished").is(":checked"),
      only_pub: $("#onlyPublicHol").is(":checked"),
      filter: $("#filterNames").val().trim()
    });

    window.open(`${window.djangoURLs.generateShiftReport}?${params.toString()}`, "_blank");
  });

    // Open modal
  $("#openAccountSummaryModal").on("click", function() {
      const modal = new bootstrap.Modal(document.getElementById("accountSummaryModal"));
      modal.show();
  });

  // Generate PDF
  $("#summaryGenerateBtn").on("click", function() {

      // Read values
      let start = $("#summaryStartDate").val();
      let end   = $("#summaryEndDate").val();
      let ignoreNoHours = $("#summaryIgnoreNoHours").is(":checked");
      let filterNames = $("#summaryFilterNames").val();

      let storeId = getSelectedStoreID(); 

      if (!storeId || !start || !end) {
          showNotification("Please select store, start date and end date.", "danger");
          return;
      }

      // Build request URL
      let url = `${window.djangoURLs.generateAccountSummaryPDF}?store_id=${storeId}`
              + `&start=${start}&end=${end}`
              + `&ignore_no_hours=${ignoreNoHours}`
              + `&filter=${encodeURIComponent(filterNames)}`;

      window.open(url, "_blank");
  });
});