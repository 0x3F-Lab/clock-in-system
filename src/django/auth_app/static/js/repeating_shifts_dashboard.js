document.addEventListener("DOMContentLoaded", () => {
  const storeSelect = document.getElementById("storeSelect");
  const weekHeaderTitle = document.getElementById("schedule-week-title");
  const previousWeekBtn = document.getElementById("previous-week-btn");
  const nextWeekBtn = document.getElementById("next-week-btn");
  const tableControllerSubmit = document.getElementById("tableControllerSubmit");

  let currentWeek = 1;
  let repeatingSchedule = null;
  let currentStoreId = null;
  let employees = [];
  let roles = [];

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
    const url = `${window.listStoreEmployeeNames}?store_id=${storeId}`;
    const res = await fetch(url);
    if (!res.ok) return;
    employees = await res.json();
    renderEmployeeList("");
  }

  async function fetchRoles(storeId) {
    const url = `${window.listStoreRoles}${storeId}`;
    const res = await fetch(url);
    if (!res.ok) return;
    roles = await res.json();
    populateRoleSelect();
  }

  async function fetchRepeatingSchedule(storeId) {
    const filters = getFilters();
    const qs = buildQueryParams(filters);
    const url = `${window.listRepeatingShifts}${storeId}?${qs}`;
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
    const url = `${window.createRepeatingShift}${storeId}`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken(),
      },
      body: JSON.stringify({...payload, active_weeks: JSON.stringify(payload.active_weeks),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.Error || err.error || "Failed to create repeating shift");
    }
    return await res.json();
  }

  async function updateRepeatingShift(shiftId, payload) {
    const url = `${window.manageRepeatingShift}${shiftId}`;
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
    const url = `${window.manageRepeatingShift}${shiftId}`;
    const res = await fetch(url, {
      method: "DELETE",
      headers: { "X-CSRFToken": getCSRFToken() },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.Error || err.error || "Failed to delete repeating shift");
    }
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
