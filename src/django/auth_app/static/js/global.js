// Function to show notifications
function showNotification(message, type = "warning") {
  // Create notification HTML element
  const notification = $(`<div class="alert alert-${type} alert-dismissible fade show" role="alert" aria-live="assertive" aria-atomic="true"></div>`);
  notification.text(message);
  
  // Add close button to the notification
  notification.append('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>');
  
  // Append notification to the notification container
  $('#notification-container').append(notification);
  
  // Automatically remove notification after 5.5 seconds
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(notification[0]);
    bsAlert.close();
  }, 5500);

  // Log warning message to console
  switch (type.toLowerCase()) {
    case "warning":
      console.warn(message);
      break;
    case "danger":
      console.error(message);
      break;
    default:
      break;
  }
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


// Get CSRF Token (allow for the method to change when using secure cookies...)
function getCSRFToken() {
  const $token = $('meta[name="csrf-token"]').attr('content')
  if (!$token) {
    console.error("CSRF token was not loaded on this page correctly. Please contact an admin for further assistance.")
  }

  // Return regardless
  return $token
}
