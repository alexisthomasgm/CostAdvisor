import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [teams, setTeams] = useState([]);
  const [activeTeamId, setActiveTeamId] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const { data } = await api.get('/auth/me');
      setUser(data);

      // Extract teams from memberships
      const userTeams = data.memberships?.map(m => ({
        id: m.team_id,
        name: m.team?.name || 'Team',
        role: m.role,
      })) || [];
      setTeams(userTeams);

      // Set active team (first one, or from localStorage)
      const savedTeam = localStorage.getItem('ca_active_team');
      if (savedTeam && userTeams.find(t => t.id === savedTeam)) {
        setActiveTeamId(savedTeam);
      } else if (userTeams.length > 0) {
        setActiveTeamId(userTeams[0].id);
      }
    } catch {
      setUser(null);
      setTeams([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const switchTeam = (teamId) => {
    setActiveTeamId(teamId);
    localStorage.setItem('ca_active_team', teamId);
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setUser(null);
    setTeams([]);
    setActiveTeamId(null);
  };

  return (
    <AuthContext.Provider value={{
      user,
      teams,
      activeTeamId,
      switchTeam,
      loading,
      logout,
      refreshUser: fetchUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}