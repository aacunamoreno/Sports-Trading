// Content script that runs on plays888.co pages

console.log('🎰 Plays888 Automation: Content script loaded on', window.location.href);

let currentBet = null;
let automationInProgress = false;

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Content script received message:', request);
  
  if (request.action === 'executeBet') {
    console.log('Received bet to execute:', request.bet);
    currentBet = request.bet;
    startAutomation();
    sendResponse({ success: true, message: 'Automation started' });
  }
  return true;
});

// Report status back to extension
function reportStatus(message, type = 'info') {
  console.log(`[${type.toUpperCase()}]`, message);
  chrome.runtime.sendMessage({
    action: 'betStatus',
    message: message,
    type: type
  });
}

function reportError(message) {
  console.error('❌ Automation Error:', message);
  chrome.runtime.sendMessage({
    action: 'betFailed',
    message: message
  });
}

function reportSuccess(result) {
  console.log('✅ Bet placed successfully:', result);
  chrome.runtime.sendMessage({
    action: 'betComplete',
    result: result
  });
}

// Main automation function
async function startAutomation() {
  if (automationInProgress) {
    reportStatus('Automation already in progress', 'info');
    return;
  }
  
  automationInProgress = true;
  
  try {
    console.log('Starting automation for bet:', currentBet);
    reportStatus('Starting bet automation...', 'info');
    
    const currentUrl = window.location.href;
    console.log('Current URL:', currentUrl);
    
    // Check if we're on the right page
    if (currentUrl.includes('Welcome.aspx') || currentUrl.includes('CreateSports.aspx')) {
      // Step 1: Click Straight in sidebar
      reportStatus('Step 1: Looking for Straight link...', 'info');
      const straightLink = findElementByText('a', 'Straight');
      
      if (straightLink && !currentUrl.includes('CreateSports.aspx')) {
        console.log('Clicking Straight link');
        straightLink.click();
        await sleep(3000);
      }
      
      // Step 2: Select league
      reportStatus(`Step 2: Selecting league: ${currentBet.league}`, 'info');
      await selectLeague(currentBet.league);
      
    } else if (currentUrl.includes('CreateWager.aspx')) {
      // Already on bet slip page
      reportStatus('On bet slip page, filling details...', 'info');
      await fillBetSlip();
      
    } else {
      reportError('Please navigate to plays888.co/wager/Welcome.aspx first');
      automationInProgress = false;
      return;
    }
    
  } catch (error) {
    console.error('Automation error:', error);
    reportError(error.message || 'Unknown error during automation');
    showNotification('Bet Placement Failed', error.message, 'error');
  } finally {
    automationInProgress = false;
    currentBet = null;
  }
}

async function selectLeague(leagueName) {
  // Look for league checkbox/link
  const allElements = document.querySelectorAll('td, span, label');
  let leagueElement = null;
  
  for (const el of allElements) {
    if (el.textContent.includes(leagueName)) {
      leagueElement = el;
      break;
    }
  }
  
  if (leagueElement) {
    // Click on it to select
    const checkbox = leagueElement.querySelector('input[type="checkbox"]') || 
                     leagueElement.closest('tr')?.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.click();
    } else {
      leagueElement.click();
    }
    await sleep(1000);
    
    // Click Continue
    reportStatus('Clicking Continue...', 'info');
    const continueBtn = document.querySelector('input[value="Continue"]');
    if (continueBtn) {
      continueBtn.click();
      await sleep(5000); // Wait for games to load
      
      // Now select odds
      await selectOdds();
    } else {
      reportError('Continue button not found');
    }
  } else {
    reportError(`League "${leagueName}" not found on page`);
  }
}

