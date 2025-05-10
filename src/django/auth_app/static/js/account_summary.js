$(document).ready(function() {
  // Update store selection component
  populateStoreSelection();

  // Set default date for table controls
  setDefaultDateControls();

  // Populate the table with all users once the stores have loaded completely
  $('#storeSelectDropdown').on('change', () => {
    updateSummaryTable();
  });

  // Handle table controls submission
  $('#summaryTableControllerSubmit').on('click', () => {
    updateSummaryTable();
  });

  // Activate the pagination system (set the update function)
  handlePagination({updateFunc: updateSummaryTable});
});


function updateSummaryTable() {
  showSpinner();

  const startDate = $('#startDate').val();
  const endDate = $('#endDate').val();
  const sort = $('#sortFields input[type="radio"]:checked').val();
  const ignoreNoHrs = $('#ignoreNoHours').is(':checked');
  const filter = $('#filterNames').val();

  $.ajax({
    url: `${window.djangoURLs.listAccountSummaries}?offset=${getPaginationOffset()}&limit=${getPaginationLimit()}&store_id=${getSelectedStoreID()}&start=${startDate}&end=${endDate}&sort=${sort}&ignore_no_hours=${ignoreNoHrs}&filter=${filter}`,
    type: "GET",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(req) {
      hideSpinner();

      const $summaryTable = $('#summaryTable tbody');
      const summaries = req.results || [];

      // If there are no users returned
      if (summaries.length <= 0) {
          $summaryTable.html(`<tr><td colspan="7" class="table-danger">No Summaries Found</td></tr>`);
          showNotification("Obtained no summaries when updating table.", "danger");
          setPaginationValues(0, 1); // Set pagination values to indicate an empty table

      } else {
        $summaryTable.html(""); // Reset inner HTML
        $.each(summaries, function(index, sum) {
          // Set row colour based on desc priority: resigned from store (red), inactive acc (yellow), manager (blue), then white 
          const rowColour = sum.acc_resigned ? 'table-danger' : (!sum.acc_active ? 'table-warning' : (sum.acc_manager ? 'table-info' : ''));
          const row = `
            <tr class="${rowColour}">
              <td>${sum.name}</td>
              <td>${sum.hours_weekday}</td>
              <td>${sum.hours_weekend}</td>
              <td>${sum.hours_public_holiday}</td>
              <td>${sum.deliveries || "N/A"}</td>
              <td class="${parseFloat(sum.hours_total) > 38 ? 'cell-danger' : ''}">${sum.hours_total}</td>
              <td>${sum.age != null ? sum.age : "N/A"}</td>
            </tr>
          `;
          $summaryTable.append(row)
        });
        // No need to update edit buttons as that is done dynamically
        setPaginationValues(req.offset, req.total); // Set pagination values
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();

      // Add error row
      $('#summaryTable tbody').html(`<tr><td colspan="7" class="table-danger">ERROR OBTAINING SUMMARIES</td></tr>`);

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to load summary table due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to load summary table. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


function setDefaultDateControls() {
  // AIM OF THIS FUNCTION IS TO SET THE DATE LIMITS TO A FULL WORKING WEEK THAT IS COMPLETE (i.e. the prev work week)
  const today = new Date();
  const daysSinceMon = (today.getDay() + 6) % 7;

  // Get the start of the week that started at least a week ago
  const monday = new Date(today);
  monday.setDate(today.getDate() - daysSinceMon - 7);
  
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  // Format to YYYY-MM-DD for input[type="date"]
  const formatDate = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  // Set the dates
  $('#startDate').val(formatDate(monday));
  $('#endDate').val(formatDate(sunday));
}