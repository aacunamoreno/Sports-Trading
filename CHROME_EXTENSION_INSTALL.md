# 🎰 Plays888 Betting Automation - Chrome Extension

## 📦 Installation Steps for Chrome

### Step 1: Download the Extension
The extension files are located in `/app/browser-extension/` on your server.

**Option A:** Download via command line:
```bash
cd /app
zip -r browser-extension.zip browser-extension/
# Download browser-extension.zip to your local computer
```

**Option B:** Copy the entire `/app/browser-extension/` folder to your local machine

### Step 2: Install in Chrome

1. **Open Chrome** and navigate to:
   ```
   chrome://extensions/
   ```

2. **Enable Developer Mode**
   - Look for the toggle switch in the **top right corner**
   - Click it to turn ON "Developer mode"

3. **Load the Extension**
   - Click the **"Load unpacked"** button (appears after enabling Developer mode)
   - Navigate to the `browser-extension` folder
   - Click **"Select Folder"**

4. **Verify Installation**
   - You should see "Plays888 Betting Automation" in your extensions list
   - A puzzle piece icon (or similar) will appear in your Chrome toolbar

---

## ⚙️ Setup

### Step 1: Configure API URL

1. **Click the extension icon** in your Chrome toolbar (top right)
2. **Enter your Backend API URL** in the first field:
   ```
   https://your-backend-url.com
   ```
   (This should be your `REACT_APP_BACKEND_URL` from the system)
3. Click **"Save API URL"**
4. You should see a green success message

### Step 2: Log into plays888.co

1. **Open a new tab** and go to: `https://www.plays888.co`
2. **Log in** with your credentials (jac075 / acuna2025!)
3. **Keep this tab open** - the extension needs it to work
4. You can minimize it, but don't close it

---

## 🎯 How to Place a Bet

### Method 1: Using the Extension Popup (Recommended)

1. **Make sure you're logged into plays888.co** in another tab
2. **Click the extension icon** in Chrome toolbar
3. **Fill in the bet details:**
   - **League**: Select from dropdown (e.g., "NCAA BASKETBALL - MEN")
   - **Game**: Enter team names (e.g., "Towson vs Kansas")
   - **Bet Type & Line**: Enter the bet (e.g., "Over 138" or "o138")
   - **Odds**: Enter American odds (e.g., -110 or +150)
   - **Wager Amount**: Amount you want to win (e.g., 300)
4. **Click "Place Bet"**
5. **Switch to your plays888.co tab** immediately
6. **Watch the automation run!**
   - You'll see green notifications as it progresses
   - Takes about 15-20 seconds
7. **Success!** You'll see a notification with the Ticket# when done

### Method 2: Via Backend API (Advanced)

Your backend can also trigger bets programmatically:

```bash
curl -X POST "YOUR_API_URL/api/bets/place-specific" \
  -H "Content-Type: application/json" \
  -d '{
    "game": "Towson vs Kansas",
    "bet_type": "Over 138",
    "line": "o138",
    "odds": -110,
    "wager": 300,
    "league": "NCAA BASKETBALL - MEN"
  }'
```

The extension will detect this and execute the bet automatically!

---

## ✨ Features

✅ **Runs in your real Chrome browser** - No bot detection issues
✅ **Uses your actual logged-in session** - No authentication problems  
✅ **Works from Phoenix, Arizona** - Uses your real IP location
✅ **Visual feedback** - Green notifications show progress
✅ **Automatic Ticket# extraction** - Confirms bet placement
✅ **Auto-syncs with backend** - Bet is recorded in your system
✅ **Fast** - Places bet in 15-20 seconds

---

## 🔧 Troubleshooting

### Extension not showing in toolbar?
- Click the puzzle piece icon in Chrome toolbar
- Find "Plays888 Betting Automation"
- Click the pin icon to keep it visible

### "No plays888.co tab found" error?
- Open `https://www.plays888.co` in a tab
- Make sure you're logged in
- Keep the tab open (can be minimized)

### Bet not placing?
1. **Check you're logged into plays888.co**
2. **Verify game and odds are currently available** on the site
3. **Open Chrome DevTools** (F12) on plays888.co tab
4. **Go to Console tab** to see automation logs
5. Look for error messages in red

### "Could not find odds button" error?
- The game might not be available anymore
- The odds might have changed
- Double-check the exact odds on plays888.co website

### Extension stopped working?
1. Go to `chrome://extensions/`
2. Find "Plays888 Betting Automation"
3. Click the **refresh icon** (circular arrow)
4. Try placing bet again

---

## 📱 Example Usage

**Scenario:** You want to place a bet on Towson vs Kansas Over 138 at -110 for $300

1. ✅ Chrome is open
2. ✅ Extension is installed and configured
3. ✅ Logged into plays888.co in one tab
4. 🎯 Click extension icon
5. 📝 Fill in:
   - League: NCAA BASKETBALL - MEN
   - Game: Towson vs Kansas
   - Bet Type: Over 138
   - Odds: -110
   - Wager: 300
6. 🚀 Click "Place Bet"
7. 👀 Switch to plays888.co tab and watch
8. ✅ Green notification shows: "Bet Placed Successfully! Ticket#: 337414312"
9. 🎉 Done! Bet is also recorded in your backend system

---

## 🔒 Security Notes

- Extension only runs on plays888.co domain
- Your credentials stay in your browser (not sent anywhere)
- Extension communicates only with your backend API
- All bet data encrypted in transit
- No third-party tracking or analytics

---

## 💡 Tips

- **Keep plays888.co tab open** while using the extension
- **Refresh the games page** on plays888.co before placing bets to ensure odds are current
- **Test with small amounts** first to verify everything works
- **Check Open Bets** on plays888.co after automation to confirm bet was placed
- **Pin the extension** to your toolbar for quick access

---

## 📞 Support

If you encounter issues:
1. Check the Console logs (F12 → Console) on plays888.co tab
2. Check that your API URL is correct in extension settings
3. Verify you're logged into plays888.co
4. Make sure the game/odds you're trying to bet on actually exist on the site

---

**Ready to automate your betting! 🚀**
