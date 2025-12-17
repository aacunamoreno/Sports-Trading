// Content script that runs on plays888.co pages

console.log('Plays888 Automation: Content script loaded');

let currentBet = null;
let automationInProgress = false;

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'executeBet') {
    console.log('Received bet to execute:', request.bet);
    currentBet = request.bet;
    startAutomation();
    sendResponse({ success: true });
  }
});

// Main automation function
async function startAutomation() {
  if (automationInProgress) {
    console.log('Automation already in progress');
    return;
  }
  
  automationInProgress = true;
  
  try {
    console.log('Starting automation for bet:', currentBet);
    
    // Step 1: Navigate to Straight if not already there
    const currentUrl = window.location.href;
    
    if (!currentUrl.includes('CreateSports.aspx') && !currentUrl.includes('CreateWager.aspx')) {
      console.log('Step 1: Navigating to Straight section...');
      const straightLink = document.querySelector('a[href*="Straight"]');
      if (straightLink) {
        straightLink.click();
        await sleep(2000);
      }
    }
    
    // Step 2: Check league checkbox if on league selection page
    if (currentUrl.includes('CreateSports.aspx') && !document.querySelector('table.table')) {
      console.log('Step 2: Selecting league...');
      const leagueText = document.evaluate(
        `//text()[contains(., '${currentBet.league}')]`,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      ).singleNodeValue;
      
      if (leagueText && leagueText.parentElement) {
        leagueText.parentElement.click();
        await sleep(1000);
        
        // Click Continue
        const continueBtn = document.querySelector('input[value="Continue"]');
        if (continueBtn) {
          continueBtn.click();
          await sleep(5000); // Wait for games to load
        }
      }
    }
    
    // Step 3: Find and click the odds button
    console.log('Step 3: Looking for odds button...');
    const oddsText = currentBet.odds > 0 ? `+${currentBet.odds}` : `${currentBet.odds}`;
    
    // Find all submit buttons
    const allButtons = document.querySelectorAll('input[type="submit"]');
    let oddsButton = null;
    
    for (const btn of allButtons) {
      const value = btn.value;
      if (value && value.includes(oddsText)) {
        console.log(`Found odds button: ${value}`);
        oddsButton = btn;
        break;
      }
    }
    
    if (oddsButton) {
      oddsButton.click();
      await sleep(1000);
      
      // Click Continue to go to bet slip
      const continueBtn = document.querySelector('input[value="Continue"]');
      if (continueBtn) {
        continueBtn.click();
        await sleep(3000);
      }
    } else {
      throw new Error(`Could not find odds button containing ${oddsText}`);
    }
    
    // Step 4: Fill bet slip
    console.log('Step 4: Filling bet slip...');
    
    // Select "To Win Amount" radio button
    const toWinRadio = document.querySelector('input[value="To Win Amount"]');
    if (toWinRadio) {
      toWinRadio.click();
      await sleep(500);
    }
    
    // Enter wager amount
    const amountInput = document.querySelector('input[type="text"]:not([style*="display: none"])');
    if (amountInput) {
      amountInput.value = '';
      amountInput.value = currentBet.wager.toString();
      await sleep(1000);
      
      // Click Continue
      const continueBtn = document.querySelector('input[value="Continue"]');
      if (continueBtn) {
        continueBtn.click();
        await sleep(3000);
      }
    } else {
      throw new Error('Could not find amount input field');
    }
    
    // Step 5: Confirm bet
    console.log('Step 5: Confirming bet...');
    const confirmBtn = document.querySelector('input[value="Confirm"]');
    if (confirmBtn) {
      confirmBtn.click();
      await sleep(3000);
      
      // Step 6: Extract ticket number
      console.log('Step 6: Extracting ticket number...');
      const pageText = document.body.textContent;
      const ticketMatch = pageText.match(/Ticket#?[:\s]*(\d+)/);
      
      if (ticketMatch) {
        const ticketNumber = ticketMatch[1];
        console.log('✅ BET PLACED SUCCESSFULLY! Ticket#:', ticketNumber);
        
        // Send success notification
        showNotification('Bet Placed Successfully!', `Ticket#: ${ticketNumber}`);
        
        // Report back to background script
        chrome.runtime.sendMessage({
          action: 'betComplete',
          result: {
            success: true,
            ticket_number: ticketNumber,
            game: currentBet.game,
            bet_type: currentBet.bet_type,
            line: currentBet.line,
            odds: currentBet.odds,
            wager: currentBet.wager
          }
        });
      } else {
        throw new Error('Bet may have been placed but could not extract ticket number');
      }
    } else {
      throw new Error('Could not find Confirm button');
    }
    
  } catch (error) {
    console.error('Automation error:', error);
    showNotification('Bet Placement Failed', error.message);
  } finally {
    automationInProgress = false;
    currentBet = null;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function showNotification(title, message) {
  // Create notification element
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #10b981;
    color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    z-index: 999999;
    font-family: Arial, sans-serif;
    max-width: 300px;
  `;
  notification.innerHTML = `
    <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px;">${title}</div>
    <div style="font-size: 14px;">${message}</div>
  `;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 5000);
}
