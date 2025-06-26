$(document).ready(function() {
    // Handle all functionality of copying a week of shifts
    handleWeekCopy();

    // Handle delete shift button and its confirmation
    handleDeleteShiftBtn();

    // Handle functionality of switching between weeks
    handleWeekSwitching();

    // Handle role edits, deletes and creations
    handleRoleModification();

    // Handle shift edits, deletes and creations
    handleShiftModification();

    // --- Store Selector ---
    $('#storeSelectDropdown').on('change', function() {
        updateStoreInformation(getSelectedStoreID());
        loadSchedule(new Date().toLocaleDateString('sv-SE'));
    });

    // --- Initial Page Load ---
    updateStoreInformation(getSelectedStoreID());
    loadSchedule(new Date().toLocaleDateString('sv-SE'));
});



function handleWeekCopy() {
    $('#copyWeekBtn').on('click', function() {
        const sourceWeekStartDate = $('#schedule-week-title').data('week-start-date');
        const storeId = getSelectedStoreID();

        if (!sourceWeekStartDate || storeId === null) {
            alert('Cannot copy because a valid week and store are not loaded.');
            return;
        }

        $('#confirmationModalTitle').text('Confirm Schedule Copy');
        $('#confirmationModalBody').html(
            "This will copy all non-conflicting shifts from the current week to the next week." +
            "<br><br><strong>This action cannot be undone.</strong>"
        );
        $('#confirmActionBtn').text('Yes, Copy Schedule').removeClass('btn-danger').addClass('btn-primary');

        const $confirmBtn = $('#confirmActionBtn');
        $confirmBtn.data('action', 'copy-week'); // Identify the action
        $confirmBtn.data('source-date', sourceWeekStartDate);
        $confirmBtn.data('store-id', storeId);

        // Show the modal
        const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));
        confirmationModal.show();
    });


    $('#confirmActionBtn').on('click', function() {
        showSpinner();
        const action = $(this).data('action');
        const modal = bootstrap.Modal.getInstance(document.getElementById('confirmationModal'));
        modal.hide();

        if (action === 'copy-week') {
            const storeId = $(this).data('store-id');

            $.ajax({
                url: window.djangoURLs.copyWeekSchedule,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    source_week_start_date: $(this).data('source-date'),
                    store_id: storeId
                }),
                xhrFields: { withCredentials: true },
                headers: { 'X-CSRFToken': getCSRFToken() },
                success: function(response) {
                    // Dont hide spinner -> gets shown in load
                    showNotification(response.message, 'success');
                    const nextWeek = $('#next-week-btn').data('week');
                    loadSchedule(nextWeek, storeId);
                },
                error: function(jqXHR) {
                    hideSpinner();
                    const errorMessage = jqXHR.responseJSON?.Error || "An unknown error occurred.";
                    showNotification(errorMessage, "danger");
                }
            });
        }
    });
}


