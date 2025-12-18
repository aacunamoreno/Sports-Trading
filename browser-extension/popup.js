document.addEventListener('DOMContentLoaded', function() {
  // Load saved API URL
  chrome.storage.local.get(['apiUrl'], function(result) {
    if (result.apiUrl) {
      document.getElementById('apiUrl').value = result.apiUrl;
      document.getElementById('apiStatus').textContent = '✓ Connected to backend';
    }
  });
  
  // Save API URL
  document.getElementById('saveApi').addEventListener('click', function() {
    var apiUrl = document.getElementById('apiUrl').value.trim();
    if (apiUrl) {
      // Remove trailing slash
      if (apiUrl.endsWith('/')) {
        apiUrl = apiUrl.slice(0, -1);
      }
      
      chrome.storage.local.set({ apiUrl: apiUrl }, function() {
        document.getElementById('apiStatus').textContent = '✓ API URL saved!';
        document.getElementById('apiStatus').style.color = '#10b981';
        
        // Test the connection
        fetch(apiUrl + '/api/telegram/status')
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.configured) {
              document.getElementById('apiStatus').textContent = '✓ Connected! Telegram: @' + data.bot_username;
            } else {
              document.getElementById('apiStatus').textContent = '✓ Connected (Telegram not configured)';
            }
          })
          .catch(function(err) {
            document.getElementById('apiStatus').textContent = '⚠ Could not connect to backend';
            document.getElementById('apiStatus').style.color = '#f59e0b';
          });
      });
    }
  });
  
  // Place bet
  document.getElementById('placeBtn').addEventListener('click', function() {
    var status = document.getElementById('status');
    status.className = 'wait';
    status.textContent = 'Sending...';
    
    chrome.runtime.sendMessage({
      action: 'placeBet',
      bet: {
        league: document.getElementById('league').value,
        game: document.getElementById('game').value,
        bet_type: document.getElementById('betType').value,
        odds: parseInt(document.getElementById('odds').value),
        wager: parseFloat(document.getElementById('wager').value)
      }
    }, function(r) {
      status.className = r && r.success ? 'ok' : 'err';
      status.textContent = r ? r.message : 'Error';
    });
  });
});
