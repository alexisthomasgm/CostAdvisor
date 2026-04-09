import { useState, useEffect } from 'react';
import FileUpload from '../components/FileUpload';
import api from '../api';
import { useAuth } from '../AuthContext';
import exportCsv from '../utils/exportCsv';

export default function Team() {
  const [tab, setTab] = useState('members');

  return (
    <div className="ca-page ca-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">Team</div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['members', 'activity', 'settings'].map(t => (
          <button key={t} className={`ca-btn ${tab === t ? 'ca-btn-primary' : 'ca-btn-ghost'}`}
            onClick={() => setTab(t)}>
            {t === 'members' ? 'Members' : t === 'activity' ? 'Activity Log' : 'Settings'}
          </button>
        ))}
      </div>

      {tab === 'members' && <MembersTab />}
      {tab === 'activity' && <ActivityTab />}
      {tab === 'settings' && <SettingsTab />}
    </div>
  );
}

function MembersTab() {
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
    <>
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
    </>
  );
}

function ActivityTab() {
  const { activeTeamId } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [entityType, setEntityType] = useState('');
  const PAGE_SIZE = 50;

  const fetchLogs = (reset = false) => {
    if (!activeTeamId) return;
    const p = reset ? 0 : page;
    if (reset) setPage(0);
    setLoading(true);
    const params = { team_id: activeTeamId, skip: p * PAGE_SIZE, limit: PAGE_SIZE };
    if (entityType) params.entity_type = entityType;
    api.get('/api/audit', { params })
      .then(res => {
        const rows = res.data;
        if (reset) setLogs(rows);
        else setLogs(prev => [...prev, ...rows]);
        setHasMore(rows.length === PAGE_SIZE);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchLogs(true); }, [activeTeamId, entityType]);

  const loadMore = () => {
    setPage(p => p + 1);
  };

  useEffect(() => {
    if (page > 0) fetchLogs();
  }, [page]);

  const formatDate = (iso) => {
    if (!iso) return '\u2014';
    return new Date(iso).toLocaleString();
  };

  return (
    <>
      <div className="ca-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label className="ca-label">Entity Type</label>
            <select className="ca-select" value={entityType} onChange={e => setEntityType(e.target.value)}>
              <option value="">All</option>
              <option value="cost_model">Cost Model</option>
              <option value="formula_version">Formula Version</option>
              <option value="price_data">Price Data</option>
              <option value="actual_volume">Volume</option>
              <option value="supplier">Supplier</option>
              <option value="product">Product</option>
              <option value="index_override">Index Override</option>
            </select>
          </div>
        </div>
      </div>

      {loading && logs.length === 0 ? (
        <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
      ) : logs.length === 0 ? (
        <div className="ca-card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
          No audit events found.
        </div>
      ) : (
        <div className="ca-card">
          <div className="ca-scroll-x">
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Event</th>
                  <th>Entity</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                      {formatDate(log.created_at)}
                    </td>
                    <td style={{ fontSize: 11 }}>{log.user_email || '\u2014'}</td>
                    <td>
                      <span style={{
                        display: 'inline-block', padding: '1px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: log.event_type === 'create' ? 'rgba(79,255,176,.12)' : log.event_type === 'delete' ? 'rgba(232,65,24,.15)' : 'rgba(116,185,255,.15)',
                        color: log.event_type === 'create' ? 'var(--accent)' : log.event_type === 'delete' ? 'var(--accent2)' : 'var(--accent3)',
                      }}>
                        {log.event_type}
                      </span>
                    </td>
                    <td style={{ fontSize: 11 }}>
                      <span style={{ color: 'var(--text)' }}>{log.entity_type}</span>
                      <span style={{ color: 'var(--muted)', marginLeft: 6, fontSize: 9 }}>{log.entity_id?.slice(0, 8)}</span>
                    </td>
                    <td style={{ maxWidth: 300 }}>
                      {log.new_value ? (
                        <details style={{ fontSize: 10 }}>
                          <summary style={{ cursor: 'pointer', color: 'var(--accent3)' }}>View changes</summary>
                          <pre style={{ marginTop: 4, padding: 8, background: 'var(--surface2)', borderRadius: 4, overflow: 'auto', maxHeight: 150, fontSize: 9 }}>
                            {JSON.stringify(log.new_value, null, 2)}
                          </pre>
                        </details>
                      ) : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <button className="ca-btn ca-btn-ghost" onClick={loadMore} disabled={loading}>
                {loading ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function SettingsTab() {
  const { user } = useAuth();
  const [rates, setRates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');

  const fetchRates = () => {
    setLoading(true);
    const params = {};
    if (filterFrom) params.from_currency = filterFrom;
    if (filterTo) params.to_currency = filterTo;
    api.get('/api/fx-rates', { params })
      .then(({ data }) => setRates(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(fetchRates, [filterFrom, filterTo]);

  const currencies = [...new Set(rates.flatMap(r => [r.from_currency, r.to_currency]))].sort();

  const pairs = {};
  for (const r of rates) {
    const key = `${r.from_currency}/${r.to_currency}`;
    if (!pairs[key]) pairs[key] = [];
    pairs[key].push(r);
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => rates.length > 0 && exportCsv(
          'fx_rates.csv',
          ['From', 'To', 'Year', 'Quarter', 'Rate'],
          rates.map(r => [r.from_currency, r.to_currency, r.year, r.quarter, r.rate])
        )}>Export CSV</button>
      </div>

      <div className="ca-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <div>
            <label className="ca-label">From Currency</label>
            <select className="ca-select" value={filterFrom} onChange={e => setFilterFrom(e.target.value)}>
              <option value="">All</option>
              {currencies.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="ca-label">To Currency</label>
            <select className="ca-select" value={filterTo} onChange={e => setFilterTo(e.target.value)}>
              <option value="">All</option>
              {currencies.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button className="ca-btn ca-btn-ghost" onClick={() => { setFilterFrom(''); setFilterTo(''); }}>Clear</button>
          </div>
        </div>
      </div>

      {user?.is_super_admin && (
        <div style={{ marginBottom: 16 }}>
          <FileUpload endpoint="/api/fx-rates/upload" onSuccess={fetchRates} />
        </div>
      )}

      {loading ? (
        <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
      ) : rates.length === 0 ? (
        <div className="ca-card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
          No FX rates found. {user?.is_super_admin ? 'Upload a CSV to get started.' : 'Ask a super admin to upload rates.'}
        </div>
      ) : (
        Object.entries(pairs).map(([pair, pairRates]) => (
          <div key={pair} className="ca-card" style={{ marginBottom: 12 }}>
            <div className="ca-card-title">{pair}</div>
            <div className="ca-scroll-x">
              <table className="ca-table">
                <thead>
                  <tr>
                    <th>Year</th>
                    <th className="center">Q1</th>
                    <th className="center">Q2</th>
                    <th className="center">Q3</th>
                    <th className="center">Q4</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const years = [...new Set(pairRates.map(r => r.year))].sort();
                    return years.map(y => (
                      <tr key={y}>
                        <td style={{ fontWeight: 600 }}>{y}</td>
                        {[1, 2, 3, 4].map(q => {
                          const val = pairRates.find(r => r.year === y && r.quarter === q);
                          return (
                            <td key={q} className="center" style={{ fontFamily: "'JetBrains Mono', monospace", color: val ? 'var(--text)' : 'var(--muted)' }}>
                              {val ? val.rate.toFixed(4) : '\u2014'}
                            </td>
                          );
                        })}
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </>
  );
}
