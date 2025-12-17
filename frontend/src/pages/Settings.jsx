import { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Bell, Send } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Settings() {
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [loading, setLoading] = useState(false);
  const [monitoringStatus, setMonitoringStatus] = useState(null);
  const [monitoringLoading, setMonitoringLoading] = useState(false);

  useEffect(() => {
    checkTelegramStatus();
  }, []);

  const checkTelegramStatus = async () => {
    try {
      const response = await axios.get(`${API}/telegram/status`);
      setTelegramStatus(response.data);
    } catch (error) {
      console.error('Error checking Telegram status:', error);
    }
  };

  const configureTelegram = async () => {
    if (!botToken || !chatId) {
      toast.error('Please enter both Bot Token and Chat ID');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/telegram/config`, {
        bot_token: botToken,
        chat_id: parseInt(chatId)
      });

      toast.success(response.data.message);
      checkTelegramStatus();
      setBotToken('');
      setChatId('');
    } catch (error) {
      console.error('Error configuring Telegram:', error);
      toast.error(error.response?.data?.detail || 'Failed to configure Telegram');
    } finally {
      setLoading(false);
    }
  };

  const sendTestNotification = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}/telegram/test`);
      toast.success('Test notification sent! Check your Telegram.');
    } catch (error) {
      console.error('Error sending test:', error);
      toast.error(error.response?.data?.detail || 'Failed to send test notification');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-heading font-bold tracking-tight mb-2" data-testid="settings-title">
          Settings
        </h1>
        <p className="text-muted-foreground">Configure your betting automation preferences</p>
      </div>

      <Card className="glass-card neon-border" data-testid="telegram-settings">
        <CardHeader className="border-b border-border">
          <div className="flex items-center gap-3">
            <Bell className="w-6 h-6 text-primary" strokeWidth={1.5} />
            <div>
              <CardTitle className="font-heading text-xl">Telegram Notifications</CardTitle>
              <CardDescription className="text-sm mt-1">
                Get instant notifications when bets are placed
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6 space-y-6">
          {telegramStatus && (
            <div className="p-4 rounded-sm border border-border bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2 h-2 rounded-full ${
                  telegramStatus.configured ? 'bg-primary' : 'bg-muted-foreground'
                }`} />
                <span className="text-sm font-medium">
                  {telegramStatus.configured ? 'Connected' : 'Not Configured'}
                </span>
              </div>
              {telegramStatus.configured && (
                <div className="space-y-1 text-sm text-muted-foreground">
                  <div>Bot: @{telegramStatus.bot_username}</div>
                  <div>Chat ID: {telegramStatus.chat_id}</div>
                </div>
              )}
            </div>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="botToken">Bot Token</Label>
              <Input
                id="botToken"
                type="password"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                placeholder="Enter your Telegram Bot Token"
                className="bg-muted border-input font-mono"
              />
              <p className="text-xs text-muted-foreground">
                Get your bot token from @BotFather on Telegram
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="chatId">Chat ID</Label>
              <Input
                id="chatId"
                type="text"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder="Enter your Chat ID"
                className="bg-muted border-input font-mono"
              />
              <p className="text-xs text-muted-foreground">
                Message your bot, then use @userinfobot to get your Chat ID
              </p>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                onClick={configureTelegram}
                disabled={loading}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                Configure Telegram
              </Button>

              {telegramStatus?.configured && (
                <Button
                  onClick={sendTestNotification}
                  disabled={loading}
                  variant="outline"
                  className="border-primary text-primary hover:bg-primary/10"
                >
                  <Send className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Send Test
                </Button>
              )}
            </div>
          </div>

          <div className="mt-6 p-4 rounded-sm bg-muted/50 border border-border">
            <h4 className="text-sm font-medium mb-3 text-foreground">Setup Instructions:</h4>
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
              <li>Open Telegram and search for <code className="text-primary">@BotFather</code></li>
              <li>Send <code className="text-primary">/newbot</code> and follow instructions</li>
              <li>Copy the bot token you receive</li>
              <li>Start a chat with your new bot (send any message)</li>
              <li>Search for <code className="text-primary">@userinfobot</code> and get your Chat ID</li>
              <li>Enter both values above and click Configure</li>
            </ol>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
