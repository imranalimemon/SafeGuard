import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import DashboardPage from './pages/DashboardPage';
import ViolationsPage from './pages/ViolationsPage';
import CamerasPage from './pages/CamerasPage';
import UploadPage from './pages/UploadPage';
import SettingsPage from './pages/SettingsPage';
import { SystemHealthProvider } from './context/SystemHealth';
import SystemLogsPage from './pages/SystemLogsPage';
import HelpPage from './pages/HelpPage';
import AuthGate from './context/Auth';

function App() {
  return (
    <BrowserRouter>
      <AuthGate>
      <SystemHealthProvider>
      {/* Fixed sidebar */}
      <Sidebar />

      {/* Fixed top navbar (offset by sidebar width) */}
      <Navbar />

      {/* Main content: offset below header (64px), left of sidebar (256px), above footer (32px) */}
      <main
        className="app-main flex flex-col overflow-hidden"
        style={{
          marginLeft: '256px',
          marginTop: '64px',
          marginBottom: '32px',
          height: 'calc(100vh - 64px - 32px)',
          background: 'var(--color-background)',
        }}
      >
        <Routes>
          <Route path="/"           element={<DashboardPage />} />
          <Route path="/violations" element={<ViolationsPage />} />
          <Route path="/cameras"    element={<CamerasPage />} />
          <Route path="/upload"     element={<UploadPage />} />
          <Route path="/settings"   element={<SettingsPage />} />
          <Route path="/logs" element={<SystemLogsPage />} />
          <Route path="/help" element={<HelpPage />} />
        </Routes>
      </main>

      {/* Fixed bottom footer */}
      <Footer />
      </SystemHealthProvider>
      </AuthGate>
    </BrowserRouter>
  );
}

export default App;
