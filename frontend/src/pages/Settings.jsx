import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function Settings() {
  const { activeTeamId, teams, refreshUser } = useAuth();
  const [members, setMembers] = useState([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [newTeamName, setNewTeamName] = useState('');
  const [message, setMessage] = useState(null);

  const fetchMembers = async () => {
    if (!activeTeamId) return;
    try {
      const { data } = await api.get(`/api/teams/${activeTeamId}/members`);
      setMembers(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { fetchMembers(); }, [activeTeamId]);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    try {
      await api.post(`/api/teams/${activeTeamId}/invite`, { email: inviteEmail });
      setMessage({ type: 'success', text: `Invited ${inviteEmail}` });
      setInviteEmail('');
      fetchMembers();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to invite' });
    }
  };

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) return;
    try {
      await api.post('/api/teams', { name: newTeamName });
      setNewTeamName('');
      setMessage({ type: 'success', text: `Team "${newTeamName}" created` });
      refreshUser();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to create team' });
    }
  };

  const handleRemoveMember = async (userId) => {
    if (!confirm('Remove this member?')) return;
    try {
      await api.delete(`/api/teams/${activeTeamId}/members/${userId}`);
      fetchMembers();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to remove' });
    }
  };

  const currentTeam = teams.find(t => t.id === activeTeamId);

  return (
    <div className="ca-page ca-fade-in">
      <div className="ca-h1">Settings</div>
      <p className="ca-subtitle">Manage your team, members, and account.</p>

      {message && (
        <div style={{
          padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 12,
          background: message.type === 'success' ? 'var(--accent-dim)' : 'var(--accent2-dim)',
          color: message.type === 'success' ? 'var(--accent)' : 'var(--accent2)',
          border: `1px solid ${message.type === 'success' ? 'rgba(79,255,176,.3)' : 'rgba(255,107,107,.3)'}`,
        }}>
          {message.text}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
        {/* Team Members */}
        <div className="ca-card">
          <div className="ca-card-title">
            Team Members — {currentTeam?.name || 'Select a team'}
          </div>
          {members.map(m => (
            <div key={m.user_id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 0', borderBottom: '1px solid var(--border)',
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500 }}>{m.display_name || m.email}</div>
                <div style={{ fontSize: 10, color: 'var(--muted)' }}>{m.email} · {m.role}</div>
              </div>
              {m.role !== 'owner' && (
                <button className="ca-btn-danger" onClick={() => handleRemoveMember(m.user_id)}>
                  Remove
                </button>
              )}
            </div>
          ))}

          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <input
              className="ca-input"
              placeholder="Invite by email..."
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleInvite()}
            />
            <button className="ca-btn ca-btn-primary ca-btn-sm" onClick={handleInvite}>
              Invite
            </button>
          </div>
        </div>

        {/* Create Team */}
        <div className="ca-card">
          <div className="ca-card-title">Create New Team</div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 16 }}>
            Teams share products, index overrides, and uploaded price data.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="ca-input"
              placeholder="Team name..."
              value={newTeamName}
              onChange={e => setNewTeamName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreateTeam()}
            />
            <button className="ca-btn ca-btn-primary ca-btn-sm" onClick={handleCreateTeam}>
              Create
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}