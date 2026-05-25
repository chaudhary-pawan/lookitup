import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { loginOrganizer, registerOrganizer } from '../api';

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [animating, setAnimating] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Please enter email and password');
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        const data = await loginOrganizer(email, password);
        sessionStorage.setItem('organizer_token', data.access_token);
        toast.success('Logged in successfully');
        navigate('/organizer');
      } else {
        await registerOrganizer(email, password);
        toast.success('Registration successful. Please log in.');
        handleToggleMode();
      }
    } catch (err) {
      toast.error(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleMode = () => {
    setAnimating(true);
    setTimeout(() => {
      setIsLogin((prev) => !prev);
      setAnimating(false);
    }, 150);
  };

  return (
    <div className="page-enter" style={{ padding: '60px 24px 80px' }}>
      <div className="container" style={{ maxWidth: 420 }}>
        
        <div className="auth-card">
          <div className="auth-icon-wrap" style={{ transform: animating ? 'scale(0.8) rotate(-45deg)' : 'none' }}>
            {isLogin ? '🔒' : '👤'}
          </div>

          <div className={`form-transition ${animating ? 'animating' : ''}`}>
            <div className="text-center mb-6">
              <h1 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                {isLogin ? 'Welcome Back' : 'Create Account'}
              </h1>
              <p className="text-muted mt-2" style={{ fontSize: '0.875rem' }}>
                {isLogin ? 'Sign in to manage your events' : 'Sign up to create new events'}
              </p>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.875rem', fontWeight: 500 }}>
                  Email Address
                </label>
                <input
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.875rem', fontWeight: 500 }}>
                  Password
                </label>
                <input
                  type="password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </div>
              <button 
                type="submit" 
                className="btn btn-primary-interactive" 
                disabled={loading} 
                style={{ padding: '12px 24px', fontWeight: 600 }}
              >
                {loading ? 'Processing...' : isLogin ? 'Sign In' : 'Sign Up'}
              </button>
            </form>

            <div style={{ marginTop: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button 
                onClick={handleToggleMode}
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--violet-light)', 
                  cursor: 'pointer', 
                  fontWeight: 500,
                  textDecoration: 'underline', 
                  padding: 0 
                }}
              >
                {isLogin ? 'Sign Up' : 'Sign In'}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
