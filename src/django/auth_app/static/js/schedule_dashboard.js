$(document).ready(function() {

    // --- CORE APPLICATION FUNCTIONS ---

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
                                <div class="shift-item" style="cursor: pointer; border-left: 4px solid ${borderColor}; background-color: ${backgroundColor};" data-shift-id="${shift.id}">
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
                        <div class="day-column">
                            <div class="day-header">
                                <div class="day-name">${getFullDayName(dayDate)}</div>
                                <div class="day-date">${getShortDate(dayDate)}</div>
                                <button class="btn add-shift-btn" data-day="${dayDate}" title="Add shift for this day">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                            <div class="shifts-list">${shiftsHtml}</div>
                        </div>`;
                    scheduleContainer.append(dayCardHtml);
                });

                $('#previous-week-btn').data('week', data.prev_week);
                $('#next-week-btn').data('week', data.next_week);
                hideSpinner();
            },
            error: function(jqXHR, textStatus, errorThrown) {
                hideSpinner();
                $('#schedule-container').html('<p class="text-center text-danger">Error loading schedule.</p>');
                let errorMessage;
                if (jqXHR.status == 500) {
                  errorMessage = "Failed to add a new shift due to internal server errors. Please try again.";
                } else {
                  errorMessage = jqXHR.responseJSON?.Error || "Failed to add a new shift. Please try again.";
                }
                showNotification(errorMessage, "danger");
            }
        });
    }

    // --- MODAL/BUTTON EVENT HANDLERS ---
    $('#schedule-container').on('click', '.shift-item', function() {
        const shiftId = $(this).data('shift-id');

        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'GET',
            xhrFields: { withCredentials: true },
            success: function(shiftData) {

                $('#editShiftForm').data('shift-date', shiftData.date); 
                $('#editShiftId').val(shiftData.id);
                $('#editRoleSelect').val(shiftData.role_id);
                $('#editStartTime').val(shiftData.start_time);
                $('#editEndTime').val(shiftData.end_time);

                $('#editEmployeeSelect').val(shiftData.employee_id);
                
                const editModal = new bootstrap.Modal(document.getElementById('editShiftModal'));
                editModal.show();
            }
        });
    });

    $('#manageRolesBtn').on('click', function() {
        const manageRolesModal = new bootstrap.Modal(document.getElementById('manageRolesModal'));
        manageRolesModal.show();
    });

    // --- ADD SHIFT ---
    $('#saveShiftBtn').on('click', function() {
        showSpinner();
        const form = $('#addShiftForm');
        const formData = {
            date: form.find('#shiftDate').val(),
            employee_id: form.find('#employeeSelect').val(),
            role_id: form.find('#addRoleSelect').val(),
            start_time: form.find('#startTime').val(),
            end_time: form.find('#endTime').val()
        };

        if (!formData.date || !formData.employee_id || !formData.start_time || !formData.end_time) {
            alert('Please fill out all required fields.');
            return;
        }
        
        $.ajax({
            url: `${window.djangoURLs.createShift}${getSelectedStoreID()}/`,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            headers: {'X-CSRFToken': getCSRFToken()},
            xhrFields: {
            withCredentials: true
            },
            success: function(response) {
                // Dont hide spinner
                const modal = bootstrap.Modal.getInstance(document.getElementById('addShiftModal'));
                modal.hide();
                form[0].reset();
                loadSchedule(response.date); 
            },
            error: function(jqXHR, textStatus, errorThrown) {
                hideSpinner();
                let errorMessage;
                if (jqXHR.status == 500) {
                  errorMessage = "Failed to add a new shift due to internal server errors. Please try again.";
                } else {
                  errorMessage = jqXHR.responseJSON?.Error || "Failed to add a new shift. Please try again.";
                }
                showNotification(errorMessage, "danger");
            }
        });
    });

    $('#schedule-container').on('click', '.add-shift-btn', function() {
        const day = $(this).data('day');
        $('#shiftDate').val(day);

        $('#employeeSelect').find('option[disabled]').prop('selected', true);
        
        const addShiftModal = new bootstrap.Modal(document.getElementById('addShiftModal'));
        addShiftModal.show();
    });

    // --- UPDATE SHIFT ---
    $('#updateShiftBtn').on('click', function() {
        showSpinner();
        const shiftId = $('#editShiftId').val();
        const shiftData = {
            date: $('#editShiftForm').data('shift-date'), 
            employee_id: $('#editEmployeeSelect').val(),
            role_id: $('#editRoleSelect').val(),
            start_time: $('#editStartTime').val(),
            end_time: $('#editEndTime').val()
        };

        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(shiftData),
            xhrFields: {withCredentials: true},
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                // Dont hide spinner
                bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                loadSchedule(response.date);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                hideSpinner();
                let errorMessage;
                if (jqXHR.status == 500) {
                  errorMessage = "Failed to update the shift due to internal server errors. Please try again.";
                } else {
                  errorMessage = jqXHR.responseJSON?.Error || "Failed to update the shift. Please try again.";
                }
                showNotification(errorMessage, "danger");
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
                // First, hide the modal
                bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                loadSchedule(response.date);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                hideSpinner();
                let errorMessage;
                if (jqXHR.status == 500) {
                    errorMessage = "Failed to delete the shift due to internal server errors. Please try again.";
                } else {
                    errorMessage = jqXHR.responseJSON?.Error || "Failed to delete the shift. Please try again.";
                }
                showNotification(errorMessage, "danger");
            }
        });
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
        
        let apiUrl, apiMethod;
        if (mode === 'edit') {
            apiUrl = `${window.djangoURLs.manageStoreRole}${roleId}/`;
            apiMethod = 'PATCH';
        } else {
            apiUrl = window.djangoURLs.createStoreRole;
            apiMethod = 'POST';
        }

        $.ajax({
            url: apiUrl,
            method: apiMethod,
            contentType: 'application/json',
            data: JSON.stringify(roleData),
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                // Dont hide spinner
                setRoleFormToAddMode();
                updateStoreInformation(getSelectedStoreID());
            },
            error: function(jqXHR, textStatus, errorThrown) {
                hideSpinner();
                let errorMessage;
                if (jqXHR.status == 500) {
                  errorMessage = "Failed to set role due to internal server errors. Please try again.";
                } else {
                  errorMessage = jqXHR.responseJSON?.Error || "Failed to update role. Please try again.";
                }
                showNotification(errorMessage, "danger");
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
                error: function(jqXHR) {
                    hideSpinner();
                    let errorMessage = jqXHR.responseJSON?.Error || "Failed to delete the role. Please try again.";
                    showNotification(errorMessage, "danger");
                }
            });
        }
    });

    // COPY WEEK
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

    $('#deleteShiftBtn').on('click', function() {
        $(this).hide();
        $('#confirmDeleteBtn').show();
        $('#updateShiftBtn').prop('disabled', true);
    });

    $('#editShiftModal').on('hide.bs.modal', function () {
        resetDeleteButtons();
    });

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

    // --- Store Selector ---
    $('#storeSelectDropdown').on('change', function() {
        updateStoreInformation(getSelectedStoreID());
        loadSchedule(new Date().toLocaleDateString('sv-SE'));
    });

    // --- Initial Page Load ---
    updateStoreInformation(getSelectedStoreID());
    loadSchedule(new Date().toLocaleDateString('sv-SE'));
});

// Function to format date strings nicely (e.g., "Jun 9, 2025")
function formatWeekTitle(dateString) {
    const options = { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

function getFullDayName(dateString) {
    if (!dateString) return "";
    const options = { weekday: 'long', timeZone: 'UTC' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

function getShortDate(dateString) {
    if (!dateString) return "";
    const options = { month: 'short', day: 'numeric', timeZone: 'UTC' };
    return new Date(dateString).toLocaleDateString('en-US', options);
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
    const $editRoleSelect = $("#editRoleSelect");
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
        let employeeOptionsHtml = '';
        
        if (keys.length > 0) {
            keys.forEach(userID => {
            const name = response[userID];
            employeeOptionsHtml += `<option value="${userID}">${name}</option>`;
            });
        } else {
            employeeOptionsHtml = '<option value="" selected>No employees available</option>';
            showNotification("There are no employees associated to the selected store.", "danger");
        }

        $addEmployeeSelect.html(employeeOptionsHtml);
        $editEmployeeSelect.html(employeeOptionsHtml);

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

function resetDeleteButtons() {
    $('#confirmDeleteBtn').hide();
    $('#deleteShiftBtn').show();
    $('#updateShiftBtn').prop('disabled', false);
}

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