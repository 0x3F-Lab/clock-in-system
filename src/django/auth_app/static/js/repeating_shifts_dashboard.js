$(document).ready(function() {
    // Handle delete shift button and its confirmation
    handleDeleteShiftBtn();

    // Handle functionality of switching between weeks
    handleWeekSwitching();

    // Handle shift edits, deletes and creations
    handleShiftModification();

    // Handle table controls submission
    $('#tableControllerSubmit').on('click', () => {
      if ($('#useLegacy').is(':checked')) {
          $('#paginationController').addClass('d-none');
      } else {
          $('#paginationController').removeClass('d-none');
      }
      resetPaginationValues();
      loadSchedule();
    });

    // Update table controller icon on collapse/show
    $('#tableControllerCollapse').on('show.bs.collapse', function () {
      $('#tableControllerToggleIcon').removeClass('fa-chevron-right').addClass('fa-chevron-down');
    });

    $('#tableControllerCollapse').on('hide.bs.collapse', function () {
      $('#tableControllerToggleIcon').removeClass('fa-chevron-down').addClass('fa-chevron-right');
    });

    // --- Store Selector ---
    $('#storeSelectDropdown').on('change', function() {
        updateStoreInformation();
        loadSchedule();
    });

    // --- Initial Page Load ---
    updateStoreInformation();
    loadSchedule();

    // Activate the pagination system (set the update function)
    handlePagination({updateFunc: loadSchedule});

    // Add page reloader to force reload after period of inactivity
    setupVisibilityReload(30); // 30 minutes
});


