import React, { useEffect } from 'react';

/**
 * Reusable right-anchored side drawer.
 *
 * Props:
 *   - open:    boolean — controls visibility
 *   - onClose: () => void — called on backdrop click, Escape, or close button
 *   - title:   string — header label
 *   - children: ReactNode — body content
 *   - width:   string — CSS width for the panel (default "480px")
 *
 * Renders inline (no portal). Locks body scroll while open. Closes on Escape
 * or click-outside. Reuses the existing `sg-*` color tokens — no new design
 * tokens are introduced.
 */
const Drawer = ({ open, onClose, title, children, width = '480px' }) => {
  // Escape key closes
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Body scroll lock while open
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/40 z-30 animate-fade-in cursor-pointer"
        aria-hidden="true"
      />
      {/* Panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="fixed top-0 right-0 h-full z-40 bg-sg-surface-container border-l border-sg-outline-variant shadow-2xl shadow-black/50 animate-slide-in-right flex flex-col"
        style={{ width }}
      >
        <header className="flex justify-between items-center px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low shrink-0">
          <h2 className="font-headline-sm text-sg-on-surface truncate pr-4">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close drawer"
            className="text-sg-on-surface-variant hover:text-sg-on-surface transition-colors p-1 rounded hover:bg-sg-surface-container-high"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </aside>
    </>
  );
};

export default Drawer;