async function selectOdds() {
  reportStatus(`Step 3: Looking for odds ${currentBet.odds}...`, 'info');
  
  const oddsText = currentBet.odds > 0 ? `+${currentBet.odds}` : `${currentBet.odds}`;
  
  // Find all submit buttons (betting options)
  const allButtons = document.querySelectorAll('input[type="submit"]');
  console.log(`Found ${allButtons.length} betting buttons`);
  
  // Log first 20 button values for debugging
  let foundButtons = [];
  allButtons.forEach((btn, i) => {
    if (i < 20) {
      foundButtons.push(btn.value);
    }
  });
  console.log('Available buttons:', foundButtons);
  
  let oddsButton = null;
  for (const btn of allButtons) {
    const value = btn.value;
    if (value && value.includes(oddsText)) {
      console.log(`Found matching odds button: ${value}`);
      oddsButton = btn;
      break;
    }
  }
  
  if (oddsButton) {
    reportStatus(`Found odds button, clicking...`, 'info');
    oddsButton.click();
    await sleep(2000);
    
    // Click Continue to go to bet slip
    const continueBtn = document.querySelector('input[value="Continue"]');
    if (continueBtn) {
      continueBtn.click();
      await sleep(3000);
      await fillBetSlip();
    } else {
      reportError('Continue button not found after selecting odds');
    }
  } else {
    reportError(`Could not find odds button containing "${oddsText}". Available: ${foundButtons.slice(0, 5).join(', ')}...`);
  }
}

async function fillBetSlip() {
  reportStatus('Step 4: Filling bet slip...', 'info');
  
  // Select "To Win Amount" radio button
  const toWinRadio = document.querySelector('input[value="To Win Amount"]');
  if (toWinRadio) {
    toWinRadio.click();
    await sleep(500);
  }
  
  // Enter wager amount
  const amountInputs = document.querySelectorAll('input[type="text"]');
  let amountInput = null;
  
  for (const input of amountInputs) {
    const style = window.getComputedStyle(input);
    if (style.display !== 'none' && style.visibility !== 'hidden') {
      amountInput = input;
      break;
    }
  }
  
  if (amountInput) {
    amountInput.value = '';
    amountInput.focus();
    amountInput.value = currentBet.wager.toString();
    // Trigger change event
    amountInput.dispatchEvent(new Event('change', { bubbles: true }));
    amountInput.dispatchEvent(new Event('input', { bubbles: true }));
    await sleep(1000);
    
    reportStatus('Step 5: Clicking Continue...', 'info');
    const continueBtn = document.querySelector('input[value="Continue"]');
    if (continueBtn) {
      continueBtn.click();
      await sleep(3000);
      await confirmBet();
    } else {
      reportError('Continue button not found on bet slip');
    }
  } else {
    reportError('Amount input field not found');
  }
}

async function confirmBet() {
  reportStatus('Step 6: Confirming bet...', 'info');
  
  const confirmBtn = document.querySelector('input[value="Confirm"]');
  if (confirmBtn) {
    confirmBtn.click();
    await sleep(3000);
    
    // Extract ticket number
    reportStatus('Looking for ticket number...', 'info');
    const pageText = document.body.textContent;
    const ticketMatch = pageText.match(/Ticket#?[:\s]*(\d+)/i);
    
    if (ticketMatch) {
      const ticketNumber = ticketMatch[1];
      console.log('✅ BET PLACED SUCCESSFULLY! Ticket#:', ticketNumber);
      
      showNotification('Bet Placed Successfully!', `Ticket#: ${ticketNumber}`, 'success');
      
      reportSuccess({
        success: true,
        ticket_number: ticketNumber,
        game: currentBet.game,
        bet_type: currentBet.bet_type,
        line: currentBet.line,
        odds: currentBet.odds,
        wager: currentBet.wager
      });
    } else {
      // Check if we're on confirmation page
      if (window.location.href.includes('ConfirmWager')) {
        reportStatus('On confirmation page but no ticket found. Check page manually.', 'info');
      } else {
        reportError('Could not find ticket number. Bet may not have been placed.');
      }
    }
  } else {
    reportError('Confirm button not found');
  }
}

function findElementByText(selector, text) {
  const elements = document.querySelectorAll(selector);
  for (const el of elements) {
    if (el.textContent.includes(text)) {
      return el;
    }
  }
  return null;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function showNotification(title, message, type = 'success') {
  const bgColor = type === 'success' ? '#10b981' : '#ef4444';
  
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${bgColor};
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
  }, 8000);
}
