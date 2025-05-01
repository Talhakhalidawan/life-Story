document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in
    checkLoginStatus();
  });

  window.addEventListener('pageshow', function(event) {
    // Check if the page is being shown from the history
    if (event.persisted) {
      // Check if user is logged in
      checkLoginStatus();
    }
  });

  function checkLoginStatus() {
    fetch('/auth/api/check_login', {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      // If user is not logged in and not already on login or signup page, redirect to login
      if (!data.is_authenticated) {
        const currentPath = window.location.pathname;
        // Don't redirect if already on login or signup pages
        if (!currentPath.includes('/auth/login') && !currentPath.includes('/auth/signup')) {
          window.location.href = '/auth/login';
        }
      }
    })
    .catch(error => {
      console.error('Error checking login status:', error);
    });
  }