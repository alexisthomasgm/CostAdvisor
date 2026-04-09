import { useAuth } from '../AuthContext';
import { Navigate } from 'react-router-dom';

export default function Login() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (user) return <Navigate to="/" replace />;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100vh', gap: 24,
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
        href="/auth/login"
        className="ca-btn ca-btn-primary"
        style={{ textDecoration: 'none', fontSize: 13, padding: '14px 32px' }}
      >
        Sign in with Google
      </a>
    </div>
  );
}