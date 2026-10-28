import React, { createContext, useContext, useEffect, useState } from 'react';
import client, { setCsrfToken } from '../api/client';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function LoginForm({ onLogin, error, busy }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  return <main className="login-screen">
    <form className="login-card" onSubmit={event => { event.preventDefault(); onLogin(username, password); }}>
      <h1>SafeGuard sign in</h1>
      <p>Use the admin account configured for this installation.</p>
      <label htmlFor="login-user">Username</label>
      <input id="login-user" autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} />
      <label htmlFor="login-password">Password</label>
      <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
      {error && <p role="alert">{error}</p>}
      <button disabled={busy} type="submit">{busy ? 'Signing in...' : 'Sign in'}</button>
    </form>
  </main>;
}

export default function AuthGate({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const accept = data => { setUser(data.authenticated ? data : null); setCsrfToken(data.csrf_token); };
  const check = async (signal) => {
    setChecking(true); setError(null);
    try {
      const { data } = await client.get('/auth/session', { signal });
      if (!signal?.aborted) accept(data);
    }
    catch { if (!signal?.aborted) setError('Backend unavailable. Start the backend and retry.'); }
    finally { if (!signal?.aborted) setChecking(false); }
  };
  useEffect(() => {
    const controller = new AbortController();
    check(controller.signal);
    const expired = () => { accept({ authenticated: false }); setError('Your session expired. Sign in again.'); };
    window.addEventListener('safeguard-session-expired', expired);
    return () => { controller.abort(); window.removeEventListener('safeguard-session-expired', expired); };
  }, []);
  const login = async (username, password) => {
    setBusy(true); setError(null);
    try { accept((await client.post('/auth/login', { username, password })).data); }
    catch (err) { const detail = err.response?.data?.detail; setError(typeof detail === 'string' ? detail : 'Sign in failed. Check your details and backend connection.'); }
    finally { setBusy(false); }
  };
  const logout = async () => { await client.post('/auth/logout'); accept({ authenticated: false }); };
  if (checking) return <main className="login-screen"><p role="status">Checking your session...</p></main>;
  if (!user) return <><LoginForm onLogin={login} error={error} busy={busy} />{error?.startsWith('Backend') && <button className="login-retry" onClick={() => check()}>Retry connection</button>}</>;
  return <AuthContext.Provider value={{ user, logout }}>{children}</AuthContext.Provider>;
}
