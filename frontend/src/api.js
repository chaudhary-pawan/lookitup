/**
 * api.js — All communication with the FastAPI backend.
 * Base URL is configured via VITE_API_BASE_URL env var (defaults to localhost:8000).
 */

// In dev, Vite proxies /api → localhost:8000. In prod, set VITE_API_BASE_URL.
export const BASE = import.meta.env.VITE_API_BASE_URL || '';

/* ── Generic fetch helper ─────────────────────────────────────────────── */
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('organizer_token');
  if (token) {
    options.headers = {
      ...options.headers,
      Authorization: `Bearer ${token}`
    };
  }

  const res = await fetch(`${BASE}${path}`, options);

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch { /* non-JSON body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  // 204 No Content
  if (res.status === 204) return null;

  return res.json();
}

/* ── Auth ─────────────────────────────────────────────────────────────── */

/**
 * Register a new organizer
 */
export async function registerOrganizer(email, password) {
  return apiFetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
}

/**
 * Login organizer
 */
export async function loginOrganizer(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email); // OAuth2 spec uses 'username'
  formData.append('password', password);

  return apiFetch('/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });
}

/**
 * Get current organizer info
 */
export async function getMe() {
  return apiFetch('/api/auth/me');
}

/* ── Events ───────────────────────────────────────────────────────────── */

/**
 * Create a new event album.
 * @param {string} name
 * @returns {{ event_id, share_token, share_link }}
 */
export async function createEvent(name) {
  return apiFetch(`/api/events/create?name=${encodeURIComponent(name)}`, {
    method: 'POST',
  });
}

/**
 * Upload photos to an event. Accepts File[] (JPEG/PNG/ZIP).
 * @param {string} eventId
 * @param {File[]} files
 * @param {function} onProgress - called with (0-100)
 * @returns {{ status, queued_photos, message }}
 */
export async function uploadPhotos(eventId, files, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));

    const xhr = new XMLHttpRequest();
    
    // Add JWT Token
    const token = localStorage.getItem('organizer_token');
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let detail = `HTTP ${xhr.status}`;
        try { detail = JSON.parse(xhr.responseText).detail || detail; } catch { /* */ }
        const err = new Error(detail);
        err.status = xhr.status;
        reject(err);
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

    xhr.open('POST', `${BASE}/api/events/${eventId}/upload`);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    xhr.send(formData);
  });
}

/**
 * Poll event processing status.
 * @param {string} eventId
 * @returns {{ event_id, status, share_link? }}
 */
export async function getEventStatus(eventId) {
  return apiFetch(`/api/events/${eventId}/status`);
}

/**
 * Delete an event and all its photos.
 * @param {string} eventId
 */
export async function deleteEvent(eventId) {
  return apiFetch(`/api/events/${eventId}`, { method: 'DELETE' });
}

/* ── Search ───────────────────────────────────────────────────────────── */

/**
 * Search an event by selfie.
 * @param {string} shareToken
 * @param {File} selfieFile
 * @returns {{ event_id, query_face_detected, results, total_matches }}
 */
export async function searchBySelfie(shareToken, selfieFile) {
  const formData = new FormData();
  formData.append('selfie', selfieFile);
  return apiFetch(`/api/events/${shareToken}/search`, {
    method: 'POST',
    body: formData,
  });
}

/* ── Health ───────────────────────────────────────────────────────────── */
export async function healthCheck() {
  return apiFetch('/health');
}
