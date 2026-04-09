import { useState, useEffect, useRef } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function Admin() {
  const { user, refreshUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('users');
  const [impersonating, setImpersonating] = useState(false);

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      api.get('/api/admin/users'),
      api.get('/api/admin/teams'),
    ])
      .then(([uRes, tRes]) => {
        setUsers(uRes.data);
        setTeams(tRes.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(fetchData, []);

  useEffect(() => {
    setImpersonating(document.cookie.includes('ca_admin_token'));
  }, []);

  const toggleSuperAdmin = async (userId, current) => {
    await api.put(`/api/admin/users/${userId}`, { is_super_admin: !current });
    fetchData();
  };

  const impersonate = async (userId) => {
    try {
      await api.post(`/api/admin/impersonate/${userId}`);
      setImpersonating(true);
      await refreshUser();
      window.location.href = '/';
    } catch (err) {
      alert('Failed to impersonate: ' + (err.response?.data?.detail || err.message));
    }
  };

  const stopImpersonating = async () => {
    try {
      await api.post('/api/admin/stop-impersonate');
      setImpersonating(false);
      await refreshUser();
      window.location.href = '/admin';
    } catch (err) {
      alert('Failed to stop impersonating: ' + (err.response?.data?.detail || err.message));
    }
  };

  if (!user?.is_super_admin && !impersonating) {
    return (
      <div className="ca-page ca-fade-in">
        <div className="ca-h1">Access Denied</div>
        <p className="ca-subtitle">You need super admin privileges to view this page.</p>
      </div>
    );
  }

  return (
    <div className="ca-page ca-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">Admin Panel</div>
      </div>
      <p className="ca-subtitle">Manage users, teams, and impersonate accounts.</p>

      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        <button className={`ca-btn ${tab === 'users' ? 'ca-btn-primary' : 'ca-btn-ghost'}`} onClick={() => setTab('users')}>
          Users ({users.length})
        </button>
        <button className={`ca-btn ${tab === 'teams' ? 'ca-btn-primary' : 'ca-btn-ghost'}`} onClick={() => setTab('teams')}>
          Teams ({teams.length})
        </button>
      </div>

      {loading ? (
        <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
      ) : tab === 'users' ? (
        <div className="ca-card">
          <div className="ca-scroll-x">
            <table className="ca-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th className="center">Role</th>
                  <th>Teams</th>
                  <th className="center">Last Login</th>
                  <th className="center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {u.avatar_url && (
                          <img src={u.avatar_url} alt="" style={{ width: 24, height: 24, borderRadius: '50%' }} />
                        )}
                        <span style={{ fontWeight: 600 }}>{u.display_name || 'No name'}</span>
                      </div>
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--muted)' }}>{u.email}</td>
                    <td className="center">
                      <span style={{
                        display: 'inline-block', padding: '2px 8px', borderRadius: 4,
                        fontSize: 10, fontWeight: 600,
                        background: u.is_super_admin ? 'rgba(79,255,176,.12)' : 'rgba(255,255,255,.05)',
                        color: u.is_super_admin ? 'var(--accent)' : 'var(--muted)',
                      }}>
                        {u.is_super_admin ? 'SUPER ADMIN' : 'USER'}
                      </span>
                    </td>
                    <td>
                      <TeamCell userId={u.id} userTeams={u.teams} allTeams={teams} onChanged={fetchData} />
                    </td>
                    <td className="center" style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : '\u2014'}
                    </td>
                    <td className="center">
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                        <button className="ca-btn ca-btn-ghost ca-btn-sm"
                          onClick={() => toggleSuperAdmin(u.id, u.is_super_admin)}>
                          {u.is_super_admin ? 'Revoke Admin' : 'Make Admin'}
                        </button>
                        {u.id !== user?.id && (
                          <button className="ca-btn ca-btn-ghost ca-btn-sm"
                            style={{ color: 'var(--accent3)', borderColor: 'var(--accent3)' }}
                            onClick={() => impersonate(u.id)}>
                            Impersonate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="ca-card">
          <div className="ca-scroll-x">
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Team Name</th>
                  <th className="center">Members</th>
                  <th>Member Details</th>
                  <th className="center">Created</th>
                </tr>
              </thead>
              <tbody>
                {teams.map(t => (
                  <tr key={t.id}>
                    <td style={{ fontWeight: 600 }}>{t.name}</td>
                    <td className="center">{t.member_count}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {t.members.map((m, i) => (
                          <span key={i} className="ca-tag">
                            {m.email || m.user_id.slice(0, 8)}
                            <span style={{ color: 'var(--accent3)', marginLeft: 4 }}>{m.role}</span>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="center" style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {t.created_at ? new Date(t.created_at).toLocaleDateString() : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


function TeamCell({ userId, userTeams, allTeams, onChanged }) {
  const [picking, setPicking] = useState(false);
  const [search, setSearch] = useState('');
  const inputRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (picking && inputRef.current) inputRef.current.focus();
  }, [picking]);

  // Close picker on outside click
  useEffect(() => {
    if (!picking) return;
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setPicking(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [picking]);

  const filtered = allTeams.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase())
  );

  const addToTeam = async (teamId) => {
    await api.post(`/api/admin/users/${userId}/add-team`, { team_id: teamId, role: 'member' });
    setPicking(false);
    setSearch('');
    onChanged();
  };

  const removeFromTeam = async (teamId) => {
    await api.delete(`/api/admin/users/${userId}/teams/${teamId}`);
    onChanged();
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', position: 'relative' }} ref={wrapRef}>
      {userTeams.map((t, i) => (
        <span key={i} style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 10, background: 'var(--surface2)', border: '1px solid var(--border)',
          borderRadius: 4, padding: '2px 6px 2px 8px', color: 'var(--text)',
        }}>
          {t.team_name}
          <span style={{ color: 'var(--accent3)', fontSize: 9 }}>{t.role}</span>
          <button
            onClick={() => removeFromTeam(t.team_id)}
            style={{
              background: 'none', border: 'none', color: 'var(--accent2)', cursor: 'pointer',
              fontSize: 11, padding: '0 2px', lineHeight: 1, opacity: 0.6,
            }}
            title="Remove from team"
          >
            x
          </button>
        </span>
      ))}
      {!picking ? (
        <button
          onClick={() => setPicking(true)}
          style={{
            background: 'none', border: '1px dashed var(--border)', borderRadius: 4,
            color: 'var(--muted)', cursor: 'pointer', fontSize: 10, padding: '2px 8px',
            transition: 'border-color .15s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
        >
          + team
        </button>
      ) : (
        <div style={{
          position: 'absolute', top: '100%', left: 0, zIndex: 50, marginTop: 4,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 6, minWidth: 220, boxShadow: '0 8px 24px rgba(0,0,0,.4)',
        }}>
          <input
            ref={inputRef}
            className="ca-input"
            placeholder="Search teams..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ fontSize: 11, padding: '6px 8px', marginBottom: 4 }}
          />
          <div style={{ maxHeight: 150, overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <div style={{ padding: '6px 8px', fontSize: 11, color: 'var(--muted)' }}>No teams found</div>
            ) : (
              filtered.map(t => {
                const alreadyIn = userTeams.some(ut => ut.team_id === t.id);
                return (
                  <div
                    key={t.id}
                    onClick={() => !alreadyIn && addToTeam(t.id)}
                    style={{
                      padding: '5px 8px', fontSize: 11, borderRadius: 4,
                      cursor: alreadyIn ? 'default' : 'pointer',
                      color: alreadyIn ? 'var(--muted)' : 'var(--text)',
                      background: 'transparent',
                      transition: 'background .1s',
                    }}
                    onMouseEnter={e => { if (!alreadyIn) e.currentTarget.style.background = 'var(--surface2)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    {t.name}
                    {alreadyIn && <span style={{ marginLeft: 6, fontSize: 9, color: 'var(--accent)' }}>joined</span>}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
