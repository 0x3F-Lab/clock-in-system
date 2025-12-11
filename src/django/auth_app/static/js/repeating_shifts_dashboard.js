document.addEventListener("DOMContentLoaded", () => {
  const storeSelect = document.getElementById("storeSelectDropdown");
  const weekHeaderTitle = document.getElementById("schedule-week-title");
  const previousWeekBtn = document.getElementById("previous-week-btn");
  const nextWeekBtn = document.getElementById("next-week-btn");
  const tableControllerSubmit = document.getElementById("tableControllerSubmit");

  const api = window.djangoURLs || {};

  let currentWeek = 1;
  let repeatingSchedule = null;
  let currentStoreId = null;
  let employees = [];
  let roles = [];


    function openCreateRepeatingShiftModal(weekNum, dayIndex) {
    
        $('#repeatingEditModalLabel').text("Add Repeating Shift");
        $('#repeatingShiftId').val('');
        $('#repeatingShiftStoreId').val(currentStoreId);
        $('#repeatingStartWeekday').val(dayIndex);
        $('#repeatingEndWeekday').val(dayIndex);
        $('#repeatingStartTime').val('');
        $('#repeatingEndTime').val('');
        $('#repeatingRole').val('');
        $('#repeatingComment').val('');
        $('#repeatingSelectedEmployeeID').val('');
    
        $('.repeating-week-checkbox').each(function () {
            $(this).prop('checked', parseInt($(this).val()) === weekNum);
        });
      
        $('#saveRepeatingShiftBtn').removeClass('d-none');
        $('#deleteRepeatingShiftBtn').addClass('d-none');
        $('#confirmDeleteRepeatingShiftBtn').addClass('d-none');
      
        bootstrap.Modal.getOrCreateInstance('#repeatingEditModal').show();
    }


    function openEditRepeatingShiftModal(shiftId) {
        $.get(`${api.manageRepeatingShift}/${shiftId}`, function(data) {
        
            $('#repeatingEditModalLabel').text("Edit Repeating Shift");
        
            const primaryId = data.id ?? data.shift_id;
        
            $('#repeatingShiftId').val(primaryId);
            $('#repeatingShiftStoreId').val(data.store_id);
        
            $('#repeatingSelectedEmployeeID').val(
                data.employee_id ??
                data.employee ??
                data.employeeId ??
                data.emp_id ??
                ''
            );
          
            renderEmployeeList($('#repeatingEmployeeSearchBar').val() || "");

            $('#repeatingStartWeekday').val(data.start_weekday);
            $('#repeatingEndWeekday').val(data.end_weekday);
            $('#repeatingStartTime').val(data.start_time.slice(0,5));
            $('#repeatingEndTime').val(data.end_time.slice(0,5));
            $('#repeatingRole').val(data.role_id || '');
            $('#repeatingComment').val(data.comment || '');
          
            const weeks = (data.active_weeks || []).map(Number);
            $('.repeating-week-checkbox').each(function () {
                $(this).prop('checked', weeks.includes(parseInt($(this).val())));
            });
          
            $('#saveRepeatingShiftBtn').removeClass('d-none');
            $('#deleteRepeatingShiftBtn').removeClass('d-none');
            $('#confirmDeleteRepeatingShiftBtn').addClass('d-none');
          
            bootstrap.Modal.getOrCreateInstance('#repeatingEditModal').show();
        });
    }



    
    $('#saveRepeatingShiftBtn').on('click', async function () {
    
        const payload = {
            employee_id: $('#repeatingSelectedEmployeeID').val(),
            start_weekday: parseInt($('#repeatingStartWeekday').val(), 10),
            end_weekday: parseInt($('#repeatingEndWeekday').val(), 10),
            start_time: $('#repeatingStartTime').val(),
            end_time: $('#repeatingEndTime').val(),
            active_weeks: $('.repeating-week-checkbox:checked').map(function () {
                return parseInt(this.value);
            }).get(),
            role_id: $('#repeatingRole').val(),
            comment: $('#repeatingComment').val().trim(),
        };
      
        const shiftId = $('#repeatingShiftId').val();
      
        if (shiftId) {
            await updateRepeatingShift(shiftId, payload);
        } else {
            await createRepeatingShift(payload);
        }
      
        const modal = bootstrap.Modal.getOrCreateInstance('#repeatingEditModal');
        modal.hide();
      
        fetchRepeatingSchedule(currentStoreId);
    });


    $('#deleteRepeatingShiftBtn').on('click', function () {
        $('#deleteRepeatingShiftBtn').addClass('d-none');
        $('#confirmDeleteRepeatingShiftBtn').removeClass('d-none');
    });

    $('#confirmDeleteRepeatingShiftBtn').on('click', async function () {
        const shiftId = $('#repeatingShiftId').val();
        if (!shiftId) return;
    
        try {
            await deleteRepeatingShift(shiftId);
            await fetchRepeatingSchedule(currentStoreId);
            bootstrap.Modal.getOrCreateInstance('#repeatingEditModal').hide();
        } catch (err) {
            console.error("Failed to delete repeating shift:", err);
        } finally {
            $('#deleteRepeatingShiftBtn').removeClass('d-none');
            $('#confirmDeleteRepeatingShiftBtn').addClass('d-none');
        }
    });



    function renderEmployeeList(filterText = "") {
    
        const $list = $('#repeatingEmployeeList');
        if ($list.length === 0) return;
    
        const term = filterText.trim().toLowerCase();
    
        const filtered = employees.filter(emp => {
            const name = (emp.name || "").toLowerCase();
            return !term || name.includes(term);
        });
      
        $list.empty();
      
        if (filtered.length === 0) {
            $list.html('<li class="list-group-item text-center text-muted">No employees found</li>');
            return;
        }
      
        const selectedId = $('#repeatingSelectedEmployeeID').val() || "";
      
        filtered.forEach(emp => {
            const thisId = String(emp.id);
        
            const $li = $(`
                <li class="list-group-item list-group-item-action cursor-pointer">${emp.name}</li>
            `);
            
            $li.data("employeeId", thisId);
            
            if (thisId === selectedId) {
                $li.addClass("active");
            }
          
            $li.on('click', function () {
                $('#repeatingSelectedEmployeeID').val(thisId);
            
                $list.find(".list-group-item").removeClass("active");
                $(this).addClass("active");
            });
          
            $list.append($li);
        });
    }




    $('#repeatingEmployeeSearchBar').on('input', function () {
        renderEmployeeList($(this).val());
    });

    $('.add-repeating-shift-btn').on('click', function (e) {
        e.preventDefault();
        const weekNum = parseInt($(this).data('week'), 10);
        const dayIndex = parseInt($(this).data('day'), 10);
        openCreateRepeatingShiftModal(weekNum, dayIndex);
    });

    $(document).on('click', '.shift-item', function () {
        const shiftId = $(this).data('shiftId');
        openEditRepeatingShiftModal(shiftId);
    });

    function populateRoleSelect() {
        const $roleSelect = $('#repeatingRole');
        if ($roleSelect.length === 0) return;
    
        $roleSelect.empty();
    
        $roleSelect.append(`<option value="">No role selected</option>`);
    
        roles.forEach(role => {
            $roleSelect.append(
                `<option value="${role.id}">${role.name}</option>`
            );
        });
    }


    function calculateDuration(startTime, endTime) {
    const start = new Date(`01/01/2000 ${startTime}`);
    let end = new Date(`01/01/2000 ${endTime}`);

    if (end < start) {
      end.setDate(end.getDate() + 1);
    }

    const diffMs = end - start;
    const hours = Math.floor(diffMs / 3600000);
    const minutes = Math.floor((diffMs % 3600000) / 60000);

    return `${hours}h ${minutes}m`;
  }

  function getSelectedSortField() {
    const checked = document.querySelector("input[name='sortField']:checked");
    return checked ? checked.value : "name";
  }

  function getFilters() {
    const hideDeactivated = document.getElementById("hideDeactivated");
    const hideResigned = document.getElementById("hideResigned");
    const filterNamesEl = document.getElementById("filterNames");
    const filterRolesEl = document.getElementById("filterRoles");

    return {
      hideDeactivated: hideDeactivated ? hideDeactivated.checked : false,
      hideResigned: hideResigned ? hideResigned.checked : false,
      filterNames: filterNamesEl ? filterNamesEl.value.trim() : "",
      filterRoles: filterRolesEl ? filterRolesEl.value.trim() : "",
      sortField: getSelectedSortField(),
    };
  }

  function buildQueryParams(filters, offset = 0, limit = 100) {
    const params = new URLSearchParams();
    params.set("offset", offset);
    params.set("limit", limit);

    params.set("hide_deactive", filters.hideDeactivated ? "true" : "false");
    params.set("hide_resign", filters.hideResigned ? "true" : "false");
    params.set("sort", filters.sortField);

    if (filters.filterNames) {
      params.set("filter_names", filters.filterNames);
    }
    if (filters.filterRoles) {
      params.set("filter_roles", filters.filterRoles);
    }
    return params.toString();
  }

  function getCSRFToken() {
    const name = "csrftoken=";
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (let c of cookies) {
      c = c.trim();
      if (c.startsWith(name)) {
        return decodeURIComponent(c.slice(name.length));
      }
    }
    return "";
  }

function fetchEmployees(storeId) {
  $.ajax({
    url: `${api.listStoreEmployeeNames}?store_id=${storeId}&only_active=false`,
    method: "GET",
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() },

    success: function (data) {
      employees = data.names || [];
      renderEmployeeList("");
    },

    error: function (jqXHR) {
      handleAjaxError(jqXHR, "Failed to load employees");
    }
  });
}



function fetchRoles(storeId) {
  $.ajax({
    url: `${api.listStoreRoles}${storeId}/`,
    method: "GET",
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() },

    success: function (resp) {
      roles = resp.data || [];
      populateRoleSelect();
    },

    error: function (jqXHR) {
      handleAjaxError(jqXHR, "Failed to load roles");
    }
  });
}


