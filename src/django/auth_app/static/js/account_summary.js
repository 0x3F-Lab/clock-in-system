$(document).ready(function() {
  // Set default date for table controls
  setDefaultDateControls();

  // Initial table update
  updateSummaryTable();

  // Populate the table with all users once the stores have loaded completely
  $('#storeSelectDropdown').on('change', () => {
    resetPaginationValues();
    updateSummaryTable();
  });

  // Handle table controls submission
  $('#summaryTableControllerSubmit').on('click', () => {
    resetPaginationValues();
    updateSummaryTable();
  });

  // Activate the pagination system (set the update function)
  handlePagination({updateFunc: updateSummaryTable});

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(45); // 45 minutes
});


function updateSummaryTable() {
  showSpinner();

  const startDate = $('#startDate').val();
  const endDate = $('#endDate').val();
  const sort = $('#sortFields input[type="radio"]:checked').val();
  const ignoreNoHrs = $('#ignoreNoHours').is(':checked');
  const filter = $('#filterNames').val();
  const legacyStyle = $('#legacyStyle').is(':checked');

  $.ajax({
    url: `${window.djangoURLs.listAccountSummaries}?offset=${getPaginationOffset()}&limit=${getPaginationLimit()}&store_id=${getSelectedStoreID()}&start=${startDate}&end=${endDate}&sort=${sort}&ignore_no_hours=${ignoreNoHrs}&filter=${filter}`,
    type: "GET",
    xhrFields: { withCredentials: true },
    headers: { 'X-CSRFToken': getCSRFToken() },

    success: function(req) {
      hideSpinner();
      const summaries = req.results || [];

      if (legacyStyle) {
         $('#legacySummaryTable').removeClass('d-none');
         $('#summaryTable').addClass('d-none');
      } else {
        $('#legacySummaryTable').addClass('d-none');
         $('#summaryTable').removeClass('d-none');
      }

      // If there are no users returned
      if (summaries.length <= 0) {
          if (legacyStyle) {
            $('#legacySummaryTable tbody').html(`<tr><td colspan="1" class="table-danger">No Summaries Found</td></tr>`);
          } else {
            $('#summaryTable tbody').html(`<tr><td colspan="7" class="table-danger">No Summaries Found</td></tr>`);
          }
          showNotification("Obtained no summaries when updating table.", "danger");
          setPaginationValues(0, 1); // Set pagination values to indicate an empty table

      } else {
        // Reset inner HTML
        $('#legacySummaryTable tbody').html("");
        $('#summaryTable tbody').html("");
        $.each(summaries, function(index, sum) {
          // Add table information based on the selected style
          addTableRowInformation(legacyStyle, sum);
        });
        // No need to update edit buttons as that is done dynamically
        setPaginationValues(req.offset, req.total); // Set pagination values
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
      const errorMessage = handleAjaxError(jqXHR, "Failed to load summary table");
      $('#summaryTable tbody').html(`<tr><td colspan="7" class="table-danger">${errorMessage}</td></tr>`);
      setPaginationValues(0, 0);
    }
  });
}


function addTableRowInformation(legacyStyle, sum) {
  // Set row colour based on desc priority: resigned from store (red), inactive acc (yellow), manager (blue), then white 
  const rowColour = sum.acc_resigned ? 'table-danger' : (!sum.acc_active ? 'table-warning' : (sum.acc_store_manager ? 'table-info' : ''));

  if (legacyStyle) {
    const row = `
      <tr class="${rowColour}">
        <td class="py-2">
          <p class="mb-1"><u><b>${sum.name}</b> (Age: ${sum.age != null ? sum.age : "N/A"})</u></p>
          <p class="mb-1"><b>Weekday Hours:</b> ${sum.hours_weekday}</p>
          <p class="mb-1"><b>Weekend Hours:</b> ${sum.hours_weekend}</p>
          <p class="mb-1"><b>Public Holiday Hours:</b> ${sum.hours_public_holiday}</p>
          <p class="mb-1"><b>Deliveries:</b> ${sum.deliveries != null ? sum.deliveries : "N/A"}</p>
          <p class="mb-1"><span class="${parseFloat(sum.hours_total) > 38 ? 'mark' : ''}"><b>Total Hours:</b> ${sum.hours_total}</span></p>
        </td>
      </tr>
    `;
    console.log(row)
    $('#legacySummaryTable tbody').append(row);

  } else {
    const row = `
      <tr class="${rowColour}">
        <td class="py-3">${sum.name}</td>
        <td class="py-3">${sum.hours_weekday}</td>
        <td class="py-3">${sum.hours_weekend}</td>
        <td class="py-3">${sum.hours_public_holiday}</td>
        <td class="py-3">${sum.deliveries != null ? sum.deliveries : "N/A"}</td>
        <td class="py-3 ${parseFloat(sum.hours_total) > 38 ? 'cell-danger' : ''}">${sum.hours_total}</td>
        <td class="py-3">${sum.age != null ? sum.age : "N/A"}</td>
      </tr>
    `;
    $('#summaryTable tbody').append(row);
  }
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

  // Set the dates
  $('#startDate').val(formatDateForInput(monday));
  $('#endDate').val(formatDateForInput(sunday));
}