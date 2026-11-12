import React from 'react';

export default function StatsCard({ icon, iconClass, value, label, delay = 0 }) {
  const isElement = React.isValidElement(icon);
  const canRenderComponent =
    !!icon &&
    (typeof icon === 'function' || typeof icon === 'object') &&
    !isElement;
  const IconComponent = canRenderComponent ? icon : null;

  return (
    <div className={`glass-card stat-card animate-in animate-in-delay-${delay}`}>
      <div className={`stat-icon ${iconClass}`}>
        {isElement ? icon : IconComponent ? <IconComponent size={16} strokeWidth={2.4} /> : icon}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
