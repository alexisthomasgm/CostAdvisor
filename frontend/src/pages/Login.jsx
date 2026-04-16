import { useAuth } from '../AuthContext';
import { Link, Navigate } from 'react-router-dom';

export default function Login() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (user) return <Navigate to="/" replace />;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: 'calc(100vh - 80px)', gap: 24,
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: "'Syne', sans-serif", fontWeight: 800,
          fontSize: 36, color: 'var(--accent)', marginBottom: 8,
        }}>
          Cost<span style={{ color: 'var(--muted)' }}>Advisor</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          Should-Cost Estimator for Chemical Products
        </p>
      </div>
      <a
        href={`${import.meta.env.VITE_API_BASE_URL || ''}/auth/login`}
        className="ca-btn ca-btn-primary"
        style={{ textDecoration: 'none', fontSize: 13, padding: '14px 32px' }}
      >
        Sign in with Google
      </a>
      <p style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', maxWidth: 320 }}>
        By signing in you agree to our{' '}
        <Link to="/terms" style={{ color: 'var(--muted)' }}>Terms</Link> and{' '}
        <Link to="/privacy" style={{ color: 'var(--muted)' }}>Privacy Policy</Link>.
      </p>
    </div>
  );
}