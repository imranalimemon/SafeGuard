import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
  const links = [
    { name: 'Dashboard', path: '/', icon: 'dashboard' },
    { name: 'Violations', path: '/violations', icon: 'warning' },
    { name: 'Upload', path: '/upload', icon: 'upload' },
    { name: 'Settings', path: '/settings', icon: 'settings' },
  ];

  const hoverAnimations = {
    dashboard: 'group-hover:scale-110',
    warning: '',
    upload: 'group-hover:-translate-y-1',
    settings: 'group-hover:rotate-45',
  };

  return (
    <nav className="fixed left-0 top-0 h-screen w-[240px] flex flex-col justify-between py-6 border-r border-sg-outline-variant bg-sg-surface-container-low animate-slide-in-left z-20">
      <div className="px-6 flex flex-col gap-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <span
            className="material-symbols-outlined text-sg-primary text-3xl"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            security
          </span>
          <div>
            <h1 className="font-headline-sm font-bold text-sg-on-surface">SafeGuard AI</h1>
            <p className="font-label-caps text-sg-on-surface-variant opacity-70">Safety Monitoring</p>
          </div>
        </div>

        {/* Navigation Links */}
        <ul className="flex flex-col gap-1">
          {links.map((link) => (
            <li key={link.path}>
              <NavLink
                to={link.path}
                end={link.path === '/'}
                className={({ isActive }) =>
                  isActive
                    ? 'flex items-center gap-3 px-4 py-3 bg-sg-primary-container/10 text-sg-primary font-bold rounded-lg border-l-4 border-sg-primary transition-all duration-200'
                    : 'flex items-center gap-3 px-4 py-3 text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-variant/50 transition-all duration-200 rounded-lg group'
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`material-symbols-outlined text-xl transition-transform duration-300 ${
                        isActive ? '' : hoverAnimations[link.icon] || ''
                      }`}
                      style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}
                    >
                      {link.icon}
                    </span>
                    <span className="font-body-md">{link.name}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>

      {/* Footer / Status */}
      <div className="px-6">
        <div className="flex items-center gap-2 px-4 py-3 bg-sg-surface border border-sg-outline-variant rounded-lg">
          <span
            className="material-symbols-outlined text-sg-tertiary text-xs animate-pulse"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            fiber_manual_record
          </span>
          <span className="font-label-caps text-sg-on-surface tracking-wider">System Online</span>
        </div>
      </div>
    </nav>
  );
};

export default Sidebar;
