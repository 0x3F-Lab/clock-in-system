$(document).ready(function() {

    const csrftoken = $('[name=csrfmiddlewaretoken]').val();

    // --- CORE APPLICATION FUNCTIONS ---

    function loadSchedule(week, storeId) {
        console.log("Requesting schedule for week:", week, "and store ID:", storeId);
        let baseApiUrl = $('#schedule-container').data('api-url');
        
        
        let params = new URLSearchParams(); 
        
        
        if (week) {
            params.append('week', week);
        }
        
        if (storeId !== null && storeId !== undefined) { 
            params.append('store_id', storeId);
        }
        
        const finalApiUrl = `${baseApiUrl}?${params.toString()}`;

        $.ajax({
            url: finalApiUrl,
            method: 'GET',
            success: function(data) {
                console.log("Received data from server:", data);
                
                $('#schedule-week-title').text(`Week of ${formatWeekTitle(data.week_start)}`);
                const scheduleContainer = $('#schedule-container');
                scheduleContainer.empty();

                if (data.days && data.days.length > 0) {
                    data.days.forEach(dayString => {
                        const dayShifts = data.schedule_data[dayString];
                        let shiftsHtml = '';
                        if (dayShifts && dayShifts.length > 0) {
                            dayShifts.forEach(shift => {
                                shiftsHtml += `
                                    <div class="mb-2 p-2 border rounded shift-item" style="cursor: pointer;" data-shift-id="${shift.id}">
                                        <strong>${shift.employee_name}</strong><br>
                                        <small class="d-block">${shift.start_time} – ${shift.end_time}</small>
                                        ${shift.role ? `<small class="text-muted d-block">${shift.role}</small>` : ''}
                                    </div>`;
                            });
                        } else {
                            shiftsHtml = '<p class="text-muted text-center my-4">No shifts</p>';
                        }

                        const dayCardHtml = `
                            <div class="card">
                                <div class="card-header text-center bg-indigo text-white d-flex justify-content-between align-items-center">
                                    <span>${formatDayHeader(dayString)}</span>
                                    <button class="btn btn-sm btn-light add-shift-btn" data-day="${dayString}">
                                        <i class="fas fa-plus"></i> +
                                    </button>
                                </div>
                                <div class="card-body p-2">${shiftsHtml}</div>
                            </div>`;
                        scheduleContainer.append(dayCardHtml);
                    });
                } else {
                    scheduleContainer.html('<p class="text-center">No schedule data to display. Please select a store.</p>');
                }

                $('#previous-week-btn').data('week', data.previous_week);
                $('#next-week-btn').data('week', data.next_week);
            },
            error: function() {
                $('#schedule-container').html('<p class="text-center text-danger">Error loading schedule.</p>');
            }
        });
    }

    // Dedicated function to handle updating the session and reloading the schedule.
    function updateActiveStoreAndReload(storeId) {
        if (storeId === null) { 
            console.log("No valid store ID provided. Clearing schedule.");
            $('#schedule-container').html('<p class="text-center">Please select a store to view the schedule.</p>');
            return; // Stop if no store is selected
        }

        const setStoreUrl = $('#schedule-container').data('set-store-url');
        console.log("Attempting to set active store to:", storeId);

        $.ajax({
            url: setStoreUrl,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ store_id: storeId }),
            headers: {'X-CSRFToken': csrftoken},
            success: function(response) {
                console.log("Successfully set active store. Now loading schedule...");
                
                // On success, reload the schedule with the new store
                const currentWeek = new URLSearchParams(window.location.search).get('week');
                loadSchedule(currentWeek, storeId);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Failed to set active store.", textStatus, errorThrown);
                alert('Could not update selected store. Please try again.');
            }
        });
    }

    // --- MODAL/BUTTON EVENT HANDLERS ---
    $('#schedule-container').on('click', '.shift-item', function() {
        const shiftId = $(this).data('shift-id');
        const shiftDetailUrl = `/api/v1/shifts/${shiftId}/`; 

        $.ajax({
            url: shiftDetailUrl,
            method: 'GET',
            success: function(shiftData) {

                $('#editShiftForm').data('shift-date', shiftData.date); 
                $('#editShiftId').val(shiftData.id);
                $('#editShiftRole').val(shiftData.role);
                $('#editStartTime').val(shiftData.start_time);
                $('#editEndTime').val(shiftData.end_time);

                $('#editEmployeeSelect').val(shiftData.employee);
                
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
            employee: form.find('#employeeSelect').val(),
            role: form.find('#shiftRole').val(),
            start_time: form.find('#startTime').val(),
            end_time: form.find('#endTime').val()
        };

        if (!formData.date || !formData.employee || !formData.start_time || !formData.end_time) {
            alert('Please fill out all required fields.');
            return;
        }

        const apiUrl = $('#schedule-container').data('api-url');
        
        $.ajax({
            url: apiUrl,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            headers: {'X-CSRFToken': csrftoken}, 
            success: function(response) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('addShiftModal'));
                modal.hide();
                form[0].reset();

                const currentWeek = new URLSearchParams(window.location.search).get('week');
                const currentStoreId = getSelectedStoreID();
                loadSchedule(currentWeek, currentStoreId); 
            },
            error: function(error) {
                if(error.responseJSON && error.responseJSON.errors) {
                    alert('Error adding shift: ' + JSON.stringify(error.responseJSON.errors));
                } else {
                    alert('An unknown error occurred while adding the shift.');
                }
                console.error("Error adding shift:", error);
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
            employee: $('#editEmployeeSelect').val(),
            role: $('#editShiftRole').val(),
            start_time: $('#editStartTime').val(),
            end_time: $('#editEndTime').val()
        };

        const updateUrl = `/api/v1/shifts/${shiftId}/`;
        $.ajax({
            url: updateUrl,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(shiftData),
            headers: {'X-CSRFToken': csrftoken},
            success: function(response) {
                bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                const currentWeek = new URLSearchParams(window.location.search).get('week');
                const currentStoreId = getSelectedStoreID();
                loadSchedule(currentWeek, currentStoreId);
            },
            error: function(error) {
                alert('Error updating shift: ' + JSON.stringify(error.responseJSON.errors));
            }
        });
    });

    // --- DELETE SHIFT ---
    $('#deleteShiftBtn').on('click', function() {
        if (confirm('Are you sure you want to delete this shift? This cannot be undone.')) {
            const shiftId = $('#editShiftId').val();
            const deleteUrl = `/api/v1/shifts/${shiftId}/`;

            $.ajax({
                url: deleteUrl,
                method: 'DELETE',
                headers: {'X-CSRFToken': csrftoken}, // Ensure 'csrftoken' is defined
                success: function(response) {
                    // First, hide the modal
                    bootstrap.Modal.getInstance(document.getElementById('editShiftModal')).hide();
                    
                    
                    const currentWeek = new URLSearchParams(window.location.search).get('week');
                    const currentStoreId = getSelectedStoreID(); // Get the currently selected store
                    
                    loadSchedule(currentWeek, currentStoreId);
                },
                error: function(error) {
                    alert('Error deleting shift.');
                }
            });
        }
    });

    // --- Shift Previous Week --- 
    $('#previous-week-btn').on('click', function(e) {
        e.preventDefault();
        const previousWeek = $(this).data('week');
        const currentStoreId = getSelectedStoreID();
        
        loadSchedule(previousWeek, currentStoreId);
    });

    // --- Shift Next Week ---
    $('#next-week-btn').on('click', function(e) {
        e.preventDefault();
        const nextWeek = $(this).data('week');
        const currentStoreId = getSelectedStoreID();
        
        loadSchedule(nextWeek, currentStoreId);
    });

    // --- Store Selector ---
    $('#storeSelectDropdown').on('change', function() {
        console.log("--- Store Dropdown Changed ---");
        const selectedStoreId = getSelectedStoreID();
        
        updateActiveStoreAndReload(selectedStoreId);
        updateStoreInformation(selectedStoreId);
    });

    // --- Initial Page Load ---
    console.log("--- Page Initializing ---");
    const initialStoreId = getSelectedStoreID();
    if (initialStoreId !== null) {
        updateActiveStoreAndReload(initialStoreId);
        updateStoreInformation(initialStoreId);
    } else {
        $('#schedule-container').html('<p class="text-center">Please select a store to view the schedule.</p>');
    }
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

    $addEmployeeSelect.html("");
    $editEmployeeSelect.html("");
    $addRoleSelect.html(`<option value="" selected>No Role</option>`);
    $editRoleSelect.html(`<option value="" selected>No Role</option>`);

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
        let roleOptionsHtml = '';
        
        if (resp.data && resp.data.length > 0) {
            resp.data.forEach(role => {
            roleOptionsHtml += `<option value="${role.id}">${role.name}</option>`;
            });
        } else {
            showNotification("There are no ROLES associated to the selected store.", "info");
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