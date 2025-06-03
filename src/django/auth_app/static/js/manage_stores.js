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
      attribution: '© OpenStreetMap contributors'
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