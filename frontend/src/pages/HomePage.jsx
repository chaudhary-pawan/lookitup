import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

const FEATURES = [
  { icon: '⚡', label: 'Sub-10ms search' },
  { icon: '🎯', label: 'ArcFace AI accuracy' },
  { icon: '🔒', label: 'Privacy first — delete anytime' },
  { icon: '📦', label: 'Bulk ZIP upload' },
  { icon: '✨', label: '512-dim face embeddings' },
];

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'Organizer creates event',
    desc: 'Upload hundreds of photos from your event — JPEGs or a bulk ZIP file.',
    icon: '📸',
    color: 'var(--violet)',
  },
  {
    step: '02',
    title: 'AI processes every face',
    desc: 'InsightFace detects and embeds every face into a fast FAISS vector index.',
    icon: '🧠',
    color: 'var(--pink)',
  },
  {
    step: '03',
    title: 'Attendees find their photos',
    desc: 'Share a link. Attendees upload a selfie and instantly see every photo they\'re in.',
    icon: '🔍',
    color: 'var(--cyan)',
  },
];

export default function HomePage() {
  const [count, setCount] = useState(0);

  // Animated counter
  useEffect(() => {
    let frame;
    const target = 10000;
    const duration = 1800;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setCount(Math.round(eased * target));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div className="page-enter">
      {/* ── Hero ─────────────────────────────────────────────────── */}
      <section className="hero">
        <div className="hero-eyebrow">
          <span className="pulse-dot" style={{ background: 'var(--emerald)' }} />
          AI-Powered · Face Recognition · Private by Design
        </div>

        <h1>
          Find <span className="gradient-text">Your Photos</span>
          <br />From Any Event
        </h1>

        <p className="hero-subtitle">
          Upload a selfie. Get every photo you're in from a wedding, conference, or party —
          powered by state-of-the-art face recognition AI.
        </p>

        <div className="hero-cta">
          <Link to="/organizer" id="hero-organizer-btn" className="btn btn-primary btn-lg">
            🎉 Create Event Album
          </Link>
          <a href="#how-it-works" className="btn btn-ghost btn-lg" id="hero-learn-btn">
            How it works ↓
          </a>
        </div>

        {/* Feature pills */}
        <div className="features-strip stagger">
          {FEATURES.map((f) => (
            <div key={f.label} className="feature-pill">
              <span className="feature-pill-icon">{f.icon}</span>
              {f.label}
            </div>
          ))}
        </div>
      </section>

      {/* ── Stats ────────────────────────────────────────────────── */}
      <div className="container">
        <div className="glow-card" style={{ padding: '32px 40px' }}>
          <div className="stats-bar" style={{ justifyContent: 'center', gap: '60px' }}>
            <div className="stat-item text-center">
              <div className="stat-value">{count.toLocaleString()}+</div>
              <div className="stat-label">Faces indexed per event</div>
            </div>
            <div className="stat-item text-center">
              <div className="stat-value">&lt;10ms</div>
              <div className="stat-label">Search latency</div>
            </div>
            <div className="stat-item text-center">
              <div className="stat-value">512-dim</div>
              <div className="stat-label">ArcFace embeddings</div>
            </div>
            <div className="stat-item text-center">
              <div className="stat-value">100%</div>
              <div className="stat-label">Private & deletable</div>
            </div>
          </div>
        </div>
      </div>

      <div className="glow-sep" />

      {/* ── How It Works ─────────────────────────────────────────── */}
      <section id="how-it-works" className="container" style={{ padding: '20px 24px 60px' }}>
        <div className="text-center" style={{ marginBottom: '48px' }}>
          <div className="hero-eyebrow" style={{ margin: '0 auto 16px' }}>The Process</div>
          <h2 style={{ fontSize: 'clamp(1.75rem, 4vw, 2.5rem)', fontWeight: 800 }}>
            How LookItUp Works
          </h2>
          <p className="text-muted" style={{ marginTop: '12px', fontSize: '1.0625rem' }}>
            Three simple steps from upload to discovery
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}
             className="stagger">
          {HOW_IT_WORKS.map((item) => (
            <div key={item.step} className="glow-card" style={{ position: 'relative', overflow: 'hidden' }}>
              <div style={{
                position: 'absolute', top: 16, right: 20,
                fontSize: '3.5rem', fontWeight: 900, opacity: 0.06,
                fontFamily: "'Space Grotesk', sans-serif",
                color: item.color,
              }}>
                {item.step}
              </div>
              <div style={{
                width: 56, height: 56, borderRadius: 16,
                background: `${item.color}22`,
                border: `1px solid ${item.color}44`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1.75rem', marginBottom: '20px',
              }}>
                {item.icon}
              </div>
              <h3 style={{ fontSize: '1.125rem', marginBottom: '10px' }}>{item.title}</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', lineHeight: 1.6 }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {/* CTA Banner */}
        <div style={{
          marginTop: 48,
          padding: '40px',
          borderRadius: 'var(--radius-xl)',
          background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(236,72,153,0.15) 100%)',
          border: '1px solid rgba(139,92,246,0.25)',
          textAlign: 'center',
          backdropFilter: 'blur(20px)',
        }}>
          <h2 style={{ fontSize: '1.75rem', marginBottom: '12px' }}>
            Ready to get started?
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '28px' }}>
            Create your first event album in under a minute.
          </p>
          <Link to="/organizer" id="cta-organizer-btn" className="btn btn-primary btn-lg">
            🚀 Create Event Album
          </Link>
        </div>
      </section>
    </div>
  );
}
