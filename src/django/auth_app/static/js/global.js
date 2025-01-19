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


// Get CSRF Token (allow for the method to change when using secure cookies...)
function getCSRFToken() {
 return getCookie('csrftoken');
}


// General loader function that runs when page loads
$(document).ready(function() {
});