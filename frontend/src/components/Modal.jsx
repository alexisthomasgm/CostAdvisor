import { useEffect, useRef } from 'react';

export default function Modal({ isOpen, onClose, title, children, width = 420 }) {
  const modalRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    // Focus trap: focus the modal when opened
    modalRef.current?.focus();
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="ca-modal-backdrop" onClick={onClose}>
      <div
        className="ca-modal"
        style={{ width }}
        onClick={(e) => e.stopPropagation()}
        ref={modalRef}
        tabIndex={-1}
      >
        <div className="ca-modal-header">
          <span style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 15 }}>
            {title}
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'var(--muted)',
              cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: 4,
            }}
          >
            &times;
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
