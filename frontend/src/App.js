import { useState } from 'react';
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from './pages/Dashboard';
import ConnectionSetup from './pages/ConnectionSetup';
import BettingRules from './pages/BettingRules';
import Opportunities from './pages/Opportunities';
import History from './pages/History';
import Layout from './components/Layout';
import { Toaster } from './components/ui/sonner';

function App() {
  const [isConnected, setIsConnected] = useState(false);

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/setup" element={<ConnectionSetup onConnect={() => setIsConnected(true)} />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="rules" element={<BettingRules />} />
            <Route path="opportunities" element={<Opportunities />} />
            <Route path="history" element={<History />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;
