# Plays888 Betting Automation Browser Extension

This Chrome/Firefox extension automates bet placement on plays888.co directly in your browser.

## Installation

### Chrome:
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `/app/browser-extension` folder
5. The extension icon should appear in your toolbar

### Firefox:
1. Open Firefox and go to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Navigate to `/app/browser-extension` and select `manifest.json`
4. The extension will load temporarily

## Setup

1. **Click the extension icon** in your browser toolbar
2. **Enter your Backend API URL** (e.g., `https://your-domain.com`)
3. Click "Save API URL"
4. **Open plays888.co** and log in to your account
5. Keep the tab open

## Usage

### To Place a Bet:

1. **Click the extension icon**
2. **Fill in bet details:**
   - League (select from dropdown)
   - Game (e.g., "Towson vs Kansas")
   - Bet Type (e.g., "Over 138")
   - Odds (e.g., -110)
   - Wager Amount (e.g., 300)
3. **Click "Place Bet"**
4. **Switch to your plays888.co tab** - the automation will run automatically
5. **Watch it work!** You'll see notifications as it progresses
6. **Success notification** will show the Ticket# when complete

## How It Works

1. Extension runs in your actual browser with your real session
2. No headless browser issues - uses your logged-in session
3. Executes the exact same steps you would manually:
   - Navigate to Straight
   - Select league
   - Click odds button
   - Fill bet slip
   - Confirm bet
4. Automatically records bet in your backend system

## Features

✅ Runs in your real browser (no bot detection)
✅ Uses your actual plays888.co session
✅ Works from your Phoenix, Arizona location
✅ Automatic Ticket# extraction
✅ Visual notifications on success/failure
✅ Automatically syncs with backend API

## Troubleshooting

**Extension not working?**
- Make sure you're logged into plays888.co
- Ensure the plays888.co tab is open
- Check that API URL is correctly set
- Open browser console (F12) to see logs

**Bet not placing?**
- Verify game and odds are currently available
- Check that you're on the plays888.co homepage or betting page
- Make sure your account has sufficient balance

## Notes

- Extension must be loaded in Developer Mode
- Keep plays888.co tab open while placing bets
- Extension works best when you're on the plays888.co homepage
- For Firefox, extension is temporary and needs to be reloaded on browser restart
