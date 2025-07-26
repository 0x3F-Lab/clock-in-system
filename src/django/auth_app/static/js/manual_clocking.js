$(document).ready(function() {
  // Ensure submit button outside form works
  $('#clockingButton').on('click', function(e) {
    e.preventDefault();
    handleManualClockingFormSubmission();
  });

  // Handle deliveries adjustment
  handleDeliveryAdjustment();

  // Initial check of enabling/disabling clocking button
  toggleClockingButton();

  // Bind updates to field to check for clocking button updates
  $('#id_store_pin, #id_employee_pin').on('input', toggleClockingButton);

  // Add page reloader to force reload after period of inactivity
  setupVisibilityReload(30); // 30 minutes
});


function handleDeliveryAdjustment() {
  const $input = $('#visibleDeliveries');

  // Copy the invisible delivery count field into visible field if the form was sent back (allows state transfer)
  $input.val($('#id_deliveries').val());

  $('#plusButton').on('click', function (e) {
    e.preventDefault();
    const curr = parseInt($input.val(), 10) || 0;
    $input.val(curr + 1);
    if (curr == 0) {
      $('#minusButton').removeClass('disabled');
    }
  });

  $('#minusButton').on('click', function (e) {
    e.preventDefault();
    const curr = parseInt($input.val(), 10) || 0;
    if (curr > 0) {
      $input.val(curr - 1);
    }
    if (curr == 1) {
      $('#minusButton').addClass('disabled');
    }
  });

  // Handle minus button disabling
  $('#visibleDeliveries').on('input', function () {
    if ($(this).val() > 0) {
      $('#minusButton').removeClass('disabled');

    } else{
      $('#minusButton').addClass('disabled');
    }
  });

  // Disable button on first load if the input field is default 0
  if ((parseInt($input.val(), 10) || 0) == 0) {
    $('#minusButton').addClass('disabled'); 
  }
}


function toggleClockingButton() {
  const storePinFilled = $('#id_store_pin').val().trim() !== "";
  const employeePinFilled = $('#id_employee_pin').val().trim() !== "";

  if (storePinFilled && employeePinFilled) {
    $('#clockingButton').prop('disabled', false);
  } else {
    $('#clockingButton').prop('disabled', true);
  }
}


async function handleManualClockingFormSubmission() {
  // Ensure delivery count is within limits (update the field if not)
  const deliveries = ensureSafeInt($('#visibleDeliveries').val(), 0, null);
  $('#visibleDeliveries').val(deliveries);

  // Ensure the deliveries is passed to the hidden field
  $('#id_deliveries').val(deliveries);
  
  // Get the location data
  const locationData = await getLocationData();
  
  if (!locationData) {
    return; // Errors handled by location function
  }

  const [userLat, userLong] = locationData;

  // Update the fields
  $('#id_latitude').val(userLat);
  $('#id_longitude').val(userLong);
  
  // Submit the form with the updated fields
  $('#manualClockingForm').submit()
}