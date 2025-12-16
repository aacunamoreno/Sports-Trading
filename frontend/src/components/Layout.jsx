import { Outlet, Link, useLocation } from 'react-router-dom';
import { Activity, Settings, TrendingUp, List, Target } from 'lucide-react';
import { useEffect, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Layout() {
  const location = useLocation();
  const [connectionStatus, setConnectionStatus] = useState(null);

  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await axios.get(`${API}/connection/status`);
      setConnectionStatus(response.data);
    } catch (error) {
      console.error('Error checking connection:', error);
    }
  };

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Activity },
    { path: '/rules', label: 'Rules', icon: Settings },
    { path: '/opportunities', label: 'Opportunities', icon: Target },
    { path: '/history', label: 'History', icon: List },
  ];

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border glass-card">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-8">
            <TrendingUp className="w-8 h-8 text-primary" strokeWidth={1.5} />
            <h1 className="text-2xl font-heading font-bold tracking-tight">BetBot</h1>
          </div>

          {/* Connection Status */}
          {connectionStatus && (
            <div className="mb-6 p-3 rounded-sm border border-border bg-muted/30">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2 h-2 rounded-full ${
                  connectionStatus.is_connected ? 'bg-primary' : 'bg-destructive'
                }`} data-testid="connection-status-indicator" />
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  {connectionStatus.is_connected ? 'CONNECTED' : 'DISCONNECTED'}
                </span>
              </div>
              {connectionStatus.username && (
                <div className="text-sm font-mono text-foreground">
                  {connectionStatus.username}
                </div>
              )}
            </div>
          )}

          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.label.toLowerCase()}`}
                  className={`flex items-center gap-3 px-3 py-2 rounded-sm transition-all duration-200 ${
                    isActive
                      ? 'bg-primary text-primary-foreground neon-glow'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon className="w-4 h-4" strokeWidth={1.5} />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-border">
          <Link
            to="/setup"
            data-testid="nav-setup"
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors duration-200"
          >
            <Settings className="w-4 h-4" strokeWidth={1.5} />
            <span>Connection Setup</span>
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1600px] mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
