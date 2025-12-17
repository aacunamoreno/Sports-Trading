# 📱 Telegram Notifications Setup Guide

Get instant notifications on Telegram when bets are placed!

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Your Telegram Bot

1. **Open Telegram** on your phone or computer
2. **Search for:** `@BotFather`
3. **Start a chat** and send: `/newbot`
4. **Follow the prompts:**
   - Choose a name for your bot (e.g., "My Betting Bot")
   - Choose a username (must end in 'bot', e.g., "mybetting_bot")
5. **Copy the Bot Token** you receive (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. **Find your new bot** in Telegram (search for the username you created)
2. **Start a chat** with it - send any message (e.g., "Hello")
3. **Search for:** `@userinfobot`
4. **Start that bot** - it will send you your Chat ID
5. **Copy your Chat ID** (a number like: `123456789`)

### Step 3: Configure in BetBot Dashboard

1. **Open your BetBot dashboard** in Chrome
2. **Go to Settings** (in left sidebar)
3. **Scroll to "Telegram Notifications"**
4. **Enter:**
   - Bot Token: (paste from Step 1)
   - Chat ID: (paste from Step 2)
5. **Click "Configure Telegram"**
6. **Check Telegram** - you should receive a test message! ✅

### Step 4: Test It!

1. **Click "Send Test"** button in Settings
2. **Check your Telegram** - you should see a test bet notification
3. **Done!** You'll now get notified for every bet placed

---

## 📲 What You'll Receive

Every time a bet is placed (manually or via extension), you'll get a message like:

```
🎰 BET PLACED

Game: Towson vs Kansas
League: NCAA BASKETBALL - MEN
Bet: Over 138 o138
Odds: -110
Wager: $300 MXN
To Win: $272.73 MXN

Ticket#: 337414312
Status: Placed

Automated via BetBot System
```

---

## 🔧 Troubleshooting

### "Failed to configure Telegram"
- Double-check your Bot Token (no extra spaces)
- Make sure you started a chat with your bot first
- Verify Chat ID is correct (numbers only)

### "Not receiving notifications"
- Click "Send Test" in Settings to verify
- Check that bot is not blocked
- Verify Chat ID matches your account

### "Bot not responding"
- Make sure you sent at least one message to your bot
- Try creating a new bot if issues persist

---

## 💡 Tips

- **Pin the bot chat** in Telegram for quick access
- **Mute other chats** to see bet notifications immediately
- **Share bets** by forwarding messages to groups
- **Keep bot token private** - don't share it with anyone

---

## 🔐 Privacy & Security

- Your bot token is stored securely on your backend
- Only you can receive notifications (via your Chat ID)
- Bot cannot access your other Telegram messages
- You can revoke the bot anytime via @BotFather

---

## 📊 Advanced: Sharing Bets

Want to share your bets with others?

### Option 1: Forward Messages
1. Receive bet notification
2. Forward it to any chat/group
3. Recipients see your bet details

### Option 2: Create a Channel
1. Create a Telegram channel for your bets
2. Add your bot as admin
3. Use the channel's Chat ID instead
4. All subscribers see your bets!

### Option 3: Group Chat
1. Create a Telegram group
2. Add your bot to the group
3. Make it admin
4. Use group Chat ID in settings
5. Everyone in group sees bets!

---

## 🎯 Example Setup (Step-by-Step)

**Scenario:** You want to share bets with friends via a group

1. **Create bot** via @BotFather → Get token
2. **Create Telegram group** with friends
3. **Add your bot** to the group (via group settings)
4. **Make bot admin** (required to send messages)
5. **Get group Chat ID:**
   - Add @userinfobot to the group temporarily
   - It will show the group's Chat ID (negative number like `-987654321`)
   - Remove @userinfobot
6. **Configure in BetBot:**
   - Bot Token: your bot token
   - Chat ID: the group's Chat ID (including the minus sign)
7. **Test it** - everyone in group sees the test bet!

---

**Ready to get notified! 🚀**

All bets placed via the Chrome extension or manual recording will automatically trigger Telegram notifications.
