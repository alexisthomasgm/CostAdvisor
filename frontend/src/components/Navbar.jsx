import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import TeamSelector from './TeamSelector';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const tabs = [
    { path: '/dashboard', label: 'Dashboard' },
    { path: '/indexes', label: 'Indexes' },
    { path: '/suppliers', label: 'Suppliers' },
    { path: '/team', label: 'Team' },
    ...(user?.is_super_admin ? [{ path: '/admin', label: 'Admin' }] : []),
  ];

  return (
    <nav className="ca-nav">
      <div className="ca-logo" onClick={() => navigate('/dashboard')}>
        Cost<span>Advisor</span>
      </div>
      {tabs.map(t => (
        <div
          key={t.path}
          className={`ca-tab ${location.pathname.startsWith(t.path) ? 'active' : ''}`}
          onClick={() => navigate(t.path)}
        >
          {t.label}
        </div>
      ))}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        <TeamSelector />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {user?.avatar_url && (
            <img
              src={user.avatar_url}
              alt=""
              style={{ width: 28, height: 28, borderRadius: '50%' }}
            />
          )}
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            {user?.display_name}
          </span>
        </div>
        <button
          className="ca-btn ca-btn-ghost"
          style={{ padding: '6px 12px', fontSize: 10 }}
          onClick={logout}
        >
          Logout
        </button>
      </div>
    </nav>
  );
}
