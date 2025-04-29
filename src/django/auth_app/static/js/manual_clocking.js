$(document).ready(function() {
  // Ensure submit button outside form works
  $('#clockingButton').on('click', () => {
    $('#hiddenDeliveries').val($('#visibleDeliveries').val()); // Ensure the deliveries is passed to the hidden field
    $('#manualClockingForm').submit()
  });

  // Handle deliveries adjustment
  handleDeliveryAdjustment();
});

function handleDeliveryAdjustment() {
  const $input = $('#visibleDeliveries');

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