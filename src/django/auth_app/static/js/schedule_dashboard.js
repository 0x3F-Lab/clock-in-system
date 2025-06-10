$(document).ready(function() {

    // Get the CSRF token from the template
    const csrftoken = $('[name=csrfmiddlewaretoken]').val();

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

    // Main function to fetch and render the schedule
    function loadSchedule(week) {
        let baseApiUrl = $('#schedule-container').data('api-url');
        let finalApiUrl = baseApiUrl;
        if (week) {
            finalApiUrl += `?week=${week}`;
        }

        $.ajax({
            url: finalApiUrl,
            method: 'GET',
            success: function(data) {
                $('#schedule-week-title').text(`Week of ${formatWeekTitle(data.week_start)}`);
                const scheduleContainer = $('#schedule-container');
                scheduleContainer.empty();

                data.days.forEach(dayString => {
                    const dayShifts = data.schedule_data[dayString];
                    let shiftsHtml = '';
                    if (dayShifts.length > 0) {
                        dayShifts.forEach(shift => {
                            shiftsHtml += `
                                <div class="mb-2 p-2 border rounded">
                                    <strong>${shift.employee_name}</strong><br>
                                    <small class="d-block">${shift.start_time} – ${shift.end_time}</small>
                                    ${shift.role ? `<small class="text-muted d-block">${shift.role}</small>` : ''}
                                </div>`;
                        });
                    } else {
                        shiftsHtml = '<p class="text-muted text-center my-4">No shifts</p>';
                    }

                    // SHIFT ADD BUTTON
                    const dayCardHtml = `
                        <div class="card">
                            <div class="card-header text-center bg-indigo text-white d-flex justify-content-between align-items-center">
                                <span>${formatDayHeader(dayString)}</span>
                                <button class="btn btn-sm btn-light add-shift-btn" data-day="${dayString}">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                            <div class="card-body p-2">${shiftsHtml}</div>
                        </div>`;
                    scheduleContainer.append(dayCardHtml);
                });

                $('#previous-week-btn').data('week', data.previous_week);
                $('#next-week-btn').data('week', data.next_week);
            },
            error: function(error) {
                console.error("Error fetching schedule data:", error);
                $('#schedule-container').html('<p class="text-center text-danger">Could not load schedule. Please try again later.</p>');
            }
        });
    }

    // ADDING NEW SHIFTS
    $('#schedule-container').on('click', '.add-shift-btn', function() {
        const day = $(this).data('day');
        $('#shiftDate').val(day); // Set the hidden date input

        // Fetch employees and populate the dropdown
        const employeeApiUrl = $('#schedule-container').data('employee-api-url');
        $.ajax({
            url: employeeApiUrl,
            method: 'GET',
            success: function(data) {
                const employeeSelect = $('#employeeSelect');
                employeeSelect.empty(); // Clear previous options
                employeeSelect.append('<option value="" disabled selected>Select an employee...</option>');
                data.employees.forEach(emp => {
                    employeeSelect.append(`<option value="${emp.id}">${emp.full_name}</option>`);
                });
            }
        });

        const addShiftModal = new bootstrap.Modal(document.getElementById('addShiftModal'));
        addShiftModal.show();
    });

    // 2. Handle the form submission
    $('#saveShiftBtn').on('click', function() {
        const form = $('#addShiftForm');
        const formData = {
            date: form.find('#shiftDate').val(),
            employee: form.find('#employeeSelect').val(),
            role: form.find('#shiftRole').val(),
            start_time: form.find('#startTime').val(),
            end_time: form.find('#endTime').val()
        };

        // Basic validation
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
            headers: {'X-CSRFToken': csrftoken}, // Include CSRF token
            success: function(response) {
                // Hide the modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('addShiftModal'));
                modal.hide();
                
                // Reset the form for next time
                form[0].reset();

                // Reload the schedule to show the new shift
                const currentWeek = new URLSearchParams(window.location.search).get('week');
                loadSchedule(currentWeek); 
            },
            error: function(error) {
                alert('Error adding shift: ' + JSON.stringify(error.responseJSON.errors));
                console.error("Error adding shift:", error);
            }
        });
    });

    // Event listener for the "Previous Week" button
    $('#previous-week-btn').on('click', function(e) {
        e.preventDefault();
        const week = $(this).data('week');
        loadSchedule(week);
    });

    // Event listener for the "Next Week" button
    $('#next-week-btn').on('click', function(e) {
        e.preventDefault();
        const week = $(this).data('week');
        loadSchedule(week);
    });

    // Initial load
    const urlParams = new URLSearchParams(window.location.search);
    const initialWeek = urlParams.get('week');
    loadSchedule(initialWeek);
});