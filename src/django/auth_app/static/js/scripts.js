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
		const rawDataTbody = rawDataTableElement.querySelector("tbody");

		const fetchRawDataLogs = () => {
			fetch(rawDataLogsURL, {
				headers: { "Accept": "application/json" },
			})
				.then((res) => {
					if (!res.ok) throw new Error("Failed to fetch raw data logs.");
					return res.json();
				})
				.then((data) => {
					console.log("Fetched raw data logs:", data);

					// Clear table
					rawDataTbody.innerHTML = "";
					if (data.length === 0) {
						rawDataTbody.innerHTML = `<tr><td colspan="7">No logs found.</td></tr>`;
					} else {
						data.forEach((log) => {
							console.log("Log being processed:", log); // Debugging line
						
							const row = document.createElement("tr");
							row.innerHTML = `
								<td>${log.staff_name}</td>
								<td>${log.login_time || "N/A"}</td> <!-- Add fallback just in case -->
								<td>${log.logout_time || "N/A"}</td> <!-- Add fallback just in case -->
								<td>${log.is_public_holiday ? "Yes" : "No"}</td>
								<td>${log.exact_login_timestamp}</td>
								<td>${log.exact_logout_timestamp || "N/A"}</td>
								<td>${log.deliveries}</td>
								<td>${log.hours_worked}</td>
							`;
							rawDataTbody.appendChild(row);
						});
						
					}
				})
				.catch((error) => {
					console.error("Error fetching raw data logs:", error);
					rawDataTbody.innerHTML = `<tr><td colspan="7">Failed to load logs. Please try again later.</td></tr>`;
				});
		};

    // Initial fetch of raw data logs
    fetchRawDataLogs();
	}
});