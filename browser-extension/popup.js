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
    
    // Send bet to background script
    chrome.runtime.sendMessage(
      { action: 'placeBet', bet: bet },
      (response) => {
        if (response.success) {
          showStatus('Bet sent! Check plays888.co tab...', 'success');
          // Clear form
          document.getElementById('game').value = '';
          document.getElementById('betType').value = '';
          document.getElementById('odds').value = '';
          document.getElementById('wager').value = '';
        } else {
          showStatus(response.message, 'error');
        }
      }
    );
  });
});

function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status ${type}`;
  statusDiv.style.display = 'block';
  
  setTimeout(() => {
    statusDiv.style.display = 'none';
  }, 5000);
}
