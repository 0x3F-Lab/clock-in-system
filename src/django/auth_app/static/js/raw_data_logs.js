$(document).ready(function() {
	handleRawDataLogs();
  });
  
  function handleRawDataLogs() {
	// Check if we're on the Raw Data Logs page
	const rawDataTableElement = document.getElementById("rawDataTable");
	if (!rawDataTableElement) {
	  return; // Not on the raw data logs page, so exit
	}
  
	// 1) Grab references to table & table body
	const rawDataTbody = rawDataTableElement.querySelector("tbody");
  
	// 2) Grab references for editing an activity
	const editModal = document.getElementById("editActivityModal");
	const editActivityForm = document.getElementById("editActivityForm");
	const closeEditModalBtn = document.getElementById("closeEditModal");
	const deleteActivityBtn = document.getElementById("deleteActivityBtn");
  
	// 3) Grab references for adding a new activity
	const addModal = document.getElementById("addActivityModal");
	const addNewLogBtn = document.getElementById("addNewLogBtn");
	const closeAddModalBtn = document.getElementById("closeAddModal");
	const addActivityForm = document.getElementById("addActivityForm");
	const addStaffSelect = document.getElementById("addStaffSelect");
  
	// 4) Endpoints from window.djangoURLs (make sure these match your Django URLs!)
	const rawDataLogsURL = window.djangoURLs.rawDataLogs;  // e.g. "/api/raw-data-logs/"
	// If you have an API endpoint to list employees for the dropdown:
	const listUsersURL = window.djangoURLs.listEmployeeNames; 
	// or something like "/api/list-employees/" if that's how your endpoints are set up
  
	// -- A) Populate the "Add New Activity" staff dropdown
	function populateStaffDropdown() {
	  if (!addStaffSelect) return; // If there's no select element, skip
	  fetch(listUsersURL)
		.then((res) => {
		  if (!res.ok) throw new Error("Failed to fetch users for dropdown.");
		  return res.json();
		})
		.then((users) => {
		  // Clear existing <option>s
		  addStaffSelect.innerHTML = "";
  
		  // Create a placeholder <option>
		  const placeholderOption = document.createElement("option");
		  placeholderOption.value = "";
		  placeholderOption.textContent = "Choose an Employee...";
		  placeholderOption.disabled = true;
		  placeholderOption.selected = true;
		  addStaffSelect.appendChild(placeholderOption);
  
		  // The response might be something like [[1, "John Smith"], [2, "Jane Doe"]]
		  users.forEach((userArray) => {
			const userId = userArray[0];
			const userName = userArray[1];
  
			const option = document.createElement("option");
			option.value = userId;
			option.textContent = userName;
			addStaffSelect.appendChild(option);
		  });
		})
		.catch((err) => {
		  console.error("Error fetching user list:", err);
		  alert("Could not load staff list. Please refresh or try again.");
		});
	}
  
	// -- B) Fetch raw data logs & display in table
	function fetchRawDataLogs() {
	  fetch(rawDataLogsURL, { headers: { "Accept": "application/json" } })
		.then((res) => {
		  if (!res.ok) throw new Error("Failed to fetch raw data logs.");
		  return res.json();
		})
		.then((data) => {
		  // Clear the table first
		  rawDataTbody.innerHTML = "";
  
		  if (!data.length) {
			rawDataTbody.innerHTML = `
			  <tr><td colspan="9">No logs found.</td></tr>
			`;
			return;
		  }
  
		  // Build each row
		  data.forEach((log) => {
			const row = document.createElement("tr");
			row.innerHTML = `
			  <td>${log.staff_name}</td>
			  <td>${log.login_time || "N/A"}</td>
			  <td>${log.logout_time || "N/A"}</td>
			  <td>${log.is_public_holiday ? "Yes" : "No"}</td>
			  <td>${log.exact_login_timestamp || "N/A"}</td>
			  <td>${log.exact_logout_timestamp || "N/A"}</td>
			  <td>${log.deliveries}</td>
			  <td>${log.hours_worked || "0"}</td>
			  <td>
				<button class="editBtn" data-id="${log.id}">Edit</button>
			  </td>
			`;
			rawDataTbody.appendChild(row);
		  });
  
		  // Hook up edit buttons
		  const editButtons = rawDataTbody.querySelectorAll(".editBtn");
		  editButtons.forEach((btn) => {
			btn.addEventListener("click", () => {
			  const activityId = btn.getAttribute("data-id");
			  openEditModal(activityId);
			});
		  });
		})
		.catch((err) => {
		  console.error("Error fetching raw data logs:", err);
		  rawDataTbody.innerHTML = `
			<tr><td colspan="9">Failed to load logs. Please try again later.</td></tr>
		  `;
		});
	}
  
	// -- C) Open Edit modal & fetch single activity
	function openEditModal(activityId) {
	  if (!editModal) return;
	  editModal.style.display = "block";
  
	  // Put the activity ID in a hidden field
	  document.getElementById("editActivityId").value = activityId;
  
	  // GET single record to fill form fields
	  fetch(`${rawDataLogsURL}${activityId}/`, {
		headers: { Accept: "application/json" },
	  })
		.then((res) => {
		  if (!res.ok) throw new Error("Failed to fetch single activity.");
		  return res.json();
		})
		.then((activityData) => {
		  // Fill form fields
		  const editLoginTime = document.getElementById("editLoginTime");
		  const editLogoutTime = document.getElementById("editLogoutTime");
		  const editIsPublicHoliday = document.getElementById("editIsPublicHoliday");
		  const editDeliveries = document.getElementById("editDeliveries");
  
		  // For datetime-local inputs, remove seconds if your times come with them
		  editLoginTime.value = activityData.login_time
			? activityData.login_time.slice(0, 16)
			: "";
		  editLogoutTime.value = activityData.logout_time
			? activityData.logout_time.slice(0, 16)
			: "";
		  editIsPublicHoliday.checked = activityData.is_public_holiday;
		  editDeliveries.value = activityData.deliveries || 0;
		})
		.catch((err) => {
		  console.error("Error fetching detail:", err);
		  alert("Failed to load data for editing.");
		});
	}
  
	// -- D) Close Edit Modal
	if (closeEditModalBtn) {
	  closeEditModalBtn.addEventListener("click", () => {
		editModal.style.display = "none";
	  });
	}
  
	// -- E) Submit form to edit an activity
	if (editActivityForm) {
	  editActivityForm.addEventListener("submit", (e) => {
		e.preventDefault();
  
		const csrftoken = document.querySelector(
		  '#editActivityForm input[name="csrfmiddlewaretoken"]'
		).value;
  
		const activityId = document.getElementById("editActivityId").value;
		const loginTime = document.getElementById("editLoginTime").value;
		const logoutTime = document.getElementById("editLogoutTime").value;
		const isPublicHoliday = document.getElementById("editIsPublicHoliday").checked;
		const deliveries = document.getElementById("editDeliveries").value;
  
		// Convert datetime-local to something your backend expects
		const payload = {
		  login_time: loginTime ? loginTime + ":00" : null,
		  logout_time: logoutTime ? logoutTime + ":00" : null,
		  is_public_holiday: isPublicHoliday,
		  deliveries: parseInt(deliveries, 10),
		};
  
		fetch(`${rawDataLogsURL}${activityId}/`, {
		  method: "PUT",
		  headers: {
			"Content-Type": "application/json",
			"X-CSRFToken": csrftoken,
		  },
		  body: JSON.stringify(payload),
		})
		  .then((res) => {
			if (!res.ok) {
			  return res.json().then((data) => {
				throw new Error(data.error || "Failed to update activity");
			  });
			}
			return res.json();
		  })
		  .then((data) => {
			console.log("Update success:", data);
			alert("Activity updated successfully!");
			editModal.style.display = "none";
			fetchRawDataLogs(); // Refresh table
		  })
		  .catch((err) => {
			console.error("Error updating activity:", err);
			alert("Error updating activity: " + err.message);
		  });
	  });
	}
  
	// -- F) Delete an Activity
	if (deleteActivityBtn) {
	  deleteActivityBtn.addEventListener("click", () => {
		if (!confirm("Are you sure you want to delete this activity?")) {
		  return;
		}
  
		const activityId = document.getElementById("editActivityId").value;
		const csrftoken = document.querySelector(
		  '#editActivityForm input[name="csrfmiddlewaretoken"]'
		).value;
  
		fetch(`${rawDataLogsURL}${activityId}/`, {
		  method: "DELETE",
		  headers: {
			"X-CSRFToken": csrftoken,
		  },
		})
		  .then((res) => {
			// Some backends return 204 for success. If it’s not 200–204, handle error
			if (!res.ok && res.status !== 204) {
			  return res.json().then((data) => {
				throw new Error(data.error || "Failed to delete activity");
			  });
			}
			return { message: "Activity deleted successfully" };
		  })
		  .then((data) => {
			console.log(data.message);
			alert("Activity deleted successfully!");
			editModal.style.display = "none";
			fetchRawDataLogs();
		  })
		  .catch((err) => {
			console.error("Error deleting activity:", err);
			alert("Error deleting activity: " + err.message);
		  });
	  });
	}
  
	// -- G) “Add New Log” button -> open the add modal
	if (addNewLogBtn) {
	  addNewLogBtn.addEventListener("click", () => {
		addModal.style.display = "block";
	  });
	}
  
	// -- H) Close Add Modal
	if (closeAddModalBtn) {
	  closeAddModalBtn.addEventListener("click", () => {
		addModal.style.display = "none";
	  });
	}
  
	// -- I) Submit form to add a new activity
	if (addActivityForm) {
	  addActivityForm.addEventListener("submit", (e) => {
		e.preventDefault();
  
		const csrftoken = document.querySelector(
		  '#addActivityForm input[name="csrfmiddlewaretoken"]'
		).value;
  
		const employeeId = addStaffSelect.value;
		const loginTime = document.getElementById("addLoginTime").value;
		const logoutTime = document.getElementById("addLogoutTime").value;
		const isPublicHoliday = document.getElementById("addIsPublicHoliday").checked;
		const deliveries = document.getElementById("addDeliveries").value;
  
		const payload = {
		  employee_id: parseInt(employeeId, 10),
		  login_time: loginTime ? loginTime + ":00" : null,
		  logout_time: logoutTime ? logoutTime + ":00" : null,
		  is_public_holiday: isPublicHoliday,
		  deliveries: parseInt(deliveries, 10),
		};
  
		fetch(rawDataLogsURL, {
		  method: "POST",
		  headers: {
			"Content-Type": "application/json",
			"X-CSRFToken": csrftoken,
		  },
		  body: JSON.stringify(payload),
		})
		  .then((res) => {
			if (!res.ok) {
			  return res.json().then((data) => {
				throw new Error(data.Error || "Failed to create new activity");
			  });
			}
			return res.json();
		  })
		  .then((data) => {
			console.log("Create success:", data);
			alert("New activity created successfully!");
			addModal.style.display = "none";
			addActivityForm.reset();
			fetchRawDataLogs(); // Refresh table
		  })
		  .catch((err) => {
			console.error("Error creating new activity:", err);
			alert("Error creating activity: " + err.message);
		  });
	  });
	}
  
	// -- J) On page load, populate staff dropdown & fetch logs
	// (only if you actually have an “Add New” form that needs staff)
	populateStaffDropdown();
	fetchRawDataLogs();
  }
  