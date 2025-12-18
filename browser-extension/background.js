chrome.action.onClicked.addListener(function() {
  chrome.tabs.create({ url: chrome.runtime.getURL('popup.html') });
});

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === 'placeBet') {
    chrome.tabs.query({ url: '*://*.plays888.co/*' }, function(tabs) {
      if (tabs.length === 0) {
        sendResponse({ success: false, message: 'Open plays888.co first!' });
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, request, function(response) {
        if (chrome.runtime.lastError) {
          sendResponse({ success: false, message: 'Refresh plays888.co page and try again' });
        } else {
          sendResponse(response || { success: false, message: 'No response' });
        }
      });
    });
    return true;
  }
  
  // Handle bet completion - send to backend for Telegram notification
  if (request.action === 'betComplete') {
    console.log('=== BET COMPLETE RECEIVED ===');
    console.log('Ticket:', request.ticketNumber);
    console.log('Bet details:', JSON.stringify(request.bet));
    
    // Get the API URL from storage and send to backend
    chrome.storage.local.get(['apiUrl'], function(result) {
      var apiUrl = result.apiUrl || 'https://betbot-1.preview.emergentagent.com';
      console.log('Using API URL:', apiUrl);
      
      var payload = {
        game: request.bet.game || 'Unknown Game',
        bet_type: request.bet.bet_type || 'Unknown',
        line: request.bet.line || request.bet.bet_type || 'Unknown',
        odds: request.bet.odds || -110,
        wager: request.bet.wager || 0,
        bet_slip_id: request.ticketNumber,
        notes: 'Placed via Chrome Extension. Ticket#: ' + request.ticketNumber
      };
      
      console.log('Sending to backend:', JSON.stringify(payload));
      
      fetch(apiUrl + '/api/bets/record-manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function(response) { 
        console.log('Response status:', response.status);
        return response.json(); 
      })
      .then(function(data) {
        console.log('=== BACKEND RESPONSE ===');
        console.log('Success:', data.success);
        console.log('Message:', data.message);
        // Show notification to user
        if (data.success) {
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icon48.png',
            title: 'Bet Recorded!',
            message: 'Telegram notification sent for Ticket#' + request.ticketNumber
          });
        }
      })
      .catch(function(err) {
        console.error('=== BACKEND ERROR ===');
        console.error('Error:', err.message || err);
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icon48.png',
          title: 'Error Recording Bet',
          message: 'Failed to send notification: ' + (err.message || 'Unknown error')
        });
      });
    });
    
    sendResponse({ received: true });
    return true;
  }
});
