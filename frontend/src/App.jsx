import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Navbar from './components/layout/Navbar';
import DashboardPage from './pages/DashboardPage';
import ViolationsPage from './pages/ViolationsPage';
import CamerasPage from './pages/CamerasPage';
import UploadPage from './pages/UploadPage';
import SettingsPage from './pages/SettingsPage';

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-sg-background text-sg-on-surface font-sans">
        <Sidebar />
        <main className="flex-1 ml-[240px] flex flex-col h-screen relative">
          <Navbar />
          <div className="flex-1 overflow-y-auto p-6 bg-sg-background">
            <div className="max-w-[1600px] mx-auto">
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/violations" element={<ViolationsPage />} />
                <Route path="/cameras" element={<CamerasPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </div>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
