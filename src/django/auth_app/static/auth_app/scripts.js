document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM fully loaded");

    // --- Manager Clock-In Section ---
    const clockButton = document.getElementById("clockButton");
    const deliveriesCount = document.getElementById("deliveriesCount");
    const minusButton = document.getElementById("minusButton");
    const plusButton = document.getElementById("plusButton");
    const timer = document.getElementById("timer");
    const totalTimeDisplay = document.getElementById("totalTime");
    const totalDeliveriesDisplay = document.getElementById("totalDeliveries");
    const localTimeDisplay = document.getElementById("localTime");
    const userDropdown = document.getElementById("userDropdown");

    let clockedIn = false; // Track clock-in state
    let startTime = null; // Store clock-in start time
    let intervalId = null; // Interval for timer

    // Only run the clock-in logic if these elements exist (i.e., on the manager page)
    if (clockButton && deliveriesCount && minusButton && plusButton && timer && totalTimeDisplay && totalDeliveriesDisplay && localTimeDisplay && userDropdown) {

        // Enable "Clock In" button when a user is selected
        userDropdown.addEventListener("change", () => {
            if (userDropdown.value) {
                clockButton.disabled = false; // Enable the clock button
            }
        });

        // Toggle Clock In/Clock Out
        function toggleClock() {
            if (!clockedIn) {
                // Clocking in
                clockedIn = true;
                startTime = new Date();
                clockButton.textContent = "Clock Out";
                clockButton.style.backgroundColor = "red";
                deliveriesCount.textContent = "0"; // Reset deliveries
                minusButton.disabled = false;
                plusButton.disabled = false;

                intervalId = setInterval(updateTimer, 1000); // Start timer
            } else {
                // Clocking out
                clockedIn = false;
                clearInterval(intervalId); // Stop timer
                const endTime = new Date();
                const totalMinutes = Math.round((endTime - startTime) / 60000);

                clockButton.textContent = "Clock In";
                clockButton.style.backgroundColor = "green";
                minusButton.disabled = true;
                plusButton.disabled = true;

                // Update left panel
                timer.textContent = "Worked: 0H 0M";
                totalTimeDisplay.textContent = `${Math.floor(totalMinutes / 60)}H ${totalMinutes % 60}M`;
                totalDeliveriesDisplay.textContent = deliveriesCount.textContent;

                deliveriesCount.textContent = "0"; // Reset deliveries after clock out
            }
        }

        // Update Timer
        function updateTimer() {
            const now = new Date();
            const elapsedMinutes = Math.round((now - startTime) / 60000);
            const hours = Math.floor(elapsedMinutes / 60);
            const minutes = elapsedMinutes % 60;

            timer.textContent = `Worked: ${hours}H ${minutes}M`;
        }

        // Update Local Time
        function updateLocalTime() {
            const now = new Date();
            localTimeDisplay.textContent = now.toLocaleTimeString();
        }

        // Adjust Deliveries Count
        function adjustDeliveries(amount) {
            if (clockedIn) {
                const current = parseInt(deliveriesCount.textContent, 10);
                deliveriesCount.textContent = Math.max(0, current + amount);
            }
        }

        // Attach Event Listeners for the Manager Page
        clockButton.addEventListener("click", toggleClock);
        minusButton.addEventListener("click", () => adjustDeliveries(-1));
        plusButton.addEventListener("click", () => adjustDeliveries(1));

        // Start Updating Local Time
        setInterval(updateLocalTime, 1000);
    }

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
            fetch("/api/employees/", {
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
            fetch(`/api/employees/${id}/`, {
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
            
            fetch(`/api/employees/${id}/`, {
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
        fetch("/api/raw-data-logs/", {
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


// Helper function to get CSRF token
function getCSRFToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
}




});
