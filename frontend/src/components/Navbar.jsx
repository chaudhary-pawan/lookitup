import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

export default function Navbar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const inputRef = useRef(null);

  // Auto-focus input when modal opens
  useEffect(() => {
    if (showModal) setTimeout(() => inputRef.current?.focus(), 50);
  }, [showModal]);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setShowModal(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const handleGo = () => {
    const raw = tokenInput.trim();
    if (!raw) return;

    // Accept full URL like http://localhost:5173/event/abc123
    // or just the token like abc123
    let token = raw;
    try {
      const url = new URL(raw);
      const parts = url.pathname.split('/').filter(Boolean);
      const idx = parts.indexOf('event');
      if (idx !== -1 && parts[idx + 1]) token = parts[idx + 1];
    } catch { /* not a URL, treat as raw token */ }

    setShowModal(false);
    setTokenInput('');
    navigate(`/event/${token}`);
  };

  const isAttendee = pathname.startsWith('/event/');

  return (
    <>
      <nav className="navbar" role="navigation" aria-label="Main navigation">
        <div className="navbar-inner">
          <Link to="/" className="logo" id="nav-logo">
            <div className="logo-icon" aria-hidden="true">🔍</div>
            <span>LookItUp</span>
          </Link>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Attendee button */}
            <button
              id="nav-attendee-btn"
              className={`btn btn-sm ${isAttendee ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setShowModal(true)}
              aria-haspopup="dialog"
            >
              🤳 Attendee
            </button>

            {/* Organizer button */}
            <Link
              to="/organizer"
              id="nav-organizer-btn"
              className={`btn btn-sm ${pathname === '/organizer' ? 'btn-primary' : 'btn-ghost'}`}
            >
              📸 Organizer
            </Link>

            {/* Logout Button (if token exists) */}
            {sessionStorage.getItem('organizer_token') && (
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  sessionStorage.removeItem('organizer_token');
                  navigate('/auth');
                }}
              >
                Logout
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* ── Attendee Modal ─────────────────────────────────────────── */}
      {showModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            padding: '80px 16px 0',
            animation: 'fadeIn 0.15s ease',
          }}
          onClick={() => setShowModal(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Enter event link"
        >
          <div
            style={{
              background: 'rgba(13,13,31,0.98)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 'var(--radius-xl)',
              padding: '28px',
              width: '100%',
              maxWidth: 480,
              boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
              animation: 'scaleIn 0.2s var(--ease-spring)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.125rem', marginBottom: '6px' }}>
                🤳 Find Your Photos
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.5 }}>
                Paste the event share link or enter just the token your organizer sent you.
              </p>
            </div>

            <input
              ref={inputRef}
              id="attendee-token-input"
              className="input"
              type="text"
              placeholder="e.g. http://localhost:5173/event/abc123  or  abc123"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGo()}
              style={{ marginBottom: '14px' }}
            />

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setShowModal(false); setTokenInput(''); }}
              >
                Cancel
              </button>
              <button
                id="attendee-go-btn"
                className="btn btn-primary btn-sm"
                onClick={handleGo}
                disabled={!tokenInput.trim()}
              >
                Go to Event →
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

