$(document).ready(function() {
  handleRawDataLogs();
});


function handleRawDataLogs() {
  const rawDataTableElement = document.getElementById("rawDataTable");

	if (rawDataTableElement) {
		const rawDataTbody = rawDataTableElement.querySelector("tbody");

		const fetchRawDataLogs = () => {
			fetch(window.djangoURLs.rawDataLogs, {
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
}