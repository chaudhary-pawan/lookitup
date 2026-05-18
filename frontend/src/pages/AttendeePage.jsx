import { useState, useRef, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { searchBySelfie, getEventStatus, BASE } from '../api';

/* ── Lightbox ─────────────────────────────────────────────────────────── */
function Lightbox({ url, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <button className="lightbox-close" onClick={onClose} aria-label="Close">✕</button>
      <img
        src={url}
        alt="Full size photo"
        className="lightbox-img"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

/* ── Photo Card ───────────────────────────────────────────────────────── */
function PhotoCard({ photo, tier, index, onOpen }) {
  const isConfident = tier === 'confident';
  const scorePercent = Math.round(photo.score * 100);

  const handleDownload = async (e) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${BASE}${photo.url}`);
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `lookitup-photo-${photo.photo_id.slice(0, 8)}.jpg`;
      a.click();
    } catch {
      toast.error('Download failed');
    }
  };

  return (
    <div
      className="photo-card fade-up"
      style={{ animationDelay: `${index * 50}ms` }}
      onClick={() => onOpen(`${BASE}${photo.url}`)}
      role="button"
      tabIndex={0}
      aria-label={`View photo — ${scorePercent}% match`}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(`${BASE}${photo.url}`)}
    >
      <img src={`${BASE}${photo.thumbnail_url || photo.url}`} alt={`Event photo ${index + 1}`} loading="lazy" />

      <div className="photo-card-overlay">
        <div className="photo-card-score">{scorePercent}% match</div>
      </div>

      <div className="photo-card-tier">
        <span className={`badge ${isConfident ? 'badge-green' : 'badge-amber'}`}>
          {isConfident ? '✓ Confident' : '~ Possible'}
        </span>
      </div>

      <button
        className="photo-download-btn"
        onClick={handleDownload}
        aria-label="Download photo"
        title="Download"
      >
        ⬇
      </button>
    </div>
  );
}

/* ── Selfie Drop Zone ─────────────────────────────────────────────────── */
function SelfieDropZone({ onFile, selfiePreview, onClear }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = useCallback((file) => {
    if (!file) return;
    if (!/\.(jpe?g|png|webp)$/i.test(file.name)) {
      toast.error('Please upload a JPEG, PNG, or WebP image');
      return;
    }
    onFile(file);
  }, [onFile]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  if (selfiePreview) {
    return (
      <div style={{ textAlign: 'center' }}>
        <div className="selfie-preview">
          <img src={selfiePreview} alt="Your selfie preview" />
          <button className="selfie-remove" onClick={onClear} aria-label="Remove selfie">✕</button>
        </div>
        <p className="text-muted text-sm mt-3">Selfie ready — click Search below</p>
      </div>
    );
  }

  return (
    <div
      id="selfie-drop-zone"
      className={`drop-zone ${dragging ? 'dragging' : ''}`}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onClick={() => inputRef.current?.click()}
      style={{ padding: '36px 24px' }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp"
        onChange={(e) => handleFile(e.target.files[0])}
        style={{ display: 'none' }}
        id="selfie-file-input"
      />
      <span className="drop-zone-icon">{dragging ? '🤳' : '🤳'}</span>
      <h3>Upload Your Selfie</h3>
      <p>
        Drop a selfie here, or click to browse<br />
        <span style={{ color: 'var(--violet-light)', fontSize: '0.8125rem' }}>
          Make sure only your face is visible
        </span>
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════ */
export default function AttendeePage() {
  const { token } = useParams();

  const [selfieFile, setSelfieFile] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState(null);  // { confident[], possible[], total }
  const [lightboxUrl, setLightboxUrl] = useState(null);
  const [eventReady, setEventReady] = useState(null); // null=checking, true, false
  const [checkingEvent, setCheckingEvent] = useState(true);

  /* ── Check event status on load ─────────────────────────────────── */
  useEffect(() => {
    // We don't have event_id from token directly, but we try searching
    // to get a meaningful error. We just set ready=true and let search handle errors.
    setEventReady(true);
    setCheckingEvent(false);
  }, [token]);

  /* ── Handle selfie selection ────────────────────────────────────── */
  const handleSelfieFile = useCallback((file) => {
    setSelfieFile(file);
    const url = URL.createObjectURL(file);
    setSelfiePreview(url);
    setResults(null);
  }, []);

  const clearSelfie = useCallback(() => {
    setSelfieFile(null);
    if (selfiePreview) URL.revokeObjectURL(selfiePreview);
    setSelfiePreview(null);
    setResults(null);
  }, [selfiePreview]);

  /* ── Search ─────────────────────────────────────────────────────── */
  const handleSearch = async () => {
    if (!selfieFile) { toast.error('Please upload a selfie first'); return; }
    setSearching(true);
    setResults(null);
    try {
      const data = await searchBySelfie(token, selfieFile);
      setResults(data.results);
      const total = data.total_matches;
      if (total === 0) {
        toast('No matching photos found. Try a clearer selfie.', { icon: '🔍' });
      } else {
        toast.success(`Found ${total} photo${total > 1 ? 's' : ''} with your face!`);
      }
    } catch (e) {
      if (e.status === 422) {
        toast.error(`Face issue: ${e.message}`);
      } else if (e.status === 425) {
        toast.error('This event is still processing. Please try again later.');
      } else if (e.status === 404) {
        toast.error('Event not found. Check the link.');
      } else {
        toast.error(e.message || 'Search failed. Try again.');
      }
    } finally {
      setSearching(false);
    }
  };

  /* ── Download all ────────────────────────────────────────────────── */
  const downloadAll = async () => {
    if (!results) return;
    const all = [...(results.confident || []), ...(results.possible || [])];
    toast('Starting downloads…', { icon: '⬇️' });
    for (let i = 0; i < all.length; i++) {
      await new Promise((r) => setTimeout(r, 300 * i));
      const a = document.createElement('a');
      a.href = `${BASE}${all[i].url}`;
      a.download = `lookitup-${i + 1}.jpg`;
      a.target = '_blank';
      a.click();
    }
  };

  const totalResults = results
    ? (results.confident?.length || 0) + (results.possible?.length || 0)
    : 0;

  /* ── Render ──────────────────────────────────────────────────────── */
  return (
    <div className="page-enter" style={{ padding: '40px 24px 60px' }}>
      <div className="container" style={{ maxWidth: 780 }}>

        {/* Header */}
        <div className="text-center mb-6">
          <div className="hero-eyebrow" style={{ margin: '0 auto 16px' }}>
            Attendee Photo Search
          </div>
          <h1 style={{ fontSize: 'clamp(1.75rem, 4vw, 2.75rem)', fontWeight: 900 }}>
            Find <span className="gradient-text">Your Photos</span>
          </h1>
          <p className="text-muted mt-2" style={{ fontSize: '1rem', lineHeight: 1.6 }}>
            Upload a selfie and we'll instantly find every photo from this event where you appear.
          </p>
        </div>

        {/* Search Card */}
        <div className="glow-card mb-6">
          <SelfieDropZone
            onFile={handleSelfieFile}
            selfiePreview={selfiePreview}
            onClear={clearSelfie}
          />

          {selfieFile && (
            <div style={{ marginTop: '20px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button className="btn btn-ghost" onClick={clearSelfie} disabled={searching}>
                🔄 Change Selfie
              </button>
              <button
                id="search-btn"
                className="btn btn-primary btn-lg"
                onClick={handleSearch}
                disabled={searching}
              >
                {searching
                  ? <><span className="spinner spinner-sm" /> Searching…</>
                  : '🔍 Find My Photos'}
              </button>
            </div>
          )}

          {/* Tips */}
          {!selfieFile && (
            <div style={{ marginTop: '20px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              {[
                { icon: '💡', text: 'Use a clear, well-lit selfie' },
                { icon: '👤', text: 'Only your face in the photo' },
                { icon: '📱', text: 'JPEG, PNG or WebP accepted' },
              ].map((tip) => (
                <div key={tip.text} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  <span>{tip.icon}</span>
                  <span>{tip.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Results ────────────────────────────────────────────── */}
        {results && (
          <div className="page-enter">
            <div className="results-header">
              <div>
                <h2 className="results-title">
                  {totalResults > 0
                    ? `Found ${totalResults} photo${totalResults > 1 ? 's' : ''} 🎉`
                    : 'No photos found'}
                </h2>
                {totalResults > 0 && (
                  <p className="text-muted text-sm mt-1">
                    {results.confident?.length || 0} confident · {results.possible?.length || 0} possible matches
                  </p>
                )}
              </div>
              {totalResults > 0 && (
                <button
                  id="download-all-btn"
                  className="btn btn-ghost btn-sm"
                  onClick={downloadAll}
                >
                  ⬇ Download All
                </button>
              )}
            </div>

            {totalResults === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">🔍</div>
                <h3>No matches found</h3>
                <p>
                  We couldn't find you in this event's photos. Try a different selfie
                  with better lighting and only your face visible.
                </p>
                <button className="btn btn-primary mt-4" onClick={clearSelfie}>
                  Try Another Selfie
                </button>
              </div>
            )}

            {/* Confident results */}
            {results.confident?.length > 0 && (
              <>
                <div className="section-divider">
                  <span className="badge badge-green">✓ Confident Matches</span>
                  <div className="section-divider-line" />
                  <span className="text-xs text-muted" style={{ whiteSpace: 'nowrap' }}>
                    {results.confident.length} photo{results.confident.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="photo-grid">
                  {results.confident.map((photo, i) => (
                    <PhotoCard
                      key={photo.photo_id}
                      photo={photo}
                      tier="confident"
                      index={i}
                      onOpen={setLightboxUrl}
                    />
                  ))}
                </div>
              </>
            )}

            {/* Possible results */}
            {results.possible?.length > 0 && (
              <>
                <div className="section-divider" style={{ marginTop: 32 }}>
                  <span className="badge badge-amber">~ Possible Matches</span>
                  <div className="section-divider-line" />
                  <span className="text-xs text-muted" style={{ whiteSpace: 'nowrap' }}>
                    {results.possible.length} photo{results.possible.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="photo-grid">
                  {results.possible.map((photo, i) => (
                    <PhotoCard
                      key={photo.photo_id}
                      photo={photo}
                      tier="possible"
                      index={i}
                      onOpen={setLightboxUrl}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightboxUrl && (
        <Lightbox url={lightboxUrl} onClose={() => setLightboxUrl(null)} />
      )}
    </div>
  );
}
