$(document).ready(function() {

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
        
        let finalApiUrl = baseApiUrl; // Use 'let' since it will be reassigned
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
                                    <small class="d-block">
                                        ${shift.start_time} – ${shift.end_time}
                                    </small>
                                    ${shift.role ? `<small class="text-muted d-block">${shift.role}</small>` : ''}
                                </div>
                            `;
                        });
                    } else {
                        shiftsHtml = '<p class="text-muted text-center my-4">No shifts</p>';
                    }

                    const dayCardHtml = `
                        <div class="card">
                            <div class="card-header text-center bg-indigo text-white">
                                ${formatDayHeader(dayString)}
                            </div>
                            <div class="card-body p-2">
                                ${shiftsHtml}
                            </div>
                        </div>
                    `;
                    scheduleContainer.append(dayCardHtml);
                });

                // 4. Update the navigation buttons' data attributes
                $('#previous-week-btn').data('week', data.previous_week);
                $('#next-week-btn').data('week', data.next_week);
            },
            error: function(error) {
                console.error("Error fetching schedule data:", error);
                $('#schedule-container').html('<p class="text-center text-danger">Could not load schedule. Please try again later.</p>');
            }
        });
    }

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

    // Initial load when the page is ready
    // Get week from URL query parameter if it exists, for deep linking
    const urlParams = new URLSearchParams(window.location.search);
    const initialWeek = urlParams.get('week');
    loadSchedule(initialWeek);
});