import { useEffect, useState } from 'react';
import { Info, Sparkles } from 'lucide-react';
import { label } from '../services/api';

export default function AIReview({ analysis, photoUrl, questions, onAnalyze, onFeedback, disabled, locked, dirty, consent, setConsent }) {
  const [decisions, setDecisions] = useState({});
  useEffect(() => setDecisions({}), [analysis?.id]);
  const result = analysis?.result;
  const stale = dirty || analysis?.is_stale;
  const canDecide = analysis?.can_decide && !stale && !locked;
  const suggestions = result?.suggestions || [];
  const ready = suggestions.length > 0 && suggestions.every(item => decisions[item.field]?.action);
  function decide(field, patch) { setDecisions(current => ({ ...current, [field]: { ...current[field], ...patch } })); }
  return <section className="panel ai-panel">
    <div className="ai-banner"><div><span className="section-kicker">AI SECOND OPINION</span><h2>Does this look right?</h2></div><Sparkles size={20} /></div>
    <div className="ai-visual">{photoUrl ? <img src={photoUrl} alt="Photo for review" /> : <div className="stream-illustration"><div className="sun" /><div className="ridge ridge-back" /><div className="ridge ridge-front" /><div className="water-line" /></div>}<div className="confidence-badge">{result ? (result.is_mock ? 'SIMULATED · no image inference' : 'AI photo analysis') : photoUrl ? 'Photo not yet analyzed' : 'Illustration · upload a photo'}</div></div>
    {!locked && <><label className="consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} disabled={disabled} />Allow this photo to be sent to the configured AI provider for a second opinion.</label><button className="primary-button" disabled={disabled || !consent || (analysis?.can_decide && !stale)} onClick={onAnalyze}>{analysis ? 'Analyze again' : 'Analyze photo'}</button></>}
    {analysis?.status === 'failed' && <p className="error-message" role="alert">{analysis.error_message}. Your draft is still saved; you can submit it for expert review.</p>}
    {analysis?.status === 'running' && <p role="status">Analysis is running. Reopen this draft shortly to refresh its result.</p>}
    {stale && analysis && <p className="notice">Your observation changed since this analysis. Save and analyze again for current suggestions.</p>}
    {result && <div className="ai-results"><p className="muted">{result.model_name} · {result.model_version}</p>{result.limitations.map((item, i) => <p className="notice" key={i}>{item}</p>)}
      {!result.image_usable && <p>No usable stream evidence was found. Try another photo or submit for expert review.</p>}
      {suggestions.map(item => <div className="suggestion" key={item.field}><div className="suggestion-title"><strong>{label(item.field)}: {label(item.value)}</strong>{item.confidence != null && <span>{Math.round(item.confidence * 100)}% model estimate</span>}</div><p>{item.explanation}</p>
        {item.evidence_region && photoUrl && !stale && <div className="region-view"><img src={photoUrl} alt={`Evidence for ${label(item.field)}`} /><span style={{ left: `${item.evidence_region.x * 100}%`, top: `${item.evidence_region.y * 100}%`, width: `${item.evidence_region.width * 100}%`, height: `${item.evidence_region.height * 100}%` }} /></div>}
        {canDecide && <><div className="review-actions">{['accept', 'edit', 'reject'].map(action => <button disabled={disabled} key={action} className={`review-button ${action} ${decisions[item.field]?.action === action ? 'selected' : ''}`} aria-pressed={decisions[item.field]?.action === action} onClick={() => decide(item.field, { action, value: item.value })}>{label(action)}</button>)}</div>
          {decisions[item.field]?.action === 'edit' && <label className="input-label">Your {label(item.field)}<select disabled={disabled} value={decisions[item.field].value} onChange={e => decide(item.field, { value: e.target.value })}>{questions.find(q => q.field === item.field)?.options.map(o => <option value={o.value} key={o.value}>{o.label}</option>)}</select></label>}</>}
      </div>)}
      {canDecide && <button className="primary-button" disabled={disabled || !ready} onClick={() => onFeedback(suggestions.map(item => { const decision = decisions[item.field]; return { field: item.field, action: decision.action, ...(decision.action === 'edit' ? { value: decision.value } : {}) }; }))}>Save AI decisions</button>}
      {analysis.feedback && <p className="success-toast">Your decisions have been saved.</p>}
    </div>}
    <div className="ai-footnote"><Info size={15} />AI suggestions only change your report after your decision. Confidence estimates are not calibrated safety scores.</div>
  </section>;
}
