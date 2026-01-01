chrome.action.onClicked.addListener(function() {
  chrome.tabs.create({ url: chrome.runtime.getURL('popup.html') });
});

// Auto-refresh plays888.co tabs with random intervals (7-15 minutes) to prevent session timeout
// SLEEP HOURS: 10:45 PM - 5:30 AM Arizona time (no refresh during this period)
var MIN_REFRESH_MINUTES = 7;
var MAX_REFRESH_MINUTES = 15;

// Arizona is UTC-7 (no daylight saving)
var ARIZONA_OFFSET = -7;

function getArizonaTime() {
  var now = new Date();
  var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  var arizona = new Date(utc + (3600000 * ARIZONA_OFFSET));
  return arizona;
}

function isSleepHours() {
  var arizona = getArizonaTime();
  var hour = arizona.getHours();
  var minute = arizona.getMinutes();
  var timeInMinutes = hour * 60 + minute;
  
  // Sleep window: 10:45 PM (22:45 = 1365 mins) to 5:30 AM (5:30 = 330 mins)
  var sleepStart = 22 * 60 + 45;  // 10:45 PM = 1365 minutes
  var sleepEnd = 5 * 60 + 30;      // 5:30 AM = 330 minutes
  
  // Check if current time is in sleep window
  if (timeInMinutes >= sleepStart || timeInMinutes < sleepEnd) {
    return true;
  }
  return false;
}

function getRandomInterval() {
  return Math.floor(Math.random() * (MAX_REFRESH_MINUTES - MIN_REFRESH_MINUTES + 1)) + MIN_REFRESH_MINUTES;
}

function refreshPlays888Tabs() {
  var arizona = getArizonaTime();
  var timeStr = arizona.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  
  // Check if we're in sleep hours
  if (isSleepHours()) {
    console.log('Sleep hours (' + timeStr + ' Arizona) - skipping refresh');
    scheduleNextRefresh();
    return;
  }
  
  console.log('Checking plays888.co tabs for refresh... (' + timeStr + ' Arizona)');
  chrome.tabs.query({ url: '*://*.plays888.co/*' }, function(tabs) {
    if (tabs.length > 0) {
      console.log('Found', tabs.length, 'plays888.co tab(s)');
      tabs.forEach(function(tab) {
        console.log('Refreshing tab:', tab.id, tab.url);
        chrome.tabs.reload(tab.id);
      });
    } else {
      console.log('No plays888.co tabs open');
    }
  });
  
  // Schedule next refresh with a new random interval
  scheduleNextRefresh();
}

function scheduleNextRefresh() {
  var nextInterval = getRandomInterval();
  chrome.alarms.create('refreshPlays888', { delayInMinutes: nextInterval });
  console.log('Next tab refresh scheduled in ' + nextInterval + ' minutes');
}

// Start the first scheduled refresh
scheduleNextRefresh();

chrome.alarms.onAlarm.addListener(function(alarm) {
  if (alarm.name === 'refreshPlays888') {
    refreshPlays888Tabs();
  }
});

console.log('Auto-refresh enabled: 7-15 min random intervals, paused 10:45 PM - 5:30 AM Arizona');

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
      var apiUrl = result.apiUrl || 'https://betsmart-28.preview.emergentagent.com';
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
