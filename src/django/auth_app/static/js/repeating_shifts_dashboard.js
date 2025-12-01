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
    params.set("hide_deactivated", filters.hideDeactivated ? "true" : "false");
    params.set("hide_resigned", filters.hideResigned ? "true" : "false");
    params.set("sort_field", filters.sortField);

    if (filters.filterNames) {
      params.set("filter_names", filters.filterNames);
    }
    if (filters.filterRoles) {
      params.set("filter_roles", filters.filterRoles);
    }
    return params.toString();
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
