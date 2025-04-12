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


///////////////////////


// General loader function that runs when page loads
$(document).ready(function() {
  handleChangePin();
});

function handleChangePin() {
  // When modal is about to be shown, populate employee list
  $("#changePinModal").on("show.bs.modal", function() {
    // Clear any previous data
    $("#changePinUserList").empty();
    $("#changePinSearchBar").val("");
    $("#changePinSelectedUserID").val("");
    $("#currentPin").val("");
    $("#newPin").val("");
    $("#confirmNewPin").val("");

    // Fetch the employees listEmployeeNames endpoint
    $.get(window.djangoURLs.listEmployeeNames, function(data) {
      // data might be [[1, "John Smith"], [2, "Jane Doe"]], etc.
      data.forEach(emp => {
        const userId = emp[0];
        const fullName = emp[1];
        $("#changePinUserList").append(`
          <li
            class="list-group-item"
            data-id="${userId}"
            style="cursor: pointer;"
          >
            ${fullName}
          </li>
        `);
      });
    })
    .fail(function(xhr) {
      showNotification("Failed to load employee list.", "danger");
      console.error(xhr);
    });
  });

  // Filter list on input
  $("#changePinSearchBar").on("input", function() {
    const term = $(this).val().toLowerCase();
    $("#changePinUserList").children("li").each(function() {
      $(this).toggle($(this).text().toLowerCase().includes(term));
    });
  });

  // Click on an employee name to select
  $("#changePinUserList").on("click", "li", function() {
    $("#changePinUserList li").removeClass("active");
    $(this).addClass("active");
    const userId = $(this).data("id");
    $("#changePinSelectedUserID").val(userId);
  });

  // Submit button
  $("#submitChangePin").on("click", function() {
    const userID = $("#changePinSelectedUserID").val();
    const currentPin = $("#currentPin").val().trim();
    const newPin = $("#newPin").val().trim();
    const confirmNewPin = $("#confirmNewPin").val().trim();

    if (!userID) {
      showNotification("Please select your name from the list.", "danger");
      return;
    }
    if (!currentPin || !newPin || !confirmNewPin) {
      showNotification("All pin fields are required.", "danger");
      return;
    }
    if (newPin !== confirmNewPin) {
      showNotification("New pin and confirmation do not match.", "danger");
      return;
    }

    const csrftoken = getCookie('csrftoken');

    // POST to your "change pin" endpoint
    $.ajax({
      url: window.djangoURLs.changePin,
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken
      },
      data: {
        user_id: userID,
        current_pin: currentPin,
        new_pin: newPin
      },
      success: function(response) {
        if (response.success) {
          showNotification(response.message, "success");
          $("#changePinModal").modal("hide");
        } else {
          showNotification(response.message, "danger");
        }
      },
      error: function(jqXHR, textStatus, errorThrown) {
        let errorMessage;
        if (jqXHR.status == 500) {
          errorMessage = "Failed to change pin due to internal error. Please try again.";
        } else {
          errorMessage = jqXHR.responseJSON?.Error || "Failed to change pin. Please try again.";
        }
        showNotification(errorMessage, "danger");
      }
    });
  });
}
