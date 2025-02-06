$(document).ready(function() {
  handleEmployeeDetailsPage();
});


function handleEmployeeDetailsPage() {
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
          fetch(window.djangoURLs.listEveryEmployeeDetails, {
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
          fetch(`${window.djangoURLs.listSingularEmployeeDetails}${id}/`, {
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
          
          fetch(`${window.djangoURLs.listSingularEmployeeDetails}${id}/`, {
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
  }
}