import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Eye, FileCheck2, FlaskConical, LogOut, MapPin, Menu, ShieldCheck, Waves } from 'lucide-react';
import Auth from './components/Auth';
import ObservationForm from './components/ObservationForm';
import AIReview from './components/AIReview';
import Insights, { TrustScore } from './components/Insights';
import ReviewerPanel from './components/ReviewerPanel';
import { allSites, hasSession, label, observationPayload, photoPath, reportPath, request, setToken } from './services/api';
import './styles.css';

const fields = ['clarity', 'smell', 'flow', 'foam', 'visible_life', 'water_color'];
function localTime(value = new Date()) { const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
function newForm() { return { ...Object.fromEntries(fields.map(key => [key, null])), notes: '', ph: '', observed_at: localTime() }; }

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(hasSession());
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState('');
  const [synthetic, setSynthetic] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [form, setForm] = useState(newForm);
  const [report, setReport] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [photoFile, setPhotoFile] = useState(null);
  const [photoUrl, setPhotoUrl] = useState('');
  const [consent, setConsent] = useState(false);
  const [reports, setReports] = useState({ items: [], total: 0 });
  const [queue, setQueue] = useState(null);
  const [card, setCard] = useState(null);
  const [needs, setNeeds] = useState(null);
  const [insightError, setInsightError] = useState('');
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [menu, setMenu] = useState(false);
  const actionLock = useRef(false);
  const analysisRequest = useRef(null);
  const reviewRequest = useRef(null);
  const site = sites.find(item => item.id === siteId);
  const locked = report?.status === 'submitted';
  const imageId = report?.photos.find(p => p.id === analysis?.evidence_photo_id)?.id || report?.photos.at(-1)?.id;

  function reset() { setForm(newForm()); setReport(null); setAnalysis(null); setAssessment(null); setPhotoFile(null); setDirty(false); setConsent(false); setError(''); setNotice(''); analysisRequest.current = null; reviewRequest.current = null; }
  function expire() { setToken(''); setUser(null); setSites([]); setSiteId(''); setReports({ items: [], total: 0 }); setQueue(null); setCard(null); setNeeds(null); reset(); }
  useEffect(() => {
    const controller = new AbortController();
    if (hasSession()) request('/users/me', { signal: controller.signal }).then(setUser).catch(err => { if (err.name !== 'AbortError') { setToken(''); setError(err.message); } }).finally(() => setBooting(false));
    window.addEventListener('session-expired', expire);
    return () => { controller.abort(); window.removeEventListener('session-expired', expire); };
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    Promise.all([allSites(), request('/questionnaire'), request('/reports?limit=20')]).then(([available, questionnaire, mine]) => {
      if (!active) return;
      setSites(available); setQuestions(questionnaire.questions); setReports(mine);
      if (available.length) { setSiteId(available[0].id); setSynthetic(available[0].is_demo); }
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    setCard(null); setNeeds(null); setInsightError(''); setQueue(null);
    if (!user || !siteId) return;
    const controller = new AbortController();
    const query = `?synthetic=${synthetic}`;
    Promise.all([request(`/sites/${siteId}/diagnosis${query}`, { signal: controller.signal }), request(`/sites/${siteId}/monitoring-needs${query}`, { signal: controller.signal })]).then(([nextCard, nextNeeds]) => { setCard(nextCard); setNeeds(nextNeeds); }).catch(err => { if (err.name !== 'AbortError') setInsightError(err.message); });
    if (user.role === 'reviewer') request(`/reviews${query}&limit=100&include_optional=true`, { signal: controller.signal }).then(setQueue).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [user, siteId, synthetic, revision]);

  useEffect(() => {
    const controller = new AbortController();
    let url = '';
    setPhotoUrl('');
    if (photoFile) { url = URL.createObjectURL(photoFile); setPhotoUrl(url); }
    else if (imageId && report?.id) request(photoPath(report.id, imageId), { blob: true, signal: controller.signal }).then(blob => {
      if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setPhotoUrl(url); }
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [photoFile, imageId, report?.id]);

  async function perform(name, task) {
    if (actionLock.current) return;
    actionLock.current = true; setBusy(name); setError(''); setNotice('');
    try { await task(); } catch (err) { setError(err.message || 'Something went wrong. Your saved data is still available.'); }
    finally { actionLock.current = false; setBusy(''); }
  }
  async function refreshReports() { setReports(await request('/reports?limit=20')); }
  function applyReport(item) {
    setReport(item); setSiteId(item.site_id); setSynthetic(item.is_synthetic);
    setForm({ ...Object.fromEntries(fields.map(key => [key, item[key]])), notes: item.notes, ph: item.ph ?? '', observed_at: localTime(item.observed_at) });
    setDirty(false); setPhotoFile(null);
  }
  async function openReport(id) {
    const item = await request(reportPath(id));
    applyReport(item); setAnalysis(null); setAssessment(null); setConsent(false);
    analysisRequest.current = null; reviewRequest.current = null;
    if (item.latest_analysis_id) setAnalysis(await request(`${reportPath(id)}/analyses/${item.latest_analysis_id}`));
    if (item.status === 'submitted') {
      try { setAssessment(await request(`${reportPath(id)}/assessment`)); }
      catch (err) { if (err.status !== 404) throw err; }
    }
    document.getElementById('checkup')?.scrollIntoView({ behavior: 'smooth' });
  }
  async function persistDraft() {
    if (!siteId) throw new Error('Select a stream site first.');
    if (!form.observed_at || Number.isNaN(new Date(form.observed_at).valueOf())) throw new Error('Choose a valid observation time.');
    if (locked) return report;
    const payload = { ...observationPayload(form), is_synthetic: synthetic };
    let saved = report;
    if (!saved) saved = await request('/reports', { method: 'POST', body: { ...payload, site_id: siteId } });
    else if (dirty) saved = await request(reportPath(saved.id), { method: 'PATCH', body: payload });
    setReport(saved); setDirty(false);
    if (photoFile) {
      const data = new FormData(); data.append('file', photoFile); data.append('source', synthetic ? 'synthetic' : 'own');
      try { await request(`${reportPath(saved.id)}/photos`, { method: 'POST', body: data }); }
      catch (err) { if (err.status !== 409 || !/already|duplicate/i.test(err.message)) throw err; }
      setPhotoFile(null);
      saved = await request(reportPath(saved.id)); setReport(saved);
    }
    return saved;
  }
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); setDirty(true); }
  function choosePhoto(event) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) { setError('Choose a photo smaller than 8 MB.'); return; }
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setError('Choose a PNG, JPEG, or WebP image.'); return; }
    setPhotoFile(file); setConsent(false); setDirty(true); setError('');
  }
  async function analyze() {
    if (!consent) throw new Error('Allow photo analysis first.');
    const saved = await persistDraft();
    const photo = saved.photos.at(-1);
    if (!photo) throw new Error('Attach a photo before requesting analysis.');
    const key = `${saved.id}:${photo.id}:${saved.version}`;
    if (analysisRequest.current?.key !== key) analysisRequest.current = { key, id: crypto.randomUUID() };
    const result = await request(`${reportPath(saved.id)}/analysis`, { method: 'POST', body: { photo_id: photo.id, request_id: analysisRequest.current.id } });
    analysisRequest.current = null; setAnalysis(result);
    applyReport(await request(reportPath(saved.id)));
    await refreshReports();
  }
  async function feedback(decisions) {
    const result = await request(`${reportPath(report.id)}/analyses/${analysis.id}/feedback`, { method: 'POST', body: { decisions } });
    setAnalysis(result); applyReport(await request(reportPath(report.id))); setNotice('Your AI decisions are saved.');
  }
  async function submit() {
    if (fields.some(field => !form[field])) throw new Error('Answer every observation question. Choose “Unknown” when you are unsure.');
    const saved = await persistDraft();
    const submitted = await request(`${reportPath(saved.id)}/submit`, { method: 'POST' });
    applyReport(submitted); setAssessment(await request(`${reportPath(saved.id)}/assessment`));
    if (submitted.latest_analysis_id) setAnalysis(await request(`${reportPath(saved.id)}/analyses/${submitted.latest_analysis_id}`));
    await refreshReports(); setRevision(value => value + 1); setNotice('Check-up submitted. Its trust assessment is ready.');
  }
  async function decide(decision, reason) {
    const payload = { assessment_id: assessment.id, decision, reason };
    const key = JSON.stringify({ report_id: report.id, ...payload });
    if (reviewRequest.current?.key !== key) reviewRequest.current = { key, id: crypto.randomUUID() };
    await request(`${reportPath(report.id)}/reviews`, { method: 'POST', body: { ...payload, request_id: reviewRequest.current.id } });
    reviewRequest.current = null;
    setAssessment(await request(`${reportPath(report.id)}/assessment`)); setRevision(value => value + 1); setNotice(`Report ${decision}.`);
  }
  async function downloadFHIR() {
    const blob = await request(`${reportPath(report.id)}/fhir`, { blob: true });
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'streamdoctor-synthetic-fhir.json'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function createSite(event) {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget));
    await perform('Creating site…', async () => {
      const created = await request('/sites', { method: 'POST', body: { name: data.name, latitude: Number(data.latitude), longitude: Number(data.longitude), is_demo: data.is_demo === 'on' } });
      setSites(await allSites()); reset(); setSiteId(created.id); setSynthetic(created.is_demo); setNotice('Stream site created.');
    });
  }

  if (booting) return <main className="auth-page"><p role="status">Restoring your session…</p></main>;
  if (!user) return <Auth onLogin={setUser} />;
  return <div className="app-shell">
    <aside className={`sidebar ${menu ? 'mobile-open' : ''}`}><div className="brand"><span className="brand-mark"><Waves size={21} /></span><span>StreamDoctor</span></div>
      <label className="site-picker"><MapPin size={15} /><select aria-label="Stream site" value={siteId} disabled={Boolean(busy)} onChange={event => { reset(); setSiteId(event.target.value); setSynthetic(sites.find(s => s.id === event.target.value)?.is_demo || false); }}><option value="" disabled>Select a stream</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <nav className="nav-list" aria-label="Main navigation"><button className="nav-item active" disabled={Boolean(busy)} onClick={() => { reset(); setMenu(false); document.getElementById('checkup')?.scrollIntoView(); }}><FlaskConical size={18} />New check-up</button><a className="nav-item" href="#overview" onClick={() => setMenu(false)}><Eye size={18} />Stream overview</a><a className="nav-item" href="#reports" onClick={() => setMenu(false)}><FileCheck2 size={18} />My reports <span className="nav-count">{reports.total}</span></a>{user.role === 'reviewer' && <a className="nav-item" href="#review" onClick={() => setMenu(false)}><ShieldCheck size={18} />Expert review</a>}</nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={18} /><div><strong>Your data matters</strong><span>Explainable evidence helps protect local water.</span></div></div><div className="profile"><div className="avatar">{user.display_name.slice(0, 2).toUpperCase()}</div><div><strong>{user.display_name}</strong><span>{label(user.role)}</span></div><button className="icon-button" aria-label="Sign out" disabled={Boolean(busy)} onClick={() => perform('Signing out…', async () => { try { await request('/auth/logout', { method: 'POST' }); } finally { expire(); } })}><LogOut size={16} /></button></div></div>
    </aside>
    <main className="main-content"><header className="topbar"><button className="mobile-menu" aria-label="Toggle navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}><Menu size={21} /></button><div className="crumbs"><span>Check-up</span><span>/</span><strong>{site?.name || 'Select a stream'}</strong></div><span className="sync-status" role="status">{busy || (dirty || photoFile ? 'Unsaved changes' : report ? `Saved · ${report.status}` : 'New observation')}</span></header>
      <div className="page-wrap"><section className="hero-row"><div><p className="eyebrow">FIELD CHECK · {new Date().toLocaleDateString()}</p><h1>How is your stream feeling today?</h1><p className="hero-copy">Observe from the bank. Share what you see, and what you’re unsure about.</p></div></section>
        <label className="cohort-control"><input type="checkbox" checked={synthetic} disabled={Boolean(busy) || Boolean(report) || Boolean(site?.is_demo)} onChange={event => { setSynthetic(event.target.checked); setDirty(true); }} />Synthetic / demonstration data {site?.is_demo && <span>· Required for this fictional site</span>}</label>
        {error && <div className="error-message" role="alert">{error}</div>}{notice && <div className="success-toast" role="status">{notice}</div>}
        {!sites.length && <p className="notice">No stream sites yet. A reviewer can create one below, or run the local demo setup.</p>}
        {siteId && <><div className="dashboard-grid"><ObservationForm questions={questions} form={form} update={update} photos={report?.photos || []} photoUrl={photoUrl} onPhoto={choosePhoto} onNew={reset} disabled={Boolean(busy)} locked={locked} onRemove={id => perform('Removing photo…', async () => { await request(`${reportPath(report.id)}/photos/${id}`, { method: 'DELETE' }); setReport(await request(reportPath(report.id))); setAnalysis(null); })} /><AIReview analysis={analysis} photoUrl={photoUrl} questions={questions} onAnalyze={() => perform('Analyzing photo…', analyze)} onFeedback={decisions => perform('Saving decisions…', () => feedback(decisions))} disabled={Boolean(busy)} locked={locked} dirty={dirty || Boolean(photoFile)} consent={consent} setConsent={setConsent} /></div>
          <div className="submit-row"><div><ShieldCheck size={19} /><span>{locked ? 'Submitted report preserved.' : 'Your observations are saved on the server when you save or submit.'}</span></div><div className="submit-actions">{!locked && <><button className="option" disabled={Boolean(busy)} onClick={() => perform('Saving draft…', async () => { await persistDraft(); await refreshReports(); setNotice('Draft saved.'); })}>Save draft</button><button className="primary-button" disabled={Boolean(busy)} onClick={() => perform('Submitting…', submit)}>Submit check-up<ArrowRight size={17} /></button></>}{locked && <button className="option" disabled={Boolean(busy)} onClick={reset}>New check-up</button>}{assessment?.expert_verified && report?.is_synthetic && <button className="option" disabled={Boolean(busy)} onClick={() => perform('Exporting…', downloadFHIR)}>Download FHIR</button>}</div></div>
          <TrustScore assessment={assessment} /><Insights card={card} needs={needs} error={insightError} />
        </>}
        <section className="panel reports-panel" id="reports"><div className="panel-heading"><h2>My reports</h2><button className="option" disabled={Boolean(busy)} onClick={() => perform('Refreshing…', refreshReports)}>Refresh</button></div>{!reports.items.length && <p className="muted">Your saved drafts and submitted check-ups will appear here.</p>}<ul className="report-list">{reports.items.map(item => <li key={item.id}><div><strong>{sites.find(s => s.id === item.site_id)?.name || 'Stream observation'}</strong><small>{new Date(item.observed_at).toLocaleString()} · {item.status}{item.is_synthetic ? ' · Synthetic' : ''}</small></div><button className="option" disabled={Boolean(busy)} onClick={() => perform('Opening report…', () => openReport(item.id))}>{item.status === 'draft' ? 'Resume draft' : 'View report'}</button></li>)}</ul>{reports.items.length < reports.total && <button className="option" disabled={Boolean(busy)} onClick={() => perform('Loading reports…', async () => { const next = await request(`/reports?limit=20&offset=${reports.items.length}`); setReports(current => ({ ...next, items: [...current.items, ...next.items] })); })}>Load more</button>}</section>
        {user.role === 'reviewer' && <><ReviewerPanel queue={queue} report={report} user={user} assessment={assessment} onOpen={id => perform('Opening evidence…', () => openReport(id))} onDecide={(decision, reason) => perform('Saving review…', () => decide(decision, reason))} onReload={() => setRevision(v => v + 1)} disabled={Boolean(busy)} onStorm={value => perform('Recording storm…', async () => { if (!siteId) throw new Error('Choose a site first.'); await request(`/sites/${siteId}/monitoring-events`, { method: 'POST', body: { kind: 'storm', occurred_at: new Date(value).toISOString(), is_synthetic: synthetic, request_id: crypto.randomUUID() } }); setRevision(v => v + 1); setNotice('Storm recorded.'); })} />
          <details className="panel site-form"><summary>Create a stream site</summary><form onSubmit={createSite}><label className="input-label">Site name<input name="name" required maxLength={120} /></label><div className="question-pair"><label className="input-label">Latitude<input name="latitude" type="number" min="-90" max="90" step="any" required /></label><label className="input-label">Longitude<input name="longitude" type="number" min="-180" max="180" step="any" required /></label></div><label className="consent"><input type="checkbox" name="is_demo" />Fictional demo site</label><button className="primary-button" disabled={Boolean(busy)}>Create site</button></form></details></>}
      </div>
    </main>
  </div>;
}
