import React from 'react';

const Toggle = ({ label, checked, onChange }) => {
  return (
    <label className="flex items-center justify-between cursor-pointer group">
      <span className="font-body-lg text-sg-on-surface">{label}</span>
      <div className="relative">
        <input
          type="checkbox"
          className="sr-only"
          checked={checked}
          onChange={onChange}
        />
        <div className={`block w-12 h-6 rounded-full transition-colors duration-200 ${checked ? 'bg-sg-primary-container' : 'bg-sg-surface-variant border border-sg-outline-variant'}`}></div>
        <div className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform duration-200 ${checked ? 'translate-x-6' : 'translate-x-0'}`}></div>
      </div>
    </label>
  );
};

export default Toggle;
