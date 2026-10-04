import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { label } from '../services/api';

export function TrustScore({ assessment }) {
  const names = { ai_photo_agreement: 'Photo agreement', plausibility: 'Plausibility', nearby_agreement: 'Nearby reports', contributor_history: 'Track record' };
  return <section className="trust-strip"><div className="trust-score"><div className="score-ring" style={{ '--score': `${(assessment?.score || 0) * 3.6}deg` }}><strong>{assessment ? Math.round(assessment.score) : '—'}</strong><span>/100</span></div><div><span className="section-kicker">REPORT TRUST SCORE</span><h3>{assessment ? label(assessment.review_status) : 'Available after submission'}</h3><p>{assessment ? `${Math.round(assessment.evidence_coverage * 100)}% evidence coverage` : 'Calculated from saved evidence'}</p></div></div>
    <div className="trust-signals">{Object.entries(names).map(([key, name]) => { const signal = assessment?.components[key]; return <details className="signal" key={key}><summary>{name}<strong>{signal?.available ? `${signal.score}/100` : 'Not enough evidence'}</strong></summary>{signal?.reasons.map((reason, i) => <p key={i}>{reason}</p>)}</details>; })}</div>
    {assessment?.reasons?.length > 0 && <details className="trust-reasons"><summary>Why this score?</summary><ul>{assessment.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul></details>}
  </section>;
}

export default function Insights({ card, needs, error }) {
  const [trustLens, setTrustLens] = useState(true);
  const [audience, setAudience] = useState('citizens');
  const verdict = card && (trustLens ? card.trusted : card.unfiltered);
  const content = card?.audiences[audience];
  return <section className="diagnosis-section" id="overview"><div className="diagnosis-heading"><div><span className="section-kicker">STREAM DIAGNOSIS</span><h2>{card?.site_name || 'Stream'} health snapshot</h2></div><div className="lens-toggle"><span>Trust Lens</span><button type="button" role="switch" aria-checked={trustLens} className={trustLens ? 'on' : ''} onClick={() => setTrustLens(v => !v)} aria-label="Trust Lens"><span /></button><span className="toggle-state">{trustLens ? 'On' : 'Off'}</span></div></div>
    <div className="lens-note"><ShieldCheck size={16} />{trustLens ? 'Trusted observations only' : 'Unfiltered comparison, including reports under review or rejected'}{card?.is_synthetic && <strong> · Synthetic data</strong>}</div>
    {error && <p className="error-message" role="alert">{error}</p>}
    {!card && !error && <p role="status">Loading stream observations…</p>}
    {verdict && <div className="diagnosis-grid"><div className={`health-card ${verdict.status}`}><div className="health-top"><span className="traffic-light"><span /></span>{verdict.status.toUpperCase()}</div><h3>{verdict.label}</h3><p>{verdict.contributing_reports} independent contributing observations. {verdict.excluded_by_trust} excluded by trust, {verdict.excluded_repeats} repeats, {verdict.excluded_incomplete} incomplete.</p><ul className="plain-list">{verdict.indicators.map(i => <li key={i.code}>{i.reason} ({i.reports})</li>)}</ul><small>{verdict.latest_observation_at ? `Latest: ${new Date(verdict.latest_observation_at).toLocaleString()}` : 'No usable observations in this window.'}</small><p className="notice">{verdict.limitations[0]} Green does not establish water safety.</p></div>
      <div className="audience-card"><div className="audience-tabs">{['citizens', 'researchers', 'planners'].map(key => <button key={key} className={audience === key ? 'selected' : ''} onClick={() => setAudience(key)}>{key}</button>)}</div><div className="audience-content"><div><span className="section-kicker">{trustLens ? 'TRUSTED VIEW' : 'INTERPRETATION REMAINS BASED ON TRUSTED DATA'}</span><h3>For {audience}</h3><p>{content?.summary}</p><ul className="plain-list">{content?.actions.map(action => <li key={action}>{action}</li>)}</ul><p>Trusted trend: {label(card.trend.direction)}</p></div></div></div>
    </div>}
    {needs?.needs.length > 0 && <div className="panel monitoring-panel"><h3>Where more observations would help</h3>{needs.needs.map(need => <p key={need.code}><strong>{label(need.code)}:</strong> {need.reason}</p>)}</div>}
  </section>;
}
