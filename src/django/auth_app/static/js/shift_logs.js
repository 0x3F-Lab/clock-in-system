$(document).ready(function() {
  // Set default date for table controls
  setDefaultDateControls();

  // Initial table update
  updateShiftLogsTable();

  // Populate the table with all users once the stores have loaded completely
  $('#storeSelectDropdown').on('change', function() {
    resetPaginationValues();
    updateShiftLogsTable();
  });

  // Handle table controls submission
  $('#tableControllerSubmit').on('click', () => {
    resetPaginationValues();
    updateShiftLogsTable();
  });

  // Update table controller icon on collapse/show
  $('#tableControllerCollapse').on('show.bs.collapse', function () {
      $('#tableControllerToggleIcon').removeClass('fa-chevron-right').addClass('fa-chevron-down');
    });

  $('#tableControllerCollapse').on('hide.bs.collapse', function () {
    $('#tableControllerToggleIcon').removeClass('fa-chevron-down').addClass('fa-chevron-right');
  });

  // Handle actionable buttons on the page (i.e., edit, create, delete)
  handleActionButtons();

  // Handle edit modal to create/edit shift daa
  handleShiftDetailsEdit();

  // Activate the pagination system (set the update function)
  handlePagination({updateFunc: updateShiftLogsTable});

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(45); // 45 minutes
});


function handleActionButtons() {
  // When clicking edit button on a row in the table -> populate the ID section as well
  $(document).on('click', '.editBtn', function () {
    const shiftId = $(this).data('id');
    $('#editActivityId').val(shiftId);
    openEditModal();
  });

  // When clicking on button to make a new entry
  $('#addNewShiftBtn').on('click', () => {
    $('#editActivityId').val("");
    openEditModal();
  });

  // When clicking delete on a row in the table -> Replace with confirmation button
  $(document).on('click', '.deleteBtn', function () {
    const $original = $(this);
    const $confirm = $(`<button class="deleteBtnConfirm btn btn-sm btn-outline-danger ms-1 mt-1" data-id="${$original.data('id')}"><i class="fas fa-exclamation-triangle"></i> Confirm</button>`);
    $(this).replaceWith($confirm);
    
    // Set timeout to revert back after 3 seconds
    setTimeout(() => {
      if ($confirm.parent().length) { // Ensure still in the DOM
        $confirm.replaceWith($original);
      }
    }, 3000);
  });

  // After clicking delete confirmation button -> Delete the shift row
  $(document).on('click', '.deleteBtnConfirm', function () {
    const activityId = $(this).data('id');
    deleteShift(activityId);
  });
}


