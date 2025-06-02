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

  // Show the selected one
  $('#store-info-' + getSelectedStoreID()).removeClass('d-none');
}