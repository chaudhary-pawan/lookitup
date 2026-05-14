import { useState, useCallback, useRef, useEffect } from 'react';
import toast from 'react-hot-toast';
import { createEvent, uploadPhotos, getEventStatus, deleteEvent } from '../api';

/* ── Helpers ──────────────────────────────────────────────────────────── */
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const ACCEPT = '.jpg,.jpeg,.png,.webp,.zip';

/* ── Steps ────────────────────────────────────────────────────────────── */
const STEP_CREATE  = 0;
const STEP_UPLOAD  = 1;
const STEP_STATUS  = 2;

/* ══════════════════════════════════════════════════════════════════════ */
export default function OrganizerPage() {
  const [step, setStep]           = useState(STEP_CREATE);
  const [eventName, setEventName] = useState('');
  const [eventId, setEventId]     = useState(null);
  const [shareToken, setShareToken] = useState(null);
  const [files, setFiles]         = useState([]);
  const [dragging, setDragging]   = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [eventStatus, setEventStatus] = useState(null); // {status, share_link?}
  const [creating, setCreating]   = useState(false);
  const [deleting, setDeleting]   = useState(false);

  const pollRef = useRef(null);
  const fileInputRef = useRef(null);

  /* ── Poll status ────────────────────────────────────────────────── */
  useEffect(() => {
    if (step === STEP_STATUS && eventId) {
      const poll = async () => {
        try {
          const data = await getEventStatus(eventId);
          setEventStatus(data);
          if (data.status === 'ready') {
            clearInterval(pollRef.current);
            toast.success('🎉 Event is ready! Share the link with attendees.');
          } else if (data.status === 'error') {
            clearInterval(pollRef.current);
            toast.error('Processing failed. Please try re-uploading.');
          }
        } catch (e) {
          console.error('Status poll error', e);
        }
      };
      poll();
      pollRef.current = setInterval(poll, 5000);
    }
    return () => clearInterval(pollRef.current);
  }, [step, eventId]);

  /* ── Create event ───────────────────────────────────────────────── */
  const handleCreate = async () => {
    if (!eventName.trim()) {
      toast.error('Please enter an event name');
      return;
    }
    setCreating(true);
    try {
      const data = await createEvent(eventName.trim());
      setEventId(data.event_id);
      setShareToken(data.share_token);
      setStep(STEP_UPLOAD);
      toast.success('Event created! Now upload your photos.');
    } catch (e) {
      toast.error(e.message || 'Failed to create event');
    } finally {
      setCreating(false);
    }
  };

  /* ── File handling ──────────────────────────────────────────────── */
  const addFiles = useCallback((newFiles) => {
    const arr = Array.from(newFiles).filter((f) => {
      const ok = /\.(jpe?g|png|webp|zip)$/i.test(f.name);
      if (!ok) toast.error(`Skipped: ${f.name} (unsupported type)`);
      return ok;
    });
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      return [...prev, ...arr.filter((f) => !existing.has(f.name + f.size))];
    });
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragging(false), []);

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  /* ── Upload ─────────────────────────────────────────────────────── */
  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select at least one photo or ZIP');
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      const data = await uploadPhotos(eventId, files, setUploadProgress);
      toast.success(`✅ ${data.queued_photos} photos queued for processing!`);
      setStep(STEP_STATUS);
      setEventStatus({ status: 'processing' });
    } catch (e) {
      toast.error(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  /* ── Delete ─────────────────────────────────────────────────────── */
  const handleDelete = async () => {
    if (!window.confirm('Delete this event and ALL its photos? This cannot be undone.')) return;
    setDeleting(true);
    try {
      await deleteEvent(eventId);
      toast.success('Event deleted.');
      // Reset everything
      setStep(STEP_CREATE);
      setEventId(null); setShareToken(null); setFiles([]);
      setEventStatus(null); setEventName('');
    } catch (e) {
      toast.error(e.message || 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  /* ── Copy share link ─────────────────────────────────────────────── */
  const shareUrl = shareToken
    ? `${window.location.origin}/event/${shareToken}`
    : '';

  const copyLink = () => {
    navigator.clipboard.writeText(shareUrl);
    toast.success('Link copied to clipboard!');
  };

  /* ── Render ──────────────────────────────────────────────────────── */
  return (
    <div className="page-enter" style={{ padding: '40px 24px 60px' }}>
      <div className="container" style={{ maxWidth: 680 }}>

        {/* Header */}
        <div className="text-center mb-6">
          <div className="hero-eyebrow" style={{ margin: '0 auto 16px' }}>Organizer Dashboard</div>
          <h1 style={{ fontSize: 'clamp(1.75rem, 4vw, 2.75rem)', fontWeight: 900 }}>
            Create Your <span className="gradient-text">Event Album</span>
          </h1>
          <p className="text-muted mt-2" style={{ fontSize: '1rem', lineHeight: 1.6 }}>
            Upload photos once — attendees find themselves in seconds.
          </p>
        </div>

        {/* Step dots */}
        <div className="step-dots">
          <div className={`step-dot ${step === STEP_CREATE ? 'active' : step > STEP_CREATE ? 'done' : ''}`} />
          <div className={`step-dot ${step === STEP_UPLOAD ? 'active' : step > STEP_UPLOAD ? 'done' : ''}`} />
          <div className={`step-dot ${step === STEP_STATUS ? 'active' : ''}`} />
        </div>

        {/* ── STEP 0: Create Event ─────────────────────────────────── */}
        {step === STEP_CREATE && (
          <div className="glow-card page-enter">
            <h2 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>Name Your Event</h2>
            <p className="text-muted text-sm mb-4">
              Give your album a memorable name so attendees recognise it.
            </p>

            <label htmlFor="event-name-input" style={{ display: 'block', fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: 500 }}>
              Event name
            </label>
            <input
              id="event-name-input"
              className="input"
              type="text"
              placeholder="e.g. Summer Wedding 2024, TechConf Bangalore…"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              maxLength={120}
              autoFocus
            />

            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                id="create-event-btn"
                className="btn btn-primary"
                onClick={handleCreate}
                disabled={creating || !eventName.trim()}
              >
                {creating
                  ? <><span className="spinner spinner-sm" /> Creating…</>
                  : '✨ Create Event →'}
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 1: Upload Photos ────────────────────────────────── */}
        {step === STEP_UPLOAD && (
          <div className="page-enter">
            <div className="glow-card mb-4">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>Upload Photos</h2>
                  <p className="text-muted text-sm">
                    Event: <strong style={{ color: 'var(--text-primary)' }}>{eventName}</strong>
                  </p>
                </div>
                <span className="badge badge-amber">Step 2</span>
              </div>

              {/* Drop Zone */}
              <div
                id="photo-drop-zone"
                className={`drop-zone ${dragging ? 'dragging' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  onChange={(e) => addFiles(e.target.files)}
                  style={{ display: 'none' }}
                  id="file-input"
                />
                <span className="drop-zone-icon">
                  {dragging ? '📂' : '🖼️'}
                </span>
                <h3>{dragging ? 'Drop to add photos' : 'Drop photos here'}</h3>
                <p>
                  Drag & drop JPEG, PNG, WebP files — or a single ZIP archive<br />
                  <span style={{ color: 'var(--violet-light)', marginTop: 4, display: 'inline-block' }}>
                    or click to browse
                  </span>
                </p>
              </div>
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="glow-card mb-4 page-enter">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>
                    {files.length} file{files.length > 1 ? 's' : ''} selected
                  </h3>
                  <button className="btn btn-sm btn-ghost" onClick={() => setFiles([])}>
                    Clear all
                  </button>
                </div>
                <div className="file-list">
                  {files.map((f, i) => (
                    <div key={i} className="file-item">
                      <span className="file-item-icon">
                        {f.name.endsWith('.zip') ? '📦' : '🖼️'}
                      </span>
                      <span className="file-item-name">{f.name}</span>
                      <span className="file-item-size">{formatBytes(f.size)}</span>
                      <button
                        className="file-item-remove"
                        onClick={() => removeFile(i)}
                        aria-label={`Remove ${f.name}`}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upload progress */}
            {uploading && (
              <div className="glow-card mb-4 page-enter">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>Uploading…</span>
                  <span style={{ fontSize: '0.875rem', color: 'var(--violet-light)' }}>
                    {uploadProgress}%
                  </span>
                </div>
                <div className="progress-bar-wrap">
                  <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setStep(STEP_CREATE)} disabled={uploading}>
                ← Back
              </button>
              <button
                id="upload-photos-btn"
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={uploading || files.length === 0}
              >
                {uploading
                  ? <><span className="spinner spinner-sm" /> Uploading…</>
                  : `🚀 Upload ${files.length} file${files.length > 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 2: Status / Share ───────────────────────────────── */}
        {step === STEP_STATUS && eventStatus && (
          <div className="page-enter">
            <div className="status-card mb-4">
              <div className="status-header">
                <div className={`status-icon-wrap ${eventStatus.status}`}>
                  {eventStatus.status === 'processing' && '⚙️'}
                  {eventStatus.status === 'ready'      && '✅'}
                  {eventStatus.status === 'error'      && '❌'}
                </div>
                <div>
                  <h2 style={{ fontSize: '1.125rem', marginBottom: '6px' }}>
                    {eventStatus.status === 'processing' && 'Processing Photos…'}
                    {eventStatus.status === 'ready'      && 'Event is Live! 🎉'}
                    {eventStatus.status === 'error'      && 'Processing Error'}
                  </h2>
                  {eventStatus.status === 'processing' && (
                    <p className="text-muted text-sm">
                      AI is detecting and indexing faces. This auto-refreshes every 5s.
                    </p>
                  )}
                  {eventStatus.status === 'ready' && (
                    <p className="text-muted text-sm">
                      All faces indexed. Share the link below with attendees.
                    </p>
                  )}
                </div>
                {eventStatus.status === 'processing' && (
                  <div className="spinner" style={{ marginLeft: 'auto' }} />
                )}
              </div>

              {eventStatus.status === 'processing' && (
                <div className="progress-bar-wrap" style={{ height: 8 }}>
                  <div
                    className="progress-bar-fill"
                    style={{ width: '60%', animation: 'shimmer 1.5s linear infinite' }}
                  />
                </div>
              )}

              {/* Share link */}
              {eventStatus.status === 'ready' && (
                <div>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)', marginBottom: '10px', fontWeight: 500 }}>
                    Attendee share link:
                  </p>
                  <div className="share-box">
                    <span className="share-link">{shareUrl}</span>
                    <button
                      id="copy-link-btn"
                      className="btn btn-sm btn-primary"
                      onClick={copyLink}
                    >
                      📋 Copy
                    </button>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <a
                      href={shareUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      id="open-attendee-link"
                      className="btn btn-ghost btn-sm w-full"
                    >
                      🔗 Open Attendee Page
                    </a>
                  </div>
                </div>
              )}
            </div>

            {/* Danger zone */}
            <div className="glow-card" style={{ borderColor: 'rgba(244,63,94,0.2)' }}>
              <h3 style={{ fontSize: '0.9375rem', color: 'var(--rose)', marginBottom: '8px' }}>
                ⚠️ Danger Zone
              </h3>
              <p className="text-muted text-sm mb-4">
                Permanently delete this event album and all uploaded photos from storage.
                This action cannot be undone.
              </p>
              <button
                id="delete-event-btn"
                className="btn btn-danger btn-sm"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting
                  ? <><span className="spinner spinner-sm" /> Deleting…</>
                  : '🗑️ Delete Event & All Photos'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
