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
  const url = `${api.listStoreEmployeeNames}?store_id=${storeId}`;
  const res = await fetch(url);
  if (!res.ok) return;
  employees = await res.json();
  renderEmployeeList("");
}

async function fetchRoles(storeId) {
  const url = `${api.listStoreRoles}${storeId}`;
  const res = await fetch(url);
  if (!res.ok) return;
  roles = await res.json();
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
  const url = `${api.createRepeatingShift}${storeId}`;
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
  const url = `${api.manageRepeatingShift}${shiftId}`;
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
  const url = `${api.manageRepeatingShift}${shiftId}`;
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
      loadRepeatingForCurrentStore();
    });

    if (storeSelect.value) {
      currentStoreId = storeSelect.value;
      updateWeekHeader();
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
