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
    console.log('Bet complete, sending to backend:', request);
    
    // Get the API URL from storage and send to backend
    chrome.storage.local.get(['apiUrl'], function(result) {
      var apiUrl = result.apiUrl || 'https://betautopilot-1.preview.emergentagent.com';
      
      fetch(apiUrl + '/api/bets/record-manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game: request.bet.game,
          bet_type: request.bet.bet_type,
          line: request.bet.line || request.bet.bet_type,
          odds: request.bet.odds,
          wager: request.bet.wager,
          bet_slip_id: request.ticketNumber,
          notes: 'Placed via Chrome Extension. Ticket#: ' + request.ticketNumber
        })
      })
      .then(function(response) { return response.json(); })
      .then(function(data) {
        console.log('Backend recorded bet:', data);
      })
      .catch(function(err) {
        console.error('Failed to record bet:', err);
      });
    });
  }
});
