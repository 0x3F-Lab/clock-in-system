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
});