// Function to show notifications
function showNotification(message, type = "warning") {
  // Create notification HTML element
  const notification = $('<div class="alert alert-' + type + ' alert-dismissible fade show" role="alert"></div>');
  notification.text(message);
  
  // Add close button to the notification
  notification.append('<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>');
  
  // Append notification to the notification container
  $('#notification-container').append(notification);
  
  // Automatically remove notification after 5 seconds
  setTimeout(() => {
      notification.alert('close');  // Close the notification
  }, 5000);
}


// Function to hash a string for API calls (i.e. passwords)
async function hashString(string) {
  // Static salt to be appended to string for increased security
  const salt = "ThZQssm2xst0K8yVCNHCtMiKUp9IJk6A";
  const saltedString = string + salt;

  // Perform SHA-256 hashing
  const encoder = new TextEncoder();
  const data = encoder.encode(saltedString);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);

  // Convert the hash to Base64
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const base64Hash = btoa(String.fromCharCode(...hashArray));

  return base64Hash;
}


// Get the required cookie from document
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}


document.addEventListener("DOMContentLoaded", () => {
    // Access Django-generated URLs
    const listEveryEmployeeDetailsURL = window.djangoURLs.listEveryEmployeeDetails
    const listSingularEmployeeDetailsURL = window.djangoURLs.listSingularEmployeeDetails
    const rawDataLogsURL = window.djangoURLs.rawDataLogs

    // --- Employee Details Section ---
    const employeeTableElement = document.getElementById("employeeTable");
    const editModal = document.getElementById("editModal");
    const editForm = document.getElementById("editForm");
    const closeModal = document.getElementById("closeModal");

    // Only run the employee details logic if these elements exist
    if (employeeTableElement && editModal && editForm && closeModal) {
        const employeeTable = employeeTableElement.querySelector("tbody");

        // Close modal functionality
        closeModal.addEventListener("click", () => {
            editModal.style.display = "none";
        });

        // Fetch and display employees
        const fetchEmployees = () => {
            fetch(listEveryEmployeeDetailsURL, {
                headers: { "Accept": "application/json" },
            })
                .then((res) => {
                    if (!res.ok) throw new Error("Failed to fetch employee data.");
                    return res.json();
                })
                .then((data) => {
                    console.log("Fetched data:", data);

                    // Clear table and display employees
                    employeeTable.innerHTML = "";
                    if (data.length === 0) {
                        employeeTable.innerHTML = `<tr><td colspan="5">No employees found.</td></tr>`;
                    } else {
                        data.forEach((employee) => {
                            const row = document.createElement("tr");
                            row.innerHTML = `
                                <td>${employee.first_name} ${employee.last_name}</td>
                                <td>${employee.email}</td>
                                <td>${employee.phone_number || "N/A"}</td>
                                <td>${employee.pin}</td>
                                <td>
                                    <button class="editBtn" data-id="${employee.id}">Edit</button>
                                </td>
                            `;
                            employeeTable.appendChild(row);
                        });
                        attachEditButtons();
                    }
                })
                .catch((error) => {
                    console.error("Error fetching employee data:", error);
                    employeeTable.innerHTML = `<tr><td colspan="5">Failed to load employees. Please try again later.</td></tr>`;
                });
        };

        // Attach event listeners to edit buttons
        const attachEditButtons = () => {
            document.querySelectorAll(".editBtn").forEach((btn) => {
                btn.addEventListener("click", (e) => {
                    const employeeId = e.target.dataset.id;
                    openEditModal(employeeId);
                });
            });
        };

        // Open the edit modal
        const openEditModal = (id) => {
            fetch(`${listSingularEmployeeDetailsURL}${id}/`, {
                headers: { "Accept": "application/json" },
            })
                .then((res) => {
                    if (!res.ok) throw new Error("Failed to fetch employee details.");
                    return res.json();
                })
                .then((data) => {
                    console.log("Employee data for editing:", data);
                    document.getElementById("editEmployeeId").value = data.id;
                    document.getElementById("editFirstName").value = data.first_name;
                    document.getElementById("editLastName").value = data.last_name;
                    document.getElementById("editEmail").value = data.email;
                    document.getElementById("editPhone").value = data.phone_number || "";
                    document.getElementById("editPin").value = data.pin || "";
                    editModal.style.display = "block";
                })
                .catch((error) => {
                    console.error("Error fetching employee details:", error);
                });
        };

        // Submit the edit form
        editForm.addEventListener("submit", (e) => {
            e.preventDefault();

            const csrftoken = document.querySelector('#editForm input[name="csrfmiddlewaretoken"]').value;

            const id = document.getElementById("editEmployeeId").value;
            const payload = {
                first_name: document.getElementById("editFirstName").value,
                last_name: document.getElementById("editLastName").value,
                email: document.getElementById("editEmail").value,
                phone_number: document.getElementById("editPhone").value,
                pin: document.getElementById("editPin").value,
            };
            
            fetch(`${listSingularEmployeeDetailsURL}${id}/`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken
                },
                body: JSON.stringify(payload),
            })
                .then((res) => {
                    if (!res.ok) throw new Error("Failed to update employee.");
                    alert("Employee updated successfully.");
                    editModal.style.display = "none";
                    fetchEmployees(); // Refresh employee list
                })
                .catch((error) => {
                    console.error("Error updating employee:", error);
                    alert("Error updating employee.");
                });
        });

        // Initial fetch of employees
        fetchEmployees();
    } else {
        console.log("Employee details elements not found on this page.");
    }
    // --- Raw Data Logs Section ---
  const rawDataTableElement = document.getElementById("rawDataTable");

  if (rawDataTableElement) {
    // 1) Grab references
    const rawDataTbody = rawDataTableElement.querySelector("tbody");
    const editModal = document.getElementById("editActivityModal");
    const editActivityForm = document.getElementById("editActivityForm");
    const closeEditModalBtn = document.getElementById("closeEditModal");
    const deleteActivityBtn = document.getElementById("deleteActivityBtn");

    const addModal = document.getElementById("addActivityModal");
    const addNewLogBtn = document.getElementById("addNewLogBtn");
    const closeAddModalBtn = document.getElementById("closeAddModal");
    const addActivityForm = document.getElementById("addActivityForm");

    // Your API endpoint:
    const rawDataLogsURL = "/api/raw-data-logs/";

    // 2) Fetch and display logs
    const fetchRawDataLogs = () => {
      fetch(rawDataLogsURL, { headers: { Accept: "application/json" } })
        .then((res) => {
          if (!res.ok) {
            throw new Error("Failed to fetch raw data logs.");
          }
          return res.json();
        })
        .then((data) => {
          // Clear table
          rawDataTbody.innerHTML = "";

          if (!data.length) {
            rawDataTbody.innerHTML = `
              <tr><td colspan="9">No logs found.</td></tr>
            `;
            return;
          }

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

          // Add click listeners to newly created Edit buttons
          const editButtons = rawDataTbody.querySelectorAll(".editBtn");
          editButtons.forEach((btn) => {
            btn.addEventListener("click", () => {
              const logId = btn.getAttribute("data-id");
              openEditModal(logId);
            });
          });
        })
        .catch((err) => {
          console.error("Error fetching raw data logs:", err);
          rawDataTbody.innerHTML = `
            <tr><td colspan="9">Failed to load logs. Please try again later.</td></tr>
          `;
        });
    };

    // 3) Open the edit modal
    const openEditModal = (logId) => {
      editModal.style.display = "block";
      document.getElementById("editActivityId").value = logId;

      // GET single record to fill form fields
      fetch(`${rawDataLogsURL}${logId}/`, {
        headers: { Accept: "application/json" },
      })
        .then((res) => {
          if (!res.ok) throw new Error("Failed to fetch single activity");
          return res.json();
        })
        .then((activityData) => {
          const editLoginTime = document.getElementById("editLoginTime");
          const editLogoutTime = document.getElementById("editLogoutTime");
          const editIsPublicHoliday = document.getElementById("editIsPublicHoliday");
          const editDeliveries = document.getElementById("editDeliveries");

          // "YYYY-MM-DDTHH:MM:SS" -> for datetime-local we want "YYYY-MM-DDTHH:MM"
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
          alert("Failed to open edit modal");
        });
    };

    // 4) Close edit modal
    closeEditModalBtn.addEventListener("click", () => {
      editModal.style.display = "none";
    });

    // 5) Handle Edit Form submission (PUT)
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

      // If your server expects seconds, append ":00"
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
          fetchRawDataLogs();
        })
        .catch((err) => {
          console.error("Error updating activity:", err);
          alert("Error updating activity: " + err.message);
        });
    });

    // 6) Delete an Activity
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
          if (!res.ok && res.status !== 204) {
            return res.json().then((data) => {
              throw new Error(data.error || "Failed to delete activity");
            });
          }
          // If status=204, there's no body, so we just proceed.
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

    // 7) "Add New Log" button -> open the add modal
    addNewLogBtn.addEventListener("click", () => {
      addModal.style.display = "block";
    });

    // 8) Close add modal
    closeAddModalBtn.addEventListener("click", () => {
      addModal.style.display = "none";
    });

    // 9) Handle Add Form submission (POST)
    addActivityForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const csrftoken = document.querySelector(
        '#addActivityForm input[name="csrfmiddlewaretoken"]'
      ).value;

      const staffId = document.getElementById("addStaffId").value;
      const loginTime = document.getElementById("addLoginTime").value;
      const logoutTime = document.getElementById("addLogoutTime").value;
      const isPublicHoliday = document.getElementById("addIsPublicHoliday").checked;
      const deliveries = document.getElementById("addDeliveries").value;

      const payload = {
        employee_id: parseInt(staffId, 10),
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
          fetchRawDataLogs();
        })
        .catch((err) => {
          console.error("Error creating new activity:", err);
          alert("Error creating activity: " + err.message);
        });
    });

    // 10) Initial fetch
    fetchRawDataLogs();
  }

    // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    // CHANGE PIN SECTION 
    // ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    // Only run if the "Change Pin" modal is on the page
    const changePinModal = document.getElementById("changePinModal");
    if (changePinModal) {
      // When modal is about to be shown, populate employee list
      $("#changePinModal").on("show.bs.modal", function() {
        // Clear any previous data
        $("#changePinUserList").empty();
        $("#changePinSearchBar").val("");
        $("#changePinSelectedUserID").val("");
        $("#currentPin").val("");
        $("#newPin").val("");
        $("#confirmNewPin").val("");

        // Fetch the employees listEmployeeNames endpoint
        $.get(window.djangoURLs.listEmployeeNames, function(data) {
          // data might be [[1, "John Smith"], [2, "Jane Doe"]], etc.
          data.forEach(emp => {
            const userId = emp[0];
            const fullName = emp[1];
            $("#changePinUserList").append(`
              <li
                class="list-group-item"
                data-id="${userId}"
                style="cursor: pointer;"
              >
                ${fullName}
              </li>
            `);
          });
        })
        .fail(function(xhr) {
          showNotification("Failed to load employee list.", "danger");
          console.error(xhr);
        });
      });

      // Filter list on input
      $("#changePinSearchBar").on("input", function() {
        const term = $(this).val().toLowerCase();
        $("#changePinUserList").children("li").each(function() {
          $(this).toggle($(this).text().toLowerCase().includes(term));
        });
      });

      // Click on an employee name to select
      $("#changePinUserList").on("click", "li", function() {
        $("#changePinUserList li").removeClass("active");
        $(this).addClass("active");
        const userId = $(this).data("id");
        $("#changePinSelectedUserID").val(userId);
      });

      // Submit button
      $("#submitChangePin").on("click", function() {
        const userID = $("#changePinSelectedUserID").val();
        const currentPin = $("#currentPin").val().trim();
        const newPin = $("#newPin").val().trim();
        const confirmNewPin = $("#confirmNewPin").val().trim();

        if (!userID) {
          showNotification("Please select your name from the list.", "danger");
          return;
        }
        if (!currentPin || !newPin || !confirmNewPin) {
          showNotification("All pin fields are required.", "danger");
          return;
        }
        if (newPin !== confirmNewPin) {
          showNotification("New pin and confirmation do not match.", "danger");
          return;
        }

        const csrftoken = getCookie('csrftoken');

        // POST to your "change pin" endpoint
        $.ajax({
          url: window.djangoURLs.changePin,
          method: "POST",
          headers: {
            "X-CSRFToken": csrftoken
          },
          data: {
            user_id: userID,
            current_pin: currentPin,
            new_pin: newPin
          },
          success: function(response) {
            if (response.success) {
              showNotification(response.message, "success");
              $("#changePinModal").modal("hide");
            } else {
              showNotification(response.message, "danger");
            }
          },
          error: function(xhr) {
            showNotification("An unexpected error occurred.", "danger");
            console.error(xhr);
          }
        });
      });
    }

});