function handleShiftModification() {
    // CLICK `+` ON A CERTAIN DAY -> OPEN EDIT MODAL AND SET TO CREATION
    $('.schedule-container').on('click', '.add-repeating-shift-btn', function() {
        const day = $(this).data('day');
        const week = $(this).data('week');
        $('#repeatingStartWeekday').val(day);
        $('.repeating-week-checkbox').prop('checked', false);
        $(`#repeatingActiveWeek${week}`).prop('checked', true).trigger('change');
        $('#editModalSelectedEmployeeID').val(''); // Select no employee
        $('#repeatingShiftId').val(''); // Set NO ID -> CREATION MODE
        $('#repeatingRole').val('');
        $('#repeatingStartTime').val('');
        $('#repeatingEndTime').val('');
        $('#repeatingComment').val('');
        $('#deleteRepeatingShiftBtn').addClass('d-none'); // Hide 'Delete' button
        
        const addShiftModal = new bootstrap.Modal(document.getElementById('editModal'));
        addShiftModal.show();
    });

    // CLICK ON EXISTING SHIFT -> OPEN EDIT MODAL AND SET TO MODIFICATION
    $('.schedule-container').on('click', '.shift-item', function() {
        showSpinner();
        const shiftId = $(this).data('shift-id');

        // Get shift info -> ENSURE ITS ALWAYS UP TO DATE
        $.ajax({
            url: `${window.djangoURLs.manageRepeatingShift}${shiftId}/`,
            method: 'GET',
            headers: { 'X-CSRFToken': getCSRFToken() },
            xhrFields: { withCredentials: true },
            success: function(shiftData) {
              $('#repeatingStartWeekday').val(shiftData.start_weekday);
              $('#editModalSelectedEmployeeID').val(shiftData.employee_id);
              $('#repeatingShiftId').val(shiftData.shift_id);
              $('#repeatingRole').val(shiftData.role_id);
              $('#repeatingStartTime').val(shiftData.start_time);
              $('#repeatingEndTime').val(shiftData.end_time);
              $('#repeatingComment').val(shiftData.comment);
              $('#deleteRepeatingShiftBtn').removeClass('d-none');

              $('.repeating-week-checkbox').prop('checked', false);
              $.each(shiftData.active_weeks, function(_, week) {
                  $(`#repeatingActiveWeek${week}`).prop('checked', true).trigger('change');
              });
              
              hideSpinner();
              const editModal = new bootstrap.Modal(document.getElementById('editModal'));
              editModal.show();
            },
            error: function(jqXHR) { handleAjaxError(jqXHR, "Failed to get shift information"); }
        });
    });

    // CLICK ON EMPLOYEE NAME -> OPEN MODEL AND SET TO CREATION
    $(document).on('click', '.employee-name-cell.cursor-pointer', function () {
        const id = $(this).data('id') || '';
        // Reset form and ONLY SET EMPLOYEE
        $('.repeating-week-checkbox').prop('checked', false);
        $('#repeatingStartWeekday').val('');
        $('#editModalSelectedEmployeeID').val(id);
        $('#repeatingShiftId').val('');
        $('#repeatingRole').val('');
        $('#repeatingStartTime').val('');
        $('#repeatingEndTime').val('');
        $('#repeatingComment').val('');
        $('#deleteRepeatingShiftBtn').addClass('d-none'); // Hide 'Delete' button
        
        const addShiftModal = new bootstrap.Modal(document.getElementById('editModal'));
        addShiftModal.show();
    });

    // --- CREATE/EDIT SHIFT FORM SUBMISSION ---
    $('#saveRepeatingShiftBtn').on('click', function() {
        const form = $('#repeatingShiftForm');
        active_week_selection = $('.repeating-week-checkbox:checked')
        .map(function () {
            return ensureSafeInt(this.value, 1, 4);
        })
        .get();

        const formData = {
            employee_id: form.find('#editModalSelectedEmployeeID').val(),
            role_id: form.find('#repeatingRole').val(),
            start_weekday: form.find('#repeatingStartWeekday').val(),
            start_time: form.find('#repeatingStartTime').val(),
            end_time: form.find('#repeatingEndTime').val(),
            comment: form.find('#repeatingComment').val(),
            active_weeks: active_week_selection
        };

        console.log(formData);
        if (!formData.employee_id || !formData.start_time || !formData.end_time || !formData.start_weekday || formData.active_weeks.length === 0) {
            showNotification('Cannot submit form without all required fields.', 'warning');
            return;
        }

        const shiftId = $('#repeatingShiftId').val();
        
        // EITHER CREATE OR UPDATE EXISTING SHIFT DEPENDING IF shiftID SET
        showSpinner();
        $.ajax({
            url: !isEmpty(shiftId) ? `${window.djangoURLs.manageRepeatingShift}${shiftId}/` : `${window.djangoURLs.createRepeatingShift}${getSelectedStoreID()}/`,
            method: !isEmpty(shiftId) ? 'POST' : 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            headers: { 'X-CSRFToken': getCSRFToken() },
            xhrFields: { withCredentials: true },
            success: function(response) {
                // Dont hide spinner
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                form[0].reset();
                loadSchedule();
                showNotification(!isEmpty(shiftId) ? "Successfully updated a repeating shift." : "Successfully created a repeating shift.", "success");
            },
            error: function(jqXHR, textStatus, errorThrown) {
                handleAjaxError(jqXHR, !isEmpty(shiftId) ? "Failed to update the repeating shift" : "Failed to create the repeating shift");
            }
        });
    });

    // --- DELETE SHIFT ---
    $('#confirmDeleteRepeatingShiftBtn').on('click', function() {
        showSpinner();
        const shiftId = $('#repeatingShiftId').val();

        $.ajax({
            url: `${window.djangoURLs.manageRepeatingShift}${shiftId}/`,
            method: 'DELETE',
            xhrFields: {withCredentials: true},
            headers: {'X-CSRFToken': getCSRFToken()},
            success: function(response) {
                // Dont hide spinner
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                loadSchedule();
                showNotification("Successfully deleted a repeating shift.", "success");
            },
            error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to delete the repeating shift"); }
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


function loadSchedule() {
    const storeId = getSelectedStoreID();

    // Get all filter and sort values
    const sort = $('#sortFields input[type="radio"]:checked').val();
    const filterNames = $('#filterNames').val();
    const filterRoles = $('#filterRoles').val();
    const hideDeactive = $('#hideDeactivated').is(':checked');
    const hideResigned = $('#hideResigned').is(':checked');
    const offset = getPaginationOffset();
    const limit = getPaginationLimit();

    showSpinner();
    $.ajax({
        // The URL now includes the 'legacy' parameter to tell the backend which data to send
        url: `${window.djangoURLs.listRepeatingShifts}${storeId}/?offset=${offset}&limit=${limit}&sort=${sort}&hide_deactive=${hideDeactive}&hide_resign=${hideResigned}&filter_names=${filterNames}&filter_roles=${filterRoles}`,
        method: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},
        success: function(data) {
            hideSpinner();
            renderScheduleTable(data);
            setPaginationValues(data.offset, data.total);
            
            $('[data-bs-toggle="tooltip"]').tooltip();
        },
        error: function(jqXHR) {
            $('.schedule-container').html(`
                <div class="d-flex flex-row gap-3 justify-content-around align-items-center bg-danger text-white text-center rounded p-2 w-100 mb-2">
                    <div><i class="fas fa-circle-exclamation"></i></div>
                    <div>
                        <p class="m-0">Error loading roster. Please try again later.</p>
                    </div>
                </div>`);
            handleAjaxError(jqXHR, "Failed to load the repeating shifts");
            setPaginationValues(0, 0); // Set pagination values to ensure selector doesnt become bugged
        }
    });
}


function renderScheduleTable(data) {
    const days = {0:"Monday", 1:"Tuesday", 2:"Wednesday", 3:"Thursday", 4:"Friday", 5:"Saturday", 6:"Sunday"};
    const mondayWeekOne = data['week_one_next_date'];
    console.log(mondayWeekOne)

    $.each([1,2,3,4], function(_, week) {
        let tableHtml = `
        <table class="schedule-table-view">
          <thead>
            <tr>
              <th class="employee-name-cell">Employee</th>
              ${Object.entries(days).map(([dayIndex, dayWord]) => `
                <th>
                  ${dayWord}<br>
                  <small class="day-date">${getDateForCycleWeek(mondayWeekOne, week, dayIndex)}</small>
                  <button class="btn add-shift-btn" data-day="${dayIndex}" data-week="${week}" title="Add repeating shift for this day">
                    <i class="fas fa-plus"></i>
                  </button>
                </th>
              `).join('')}
            </tr>
          </thead>
        <tbody>`;

        // Go through a week for every employee
        $.each(data.schedule, function (employeeName, employeeData) {
            const weekData = employeeData[`week${week}`];

            if (weekData && Object.entries(weekData).length > 0) {
                tableHtml += `<tr><td class="employee-name-cell cursor-pointer" data-id="${employeeData['id']}">${employeeName}</td>`;

                // Go through every day for that week
                $.each([0,1,2,3,4,5,6], function(_, day) {
                    const dayData = weekData[day];

                    if (dayData && Object.entries(weekData).length > 0) {
                        // Go through every shift for that day
                        $.each(dayData, function(_, shift) {
                            const duration = calculateDuration(shift.start_time, shift.end_time);
                            const borderColor = shift.role_colour || '#adb5bd';

                            tableHtml += `
                            <td class="shift-cell">
                              <div class="shift-item cursor-pointer mb-2 position-relative" style="border-left: 8px solid ${borderColor}; background-color: #f8f9fa;" data-shift-id="${shift.id}">
                                  <div class="shift-item-details">
                                      ${shift.has_comment ? '<span class="danger-tooltip-icon position-absolute p-1" data-bs-toggle="tooltip" title="This shift has a comment">C</span>' : ''}
                                      <span>🕒 ${shift.start_time} – ${shift.end_time}</span>
                                      <span>⌛ ${duration}</span>
                                      ${shift.role_name ? `<span>👤 ${shift.role_name}</span>` : ''}
                                  </div>
                              </div>
                            </td>`;
                        });

                    } else{
                      tableHtml += `<td></td>`;
                    }
                });

                tableHtml +='</tr>';

            } else {
              tableHtml += `
              <tr>
                <td class="employee-name-cell cursor-pointer" data-id="${employeeData['id']}">${employeeName}</td>
                <td></td><td></td><td></td><td></td><td></td><td></td><td></td>
              </tr>`
            }
        });

        tableHtml += `</tbody></table>`;

        $(`#schedule-container-week-${week}`).html(tableHtml);
    });
}


// Fetches employees and roles for the currently selected store and updates the dropdown
function updateStoreInformation() {
    showSpinner();

    const $editEmployeeList = $("#editModalEmployeeList");
    const $editShiftSelect = $("#repeatingRole");

    // Clear everything first
    $editEmployeeList.empty();
    $editShiftSelect.html(`<option value="" selected>No Role</option>`);

    // Fetch employees names
    $.ajax({
        url: `${window.djangoURLs.listStoreEmployeeNames}?store_id=${getSelectedStoreID()}&only_active=false`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},

        success: function(response) {
            const employeeList = response.names;

            if (Array.isArray(employeeList) && employeeList.length > 0) {
                employeeList.forEach(employee => {
                    $editEmployeeList.append(
                        `<li class="list-group-item cursor-pointer" data-id="${employee.id}">${employee.name}</li>`
                    );
                });
            } else {
                $editEmployeeList.append('<option value="">No Employees available</option>');
                showNotification("There are no employees associated to the selected store.", "danger");
            }
        },

        error: function(jqXHR, textStatus, errorThrown) {
            handleAjaxError(jqXHR, "Failed to load employee names", false);
            $editEmployeeList.append('<option value="">Error getting employees</option>');
        }
    });

    // Fetch store roles
    $.ajax({
        url: `${window.djangoURLs.listStoreRoles}${getSelectedStoreID()}/`,
        type: 'GET',
        xhrFields: {withCredentials: true},
        headers: {'X-CSRFToken': getCSRFToken()},

        success: function(resp) {
            let roleOptionsHtml = '';

            if (resp.data && resp.data.length > 0) {
                resp.data.forEach(role => {
                    roleOptionsHtml += `<option value="${role.id}">${role.name}</option>`;
                });
            }
            $editShiftSelect.append(roleOptionsHtml);
        },

        error: function(jqXHR, textStatus, errorThrown) { handleAjaxError(jqXHR, "Failed to load store roles", false); }
    });

    hideSpinner();
}


function handleDeleteShiftBtn() {
    $('#deleteRepeatingShiftBtn').on('click', () => {
        $('#confirmDeleteRepeatingShiftBtn').removeClass('d-none');
        $('#deleteRepeatingShiftBtn').addClass('d-none');
    });

    $('#editModal').on('hide.bs.modal', () => {
        $('#confirmDeleteRepeatingShiftBtn').addClass('d-none');
        $('#deleteRepeatingShiftBtn').removeClass('d-none');
    });
}


function handleWeekSwitching() {
    $('#previous-week-btn').on('click', function(e) {
        e.preventDefault();
        const currentWeek = ensureSafeInt($('.repeating-week:not(.d-none)').first().data('week'), 1, 4);
        const newWeek = ((currentWeek + 2) % 4) + 1;
        
        $('.repeating-week').addClass('d-none');
        $(`#repeating-week-${newWeek}`).removeClass('d-none');
        $('#schedule-week-title').text(`Cycle Week ${newWeek} of 4`);
    });

    $('#next-week-btn').on('click', function(e) {
        e.preventDefault();
        const currentWeek = ensureSafeInt($('.repeating-week:not(.d-none)').first().data('week'), 1, 4);
        const newWeek = (currentWeek % 4) + 1;
        
        $('.repeating-week').addClass('d-none');
        $(`#repeating-week-${newWeek}`).removeClass('d-none');
        $('#schedule-week-title').text(`Cycle Week ${newWeek} of 4`);
    });
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

function getDateForCycleWeek(mondayWeekOne, weekNumber, dayIndex) {
    const baseDate = new Date(Date.parse(mondayWeekOne));

    const weeksOffset = (weekNumber - 1) * 7;
    const totalDays = weeksOffset + ensureSafeInt(dayIndex, 0, 6);

    const resultDate = new Date(baseDate);
    resultDate.setDate(baseDate.getDate() + totalDays);

    // Format as DD/MM/YYYY
    const dd = String(resultDate.getDate()).padStart(2, '0');
    const mm = String(resultDate.getMonth() + 1).padStart(2, '0');
    const yyyy = resultDate.getFullYear();

    return `${dd}/${mm}/${yyyy}`;
}