function openEditModal() {
  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function deleteShift(activityId) {
  $.ajax({
    url: `${window.djangoURLs.updateShiftDetails}${activityId}/`,
    type: "DELETE",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(req) {
      hideSpinner();

      showNotification("Successfully deleted shift.", "success");
      
      // Update the table
      updateShiftLogsTable();
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to delete the shift due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to delete the shift. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


function updateShiftLogsTable() {
  showSpinner();
  const startDate = $('#startDate').val();
  const endDate = $('#endDate').val();
  const sort = $('#sortFields input[type="radio"]:checked').val();
  const filter = $('#filterNames').val();
  const onlyUnfinished = $('#onlyUnfinished').is(':checked');
  const onlyPubHol = $('#onlyPublicHol').is(':checked');
  const hideDeactive = $('#hideDeactivated').is(':checked');
  const hideResign = $('#hideResigned').is(':checked');


  $.ajax({
    url: `${window.djangoURLs.listEveryShiftDetails}?offset=${getPaginationOffset()}&limit=${getPaginationLimit()}&store_id=${getSelectedStoreID()}&start=${startDate}&end=${endDate}&sort=${sort}&only_unfinished=${onlyUnfinished}&only_pub=${onlyPubHol}&hide_deactive=${hideDeactive}&hide_resign=${hideResign}&filter=${filter}`,
    type: "GET",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(req) {
      hideSpinner();

      const $shiftLogsTable = $('#shiftLogsTable tbody');
      const shifts = req.results || [];

      // If there are no users returned
      if (shifts.length <= 0) {
          $shiftLogsTable.html(`<tr><td colspan="9" class="table-danger">No shifts found</td></tr>`);
          showNotification("Obtained no shifts when updating table.", "danger");
          setPaginationValues(0, 1); // Set pagination values to indicate an empty table

      } else {
        $shiftLogsTable.html(""); // Reset inner HTML
        $.each(shifts, function(index, shift) {
          const rowColour = (!shift.logout_time || !shift.logout_timestamp) ? 'table-success' : (shift.emp_resigned ? 'table-danger' : (!shift.emp_active ? 'table-warning' : ''));
          const row = `
            <tr class="${rowColour}">
              <td>${shift.emp_first_name} ${shift.emp_last_name}</td>
              <td>${shift.login_time || "N/A"}</td>
              <td>${shift.logout_time || "N/A"}</td>
              <td class="${shift.is_public_holiday ? 'table-info' : ''}">${shift.is_public_holiday ? "Yes" : "No"}</td>
              <td>${shift.login_timestamp}</td>
              <td>${shift.logout_timestamp || "N/A"}</td>
              <td class="${parseInt(shift.deliveries, 10) > 0 ? 'table-purple' : ''}">${shift.deliveries}</td>
              <td class="${(shift.logout_time && parseFloat(shift.hours_worked) < 0.75) ? 'table-red' : (parseFloat(shift.hours_worked) > 10.0 ? 'table-red' : '')}">${shift.hours_worked}</td>
              <td>
                <div class="d-flex flex-row">
                  <button class="editBtn btn btn-sm btn-outline-primary" data-id="${shift.id}"><i class="fa-solid fa-pen"></i> Edit</button>
                  <button class="deleteBtn btn btn-sm btn-outline-danger ms-1 mt-1" data-id="${shift.id}"><i class="fa-solid fa-trash"></i> Delete</button>
                </div>
              </td>
            </tr>
          `;
          $shiftLogsTable.append(row)
        });
        // No need to update edit buttons as that is done dynamically
        setPaginationValues(req.offset, req.total); // Set pagination values
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
      const errorMessage = handleAjaxError(jqXHR, "Failed to load shift logs table");
      $('#shiftLogsTable tbody').html(`<tr><td colspan="9" class="table-danger">${errorMessage}</td></tr>`);
      setPaginationValues(0, 0);
    }
  });
}


function handleShiftDetailsEdit() {
  // When modal is about to be shown, populate employee list
  $("#editModal").on("show.bs.modal", () => {
    // Remove old content
    $("#editModalEmployeeList").empty();
    $('#editLoginTimestamp').val("");
    $('#editLogoutTimestamp').val("");
    $('#editIsPublicHoliday').prop('checked', false);
    $('#editDeliveries').val(0);
    const id = $('#editActivityId').val();

    // Attempt to populate the fields by requesting info ONLY IF an ID is supplied. (i.e. not making new user)
    if (id && id != -1) {
      // Ensure not changing user
      $('#editModalEmployeeListContainer').addClass('d-none');

      $.ajax({
        url: `${window.djangoURLs.listSingularShiftDetails}${id}/?store_id=${getSelectedStoreID()}`,
        type: 'GET',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
    
        success: function(req) {
          $('#editActivityId').val(req.id);
          $('#editLoginTimestamp').val(formatToDatetimeLocal(req.login_timestamp));
          $('#editLogoutTimestamp').val(formatToDatetimeLocal(req.logout_timestamp));
          $('#editIsPublicHoliday').prop('checked', req.is_public_holiday === true);
          $('#editDeliveries').val(req.deliveries || 0);
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to load shift details due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to load shift details. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });

    // Make list visible when creating new activity and populate list
    } else {
      $('#editModalEmployeeListContainer').removeClass('d-none');

      // Remove old list of users to select from
      $("#editModalEmployeeList").empty()

      $.ajax({
        url: `${window.djangoURLs.listStoreEmployeeNames}?store_id=${getSelectedStoreID()}`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},
    
        success: function(response) {
          const employeeList = response.names;

          if (Array.isArray(employeeList) && employeeList.length > 0) {
            employeeList.forEach(employee => {
              $("#editModalEmployeeList").append(
                `<li class="list-group-item cursor-pointer" data-id="${employee.id}">${employee.name}</li>`
              );
            });
          } else {
            $("#editModalEmployeeList").append('<option value="">No Employees available</option>');
            showNotification("There are no employees associated to the selected store.", "danger");
          }
        },
        error: function(jqXHR, textStatus, errorThrown) {
          handleAjaxError(jqXHR, "Failed to load employee names", false);
          $("#editModalEmployeeList").append('<option value="">Error loading employees</option>');
        }
      });

      // Filter list on input
      $("#editModalEmployeeSearchBar").on("input", function() {
        const term = $(this).val().toLowerCase();
        $("#editModalEmployeeList").children("li").each(function() {
          $(this).toggle($(this).text().toLowerCase().includes(term));
        });
      });

      // Click on an employee name to select
      $("#editModalEmployeeList").on("click", "li", function() {
        $("#editModalEmployeeList li").removeClass("active");
        $(this).addClass("active");
        const userId = $(this).data("id");
        $("#editModalListSelectedEmployeeID").val(userId);
      });
    }
  });

  // When the edit modal is submitted
  $('#editModalSubmit').on('click', function (e) {
    e.preventDefault();
    const id = $('#editActivityId').val();

    // Check the form is correctly filled
    const loginTimestamp = $('#editLoginTimestamp').val().trim();
    const logoutTimestamp = $('#editLogoutTimestamp').val().trim();
    const isPublicHoliday = ($('#editIsPublicHoliday').prop('checked') === true);
    const deliveries = ensureSafeInt($('#editDeliveries').val(), 0, null); // Min=0
    $('#editDeliveries').val(deliveries); // Update if user set it to -ve values.

    if (!loginTimestamp) {
      showNotification("Please enter the required field of Login Timestamp.", "danger");
      return;
    }

    showSpinner();

    // If updating EXISTING SHIFT
    if (id && id != -1) {
      $.ajax({
        url: `${window.djangoURLs.updateShiftDetails}${id}/`,
        type: 'POST',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        contentType: 'application/json',
        data: JSON.stringify({
          login_timestamp: correctAPITimestamps(loginTimestamp),
          logout_timestamp: correctAPITimestamps(logoutTimestamp),
          is_public_holiday: isPublicHoliday,
          deliveries: deliveries,
        }),
    
        success: function(req) {
          hideSpinner();
          $("#editModal").modal("hide");
          updateShiftLogsTable();
          showNotification("Successfully updated shift details.", "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          hideSpinner();
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to update existing shift details due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to update existing shift details. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });

    // If creating NEW SHIFT
    } else {
      const selectedID = $("#editModalListSelectedEmployeeID").val();

      $.ajax({
        url: `${window.djangoURLs.createShift}`,
        type: 'PUT',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        contentType: 'application/json',
        data: JSON.stringify({
          employee_id: selectedID,
          login_timestamp: correctAPITimestamps(loginTimestamp),
          logout_timestamp: correctAPITimestamps(logoutTimestamp),
          is_public_holiday: isPublicHoliday,
          deliveries: deliveries,
          store_id: getSelectedStoreID(),
        }),
    
        success: function(req) {
          hideSpinner();
          $("#editModal").modal("hide");
          updateShiftLogsTable();
          showNotification("Successfully created new shift.", "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          hideSpinner();
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to create new shift due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to create new shift. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });
    }
  });
}


function setDefaultDateControls() {
  // AIM OF THIS FUNCTION IS TO SET THE DATE LIMITS TO A FULL MONTH
  const end = new Date(); // today
  const start = new Date(end); // clone today's date

  // Subtract one month
  start.setMonth(start.getMonth() - 1);

  // Set the dates
  $('#startDate').val(formatDateForInput(start));
  $('#endDate').val(formatDateForInput(end));
}


// HELPER FUNCTIONS

function correctAPITimestamps(time) {
  if (!time || time === "" || time === null) return "";
  // Else append ':SS' to string 'YYYY-MM-DDTHH:MM'
  return (time + ":00")
}