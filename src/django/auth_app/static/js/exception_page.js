$(document).ready(function () {
  // Handle button(s) to mark a exception as approved
  handleExceptionApproveBtns();

  // Function to handle switching between the multiple pages on the notification page (i.e. seeing notifications to sending notifications)
  handleExceptionTypeSwitching();

  // Activate the pagination system (set the update function)
  handlePagination({updateFunc: updateExceptions});

  // Upon changing stores update the exception list
  $('#storeSelectDropdown').on('change', function() {
    updateStoreRoles();
    updateExceptions();
  });

  // Initial call to update exceptions and store roles
  updateStoreRoles();
  updateExceptions();

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(45); // 45 minutes
});

function openEditModal() {
  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function handleExceptionTypeSwitching() {
  // Switch to unapproved exceptions
  $('#excep-btn').on('click', function () {
    $('#excep-page').attr('data-type', 'unapproved');
    $(this).addClass('active');
    $('#approved-excep-btn').removeClass('active');
    $('#approved-excep-info').addClass('d-none');

    resetPaginationValues(); // Reset pagination (start from beginning)
    updateExceptions();
  });

  // Switch to approved exceptions
  $('#approved-excep-btn').on('click', function () {
    $('#excep-page').attr('data-type', 'approved');
    $(this).addClass('active');
    $('#excep-btn').removeClass('active');
    $('#approved-excep-info').removeClass('d-none');

    resetPaginationValues();
    updateExceptions();
  });
}



function handleExceptionApproveBtns() {
  // Forcefully create a BS collapse item if it doesnt already exist (PREVENTS NICHE BUGGED SITUATIONS)
  $(document).on('click', '[data-bs-toggle="collapse"]', function (e) {
    const targetSelector = $(this).attr('data-bs-target');
    const collapseEl = document.querySelector(targetSelector);
    if (collapseEl) {
      bootstrap.Collapse.getOrCreateInstance(collapseEl);
    }
  });

  // Listen for any collapse being shown
  $(document).on('show.bs.collapse', '.collapse', function () {
    const excepID = $(this).attr('id').split('-').pop();
    $(`[data-approve-id="${excepID}"]`).removeClass('d-none');
  });

  // Hide the button when the collapse is closed
  $(document).on('hide.bs.collapse', '.collapse', function () {
    const excepID = $(this).attr('id').split('-').pop();
    $(`[data-approve-id="${excepID}"]`).addClass('d-none');
  });

  // Handle user pressing 'Approve'
  $(document).on('click', '.mark-approved', function (e) {
    e.preventDefault();
    e.stopPropagation();
    const ID = $(this).attr('data-approve-id');
    markExceptionApproved(ID, false);
  });

  // Handle user pressing 'Approve & Edit'
  $(document).on('click', '.mark-approved-edit', function (e) {
    e.preventDefault();
    e.stopPropagation();
    const ID = $(this).attr('data-approve-id');
    const login = $(this).attr('data-login');
    const logout = $(this).attr('data-logout');
    const roleID = $(this).attr('data-role-id');
    const comment = $(this).data('comment');
    if (login) { $('#editLoginTimestamp').val(login); }
    if (logout) { $('#editLogoutTimestamp').val(logout); }
    if (roleID) { $('#editRoleSelect').val(roleID); }
    if (comment) { $('#editComment').val(comment); }
    $('#editModalSubmit').attr('data-id', ID);
    openEditModal();
  });

  // Upon submitting edit modal -> mark exception as approved
  $('#editModalSubmit').on('click', function (e) {
    e.preventDefault();
    const ID = $(this).attr('data-id');
    markExceptionApproved(ID, true);
  });
}


function markExceptionApproved(id, edit) {
  showSpinner();

  // If making no edits to clocking times
  if (!edit) {
    $.ajax({
      url: `${window.djangoURLs.manageStoreException}${id}/`,
      method: "POST",
      xhrFields: {withCredentials: true},
      headers: {'X-CSRFToken': getCSRFToken()},

      success: function(req) {
        hideSpinner();

        // Delete the notification from the page (no need to reload)
        $(`#excep-${id}`).remove();

        // Update the code
        count = ensureSafeInt($('#notification-page-count').html(), 0, null);
        $('#notification-page-count').html(count - 1);

        showNotification("Successfully approved the exception.", "success");
      },

      error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to approve the exception"); }
    });

    // If making edits to clocking times
  } else {
    $.ajax({
      url: `${window.djangoURLs.manageStoreException}${id}/`,
      method: "PATCH",
      xhrFields: {withCredentials: true},
      headers: {'X-CSRFToken': getCSRFToken()},
      contentType: 'application/json',
        data: JSON.stringify({
          login_time: $('#editLoginTimestamp').val(),
          logout_time: $('#editLogoutTimestamp').val(),
          role_id: $('#editRoleSelect').val(),
          comment: $('#editComment').val(),
        }),

      success: function(req) {
        hideSpinner();

        // Delete the notification from the page (no need to reload)
        $(`#excep-${id}`).remove();

        // Update the code
        count = ensureSafeInt($('#notification-page-count').html(), 0, null);
        $('#notification-page-count').html(count - 1);
        $("#editModal").modal("hide");
        showNotification("Successfully approved the exception.", "success");
      },

      error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to approve the exception"); }
    });
  }
}

function updateExceptions() {
  showSpinner();
  const isExceptionListTypeUnapproved = $('#excep-page').attr('data-type') === "unapproved";

  function formatDateTime(isoString) {
    const date = new Date(isoString);
    const options = {
      year: "numeric",
      month: "short", // e.g., "Jun"
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true, // for AM/PM format
    };

    return date.toLocaleString("en-US", options);
  }

  $.ajax({
    url: `${window.djangoURLs.listStoreExceptions}${getSelectedStoreID()}/?get_unapproved=${isExceptionListTypeUnapproved}&offset=${getPaginationOffset()}&limit=${getPaginationLimit()}`,
    method: "GET",
    xhrFields: {withCredentials: true},
    headers: {'X-CSRFToken': getCSRFToken()},

    success: function(resp) {
      $('#list-title').text(`${isExceptionListTypeUnapproved ? 'Active' : 'Approved'} Store Exceptions (${resp.total})`);
      const excepList = $('#excep-list')
      const exceptions = resp.exceptions || [];
      excepList.empty();

      // Add exceptions
      if (exceptions.length > 0) {
        $.each(resp.exceptions || [], function(index, e) {
          const rowColour = isExceptionListTypeUnapproved ? 'bg-warning-subtle' : '';
          const badgeColour = e.reason==='No Shift' ? 'bg-indigo' : (e.reason==='Incorrectly Clocked' ? 'bg-info' : (e.reason==='Missed Shift' ? 'bg-orange' : 'bg-secondary'));
          const showEditBtn = e.reason.trim().toUpperCase() !== 'MISSED SHIFT';
          const btn = !isExceptionListTypeUnapproved ? '' : 
            `<div class="d-flex gap-2 mt-1">
              <button class="mark-approved btn btn-sm btn-outline-success mt-1 d-none" data-approve-id="${e.id}">
                <i class="fas fa-check-circle me-1"></i> Approve
              </button>
              ${showEditBtn ? `
                <button class="mark-approved-edit btn btn-sm btn-outline-primary mt-1 d-none"
                        data-bs-toggle="none"
                        data-approve-id="${e.id}"
                        data-login="${e.act_start}"
                        data-logout="${e.act_end}"
                        data-role-id="${e.shift_role_id}">
                  <i class="fas fa-check-circle me-1"></i> Edit & Approve
                </button>` : ''}
            </div>`;
          const row = `
            <div class="${rowColour} list-group-item list-group-item-action flex-column align-items-start p-3 collapsed cursor-pointer"
                id="excep-${e.id}"
                data-bs-toggle="collapse"
                data-bs-target="#excep-info-${e.id}"
                aria-expanded="false"
                aria-controls="excep-info-${e.id}">
      
              <div class="d-flex w-100 justify-content-between align-items-start">
                <div>
                  <h5 class="mb-1">
                    <span class="${badgeColour} badge me-2">${e.reason}</span>
                    (${e.date}: ${getFullDayName(e.date)}) ${e.emp_name}
                  </h5>
                  <small class="text-muted">Store: [<code>${e.store_code}</code>]</small>
                </div>

                <div class="text-end d-flex flex-column align-items-end">
                  <small class="text-muted">Created: ${formatDateTime(e.created_at)}</small>
                  ${btn}
                </div>
              </div>

              <div class="collapse mt-3" id="excep-info-${e.id}">
                <div class="card card-body bg-light text-dark">
                  <p>Employee <b>${e.emp_name}</b> has had a Shift Exception generated for the reason: <u>${e.reason}</u></p>
                  <br>
                  ${generateExceptionMessage(e)}
                  <hr>
                  Exception was last updated at: ${formatDateTime(e.updated_at)}
                </div>
              </div>
            </div>
          `;
          excepList.append(row);
          if (e.shift_comment) {
            // Use jquery data in case comment is too large
            $(`#excep-${e.id} .mark-approved-edit`).data('comment', e.shift_comment);
          }
        });

      } else {
        const msg = isExceptionListTypeUnapproved ? "You're all caught up. New exceptions will appear here for all store managers." : "Your store has no past exceptions. Any new exceptions approved will appear here.";
        excepList.append(`
          <div class="list-group-item list-group-item-action flex-column align-items-start p-3 bg-light text-muted">
            <div class="d-flex w-100 justify-content-between align-items-center">
              <h5 class="mb-1">
                <i class="fas fa-bell-slash me-2"></i>No ${isExceptionListTypeUnapproved ? 'Active' : 'Approved'} Store Exceptions
              </h5>
            </div>
            <small class="mt-2">${msg}</small>
          </div>
          `);
      }

      setPaginationValues(resp.offset, resp.total); // Set pagination values
      hideSpinner();
    },

    error: function(jqXHR, textStatus, errorThrown) {
      $('#list-title').text(`${isExceptionListTypeUnapproved ? "Active" : "Approved"} Store Exceptions (ERR)`);
      handleAjaxError(jqXHR, "Failed to get store exceptions");
    }
  });
}


// Function to generate exception messages for each exception panel, which is dependant on the exception reason.
function generateExceptionMessage(exception) {
  switch (exception.reason) {
    case "No Shift":
      return `
        <p>They were not rostered to be working on <b>${exception.date}</b>.</p>
        <p>But they worked:<br>
        ${exception.act_start} (${exception.act_start_timestamp}) ⟶ 
        ${exception.act_end ? exception.act_end : "N/A"} (${exception.act_end_timestamp ? exception.act_end_timestamp : "N/A"}) [Length: ${exception.act_length_hr ? exception.act_length_hr : "N/A"} Hours]</p>
        ${exception.act_pub_hol ? '<p>This shift was counted as a <em>Public Holiday</em>.</p>' : ''}
        <p>By approving this exception, a rostered shift will be generated for the rosters.</p>
      `;

    case "Missed Shift":
      return `
        <p>They were expected to work:<br>
        ${exception.shift_start} ⟶ ${exception.shift_end} (Role: ${exception.shift_role_name || "N/A"}) [Length: ${exception.shift_length_hr ? exception.shift_length_hr : "N/A"} Hours]</p>
        <p>However, they did not show up to their shift.</p>
        <p>By approving this exception, the rostered shift will be deleted from the rosters. <em>This is unrecoverable.</em><br>
        <b>If the employee actually worked this shift, please add it manually using the 'Shift Logs' manager page.</b> This will also update this exception.</p>
      `;

    default:
      return `
        <p>They were expected to work:<br>
        ${exception.shift_start} ⟶ ${exception.shift_end} (Role: ${exception.shift_role_name || "N/A"}) [Length: ${exception.shift_length_hr ? exception.shift_length_hr : "N/A"} Hours]</p>
        <p>But they worked:<br>
        ${exception.act_start} (${exception.act_start_timestamp}) ⟶ 
        ${exception.act_end ? exception.act_end : "N/A"} (${exception.act_end_timestamp || "N/A"}) [Length: ${exception.act_length_hr ? exception.act_length_hr : "N/A"} Hours]</p>
        ${exception.act_pub_hol ? '<p>This shift was counted as a <em>Public Holiday</em>.</p>' : ''}
        <p>By approving this exception, the rostered shift will match the worked shift.</p>
      `;
  }
}


function updateStoreRoles() {
  const $editRoleSelect = $("#editRoleSelect");
  $editRoleSelect.html(`<option value="" selected>No Role</option>`);

  // Fetch roles
  $.ajax({
      url: `${window.djangoURLs.listStoreRoles}${getSelectedStoreID()}/`,
      type: 'GET',
      xhrFields: {withCredentials: true},
      headers: {'X-CSRFToken': getCSRFToken()},

      success: function(resp) {
        if (resp.data && resp.data.length > 0) {
            resp.data.forEach(role => {
                // Build options for the <select> dropdowns
                $editRoleSelect.append(`<option value="${role.id}">${role.name}</option>`);
            });
        } else {
            showNotification("There are NO ROLES associated to the selected store.", "info");
        }
      },

      error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to load store roles"); }
  });
}