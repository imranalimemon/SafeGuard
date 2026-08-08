import React from 'react';

const StatCard = ({ icon, label, value, iconBg = 'bg-sg-surface-container-high', iconBorder = 'border-sg-outline-variant', iconColor = 'text-sg-on-surface', animClass = '' }) => {
  return (
    <div className={`bg-sg-surface border border-sg-outline-variant rounded-xl p-5 flex flex-col justify-between ${animClass}`}>
      <div>
        <div className={`w-10 h-10 rounded ${iconBg} flex items-center justify-center border ${iconBorder} mb-4`}>
          <span className={`material-symbols-outlined ${iconColor}`}>{icon}</span>
        </div>
        <h3 className="font-body-md text-sg-on-surface-variant">{label}</h3>
      </div>
      <div className="font-headline text-[48px] leading-none text-sg-on-surface font-bold mt-2">{value}</div>
    </div>
  );
};

export default StatCard;
