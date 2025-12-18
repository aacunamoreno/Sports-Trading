console.log('=== PLAYS888 BOT LOADED ===');
console.log('Page:', window.location.href);

// Check for pending bet on ANY page load
var pendingBet = localStorage.getItem('plays888_pending_bet');

// Check if Confirm button exists on this page
setTimeout(function() {
  var confirmBtn = document.querySelector('input[value="Confirm"]');
  if (confirmBtn && pendingBet) {
    console.log('CONFIRM BUTTON FOUND! Clicking...');
    confirmBtn.click();
    
    // Wait for confirmation and extract ticket number
    setTimeout(function() {
      var pageText = document.body.textContent;
      var ticketMatch = pageText.match(/Ticket#?\s*:?\s*(\d+)/i);
      
      if (ticketMatch) {
        var ticketNumber = ticketMatch[1];
        var bet = JSON.parse(pendingBet);
        
        console.log('BET PLACED! Ticket#:', ticketNumber);
        alert('BET PLACED! Ticket#: ' + ticketNumber);
        
        // Send to background script to record and send Telegram notification
        chrome.runtime.sendMessage({
          action: 'betComplete',
          ticketNumber: ticketNumber,
          bet: bet
        });
        
        localStorage.removeItem('plays888_pending_bet');
      }
    }, 3000);
  }
}, 1500);

// Listen for bet requests
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  console.log('MESSAGE:', request);
  
  if (request.action === 'placeBet') {
    var bet = request.bet;
    localStorage.setItem('plays888_pending_bet', JSON.stringify(bet));
    
    var lineNumber = bet.bet_type.replace(/[^0-9.]/g, '');
    var oddsNumber = String(bet.odds);
    
    console.log('Looking for:', lineNumber, oddsNumber);
    
    var inputs = document.querySelectorAll('input');
    var found = false;
    
    for (var i = 0; i < inputs.length; i++) {
      var val = inputs[i].value || '';
      if (val.indexOf(lineNumber) >= 0 && val.indexOf(oddsNumber) >= 0) {
        console.log('FOUND:', val);
        inputs[i].click();
        found = true;
        
        setTimeout(function() {
          var cont = document.querySelector('input[value="Continue"]');
          if (cont) cont.click();
        }, 1500);
        break;
      }
    }
    
    sendResponse({ success: found, message: found ? 'Started!' : 'Not found' });
  }
  return true;
});

console.log('Ready!');
