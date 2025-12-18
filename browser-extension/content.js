console.log('=== PLAYS888 BOT LOADED ===');
console.log('Page:', window.location.href);

// Check for pending bet on ANY page load
var pendingBetRaw = localStorage.getItem('plays888_pending_bet');
var pendingBet = null;

// Only use pending bet if it's recent (within 60 seconds) and has bot_initiated flag
if (pendingBetRaw) {
  try {
    var parsed = JSON.parse(pendingBetRaw);
    var betTime = parsed.timestamp || 0;
    var now = Date.now();
    var age = (now - betTime) / 1000;
    
    // Only consider it valid if:
    // 1. It was created within the last 60 seconds
    // 2. It has the bot_initiated flag (meaning it came from the extension popup)
    if (age < 60 && parsed.bot_initiated === true) {
      pendingBet = pendingBetRaw;
      console.log('Valid pending bot bet found, age:', age, 'seconds');
    } else {
      console.log('Pending bet expired or not bot-initiated, ignoring. Age:', age, 'Bot initiated:', parsed.bot_initiated);
      localStorage.removeItem('plays888_pending_bet');
    }
  } catch(e) {
    console.log('Error parsing pending bet, clearing it');
    localStorage.removeItem('plays888_pending_bet');
  }
}

console.log('Active pending bet:', pendingBet ? 'YES' : 'NO');

// Check if Confirm button exists on this page
setTimeout(function() {
  var confirmBtn = document.querySelector('input[value="Confirm"]');
  console.log('Confirm button found:', confirmBtn ? 'YES' : 'NO');
  
  // ONLY auto-click if there's a valid, recent, bot-initiated pending bet
  if (confirmBtn && pendingBet) {
    console.log('CONFIRM BUTTON FOUND with valid bot bet! Clicking...');
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
