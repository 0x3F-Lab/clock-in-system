// Shared global variables so they persist accross calls
let map;
let marker;
let circle;

$(document).ready(function() {
  // Show the initial selected store's info
  showSelectedStoreInfo();

  // If selected store is updated, change the store info shown
  $('#storeSelectDropdown').on('change', function() {
    showSelectedStoreInfo();
  });

  // Add event handler to when user clicks "Update" button
  $('#openEditModal').on('click', () => {
    openEditModal();
  });

  // Add event to submitting the edit modal
  $('#editModalSubmit').on('click', () => {
    updateStoreInfo();
  });

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(45); // 45 minutes
});


function showSelectedStoreInfo() {
  // Hide all store info blocks
  $('[id^="store-info-"]').addClass('d-none');

  // Show selected one
  const selectedID = getSelectedStoreID();
  const infoDiv = $('#store-info-' + selectedID).removeClass('d-none');

  // If lat/lng are defined, update the map
  const lat = ensureSafeFloat(infoDiv.data('lat'), -90.0, 90.0);
  const lng = ensureSafeFloat(infoDiv.data('lng'), -180.0, 180.0);
  const radius = ensureSafeFloat(infoDiv.data('radius'), 0.0, null);

  if (!isNaN(lat) && !isNaN(lng)) {
    addMap(lat, lng, radius || 500);
  }
}


function addMap(lat, lng, radius) {
  const position = [lat, lng];

  if (!map) {
    map = L.map('map').setView(position, 15);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }).addTo(map);

    marker = L.marker(position).addTo(map).bindPopup("Store Location").openPopup();

    circle = L.circle(position, {
      color: '#007BFF',
      fillColor: '#007BFF',
      fillOpacity: 0.2,
      radius: radius
    }).addTo(map);
  } else {
    map.setView(position, 15);
    marker.setLatLng(position);
    circle.setLatLng(position).setRadius(radius);
  }
}


function openEditModal() {
  const selectedID = getSelectedStoreID();
  const infoDiv = $('#store-info-' + selectedID);

  if (!infoDiv.length) {
    console.error('Store info not found for ID:', selectedID);
    return;
  }

  // Extract values from the displayed info
  const street = infoDiv.find('p:contains("Street Location:")').text().replace('Street Location:', '').trim();
  const dist = infoDiv.find('p:contains("Allowable Clocking Distance:")').text().replace('Allowable Clocking Distance:', '').replace('meters', '').trim();

  // Update modal inputs
  $('#editStreet').val(street);
  $('#editDist').val(dist);

  const editModal = new bootstrap.Modal(document.getElementById("editModal"));
  editModal.show();
}


function updateStoreInfo() {
  showSpinner();

  $.ajax({
        url: `${window.djangoURLs.updateStoreInfo}${getSelectedStoreID()}/`,
        type: 'PATCH',
        xhrFields: {
          withCredentials: true
        },
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        contentType: 'application/json',
        data: JSON.stringify({
          loc_street: $('#editStreet').val(),
          clocking_dist: $('#editDist').val(),
        }),
    
        success: function(resp) {
          hideSpinner();
          $("#editModal").modal("hide");
          const saved = saveNotificationForReload(`Successfully updated store information for ${resp.code}.`, "success", `Successfully updated store information for ${resp.code}. Please reload the page to see changes.`);
          if (saved) {location.reload();}
        },
    
        error: function(jqXHR, textStatus, errorThrown) {
          hideSpinner();
          let errorMessage;
          if (jqXHR.status == 500) {
            errorMessage = "Failed to update store information due to internal server errors. Please try again.";
          } else {
            errorMessage = jqXHR.responseJSON?.Error || "Failed to update store information. Please try again.";
          }
          showNotification(errorMessage, "danger");
        }
      });
}