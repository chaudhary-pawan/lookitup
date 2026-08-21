# LookItUp

---

## What problem was i solving?

So this came from something I noticed at events — weddings, college fests, corporate meetups. The photographer takes like 500 photos, dumps them in a Google Drive or shared album, and then every attendee has to sit there and scroll through all 500 to find the 5 photos they're actually in. Nobody does that. Most people open the folder, scroll for 2 minutes, get bored, and close it.

That's a lose-lose. The attendees never find their photos, and the organizer wasted money on a photographer whose work nobody even sees.

I wanted to fix that. The idea behind LookItUp is simple — you upload one selfie, and the app instantly pulls up every photo from the event where your face appears. No scrolling, no tagging, no manual work. You just get your photos.

---

## Which AI tool did i use?

I used **InsightFace with the ArcFace model** — it's an open-source deep learning framework that's specifically built for face recognition and is one of the top performers on standard benchmarks (99.83% on LFW).

Here's what actually happens when someone uses the app:

**When the organizer uploads photos**, each image gets run through InsightFace's detection pipeline. It finds every face in the photo, draws a bounding box around it, and then ArcFace converts each face into a 512-dimensional vector — basically a numerical fingerprint of that person's face. I store these vectors in PostgreSQL using the pgvector extension, so they're searchable right from the database.

**When an attendee uploads a selfie**, the same model generates their face vector in real time. Then I run a cosine similarity search against all the stored vectors for that event. If two vectors are close enough, it means the faces look alike. I split the results into two tiers — "Confident" matches (above 0.75 similarity) and "Possible" matches (above 0.55) — so the user knows which ones are near-certain and which ones are more like "hey, this might be you."

I originally used FAISS for the vector search, which worked fine locally but was kind of a pain for deployment — the index lives in memory and gets lost on restart. So I migrated to pgvector, which keeps everything in Postgres. That made the whole system cloud-friendly without losing search speed.

The rest of the stack supports the ML pipeline:

- **Celery + Redis** handle the heavy lifting in the background — when someone uploads 300 photos, you can't process all of them in a single API request. Celery picks them up and processes them asynchronously.
- **OpenCV and Pillow** handle image decoding and thumbnail generation.
- The InsightFace model itself is about 200MB, so I load it once at startup using a singleton pattern and share it across all workers. No repeated disk I/O.

---

## What changed because of it?

The biggest thing is the time difference. Finding your photos in a 500-photo album used to be a 30-minute chore that most people just skipped. Now it takes about 3 seconds and a single selfie. That alone changes how people interact with event photos.

For attendees — there's nothing to install, no account to create. They get a link, open it, upload a selfie, and they're done. The results show up ranked with confidence scores, so they can trust what they're seeing.

For organizers — they just upload the album and share one link. No manual tagging, no emailing individual photos. And because people can actually find their photos now, the engagement rate goes way up. Photos that would've never been viewed actually get downloaded.

On the engineering side, this isn't just a Jupyter notebook with a model — it's a full-stack app with 7 modules that each handle one thing:

- A **FastAPI backend** with JWT auth, role-based access (organizer vs attendee), and upload validation
- A **pluggable storage layer** — I built it with a strategy pattern so switching from local disk to Cloudinary is just a config change, no code edits
- An **async ingestion pipeline** (Celery + Redis) that processes photo batches in the background without blocking the API
- A **database layer** using SQLAlchemy with Alembic migrations and pgvector for native vector search
- A **face engine module** that wraps InsightFace — it's the only part that knows anything about ML, everything else is ML-agnostic
- A **React + Vite frontend** with drag-and-drop selfie upload, a photo grid with lightbox view, confidence badges, and a download-all button

The whole thing runs on Docker Compose — API, Celery worker, Redis, and frontend all in separate containers. And I wrote 11 test files covering the face engine, vector search, database layer, API endpoints, and the batch processor.

---

## The short version

I built LookItUp because finding your photos in a large event album is a surprisingly annoying problem. I used ArcFace for face recognition and pgvector for similarity search to turn a 30-minute scroll into a 3-second selfie search. It's a full-stack app — FastAPI, React, Celery, PostgreSQL, Docker — not just an ML demo.
