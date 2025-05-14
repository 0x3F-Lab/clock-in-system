$(document).ready(function() {
  // Initial table update
  updateEmployeeDetailsTable();

  // Update the table with all users if user changes store
  $('#storeSelectDropdown').on('change', function() {
    updateEmployeeDetailsTable();
  });

  // Handle actionable buttons on the page (i.e., edit, create, delete)
  handleActionButtons();

  // Handle edit modal to create/edit user data
  handleEmployeeDetailsEdit();

  // Activate the pagination system (set the update function)
  handlePagination({updateFunc: updateEmployeeDetailsTable});
});


function handleActionButtons() {
  // When clicking edit button on an employee row in the table -> populate the ID section as well
  $(document).on('click', '.editBtn', function () {
    const employeeId = $(this).data('id');
    $('#editEmployeeId').val(employeeId);
    openEditModal();
  });

  // When clicking on button to make new employee
  $('#addNewEmployeeButton').on('click', () => {
    $('#editEmployeeId').val("");
    openEditModal();
  });

  // Handle initial action click and show confirmation button
  $(document).on('click', '.actionBtn', function () {
    const $original = $(this);
    const employeeID = $original.data('id');
    const actionType = $original.data('action');
    const originalIcon = $original.find('i').prop('outerHTML');

    const $confirm = $(`
      <button class="actionBtnConfirm btn btn-sm btn-danger ms-1 mt-1" 
              data-id="${employeeID}" 
              data-action="${actionType}">
        ${originalIcon} Confirm
      </button>
    `);

    $original.replaceWith($confirm);

    // Auto-revert after 3 seconds
    setTimeout(() => {
      if ($confirm.parent().length) {
        $confirm.replaceWith($original);
      }
    }, 3000);
  });

  // Handle confirmation click
  $(document).on('click', '.actionBtnConfirm', function () {
    const employeeID = $(this).data('id');
    const actionType = $(this).data('action');

    updateEmployeeStatus(employeeID, actionType);
  });
}


