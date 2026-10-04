import { useState } from 'react';
import { label } from '../services/api';

export default function ReviewerPanel({ queue, report, user, assessment, onOpen, onDecide, onReload, disabled, onStorm }) {
  const [reason, setReason] = useState('');
  const [stormAt, setStormAt] = useState('');
  const canReview = report?.status === 'submitted' && report.contributor_id !== user.id && assessment?.review_status === 'pending';
  return <section className="panel review-panel" id="review"><div className="panel-heading"><div><span className="section-kicker">EXPERT WORKSPACE</span><h2>Review queue</h2></div><button disabled={disabled} className="option" onClick={onReload}>Refresh</button></div>
    {!queue?.items.length && <p className="muted">No reports waiting in this cohort.</p>}
    <ul className="report-list">{queue?.items.map(item => <li key={item.report_id}><div><strong>{item.is_synthetic ? 'Synthetic report' : 'Field report'}</strong><small>Trust {Math.round(item.score)}/100 · {label(item.status)}</small></div><button disabled={disabled} className="option" onClick={() => { setReason(''); onOpen(item.report_id); }}>Inspect report</button></li>)}</ul>
    {queue && queue.total > queue.items.length && <p>Showing {queue.items.length} of {queue.total}; completed decisions reveal the next reports.</p>}
    {canReview && <div className="decision-form"><h3>Decision on the open report</h3><p>Review the observations, photo, and score reasons above before deciding.</p><label className="input-label">Review reason<textarea value={reason} minLength={10} maxLength={3000} onChange={e => setReason(e.target.value)} disabled={disabled} /></label><div className="review-actions">{['approved', 'rejected'].map(decision => <button key={decision} className={`review-button ${decision === 'approved' ? 'accept' : 'reject'}`} disabled={disabled || reason.trim().length < 10} onClick={() => onDecide(decision, reason.trim())}>{decision === 'approved' ? 'Approve report' : 'Reject report'}</button>)}</div></div>}
    <form className="storm-form" onSubmit={e => { e.preventDefault(); onStorm(stormAt); }}><h3>Record a storm at the selected site</h3><label className="input-label">When did it occur?<input required type="datetime-local" value={stormAt} onChange={e => setStormAt(e.target.value)} disabled={disabled} /></label><button className="option" disabled={disabled || !stormAt}>Record event</button></form>
  </section>;
}
