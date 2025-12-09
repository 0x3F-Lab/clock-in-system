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

  // REPEATING SHIFT MODAL ELEMENTS --------------------------------------------
  const repeatingModalEl = document.getElementById("repeatingEditModal");
  const saveRepeatingShiftBtn = document.getElementById("saveRepeatingShiftBtn");
  const deleteRepeatingShiftBtn = document.getElementById("deleteRepeatingShiftBtn");
  const confirmDeleteRepeatingShiftBtn = document.getElementById("confirmDeleteRepeatingShiftBtn");
  const repeatingModal = repeatingModalEl ? new bootstrap.Modal(repeatingModalEl) : null;
  const repeatingShiftIdInput = document.getElementById("repeatingShiftId");
  const repeatingShiftStoreIdInput = document.getElementById("repeatingShiftStoreId");
  const repeatingStartWeekdaySelect = document.getElementById("repeatingStartWeekday");
  const repeatingEndWeekdaySelect = document.getElementById("repeatingEndWeekday");
  const repeatingStartTimeInput = document.getElementById("repeatingStartTime");
  const repeatingEndTimeInput = document.getElementById("repeatingEndTime");
  const repeatingRoleSelect = document.getElementById("repeatingRole");
  const repeatingCommentTextarea = document.getElementById("repeatingComment");
  const repeatingWeekCheckboxes = document.querySelectorAll(".repeating-week-checkbox");
  const repeatingSelectedEmployeeIDInput = document.getElementById("repeatingSelectedEmployeeID");
  const repeatingModalTitle = document.getElementById("repeatingEditModalLabel");
  const repeatingEmployeeListEl = document.getElementById("repeatingEmployeeList");
  const repeatingEmployeeSearchBar = document.getElementById("repeatingEmployeeSearchBar");

    function openCreateRepeatingShiftModal(weekNum, dayIndex) {
      if (!repeatingModal) return;
      if (!currentStoreId) {
        console.error("No store selected");
        return;
      }
    
      repeatingModalTitle.textContent = "Add Repeating Shift";
    
      if (repeatingShiftIdInput) repeatingShiftIdInput.value = "";
    
      if (repeatingShiftStoreIdInput) repeatingShiftStoreIdInput.value = currentStoreId;
    
      if (repeatingStartWeekdaySelect) repeatingStartWeekdaySelect.value = String(dayIndex);
      if (repeatingEndWeekdaySelect) repeatingEndWeekdaySelect.value = String(dayIndex);
    
      if (repeatingStartTimeInput) repeatingStartTimeInput.value = "";
      if (repeatingEndTimeInput) repeatingEndTimeInput.value = "";
    
      if (repeatingRoleSelect) repeatingRoleSelect.value = "";
      if (repeatingCommentTextarea) repeatingCommentTextarea.value = "";
    
      if (repeatingSelectedEmployeeIDInput) repeatingSelectedEmployeeIDInput.value = "";
    
      if (repeatingWeekCheckboxes && repeatingWeekCheckboxes.length) {
        repeatingWeekCheckboxes.forEach(cb => {
          cb.checked = (parseInt(cb.value, 10) === weekNum);
        });
      }
      if (saveRepeatingShiftBtn) saveRepeatingShiftBtn.classList.remove("d-none");
      if (deleteRepeatingShiftBtn) deleteRepeatingShiftBtn.classList.add("d-none");
      if (confirmDeleteRepeatingShiftBtn) confirmDeleteRepeatingShiftBtn.classList.add("d-none");
      repeatingModal.show();
    }
    
    if (saveRepeatingShiftBtn) {
      saveRepeatingShiftBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        if (!currentStoreId) {
          console.error("No store selected");
          return;
        }
      
        const employee_id = repeatingSelectedEmployeeIDInput
          ? repeatingSelectedEmployeeIDInput.value
          : null;
      
        if (!employee_id) {
          console.error("No employee selected for repeating shift");
          return;
        }
      
        const start_weekday = parseInt(repeatingStartWeekdaySelect.value, 10);
        const end_weekday = parseInt(repeatingEndWeekdaySelect.value, 10);
        const start_time = repeatingStartTimeInput.value;
        const end_time = repeatingEndTimeInput.value;
      
        const active_weeks = Array.from(repeatingWeekCheckboxes)
          .filter(cb => cb.checked)
          .map(cb => parseInt(cb.value, 10));
      
        const role_id = repeatingRoleSelect && repeatingRoleSelect.value
          ? repeatingRoleSelect.value
          : null;
      
        const comment = repeatingCommentTextarea ? repeatingCommentTextarea.value.trim() : "";
      
        const payload = {
          employee_id,
          start_weekday,
          end_weekday,
          start_time,
          end_time,
          active_weeks,
          role_id,
          comment,
        };
      
        try {
          await createRepeatingShift(payload);
          await fetchRepeatingSchedule(currentStoreId);
          if (repeatingModal) repeatingModal.hide();
        } catch (err) {
          console.error("Error creating repeating shift:", err);
        }
      });
    }   


    function renderEmployeeList(filterText = "") {
      if (!repeatingEmployeeListEl) return;

      const term = filterText.trim().toLowerCase();

      const filtered = employees.filter(emp => {
        const name = (emp.name || "").toLowerCase();
        return !term || name.includes(term);
      });
    
      if (filtered.length === 0) {
        repeatingEmployeeListEl.innerHTML =
          '<li class="list-group-item text-center text-muted">No employees found</li>';
        return;
      }
    
      repeatingEmployeeListEl.innerHTML = "";
    
      filtered.forEach(emp => {
        const li = document.createElement("li");
        li.className = "list-group-item list-group-item-action cursor-pointer";
        li.textContent = emp.name;
        li.dataset.employeeId = emp.id;
      
        li.addEventListener("click", () => {
          if (repeatingSelectedEmployeeIDInput) {
            repeatingSelectedEmployeeIDInput.value = emp.id;
          }
        
          repeatingEmployeeListEl
            .querySelectorAll(".list-group-item")
            .forEach(el => el.classList.remove("active"));
          li.classList.add("active");
        });
      
        repeatingEmployeeListEl.appendChild(li);
      });
    }

    if (repeatingEmployeeSearchBar) {
      repeatingEmployeeSearchBar.addEventListener("input", (e) => {
        renderEmployeeList(e.target.value);
      });
    }

    document.querySelectorAll(".add-repeating-shift-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const weekNum = parseInt(btn.dataset.week, 10);
        const dayIndex = parseInt(btn.dataset.day, 10);

        openCreateRepeatingShiftModal(weekNum, dayIndex);
      });
    });

    function populateRoleSelect() {
      if (!repeatingRoleSelect) return;

      repeatingRoleSelect.innerHTML = "";

      const emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = "No role selected";
      repeatingRoleSelect.appendChild(emptyOpt);

      roles.forEach(role => {
        const opt = document.createElement("option");
        opt.value = role.id; 
        opt.textContent = role.name;
        repeatingRoleSelect.appendChild(opt);
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

async function fetchEmployees(storeId) {
  const url = `${api.listStoreEmployeeNames}?store_id=${storeId}&only_active=false`;
  const res = await fetch(url);
  if (!res.ok) return;
  const data = await res.json();
  employees = data.names || [];
  console.log("Loaded employees:", employees);
  renderEmployeeList("");
}


async function fetchRoles(storeId) {
  const url = `${api.listStoreRoles}${storeId}/`;
  const res = await fetch(url);
  if (!res.ok) return;
  const data = await res.json();
  roles = data.data || [];
  console.log("Loaded roles:", roles);
  populateRoleSelect();
}


async function fetchRepeatingSchedule(storeId) {
  const filters = getFilters();
  const qs = buildQueryParams(filters);

  const url = `${api.listRepeatingShifts}${storeId}/?${qs}`;
  console.log("Fetching repeating shifts from:", url);

  const res = await fetch(url);
  if (!res.ok) {
    console.error("Failed to load repeating shifts");
    return;
  }
  const data = await res.json();
  repeatingSchedule = data.schedule || {};
  renderAllWeeks();
}


  async function fetchRepeatingShiftDetails(shiftId) {
    const url = `${window.manageRepeatingShift}${shiftId}`;
    const res = await fetch(url);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.Error || errData.error || "Failed to load repeating shift");
    }
    return await res.json();
  }

async function createRepeatingShift(payload) {
  const storeId = currentStoreId;
  const url = `${api.createRepeatingShift}/${storeId}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
    },
    body: JSON.stringify({
      ...payload,
      active_weeks: JSON.stringify(payload.active_weeks),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.Error || err.error || "Failed to create repeating shift");
  }
  return await res.json();
}


async function updateRepeatingShift(shiftId, payload) {
  const url = `${api.manageRepeatingShift}/${shiftId}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken(),
    },
    body: JSON.stringify({
      ...payload,
      active_weeks: JSON.stringify(payload.active_weeks),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.Error || err.error || "Failed to update repeating shift");
  }
  return await res.json();
}


async function deleteRepeatingShift(shiftId) {
  const url = `${api.manageRepeatingShift}/${shiftId}`;
  const res = await fetch(url, {
    method: "DELETE",
    headers: { "X-CSRFToken": getCSRFToken() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.Error || err.error || "Failed to delete repeating shift");
  }
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
