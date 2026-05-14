import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import './App.css';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Orbs from './components/Orbs';
import HomePage from './pages/HomePage';
import OrganizerPage from './pages/OrganizerPage';
import AttendeePage from './pages/AttendeePage';

export default function App() {
  return (
    <BrowserRouter>
      <Orbs />
      <Navbar />
      <main style={{ position: 'relative', zIndex: 1, minHeight: 'calc(100vh - 128px)' }}>
        <Routes>
          <Route path="/"            element={<HomePage />} />
          <Route path="/organizer"   element={<OrganizerPage />} />
          <Route path="/event/:token" element={<AttendeePage />} />
        </Routes>
      </main>
      <Footer />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'rgba(13,13,31,0.95)',
            color: '#f1f0ff',
            border: '1px solid rgba(255,255,255,0.1)',
            backdropFilter: 'blur(20px)',
            fontFamily: "'Inter', sans-serif",
            fontSize: '0.875rem',
            borderRadius: '12px',
            padding: '12px 16px',
          },
          success: {
            iconTheme: { primary: '#10b981', secondary: '#060612' },
          },
          error: {
            iconTheme: { primary: '#f43f5e', secondary: '#060612' },
          },
        }}
      />
    </BrowserRouter>
  );
}
