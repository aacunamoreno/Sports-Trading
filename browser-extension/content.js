console.log('=== PLAYS888 BOT LOADED ===');
console.log('Page:', window.location.href);

// Check for pending bet on ANY page load
var pendingBet = localStorage.getItem('plays888_pending_bet');
console.log('Pending bet in localStorage:', pendingBet ? 'YES' : 'NO');

// Check if Confirm button exists on this page
setTimeout(function() {
  var confirmBtn = document.querySelector('input[value="Confirm"]');
  console.log('Confirm button found:', confirmBtn ? 'YES' : 'NO');
  
  if (confirmBtn && pendingBet) {
    console.log('CONFIRM BUTTON FOUND! Clicking...');
    confirmBtn.click();
    
    // Wait for confirmation and extract ticket number
    setTimeout(function() {
      var pageText = document.body.textContent;
      var ticketMatch = pageText.match(/Ticket#?\s*:?\s*(\d+)/i);
      
      console.log('Looking for ticket number in page...');
      console.log('Ticket match:', ticketMatch);
      
      if (ticketMatch) {
        var ticketNumber = ticketMatch[1];
        var bet = JSON.parse(pendingBet);
        
        console.log('=== BET PLACED ===');
        console.log('Ticket#:', ticketNumber);
        console.log('Bet details:', JSON.stringify(bet));
        
        alert('BET PLACED! Ticket#: ' + ticketNumber + '\n\nSending Telegram notification...');
        
        // Send to background script to record and send Telegram notification
        console.log('Sending betComplete message to background...');
        chrome.runtime.sendMessage({
          action: 'betComplete',
          ticketNumber: ticketNumber,
          bet: bet
        }, function(response) {
          console.log('Background response:', response);
          if (chrome.runtime.lastError) {
            console.error('Message error:', chrome.runtime.lastError.message);
            alert('ERROR: Could not send notification. Check extension logs.');
          } else {
            console.log('Message sent successfully!');
          }
        });
        
        localStorage.removeItem('plays888_pending_bet');
        console.log('Pending bet cleared from localStorage');
      } else {
        console.log('No ticket number found on page');
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
