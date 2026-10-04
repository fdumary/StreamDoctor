import { useState } from 'react';
import { Waves } from 'lucide-react';
import { request, setToken } from '../services/api';

export default function Auth({ onLogin }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (register) await request('/auth/register', { method: 'POST', body: data });
      const session = await request('/auth/login', { method: 'POST', body: { email: data.email, password: data.password } });
      setToken(session.access_token);
      onLogin(await request('/users/me'));
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function skipLogin() {
    setBusy(true); setError('');
    try {
      const session = await request('/auth/guest', { method: 'POST' });
      setToken(session.access_token);
      onLogin(await request('/users/me'));
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="panel auth-card">
    <div className="brand"><span className="brand-mark"><Waves size={21} /></span>StreamDoctor</div>
    <p className="eyebrow">OBSERVE · REVIEW · UNDERSTAND</p>
    <h1>{register ? 'Join your stream’s story.' : 'Welcome back.'}</h1>
    <p>Record what you see, review a second opinion, and help build a clearer picture of your stream.</p>
    <form onSubmit={submit}>
      {register && <label>Display name<input name="display_name" required maxLength={100} autoComplete="name" /></label>}
      <label>Email<input type="email" name="email" required autoComplete="email" /></label>
      <label>Password<input type="password" name="password" required minLength={12} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'} /></label>
      {error && <p className="error-message" role="alert">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? 'Connecting…' : register ? 'Create account' : 'Sign in'}</button>
    </form>
    <button className="text-button" disabled={busy} onClick={() => { setRegister(!register); setError(''); }}>{register ? 'Already have an account? Sign in' : 'New here? Create an account'}</button>
    <button className="text-button" disabled={busy} onClick={skipLogin}>Skip login</button>
  </div></main>;
}
