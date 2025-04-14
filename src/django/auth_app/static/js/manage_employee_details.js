$(document).ready(function() {
  // All required URLs
  const listEveryEmployeeDetailsURL = window.djangoURLs.listEveryEmployeeDetails

  // Populate the table with all users once the page has loaded
  updateEmployeeDetailsTable(listEveryEmployeeDetailsURL);

  // Handle edit and create employee buttons on the table
  handleActionButtons();

  // Handle edit modal to create/edit user data
  handleEmployeeDetailsEdit();
});



function handleActionButtons() {
  // When clicking edit button on an employee row in the table -> populate the ID section as well
  $(document).on('click', '.editBtn', function(e) {
    const employeeId = $(this).data('id');
    $('#editEmployeeId').val(employeeId);
    openEditModal();
  });

  // When clicking on button to make new employee
  $('#addNewEmployeeButton').on('click', function(e) {
    $('#editEmployeeId').val("");
    openEditModal();
  });

  // When clicking activate button on employee row in table
  $(document).on('click', '.activateEmployeeBtn', function(e) {
    const employeeId = $(this).data('id');
    updateEmployeeActivationStatus(employeeId, "activation");
  });

  // When clicking deactivate button on employee row in table
  $(document).on('click', '.deactivateEmployeeBtn', function(e) {
    const employeeId = $(this).data('id');
    updateEmployeeActivationStatus(employeeId, "deactivation");
  });
}


function updateEmployeeActivationStatus(id, type) {
  $.ajax({
    url: `${window.djangoURLs.modifyAccountStatus}${id}/`,
    type: "PUT",
    contentType: "application/json",
    headers: {
      'X-CSRFToken': `${getCookie('csrftoken')}`, // Include CSRF token
    },
    data: JSON.stringify({
      status_type: type
    }),

    success: function(req) {
      updateEmployeeDetailsTable();
      showNotification("Successfully updated employee activation status.", "success");
    },

    error: function(jqXHR, textStatus, errorThrown) {
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
  $.ajax({
    url: window.djangoURLs.listEveryEmployeeDetails,
    type: "GET",
    contentType: "application/json",
    headers: {
      'X-CSRFToken': `${getCookie('csrftoken')}`, // Include CSRF token
    },

    success: function(req) {
      const $employeeTable = $('#employeeTable tbody');
      // If there are no users returned
      if (req.length <= 0) {
        if ($employeeTable.html().length > 0) {
          showNotification("Obtained no employees when updating table.... Keeping table.", "danger");
        } else {
          $employeeTable.html(`<tr><td colspan="5">No employees found.</td></tr>`);
          showNotification("Obtained no employees when updating table.", "danger");
        }

      } else {
        $employeeTable.html(""); // Reset inner HTML
        $.each(req, function(index, employee) {
          const activationButton = employee.is_active
            ? `<button class="deactivateEmployeeBtn" data-id="${employee.id}" data-type="deactivate">Deactivate</button>`
            : `<button class="activateEmployeeBtn" data-id="${employee.id}" data-type="activate">Activate</button>`;

          const row = `
            <tr>
              <td>${employee.first_name} ${employee.last_name}</td>
              <td>${employee.email || "N/A"}</td>
              <td>${employee.phone_number || "N/A"}</td>
              <td>${employee.pin}</td>
              <td>
                <button class="editBtn" data-id="${employee.id}">Edit</button>
                ${activationButton}
              </td>
            </tr>
          `;
          $employeeTable.append(row)
        });
        // No need to update edit buttons as that is done dynamically
      }
    },

    error: function(jqXHR, textStatus, errorThrown) {
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
  const editModalElement = document.getElementById("editModal");
  const editModal = new bootstrap.Modal(editModalElement);

  // When modal is about to be shown, populate employee list
  $("#editModal").on("show.bs.modal", function() {
    // Remove old content
    $('#editFirstName').val("");
    $('#editLastName').val("");
    $('#editEmail').val("");
    $('#editPhone').val("");
    $('#editPin').val("");
    const id = $('#editEmployeeId').val();

    // Attempt to populate the fields by requesting info ONLY IF an ID is supplied. (i.e. not making new user)
    if (id && id != -1) {
      $.ajax({
        url: `${window.djangoURLs.listSingularEmployeeDetails}${id}/`,
        type: 'GET',
        headers: {
          'X-CSRFToken': `${getCookie('csrftoken')}`,
        },
    
        success: function(req) {
          $('#editEmployeeId').val(req.id);
          $('#editFirstName').val(req.first_name);
          $('#editLastName').val(req.last_name);
          $('#editEmail').val(req.email);
          $('#editPhone').val(req.phone_number || "");
          $('#editPin').val(req.pin || "");
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
  $('#editModalSubmit').on('click', () => {
    const id = $('#editEmployeeId').val();

    // Check the form is correctly filled
    const firstName = $("#editFirstName").val().trim();
    const lastName = $("#editLastName").val().trim();
    const email = $("#editEmail").val().trim();
    const phone = $("#editPhone").val().trim();
    const pin = $("#editPin").val().trim();

    if (!firstName || !lastName || !email || !pin) {
      showNotification("Please enter the required fields of: first name, last name, email and pin.", "danger");
      return;
    }

    // If updating EXISTING USER
    if (id && id != -1) {
      $.ajax({
        url: `${window.djangoURLs.updateEmployeeDetails}${id}/`,
        type: 'POST',
        headers: {
          'X-CSRFToken': `${getCookie('csrftoken')}`,
        },
        data: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email: email,
          phone: phone,
          pin: pin,
        }),
    
        success: function(req) {
          $("#editModal").modal("hide");
          updateEmployeeDetailsTable();
          showNotification("Successfully updated employee details.", "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
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
        headers: {
          'X-CSRFToken': `${getCookie('csrftoken')}`,
        },
        data: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email: email,
          phone: phone,
          pin: pin,
        }),
    
        success: function(req) {
          $("#editModal").modal("hide");
          updateEmployeeDetailsTable();
          showNotification("Successfully created new employee.", "success");
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
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