function fetchRepeatingSchedule(storeId) {
  const filters = getFilters();
  const qs = buildQueryParams(filters);

  $.ajax({
    url: `${api.listRepeatingShifts}${storeId}/?${qs}`,
    method: "GET",
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() },

    success: function (data) {
      repeatingSchedule = data.schedule || {};
      renderAllWeeks();
    },

    error: function (jqXHR) {
      handleAjaxError(jqXHR, "Failed to load repeating shifts");
    }
  });
}



  async function fetchRepeatingShiftDetails(shiftId) {
    const url = `${api.manageRepeatingShift}/${shiftId}`;
    console.log("Fetching repeating shift details from:", url);

    const res = await fetch(url);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.Error || errData.error || "Failed to load repeating shift");
    }
    return await res.json();
  }

function createRepeatingShift(payload) {
  return $.ajax({
    url: `${api.createRepeatingShift}/${currentStoreId}`,
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({
      ...payload,
      active_weeks: JSON.stringify(payload.active_weeks),
    }),
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() }
  });
}

function updateRepeatingShift(shiftId, payload) {
  return $.ajax({
    url: `${api.manageRepeatingShift}/${shiftId}`,
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({
      ...payload,
      active_weeks: JSON.stringify(payload.active_weeks),
      employee_id: payload.employee_id,
    }),
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() }
  });
}

