// Background service worker for the extension

let apiUrl = '';
let pendingBet = null;

// Initialize
chrome.runtime.onInstalled.addListener(() => {
  console.log('Plays888 Automation Extension Installed');
});

// Listen for messages from popup or content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'setApiUrl') {
    apiUrl = request.url;
    chrome.storage.local.set({ apiUrl: apiUrl });
    sendResponse({ success: true });
  }
  
  if (request.action === 'getApiUrl') {
    chrome.storage.local.get(['apiUrl'], (result) => {
      sendResponse({ url: result.apiUrl || '' });
    });
    return true; // Keep channel open for async response
  }
  
  if (request.action === 'placeBet') {
    pendingBet = request.bet;
    // Send bet to content script on plays888.co tab
    chrome.tabs.query({ url: 'https://www.plays888.co/*' }, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'executeBet',
          bet: pendingBet
        });
        sendResponse({ success: true, message: 'Bet sent to plays888.co tab' });
      } else {
        sendResponse({ success: false, message: 'No plays888.co tab found. Please open the site first.' });
      }
    });
    return true;
  }
  
  if (request.action === 'betComplete') {
    // Report bet result back to backend
    chrome.storage.local.get(['apiUrl'], async (result) => {
      if (result.apiUrl) {
        try {
          const response = await fetch(`${result.apiUrl}/api/bets/record-manual`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              game: request.result.game,
              bet_type: request.result.bet_type,
              line: request.result.line,
              odds: request.result.odds,
              wager: request.result.wager,
              bet_slip_id: request.result.ticket_number,
              notes: `Auto-placed via extension. Ticket#: ${request.result.ticket_number}`
            })
          });
          const data = await response.json();
          console.log('Bet recorded in backend:', data);
        } catch (error) {
          console.error('Failed to record bet:', error);
        }
      }
    });
    pendingBet = null;
  }
});
