import { useAuth } from '../AuthContext';

export default function TeamSelector() {
  const { teams, activeTeamId, switchTeam } = useAuth();

  if (teams.length <= 1) return null;

  return (
    <select
      className="ca-select"
      style={{ width: 'auto', minWidth: 140, fontSize: 11, padding: '6px 10px' }}
      value={activeTeamId || ''}
      onChange={(e) => switchTeam(e.target.value)}
    >
      {teams.map(t => (
        <option key={t.id} value={t.id}>{t.name}</option>
      ))}
    </select>
  );
}