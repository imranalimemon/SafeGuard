import React from 'react';
import { NavLink } from 'react-router-dom';

const Navbar = () => (
  <header className="fixed top-0 left-64 right-0 h-16 z-50 flex items-center justify-between px-6" style={{ background: 'var(--color-surface)', borderBottom: '1px solid var(--color-outline-variant)' }}>
    <strong style={{ color: '#FF6B00' }}>SafeGuard AI</strong>
    <nav className="flex gap-6">
      <NavLink to="/">Live View</NavLink>
      <NavLink to="/upload">Analysis</NavLink>
      <NavLink to="/violations">Violations</NavLink>
      <NavLink to="/settings">Settings</NavLink>
    </nav>
  </header>
);
export default Navbar;
