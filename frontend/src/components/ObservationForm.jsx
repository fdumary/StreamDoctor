import { Camera, CircleHelp, Droplets, RotateCcw } from 'lucide-react';

export default function ObservationForm({ questions, form, update, photoUrl, photos, onPhoto, onRemove, onNew, disabled, locked }) {
  return <section className="panel checkup-panel" id="checkup">
    <div className="panel-heading"><div><span className="section-kicker">YOUR OBSERVATION</span><h2>What are you noticing?</h2></div><button className="icon-button" onClick={onNew} disabled={disabled} aria-label="New check-up"><RotateCcw size={17} /></button></div>
    <fieldset disabled={disabled || locked} className="plain-fieldset">
      <label className="input-label">Observation time<input type="datetime-local" value={form.observed_at} onChange={e => update('observed_at', e.target.value)} required /></label>
      <div className="question-list">{questions.map(question => <div className="question" key={question.field}>
        <div className="question-label"><span className="question-icon"><Droplets size={18} /></span><strong>{question.question}</strong></div>
        <details className="question-explanation"><summary><CircleHelp size={13} />What does this mean?</summary><p>{question.help}</p></details>
        <div className="option-row">{question.options.map(option => <button type="button" key={option.value} aria-pressed={form[question.field] === option.value} className={form[question.field] === option.value ? 'option selected' : 'option'} onClick={() => update(question.field, option.value)}>{option.label}</button>)}</div>
      </div>)}</div>
      <label className="input-label">Measured pH <span>Optional; do not estimate from appearance</span><input type="number" min="0" max="14" step="0.1" value={form.ph ?? ''} onChange={e => update('ph', e.target.value)} /></label>
      <label className="input-label">Notes<textarea value={form.notes} maxLength={5000} onChange={e => update('notes', e.target.value)} rows={3} /></label>
      <div className="photo-upload"><div className="photo-copy"><span className="upload-icon"><Camera size={18} /></span><div><strong>Stream photo</strong><small>Required to submit. PNG, JPEG, or WebP, up to 8 MB.</small></div></div>
        <label className="upload-button">{photos.length ? 'Add photo' : 'Choose photo'}<input disabled={disabled || locked || photos.length >= 5} type="file" accept="image/png,image/jpeg,image/webp" onChange={onPhoto} /></label>
        {photoUrl && <img className="photo-thumb" src={photoUrl} alt="Selected observation" />}
      </div>
      {photos.length > 0 && <div className="attached-photos">{photos.map((photo, i) => <span key={photo.id}>Photo {i + 1}<button className="text-button" type="button" onClick={() => onRemove(photo.id)}>Remove</button></span>)}</div>}
    </fieldset>
    {locked && <p className="muted">Submitted observations are preserved. Start a new check-up to record a change.</p>}
  </section>;
}
