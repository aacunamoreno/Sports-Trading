import { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Loader2, Lock, User } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ConnectionSetup({ onConnect }) {
  const [username, setUsername] = useState('jac075');
  const [password, setPassword] = useState('acuna2025!');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSetup = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${API}/connection/setup`, {
        username,
        password,
      });

      if (response.data.success) {
        toast.success('Connected to plays888.co successfully!');
        if (onConnect) onConnect();
        setTimeout(() => navigate('/'), 1000);
      } else {
        toast.error(response.data.message || 'Connection failed');
      }
    } catch (error) {
      console.error('Setup error:', error);
      toast.error('Failed to connect. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        backgroundImage: 'url(https://images.unsplash.com/photo-1761319659795-543075eaeaad?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDJ8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGRhcmslMjB0ZWNobm9sb2d5JTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NjU5MTcwMDN8MA&ixlib=rb-4.1.0&q=85)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <Card className="w-full max-w-md glass-card neon-border" data-testid="connection-setup-card">
        <CardHeader className="space-y-3 text-center">
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center">
              <Lock className="w-8 h-8 text-primary" strokeWidth={1.5} />
            </div>
          </div>
          <CardTitle className="text-3xl font-heading font-bold tracking-tight">
            Connect to Plays888
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Enter your plays888.co credentials to enable automated betting
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSetup} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" strokeWidth={1.5} />
                <Input
                  id="username"
                  data-testid="username-input"
                  type="text"
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="pl-10 bg-muted border-input focus:ring-primary font-mono"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" strokeWidth={1.5} />
                <Input
                  id="password"
                  data-testid="password-input"
                  type="password"
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="pl-10 bg-muted border-input focus:ring-primary font-mono"
                />
              </div>
            </div>

            <div className="pt-4">
              <Button
                type="submit"
                data-testid="connect-button"
                disabled={loading}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200 neon-glow"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  'Connect Account'
                )}
              </Button>
            </div>

            <div className="pt-4 border-t border-border">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Lock className="w-3 h-3" strokeWidth={1.5} />
                <span>Your credentials are encrypted and stored securely</span>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