function handleShiftModification() {
    // CLICK `+` ON A CERTAIN DAY -> OPEN EDIT MODAL AND SET TO CREATION
    $('#schedule-container').on('click', '.add-shift-btn', function() {
        const day = $(this).data('day');
        $('#editShiftDate').val(day);
        $('#editModalSelectedEmployeeID').val(''); // Select no employee
        $('#editShiftId').val(''); // Set NO ID -> CREATION MODE
        $('#editShiftRole').val('');
        $('#editStartTime').val('');
        $('#editEndTime').val('');
        $('#deleteShiftBtn').addClass('d-none'); // Hide 'Delete' button
        
        const addShiftModal = new bootstrap.Modal(document.getElementById('editModal'));
        addShiftModal.show();
    });

    // CLICK ON EXISTING SHIFT -> OPEN EDIT MODAL AND SET TO MODIFICATION
    $('#schedule-container').on('click', '.shift-item', function() {
        showSpinner();
        const shiftId = $(this).data('shift-id');

        // Get shift info -> ENSURE ITS ALWAYS UP TO DATE
        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'GET',
            xhrFields: { withCredentials: true },
            success: function(shiftData) {
                $('#editShiftDate').val(shiftData.date); 
                $('#editShiftId').val(shiftData.id);
                $('#editShiftRole').val(shiftData.role_id);
                $('#editStartTime').val(shiftData.start_time);
                $('#editEndTime').val(shiftData.end_time);
                $('#editModalSelectedEmployeeID').val(shiftData.employee_id);
                $('#deleteShiftBtn').removeClass('d-none'); // Show 'Delete' button
                
                hideSpinner();
                const editModal = new bootstrap.Modal(document.getElementById('editModal'));
                editModal.show();
            },
            error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to get shift information"); }
        });
    });

    // --- CREATE/EDIT SHIFT FORM SUBMISSION ---
    $('#saveShiftBtn').on('click', function() {
        const form = $('#editShiftForm');
        const formData = {
            date: form.find('#editShiftDate').val(),
            employee_id: form.find('#editModalSelectedEmployeeID').val(),
            role_id: form.find('#editShiftRole').val(),
            start_time: form.find('#editStartTime').val(),
            end_time: form.find('#editEndTime').val()
        };

        if (!formData.date || !formData.employee_id || !formData.start_time || !formData.end_time) {
            showNotification('Cannot submit form without all required fields.', 'warning');
            return;
        }

        const shiftId = $('#editShiftId').val();
        console.log(form.find('#editShiftRole').val());
        
        // EITHER CREATE OR UPDATE EXISTING SHIFT DEPENDING IF shiftID SET
        showSpinner();
        $.ajax({
            url: isNonEmpty(shiftId) ? `${window.djangoURLs.manageShift}${shiftId}/` : `${window.djangoURLs.createShift}${getSelectedStoreID()}/`,
            method: isNonEmpty(shiftId) ? 'POST' :'PUT',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            headers: {'X-CSRFToken': getCSRFToken()},
            xhrFields: {
            withCredentials: true
            },
            success: function(response) {
                // Dont hide spinner
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                form[0].reset();
                loadSchedule(response.date);
                showNotification(isNonEmpty(shiftId) ? "Successfully updated a shift." : "Successfully created a shift.", "success");
            },
            error: function(jqXHR, textStatus, errorThrown) {
                handleAjaxError(jqXHR, isNonEmpty(shiftId) ? "Failed to update the shift" : "Failed to create the shift");
            }
        });
    });

    // --- DELETE SHIFT ---
    $('#confirmDeleteBtn').on('click', function() {
        showSpinner();
        const shiftId = $('#editShiftId').val();

        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'DELETE',
            xhrFields: {withCredentials: true},
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                // Dont hide spinner
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                loadSchedule(response.date);
                showNotification("Successfully deleted a shift.", "success");
            },
            error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to delete the shift"); }
        });
    });

    // MODAL IS OPENED -> Show the employee in the list
    $('#editModal').on('shown.bs.modal', () => {
        showEmployeeInSelectionList();
    });

    // HANDLE EMPLOYEE LIST INPUT/SELECTION
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
        $("#editModalSelectedEmployeeID").val(userId);
    });
}


