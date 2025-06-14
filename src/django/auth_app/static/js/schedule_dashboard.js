$(document).ready(function() {

    // --- CORE APPLICATION FUNCTIONS ---

    function loadSchedule(week) {
        console.log("Requesting schedule for week:", week, "and store ID:", getSelectedStoreID());
      
        $.ajax({
            url: `${window.djangoURLs.listAllStoreShifts}${getSelectedStoreID()}/?week=${week}`,
            method: 'GET',
            xhrFields: {withCredentials: true},
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(data) {
                console.log("Received data from server:", data);
                
                $('#schedule-week-title').text(`Week of ${formatWeekTitle(data.week_start)}`);
                const scheduleContainer = $('#schedule-container');
                scheduleContainer.empty();

                $.each(data.schedule || {}, function (dayDate, dayShifts) {
                    let shiftsHtml = '';
                    if (dayShifts && dayShifts.length > 0) {
                        dayShifts.forEach(shift => {
                            shiftsHtml += `
                                <div class="mb-2 p-2 border rounded shift-item" style="cursor: pointer;" data-shift-id="${shift.id}">
                                    <strong>${shift.employee_name}</strong><br>
                                    <small class="d-block">${shift.start_time} – ${shift.end_time}</small>
                                    ${shift.role_name ? `<small class="text-muted d-block">${shift.role_name} - ${shift.role_colour}</small>` : ''}
                                </div>`;
                        });
                    } else {
                        shiftsHtml = '<p class="text-muted text-center my-4">No shifts</p>';
                    }
                    
                    const dayCardHtml = `
                        <div class="card">
                            <div class="card-header text-center bg-indigo text-white d-flex justify-content-between align-items-center">
                                <span>${formatDayHeader(dayDate)}</span>
                                <button class="btn btn-sm btn-light add-shift-btn" data-day="${dayDate}">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                            <div class="card-body p-2">${shiftsHtml}</div>
                        </div>`;
                    scheduleContainer.append(dayCardHtml);
                });

                $('#previous-week-btn').data('week', data.prev_week);
                $('#next-week-btn').data('week', data.next_week);
            },
            error: function(jqXHR, textStatus, errorThrown) {
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

    $('#manageRolesBtn').on('click', function() {
        const manageRolesModal = new bootstrap.Modal(document.getElementById('manageRolesModal'));
        // refreshRolesList(); // Fetch the latest roles list
        manageRolesModal.show();
    });

    // --- MODAL/BUTTON EVENT HANDLERS ---
    $('#schedule-container').on('click', '.shift-item', function() {
        const shiftId = $(this).data('shift-id');

        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'GET',
            success: function(shiftData) {

                $('#editShiftForm').data('shift-date', shiftData.date); 
                $('#editShiftId').val(shiftData.id);
                $('#editShiftRole').val(shiftData.role_id);
                $('#editStartTime').val(shiftData.start_time);
                $('#editEndTime').val(shiftData.end_time);

                $('#editEmployeeSelect').val(shiftData.employee_id);
                
                const editModal = new bootstrap.Modal(document.getElementById('editShiftModal'));
                editModal.show();
            }
        });
    });

    // --- ADD SHIFT ---
    $('#saveShiftBtn').on('click', function() {
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
                const modal = bootstrap.Modal.getInstance(document.getElementById('addShiftModal'));
                modal.hide();
                form[0].reset();
                loadSchedule(new Date().toLocaleDateString('sv-SE')); 
            },
            error: function(jqXHR, textStatus, errorThrown) {
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
        const shiftId = $('#editShiftId').val();
        const shiftData = {
            date: $('#editShiftForm').data('shift-date'), 
            employee_id: $('#editEmployeeSelect').val(),
            role_id: $('#editShiftRole').val(),
            start_time: $('#editStartTime').val(),
            end_time: $('#editEndTime').val()
        };

        const updateUrl = `/api/v1/shifts/${shiftId}/`;
        $.ajax({
            url: `${window.djangoURLs.manageShift}${shiftId}/`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(shiftData),
            xhrFields: {withCredentials: true},
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                ////////////// EITHER RELOAD TABLE WITH loadSchedule(new Date().toLocaleDateString('sv-SE')); --- ORRR ---- REMOVE THE DIV CLIENT-SIDE (SO YOU DONT HAVE TO RELOAD)
            },
            error: function(jqXHR, textStatus, errorThrown) {
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
    $('#deleteShiftBtn').on('click', function() {
        // INSTEAD OF CONFIRM -- why not copy the js to have the inplace confirm button from the employee dashboard (manager page)
        if (confirm('Are you sure you want to delete this shift? This cannot be undone.')) {
            const shiftId = $('#editShiftId').val();

            $.ajax({
                url: `${window.djangoURLs.manageShift}${shiftId}/`,
                method: 'DELETE',
                xhrFields: {withCredentials: true},
                headers: {'X-CSRFToken': getCSRFToken()},
                success: function(response) {
                    // First, hide the modal
                    bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                    ////////////// EITHER RELOAD TABLE WITH loadSchedule(new Date().toLocaleDateString('sv-SE')); --- ORRR ---- REMOVE THE DIV CLIENT-SIDE (SO YOU DONT HAVE TO RELOAD)
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    let errorMessage;
                    if (jqXHR.status == 500) {
                      errorMessage = "Failed to delete the shift due to internal server errors. Please try again.";
                    } else {
                      errorMessage = jqXHR.responseJSON?.Error || "Failed to adelete the shift. Please try again.";
                    }
                    showNotification(errorMessage, "danger");
                }
            });
        }
    });

    // EDIT button click
    $('#existingRolesList').on('click', '.edit-role-btn', function() {
        const $listItem = $(this).closest('li');
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
        const $form = $(this);
        const mode = $form.data('mode') || 'add';
        const roleId = $form.data('role-id');

        const roleData = {
            name: $('#newRoleName').val(),
            description: $('#newRoleDescription').val(),
            colour_hex: $('#newRoleColor').val()
        };
        
        let apiUrl, apiMethod;
        if (mode === 'edit') {
            apiUrl = `/api/v1/roles/${roleId}/`;
            apiMethod = 'PUT';
        } else {
            apiUrl = `/api/v1/roles/`;
            apiMethod = 'POST';
        }

        $.ajax({
            url: apiUrl,
            method: apiMethod,
            contentType: 'application/json',
            data: JSON.stringify(roleData),
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                setRoleFormToAddMode();
                updateStoreInformation(getSelectedStoreID());
            },
            error: function() { alert('Failed to update role.'); }
        });
    });

    // DELETE button click
    $('#existingRolesList').on('click', '.delete-role-btn', function() {
        const $listItem = $(this).closest('li');
        const roleId = $listItem.data('role-id');
        const roleName = $listItem.data('role-name');

        if (confirm(`Are you sure you want to delete the role "${roleName}"?`)) {
            $.ajax({
                url: `/api/v1/roles/${roleId}/`,
                method: 'DELETE',
                headers: {'X-CSRFToken': getCSRFToken()},
                success: function() {
                    // --- THE FIX ---
                    // Also pass the current store ID here.
                    updateStoreInformation(getSelectedStoreID());
                },
                error: function() { alert('Failed to delete role.'); }
            });
        }
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
        console.log("--- Store Dropdown Changed ---");
        const selectedStoreId = getSelectedStoreID();
        
        updateStoreInformation(selectedStoreId);
    });

    // --- Initial Page Load ---
    console.log("--- Page Initializing ---");
    updateStoreInformation(getSelectedStoreID());
    loadSchedule(new Date().toLocaleDateString('sv-SE'));
});

// Function to format date strings nicely (e.g., "Jun 9, 2025")
function formatWeekTitle(dateString) {
    const options = { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

// Function to format day headers (e.g., "Mon, Jun 9")
function formatDayHeader(dateString) {
    const options = { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}


/**
 * Fetches employees and roles for the currently selected store and updates
 * the dropdowns in BOTH the 'Add Shift' and 'Edit Shift' modals.
 */
function updateStoreInformation(storeId) {
    if (storeId === null) return;
    console.log("updateStoreInformation: Updating modal dropdowns for store:", storeId);

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
        xhrFields: {
        withCredentials: true
        },
        headers: {
        'X-CSRFToken': getCSRFToken(),
        },

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
        xhrFields: {
        withCredentials: true
        },
        headers: {
        'X-CSRFToken': getCSRFToken(),
        },

        success: function(resp) {
        let roleOptionsHtml = ''; // For the dropdowns
        $existingRolesList.empty(); // Clear the management list

        if (resp.data && resp.data.length > 0) {
            resp.data.forEach(role => {
                // Build options for the <select> dropdowns
                roleOptionsHtml += `<option value="${role.id}">${role.name}</option>`;
                
                // Build the interactive list for the management modal
                const roleListItemHtml = `
                    <li class="list-group-item d-flex justify-content-between align-items-center" data-role-id="${role.id}" data-role-name="${role.name}" data-role-description="${role.description || ''}" data-role-color="${role.colour}">
                        <div>
                            <span class="d-inline-block me-2" style="width: 20px; height: 20px; background-color: ${role.colour}; border: 1px solid #ccc; border-radius: 4px;"></span>
                            ${role.name}
                        </div>
                        <div>
                            <button class="btn btn-sm btn-outline-secondary edit-role-btn me-2">Edit</button>
                            <button class="btn btn-sm btn-outline-danger delete-role-btn">Delete</button>
                        </div>
                    </li>`;
                $existingRolesList.append(roleListItemHtml);
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