function updateEmployeeStatus(id, type) {
  // Show spinner before the request
  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.modifyAccountStatus}${id}/`,
    type: "PUT",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },
    contentType: 'application/json',
    data: JSON.stringify({
      status_type: type,
      store_id: getSelectedStoreID(),
    }),

    success: function(req) {
      // Hide spinner once data comes in
      hideSpinner();
      
      updateEmployeeDetailsTable();
      showNotification("Successfully updated employee status.", "success");
    },

    error: function(jqXHR, textStatus, errorThrown) {
      // Hide spinner on error too
      hideSpinner();

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to update employee status due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to update employee status. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


function openEditModal() {
  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function updateEmployeeDetailsTable() {
  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.listEveryEmployeeDetails}?offset=${getPaginationOffset()}&limit=${getPaginationLimit()}&store_id=${getSelectedStoreID()}`,
    type: "GET",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },

    success: function(req) {
      hideSpinner();

      const $employeeTable = $('#employeeTable tbody');
      const employees = req.results || [];

      // If there are no users returned
      if (employees.length <= 0) {
        $shiftLogsTable.html(`<tr><td colspan="7" class="table-danger">No employees found</td></tr>`);
          showNotification("Obtained no employees when updating table.", "danger");
          setPaginationValues(0, 1); // Set pagination values to indicate an empty table

      } else {
        $employeeTable.html(""); // Reset inner HTML
        $.each(employees, function(index, employee) {
          const activationButton = employee.is_active
            ? `<button class="actionBtn btn btn-sm btn-outline-danger" data-action="deactivate" data-id="${employee.id}"><i class="fa-solid fa-user-xmark"></i> Deactivate</button>`
            : `<button class="actionBtn btn btn-sm btn-outline-success" data-action="activate" data-id="${employee.id}"><i class="fa-solid fa-user-check"></i> Activate</button>`;
          const rowColour = (!employee.is_active) ? 'table-danger' : '';

          const row = `
            <tr class="${rowColour}">
              <td>${employee.first_name} ${employee.last_name}</td>
              <td class="${!employee.email ? 'table-warning' : ''}">${employee.email || "N/A"}</td>
              <td>${employee.phone_number || "N/A"}</td>
              <td>${employee.dob || "N/A"}</td>
              <td>${employee.pin}</td>
              <td>
                <div class="d-flex flex-row gap-2">
                  <button class="editBtn btn btn-sm btn-outline-primary" data-id="${employee.id}"><i class="fa-solid fa-pen"></i> Edit</button>
                  ${activationButton}
                  <div class="vertical-divider bg-secondary"></div>
                  <button class="actionBtn btn btn-sm btn-outline-indigo" data-action="reset_pin" data-id="${employee.id}"><i class="fa-solid fa-key"></i> Reset PIN</button>
                  <button class="actionBtn btn btn-sm btn-outline-cyan" data-action="reset_password" data-id="${employee.id}"><i class="fa-solid fa-lock"></i> Reset Pass</button>
                  <button class="actionBtn btn btn-sm btn-outline-orange" data-action="resign" data-id="${employee.id}"><i class="fa-solid fa-user-slash"></i> Resign</button>
                </div>
              </td>
            </tr>
          `;
          $employeeTable.append(row)
        });
        // No need to update edit buttons as that is done dynamically
        // Set pagination values
        setPaginationValues(req.offset, req.total);
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();

      // Add error row
      $('#employeeTable tbody').html(`<tr><td colspan="7" class="table-danger">ERROR OBTAINING EMPLOYEES</td></tr>`);

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to load employee details table due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to load employee details table. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


function handleEmployeeDetailsEdit() {
  // When modal is about to be shown, populate employee list
  $("#editModal").on("show.bs.modal", () => {
    // Remove old content
    $('#editFirstName').val("");
    $('#editLastName').val("");
    $('#editEmail').val("").prop('disabled', false); // Ensure its enabled for creating a user
    $('#editPhone').val("");
    $('#editDOB').val("");
    const id = $('#editEmployeeId').val();

    // Attempt to populate the fields by requesting info ONLY IF an ID is supplied. (i.e. not making new user)
    if (id && id != -1) {
      $.ajax({
        url: `${window.djangoURLs.listSingularEmployeeDetails}${id}/`,
        type: 'GET',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
    
        success: function(req) {
          $('#editEmployeeId').val(req.id);
          $('#editFirstName').val(req.first_name);
          $('#editLastName').val(req.last_name);
          $('#editEmail').val(req.email).prop('disabled', true); // Disable email as manager cant modify email
          $('#editPhone').val(req.phone_number || "");
          $('#editDOB').val(req.dob || "");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to load employee details due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to load employee details. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });
    }
  });

  // When the edit modal is submitted
  $('#editModalSubmit').on('click', function (e) {
    e.preventDefault();
    const id = $('#editEmployeeId').val();

    // Check the form is correctly filled
    const firstName = $("#editFirstName").val().trim();
    const lastName = $("#editLastName").val().trim();
    const email = $("#editEmail").val().trim();
    const phone = $("#editPhone").val().trim();
    const dob = $("#editDOB").val().trim();

    showSpinner();

    // If updating EXISTING USER
    if (id && id != -1) {
      $.ajax({
        url: `${window.djangoURLs.updateEmployeeDetails}${id}/`,
        type: 'POST',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        contentType: 'application/json',
        data: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          phone: phone,
          dob: dob,
        }),
    
        success: function(response) {
          hideSpinner();
          $("#editModal").modal("hide");
          updateEmployeeDetailsTable();
          showNotification("Successfully updated employee details.", "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          hideSpinner();
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to update existing employee details due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to update existing employee details. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });

    // If creating NEW USER
    } else {
      $.ajax({
        url: `${window.djangoURLs.createEmployeeAccount}`,
        type: 'PUT',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        contentType: 'application/json',
        data: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email: email,
          phone: phone,
          dob: dob,
          store_id: getSelectedStoreID(),
        }),
    
        success: function(response) {
          hideSpinner();
          $("#editModal").modal("hide");
          updateEmployeeDetailsTable();
          showNotification(response.message, "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          hideSpinner();
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to create new employee due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to create new employee. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });
    }
  });
}