function handleRoleModification() {
    // CLICK BUTTON TO EDIT ROLES -> OPEN MODAL
    $('#manageRolesBtn').on('click', function() {
        const manageRolesModal = new bootstrap.Modal(document.getElementById('manageRolesModal'));
        manageRolesModal.show();
    });

    // CLICK '+' BUTTON ON ROLE MODAL -> SET FORM TO CREATE
    $('#addNewRoleBtn').on('click', () => {
        setRoleFormToAddMode();
    });

    // EDIT button click
    $('#existingRolesList').on('click', '.edit-role-btn', function() {
        const $listItem = $(this).closest('.list-group-item');
        const role = $listItem.data();
        
        const $form = $('#addRoleForm');
        const $submitBtn = $form.find('button[type="submit"]');
        
        $form.data('mode', 'edit');
        $form.data('role-id', role.roleId);
        $form.parent().find('h6').text(`Edit Role: ${role.roleName}`);
        
        $('#newRoleName').val(role.roleName);
        $('#newRoleDescription').val(role.roleDescription);
        $('#newRoleColor').val(role.roleColor);
        
        $submitBtn.text('Update Role').removeClass('btn-primary').addClass('btn-success');
    });

    // ADD/UPDATE form submission
    $('#addRoleForm').on('submit', function(e) {
        e.preventDefault();
        showSpinner();
        const $form = $(this);
        const mode = $form.data('mode') || 'add';
        const roleId = $form.data('role-id');

        const roleData = {
            name: $('#newRoleName').val(),
            description: $('#newRoleDescription').val(),
            colour_hex: $('#newRoleColor').val(),
            store_id: getSelectedStoreID(),
        };

        $.ajax({
            url: mode==='edit' ? `${window.djangoURLs.manageStoreRole}${roleId}/` : window.djangoURLs.createStoreRole,
            method: mode==='edit' ? 'PATCH' : 'POST',
            contentType: 'application/json',
            data: JSON.stringify(roleData),
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                // Dont hide spinner
                setRoleFormToAddMode();
                updateStoreInformation(getSelectedStoreID());
                showNotification(mode==='edit' ? "Successfully updated the role." : "Successfully created a role.", "success");
            },
            error: function(jqXHR, textStatus, errorThrown) {
                handleAjaxError(jqXHR, mode==='edit' ? "Failed to update the role" : "Failed to create a role");
            }
        });
    });

    $('#existingRolesList').on('click', '.delete-role-btn', function() {
        const $listItem = $(this).closest('.list-group-item');
        const roleId = $listItem.data('role-id');
        const roleName = $listItem.data('role-name');

        if (confirm(`Are you sure you want to delete the role "${roleName}"?`)) {
            showSpinner();
            $.ajax({
                url: `${window.djangoURLs.manageRole}${roleId}/`,
                method: 'DELETE',
                xhrFields: {withCredentials: true},
                headers: {'X-CSRFToken': getCSRFToken()},
                success: function() {
                    // DONT HIDE SPINNER AS IT GETS SHOWN AGAIN WHEN UPDATING INFO
                    updateStoreInformation(getSelectedStoreID());
                },
                error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to delete the role"); }
            });
        }
    });
}


function handleDeleteShiftBtn() {
    $('#deleteShiftBtn').on('click', () => {
        $('#confirmDeleteBtn').removeClass('d-none');
        $('#deleteShiftBtn').addClass('d-none');
        $('#updateShiftBtn').addClass('disabled');
    });

    $('#editModal').on('hide.bs.modal', () => {
        $('#confirmDeleteBtn').addClass('d-none');
        $('#deleteShiftBtn').removeClass('d-none');
        $('#updateShiftBtn').removeClass('disabled');
    });
}


function handleWeekSwitching() {
    // --- Shift Previous Week --- 
    $('#previous-week-btn').on('click', function(e) {
        e.preventDefault();
        const previousWeek = $(this).data('week');
        
        loadSchedule(previousWeek);
    });

    // --- Shift Next Week ---
    $('#next-week-btn').on('click', function(e) {
        e.preventDefault();
        const nextWeek = $(this).data('week');
        
        loadSchedule(nextWeek);
    });
}