function deleteRepeatingShift(shiftId) {
  return $.ajax({
    url: `${api.manageRepeatingShift}/${shiftId}`,
    method: "DELETE",
    xhrFields: { withCredentials: true },
    headers: { "X-CSRFToken": getCSRFToken() }
  });
}



  // RENDERING THE 4-WEEK CYCLE HERE ---------------------------------------------

    function renderAllWeeks() {
    for (let week = 1; week <= 4; week++) {
      renderWeek(week);
    }
    updateWeekHeader();
  }

  function renderWeek(weekNum) {
    const container = document.getElementById(`week-${weekNum}-schedule-container`);
    if (!container || !repeatingSchedule) return;

    container.querySelectorAll(".day-column").forEach(dayCol => {
      const dayIndex = parseInt(dayCol.dataset.day);
      const shiftsList = dayCol.querySelector(".shifts-list");
      if (!shiftsList) return;

      shiftsList.innerHTML = "";

      const shiftsForDay = [];

      // repeatingSchedule shape from backend:
      // {
      //   "John Doe": {
      //     "id": 3,
      //     "week1": { 0: [shift, ...], 1: [...], ... },
      //     "week2": {...},
      //     ...
      //   },
      //   ...
      // }
      for (const empName in repeatingSchedule) {
        const empData = repeatingSchedule[empName];
        const weekKey = `week${weekNum}`;
        if (!empData[weekKey]) continue;

        const dayShifts = empData[weekKey][String(dayIndex)];
        if (!dayShifts || !Array.isArray(dayShifts)) continue;

        dayShifts.forEach(s => {
          shiftsForDay.push({
            employee_name: empName,
            ...s,
          });
        });
      }

      if (shiftsForDay.length === 0) {
        shiftsList.innerHTML = '<div class="text-center text-white p-3"><small>No repeating shifts</small></div>';
        return;
      }

      const fragment = document.createDocumentFragment();

      shiftsForDay.forEach(shift => {
        const card = document.createElement("div");
        const shiftId = shift.id || shift.shift_id;
        const borderColor = shift.role_colour || "#adb5bd";
        const backgroundColor = "#f8f9fa"; 
        const duration = calculateDuration(shift.start_time, shift.end_time);

        card.className = "shift-item position-relative cursor-pointer";
        if (shiftId) {
          card.dataset.shiftId = shiftId;
        }
        card.style.borderLeft = `8px solid ${borderColor}`;
        card.style.backgroundColor = backgroundColor;

        card.innerHTML = `
          ${shift.has_comment
            ? '<span class="danger-tooltip-icon position-absolute p-1" data-bs-toggle="tooltip" title="This repeating shift has a comment">C</span>'
            : ""
          }
          <div class="shift-item-employee">${shift.employee_name}</div>
          <div class="shift-item-details">
            <span>🕒 ${shift.start_time} – ${shift.end_time}</span>
            <span>⌛ ${duration}</span>
            ${shift.role_name ? `<span>👤 ${shift.role_name}</span>` : ""}
          </div>
        `;

        fragment.appendChild(card);
      });

      shiftsList.appendChild(fragment);
    });
  }

  async function loadRepeatingForCurrentStore() {
    if (!currentStoreId) return;

    try {
      await fetchRepeatingSchedule(currentStoreId);
    } catch (err) {
      console.error("Error loading repeating shifts:", err);
    }
  }

  if (storeSelect) {
    storeSelect.addEventListener("change", () => {
      const value = storeSelect.value;
      currentStoreId = value || null;
      currentWeek = 1;

      updateWeekHeader();

      if (currentStoreId) {
        fetchEmployees(currentStoreId);
        fetchRoles(currentStoreId);
        loadRepeatingForCurrentStore();
      }
    });

    if (storeSelect.value) {
      currentStoreId = storeSelect.value;
      updateWeekHeader();
      fetchEmployees(currentStoreId);
      fetchRoles(currentStoreId);
      loadRepeatingForCurrentStore();
    } else {
      updateWeekHeader();
    }
  } else {
    updateWeekHeader();
  }


  if (tableControllerSubmit) {
    tableControllerSubmit.addEventListener("click", e => {
      e.preventDefault();
      if (!currentStoreId) return;
      fetchRepeatingSchedule(currentStoreId);
    });
  }


  function updateWeekHeader() {
    if (weekHeaderTitle) {
      weekHeaderTitle.textContent = `Cycle Week ${currentWeek} of 4`;
    }
    document.querySelectorAll(".repeating-week").forEach(el => {
      const w = parseInt(el.dataset.week);
      el.style.display = (w === currentWeek) ? "" : "none";
    });
  }

  if (previousWeekBtn) {
    previousWeekBtn.addEventListener("click", e => {
      e.preventDefault();
      currentWeek = currentWeek === 1 ? 4 : currentWeek - 1;
      updateWeekHeader();
    });
  }

  if (nextWeekBtn) {
    nextWeekBtn.addEventListener("click", e => {
      e.preventDefault();
      currentWeek = currentWeek === 4 ? 1 : currentWeek + 1;
      updateWeekHeader();
    });
  }

});
