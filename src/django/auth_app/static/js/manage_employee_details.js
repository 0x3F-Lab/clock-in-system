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

  // Attach event to MESSAGE field of message modal to update char count
  $('#msg_message').on('input', () => {
    updateCharCount();
  });
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

  // Handle clicking an action button -> open WARNING modal
  $(document).on('click', '.actionBtn', function () {
    const employeeID = $(this).data('id');
    const employeeName = $(this).data('name');
    const actionType = $(this).data('action');
    
    openWarningModal(employeeID, actionType, employeeName);
  });

  // Handle clicking on the Message button -> open Message modal
  $(document).on('click', '.messageBtn', function () {
    const employeeID = $(this).data('id');
    const employeeName = $(this).data('name');
    
    openMessageModal(employeeID, employeeName);
  });
}


function openEditModal() {
  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function openWarningModal(id, actionType, name) {
  // Reset the modal
  $('#notrevertibleBanner').addClass('d-none');
  $('#revertibleBanner').addClass('d-none');
  $('#warningModalSubmit').off(); // Remove all past events

  // Add the info
  let info
  if (actionType.toLowerCase() === "reset_pin") {
     info = `
      <p>You are about to reset an Employee's PIN.</p>
      <p>This resets their pin to a UNIQUE random 6-didgit PIN for the employee to use.</p>
      <p>You cannot chose a custom PIN due to PIN constraints.</p>
      <p>You cannot go back to an old PIN or cycle between PINs.</p>
      <p><em>A notification will be sent to the respective user informing them of this change.</em></p>
    `;
    $('#notrevertibleBanner').removeClass('d-none');

  } else if (actionType.toLowerCase() === "reset_password") {
    info = `
      <p>You are about to reset an Employee's account password.</p>
      <p>This resets their account to a non-setup state, allowing them to re-setup their account.</p>
      <p>This does not affect any other account information or history.</p>
      <p>The user can still clock in/out manually without setting up their account.</p>
      <p>Be warned that the user can change their DOB on the setup page.</p>
      <p><em>A notification will be sent to the respective user informing them of this change.</em></p>
    `;
    $('#notrevertibleBanner').removeClass('d-none');
  
  } else if (actionType.toLowerCase() === "resign") {
    info = `
      <p>You are about to RESIGN an Employee from your selected store.</p>
      <p>This means that the employee can no longer interact with the store.</p>
      <p>If the employee is still clocked in, then they can no longer clock out.</p>
      <p>To UNDO this and re-assign the employee to the store again, you must '+ Add New Employee' and then use their email (no need for the other information).</p>
      <p><em>A notification will be sent to the respective user and the store's manager(s) informing them of this change.</em></p>
    `;
    $('#revertibleBanner').removeClass('d-none');
  
  } else if (actionType.toLowerCase() === "deactivate") {
    info = `
      <p>You are about to DEACTIVATE an Employee account.</p>
      <p>This "freeze's" the account such that they cannot login or clock in/out.</p>
      <p>This affects every store the employee is assigned to - its GLOBAL.</p>
      <p><em>A notification will be sent to the respective user and the store's manager(s) informing them of this change.</em></p>
    `;
    $('#revertibleBanner').removeClass('d-none');

  } else if (actionType.toLowerCase() === "activate") {
    info = `
      <p>You are about to ACTIVATE an Employee account.</p>
      <p>This "unfreeze's" the account such that they can now again login or clock in/out.</p>
      <p>This affects every store the employee is assigned to - its GLOBAL.</p>
      <p><em>A notification will be sent to the respective user and the store's manager(s) informing them of this change.</em></p>
    `;
    $('#revertibleBanner').removeClass('d-none');
  }

  $('#warningModalText').html(info);
  $('#warningModalEmployeeName').text(name);
  $('#warningModalSubmit').on('click', () => {
    updateEmployeeStatus(id, actionType);
    warningModal.hide();
  });

  const warningModal = new bootstrap.Modal(document.getElementById("warningModal"));
  warningModal.show();
}


function openMessageModal(id, name) {
  // Reset the modal
  $('#msg_title').val('');
  $('#msg_message').val('');
  $('#msg_type').val('general'); // Reset type as well
  $('#sendMsgModalSubmit').off(); // Remove all past events
  updateCharCount(); // Reset count

  // Add employee name
  $('#sendMsgModalEmployee').text(name);

  // Add event to form submission
  $('#sendMsgModalSubmit').on('click', () => {
    const result = sendMessage(id);
    // Dont hide the menu if its errored
    if (result === false) {
      return;
    }
    msgModal.hide();
  });

  const msgModal = new bootstrap.Modal(document.getElementById("sendMsgModal"));
  msgModal.show();
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
            ? `<button type="button" class="dropdown-item actionBtn text-warning" data-action="deactivate" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}"><i class="fa-solid fa-user-xmark me-2"></i> Deactivate</button>`
            : `<button type="button" class="dropdown-item actionBtn text-success" data-action="activate" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}"><i class="fa-solid fa-user-check me-2"></i> Activate</button>`;
          const rowColour = (!employee.is_active) ? 'table-danger' : (employee.is_manager ? 'table-info' : '');

          const row = `
            <tr class="${rowColour}">
              <td>${employee.first_name} ${employee.last_name}</td>
              <td class="${!employee.email ? 'table-warning' : ''}">${employee.email || "N/A"}</td>
              <td>${employee.phone_number || "N/A"}</td>
              <td>${employee.dob || "N/A"}</td>
              <td>${employee.pin}</td>
              <td>
                <div class="d-flex flex-row gap-2 align-items-center">
                  <button class="editBtn btn btn-sm btn-outline-primary" data-id="${employee.id}">
                    <i class="fa-solid fa-pen"></i> Edit
                  </button>

                  <button class="btn btn-sm btn-outline-success messageBtn" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}">
                    <i class="fa-solid fa-paper-plane"></i> Message
                  </button>

                  <div class="btn-group">
                    <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle px-3 py-3" data-bs-toggle="dropdown" aria-expanded="false">
                      <i class="fa-solid fa-ellipsis-vertical"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                      <li>
                        ${activationButton}
                      </li>
                      <li>
                        <button class="dropdown-item actionBtn text-indigo" data-action="reset_pin" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}">
                          <i class="fa-solid fa-key me-2"></i> Reset PIN
                        </button>
                      </li>
                      <li>
                        <button class="dropdown-item actionBtn text-cyan" data-action="reset_password" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}">
                          <i class="fa-solid fa-lock me-2"></i> Reset Password
                        </button>
                      </li>
                      <li>
                        <button class="dropdown-item actionBtn text-danger" data-action="resign" data-id="${employee.id}" data-name="${employee.first_name} ${employee.last_name}">
                          <i class="fa-solid fa-user-slash me-2"></i> Resign
                        </button>
                      </li>
                    </ul>
                  </div>
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


function sendMessage(id) {
  const title = $('#msg_title').val();
  const msg = $('#msg_message').val();
  const type = $('#msg_type').val();

  if (title.trim() === "" || msg.trim() === "") {
    showNotification("Cannot send a message without a title or message.", "error");
    return false;
  }

  showSpinner();

  $.ajax({
    url: `${window.djangoURLs.sendEmployeeMessage}${id}/`,
    type: "POST",
    xhrFields: {
      withCredentials: true
    },
    headers: {
      'X-CSRFToken': getCSRFToken(), // Include CSRF token
    },
    contentType: 'application/json',
    data: JSON.stringify({
      "title": title,
      "message": msg,
      "notification_type": type,
    }),

    success: function(resp) {
      hideSpinner();
      showNotification(`Successfully sent message to ${resp.employee_name}.`, "success");
    },

    error: function(jqXHR, textStatus, errorThrown) {
      hideSpinner();

      // Extract the error message from the API response if available
      let errorMessage;
      if (jqXHR.status == 500) {
        errorMessage = "Failed to send employee message due to internal server errors. Please try again.";
      } else {
        errorMessage = jqXHR.responseJSON?.Error || "Failed to send employee message. Please try again.";
      }
      showNotification(errorMessage, "danger");
    }
  });
}


// Helper function
function updateCharCount() {
  const max = $('#msg_message').attr('maxlength');
  const len = $('#msg_message').val().length;
  $('#charCount').text(`${len}/${max} Characters`)
}