function loadSchedule(week) {
    showSpinner();
    $.ajax({
        url: `${window.djangoURLs.listStoreShifts}${getSelectedStoreID()}/?get_all=true&week=${week}`,
        method: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},
        success: function(data) {
            $('#schedule-week-title')
                .text(`Week of ${formatWeekTitle(data.week_start)}`)
                .data('week-start-date', data.week_start);
            
            $('#schedule-week-title').text(`Week of ${formatWeekTitle(data.week_start)}`);
            const scheduleContainer = $('#schedule-container');
            scheduleContainer.empty();

            $.each(data.schedule || {}, function (dayDate, dayShifts) {
                let shiftsHtml = '';
                if (dayShifts && dayShifts.length > 0) {
                    dayShifts.forEach(shift => {
                        const backgroundColor = '#f8f9fa'; // A soft, off-white color.
                        const borderColor = shift.role_colour || '#adb5bd'; 

                        const duration = calculateDuration(shift.start_time, shift.end_time);

                        // Build the HTML with the new color logic.
                        shiftsHtml += `
                            <div class="shift-item cursor-pointer" style="border-left: 4px solid ${borderColor}; background-color: ${backgroundColor};" data-shift-id="${shift.id}">
                                <div class="shift-item-employee">${shift.employee_name}</div>
                                <div class="shift-item-details">
                                    <span>🕒 ${shift.start_time} – ${shift.end_time}</span>
                                    <span>⌛ ${duration}</span>
                                    ${shift.role_name ? `<span>👤 ${shift.role_name}</span>` : ''}
                                </div>
                            </div>`;
                    });
                } else {
                    shiftsHtml = '<div class="text-center text-white p-3"><small>No shifts scheduled</small></div>';
                }
                
                const dayCardHtml = `
                    <div class="day-column mb-4">
                        <div class="day-header">
                            <div class="day-name">${getFullDayName(dayDate)}</div>
                            <div class="day-date">${getShortDate(dayDate)}</div>
                            <button class="btn add-shift-btn" data-day="${dayDate}" data-bs-toggle="tooltip" title="Add shift for this day">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                        <div class="shifts-list">${shiftsHtml}</div>
                    </div>`;
                scheduleContainer.append(dayCardHtml);
            });
            // Initialise tooltips for buttons
            $('[data-bs-toggle="tooltip"]').tooltip();

            $('#previous-week-btn').data('week', data.prev_week);
            $('#next-week-btn').data('week', data.next_week);
            hideSpinner();
        },
        error: function(jqXHR, textStatus, errorThrown) {
            $('#schedule-container').html(`
                <div class="d-flex flex-row gap-3 justify-content-around align-items-center bg-danger text-white text-center rounded p-2 w-100 mb-2">
                    <div><i class="fas fa-circle-exclamation"></i></div>
                    <div>
                        <p class="m-0">Error loading roster. Please try again later.</p>
                    </div>
                </div>`);
            handleAjaxError(jqXHR, "Failed to load the roster week");
        }
    });
}


/**
 * Fetches employees and roles for the currently selected store and updates
 * the dropdowns in BOTH the 'Add Shift' and 'Edit Shift' modals.
 */
