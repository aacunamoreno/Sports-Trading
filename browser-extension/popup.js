// Popup script

document.addEventListener('DOMContentLoaded', () => {
  // Load saved API URL
  chrome.storage.local.get(['apiUrl'], (result) => {
    if (result.apiUrl) {
      document.getElementById('apiUrl').value = result.apiUrl;
    }
  });
  
  // Save API URL
  document.getElementById('saveApi').addEventListener('click', () => {
    const apiUrl = document.getElementById('apiUrl').value;
    chrome.storage.local.set({ apiUrl: apiUrl }, () => {
      showStatus('API URL saved successfully!', 'success');
    });
  });
  
  // Place bet
  document.getElementById('placeBet').addEventListener('click', async () => {
    const league = document.getElementById('league').value;
    const game = document.getElementById('game').value;
    const betType = document.getElementById('betType').value;
    const odds = parseInt(document.getElementById('odds').value);
    const wager = parseFloat(document.getElementById('wager').value);
    
    if (!game || !betType || !odds || !wager) {
      showStatus('Please fill in all fields', 'error');
      return;
    }
    
    const bet = {
      league: league,
      game: game,
      bet_type: betType,
      line: betType.match(/[ou]\d+/i)?.[0] || betType,
      odds: odds,
      wager: wager
    };
    
    showStatus('Sending bet to plays888.co...', 'info');
    
    // Send bet to background script
    chrome.runtime.sendMessage(
      { action: 'placeBet', bet: bet },
      (response) => {
        if (response.success) {
          showStatus('Automation started! Watch plays888.co tab...', 'info');
          // Don't clear form until bet is confirmed
        } else {
          showStatus(response.message, 'error');
        }
      }
    );
  });
  
  // Listen for bet completion messages
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'betStatus') {
      showStatus(request.message, request.type);
      if (request.type === 'success') {
        // Clear form on success
        document.getElementById('game').value = '';
        document.getElementById('betType').value = '';
        document.getElementById('odds').value = '';
        document.getElementById('wager').value = '';
      }
    }
  });
});

function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  statusDiv.style.display = 'block';
  
  // Don't auto-hide info messages
  if (type !== 'info') {
    setTimeout(() => {
      statusDiv.style.display = 'none';
    }, 10000);
  }
}
