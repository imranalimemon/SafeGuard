import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getViolations } from '../../api/client';

const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/': return 'Dashboard';
      case '/violations': return 'Violations History';
      case '/cameras': return 'Camera Management';
      case '/upload': return 'Upload & Detect';
      case '/settings': return 'System Settings';
      default: return '';
    }
  };

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const res = await getViolations({ limit: 5, offset: 0 });
        const data = Array.isArray(res.data) ? res.data : [];
        setNotifications(data);
        setUnreadCount(data.length);
      } catch (e) {
        // API not available yet
      }
    };
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="flex justify-between items-center h-16 px-8 border-b border-sg-outline-variant bg-sg-surface sticky top-0 z-10 animate-fade-in-down shrink-0">
      <h1 className="font-headline-lg text-sg-on-surface tracking-tight">{getPageTitle()}</h1>

      <div className="flex items-center gap-6">
        {/* Status Chip */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-sg-surface-container-high border border-sg-outline-variant rounded-full">
          <span className="w-2 h-2 rounded-full bg-sg-primary animate-pulse"></span>
          <span className="font-data-mono text-sg-primary">YOLOv8s Active</span>
        </div>

        {/* Notification Bell */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-2 text-sg-on-surface-variant hover:text-sg-on-surface transition-colors hover:bg-sg-surface-container-high rounded-full"
          >
            <span className="material-symbols-outlined text-xl">notifications</span>
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-sg-error rounded-full border border-sg-surface"></span>
            )}
          </button>

          {/* Notification Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 top-12 w-80 bg-sg-surface border border-sg-outline-variant rounded-xl shadow-2xl shadow-black/50 z-50 overflow-hidden">
              <div className="flex justify-between items-center px-5 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
                <h3 className="font-headline-sm text-sg-on-surface">Recent Alerts</h3>
                <button
                  onClick={() => setShowNotifications(false)}
                  className="text-sg-on-surface-variant hover:text-sg-on-surface transition-colors"
                >
                  <span className="material-symbols-outlined text-lg">close</span>
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <p className="p-5 text-center font-body-md text-sg-on-surface-variant">No notifications</p>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      onClick={() => { navigate('/violations'); setShowNotifications(false); }}
                      className="px-5 py-3 border-b border-sg-outline-variant/50 hover:bg-sg-surface-variant transition-colors cursor-pointer"
                    >
                      <div className="flex justify-between items-start">
                        <span className="font-body-md font-medium text-sg-error">{n.violation_type || 'Violation'}</span>
                        <span className="font-data-mono text-sg-on-surface-variant">
                          {new Date(n.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="font-body-md text-sg-on-surface-variant mt-1">
                        {n.person_count} worker(s) &bull; {Math.round((n.confidence || 0) * 100)}% confidence
                      </p>
                    </div>
                  ))
                )}
              </div>
              {notifications.length > 0 && (
                <div
                  onClick={() => { navigate('/violations'); setShowNotifications(false); }}
                  className="px-5 py-3 text-center font-body-md font-bold text-sg-primary hover:bg-sg-surface-container-high cursor-pointer border-t border-sg-outline-variant transition-colors"
                >
                  View All Violations
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