function updateStoreInformation(storeId) {
    if (storeId === null) return;

    showSpinner();

    const $addEmployeeSelect = $("#employeeSelect");
    const $editEmployeeSelect = $("#editEmployeeSelect");
    const $addRoleSelect = $("#addRoleSelect");
    const $editRoleSelect = $("#editShiftRole");
    const $existingRolesList = $("#existingRolesList");

    // Clear everything first
    $addEmployeeSelect.empty();
    $editEmployeeSelect.empty();
    $addRoleSelect.html(`<option value="" selected>No Role</option>`);
    $editRoleSelect.html(`<option value="" selected>No Role</option>`);
    $existingRolesList.html('<li class="list-group-item">Loading...</li>');

    // Fetch employees names
    $.ajax({
        url: `${window.djangoURLs.listStoreEmployeeNames}?store_id=${storeId}`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},

        success: function(response) {
            // Data should be {1: "Alice Jane", 2: "Akhil Mitanoski"} etc.
            const keys = Object.keys(response);
            if (keys.length > 0) {
                keys.forEach(userID => {
                    const name = response[userID];
                    $("#editModalEmployeeList").append(`<li class="list-group-item cursor-pointer" data-id="${userID}">${name}</li>`);
                });
            } else {
                $("#editModalEmployeeList").append('<option value="">No Employees available</option>');
                showNotification("There are no employees associated to the selected store.", "danger");
            }
        },

        error: function(jqXHR, textStatus, errorThrown) {
            let errorMessage;
            if (jqXHR.status == 500) {
                errorMessage = "Failed to load employee names due to internal server errors. Please try again.";
            } else {
                errorMessage = jqXHR.responseJSON?.Error || "Failed to load employee names. Please try again.";
            }
            showNotification(errorMessage, "danger");
        }
    });

    // Fetch store roles
    $.ajax({
        url: `${window.djangoURLs.listStoreRoles}${storeId}/`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},

        success: function(resp) {
        let roleOptionsHtml = '';
        $existingRolesList.empty(); 

        if (resp.data && resp.data.length > 0) {
            resp.data.forEach(role => {
                roleOptionsHtml += `<option value="${role.id}">${role.name}</option>`;
                const roleListItemHtml = `
                    <li class="list-group-item d-flex justify-content-between align-items-center" 
                        data-role-id="${role.id}" 
                        data-role-name="${role.name}" 
                        data-role-description="${role.description || ''}" 
                        data-role-color="${role.colour}">
                        
                        <div class="d-flex align-items-center text-truncate">
                            <span class="d-inline-block me-3 flex-shrink-0 role-colour-block" style="background-color: ${role.colour};"></span>
                            <span class="text-truncate" data-bs-toggle="tooltip" title="${role.name}">${role.name}</span>
                        </div>
                        
                        <div class="dropdown">
                            <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                <i class="fas fa-ellipsis-v"></i> </button>
                            <ul class="dropdown-menu">
                                <li><button class="dropdown-item edit-role-btn" type="button">Edit</button></li>
                                <li><button class="dropdown-item delete-role-btn text-danger" type="button">Delete</button></li>
                            </ul>
                        </div>
                    </li>`;
                $existingRolesList.append(roleListItemHtml);
                // Initialize Bootstrap tooltips for newly added elements
                $('[data-bs-toggle="tooltip"]').tooltip();
            });
        } else {
            showNotification("There are no ROLES associated to the selected store.", "info");
            $existingRolesList.append('<li class="list-group-item">No roles found.</li>');
        }

        $addRoleSelect.append(roleOptionsHtml);
        $editRoleSelect.append(roleOptionsHtml);
    },

        error: function(jqXHR, textStatus, errorThrown) {
            let errorMessage;
            if (jqXHR.status == 500) {
                errorMessage = "Failed to load store roles due to internal server errors. Please try again.";
            } else {
                errorMessage = jqXHR.responseJSON?.Error || "Failed to load store roles. Please try again.";
            }
            showNotification(errorMessage, "danger");
        }
    });

    hideSpinner();
}


// --- UPDATE ROLE FORM ---
function setRoleFormToAddMode() {
    const $form = $('#addRoleForm');
    const $submitBtn = $form.find('button[type="submit"]');

    $form.data('mode', 'add');
    $form.data('role-id', '');
    $form[0].reset();
    $form.parent().find('h6').text('Add New Role');
    $submitBtn.text('Add Role').removeClass('btn-success').addClass('btn-primary');
}


// This function scroll to the position of a user in the list IF GIVEN (otherwise scroll to top)
function showEmployeeInSelectionList() {
  const $listItems = $('#editModalEmployeeList .list-group-item');
  const $container = $('#editModalEmployeeList');
  const userId = $('#editModalSelectedEmployeeID').val();
  $listItems.removeClass('active'); // Clear any existing selections


  if (!userId) {
    // Scroll to top if no userId is provided
    $container.scrollTop(0);
    return;
  }

  // Find and highlight the item
  const $selectedItem = $listItems.filter(`[data-id="${userId}"]`);
  if ($selectedItem.length) {
    $selectedItem.addClass('active');
    // Scroll to the selected item (centered)
    $container.scrollTop(
        $selectedItem.offset().top - $container.offset().top + $container.scrollTop() - $container.height() / 2
    );
  }
}


//////////////////////////////// HELPER FUNCTIONS /////////////////////////////////////

function calculateDuration(startTime, endTime) {
    // Create date objects to calculate the difference. Date itself doesn't matter.
    const start = new Date(`01/01/2000 ${startTime}`);
    let end = new Date(`01/01/2000 ${endTime}`);

    // Handle overnight shifts
    if (end < start) {
        end.setDate(end.getDate() + 1);
    }
    
    let diffMs = end - start;
    const hours = Math.floor(diffMs / 3600000);
    const minutes = Math.floor((diffMs % 3600000) / 60000);

    return `${hours}h ${minutes}m`;
}

// Function to format date strings nicely (e.g., "Jun 9, 2025")
function formatWeekTitle(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
}