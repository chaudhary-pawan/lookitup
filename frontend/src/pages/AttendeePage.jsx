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
function PhotoCard({ photo, index, onOpen }) {
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

/* ── Selfie Camera Zone (Privacy Enforced Live Capture) ──────────────── */
function SelfieCameraZone({ onCapture, selfiePreview, onClear }) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);
  const [stream, setStream] = useState(null);
  const videoRef = useRef(null);

  const startCamera = async () => {
    setError(null);
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
      });
      setStream(mediaStream);
      setActive(true);
      // Wait for React to render the video element, then attach stream
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
        }
      }, 50);
    } catch (err) {
      console.error(err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('Camera permission denied. Please allow camera access in your browser settings to continue.');
      } else {
        setError('Could not access camera. Please make sure your camera is connected and not in use by another app.');
      }
    }
  };

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
    setActive(false);
  }, [stream]);

  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stream]);

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    
    const ctx = canvas.getContext('2d');
    // Mirror the canvas image to match user-facing preview
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], 'selfie.jpg', { type: 'image/jpeg' });
        onCapture(file);
        stopCamera();
      }
    }, 'image/jpeg', 0.95);
  };

  if (selfiePreview) {
    return (
      <div style={{ textAlign: 'center', padding: '12px 0' }}>
        <div className="selfie-preview">
          <img src={selfiePreview} alt="Your live selfie preview" style={{ width: 140, height: 140, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border-active)' }} />
          <button className="selfie-remove" onClick={onClear} aria-label="Remove selfie">✕</button>
        </div>
        <p className="text-muted text-sm mt-3">Live selfie captured successfully!</p>
      </div>
    );
  }

  if (active) {
    return (
      <div className="flex flex-col items-center gap-4 w-full" style={{ padding: '10px 0' }}>
        <div style={{
          position: 'relative',
          width: '100%',
          maxWidth: '400px',
          aspectRatio: '4/3',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
          background: '#000',
          border: '1px solid var(--border-glass)',
        }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              transform: 'scaleX(-1)', // Mirror user preview
            }}
          />
          <div style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <div style={{
              width: '180px',
              height: '220px',
              borderRadius: '50%',
              border: '2px dashed rgba(255, 255, 255, 0.5)',
              boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)',
            }} />
          </div>
        </div>
        <p className="text-muted text-xs">Center your face inside the guide</p>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm" onClick={stopCamera}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={capturePhoto}>
            📸 Snap Photo
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="drop-zone"
      onClick={startCamera}
      style={{ padding: '36px 24px', cursor: 'pointer' }}
    >
      <span className="drop-zone-icon">📸</span>
      <h3>Take Live Selfie</h3>
      <p>
        Click to open camera and snap a photo<br />
        <span style={{ color: 'var(--violet-light)', fontSize: '0.8125rem' }}>
          Live capture only. File uploads are disabled for privacy.
        </span>
      </p>
      {error && (
        <div style={{
          color: 'var(--rose)',
          fontSize: '0.85rem',
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          padding: '8px 12px',
          borderRadius: 'var(--radius-sm)',
          maxWidth: '440px',
          marginTop: '16px',
          marginLeft: 'auto',
          marginRight: 'auto',
        }}>
          ⚠️ {error}
        </div>
      )}
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

  const allMatches = results
    ? [...(results.confident || []), ...(results.possible || [])].sort((a, b) => b.score - a.score)
    : [];

  /* ── Download all ────────────────────────────────────────────────── */
  const downloadAll = async () => {
    if (allMatches.length === 0) return;
    toast('Starting downloads…', { icon: '⬇️' });
    for (let i = 0; i < allMatches.length; i++) {
      await new Promise((r) => setTimeout(r, 300 * i));
      const a = document.createElement('a');
      a.href = `${BASE}${allMatches[i].url}`;
      a.download = `lookitup-${i + 1}.jpg`;
      a.target = '_blank';
      a.click();
    }
  };

  const totalResults = allMatches.length;

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
            Take a live selfie and we'll instantly find every photo from this event where you appear.
          </p>
        </div>

        {/* Search Card */}
        <div className="glow-card mb-6">
          <SelfieCameraZone
            onCapture={handleSelfieFile}
            selfiePreview={selfiePreview}
            onClear={clearSelfie}
          />

          {selfieFile && (
            <div style={{ marginTop: '20px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button className="btn btn-ghost" onClick={clearSelfie} disabled={searching}>
                🔄 Retake Selfie
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
            <div style={{ marginTop: '20px', display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
              {[
                { icon: '💡', text: 'Use a clear, well-lit selfie' },
                { icon: '👤', text: 'Only your face in the photo' },
                { icon: '🔒', text: 'Live capture ensures privacy' },
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

            {totalResults > 0 && (
              <div className="photo-grid mt-4">
                {allMatches.map((photo, i) => (
                  <PhotoCard
                    key={photo.photo_id}
                    photo={photo}
                    index={i}
                    onOpen={setLightboxUrl}
                  />
                ))}
              </div>
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
