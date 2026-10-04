import { useMemo, useState } from 'react';
import {
	AlertTriangle,
	ArrowRight,
	Camera,
	Check,
	ChevronDown,
	CircleHelp,
	CloudRain,
	Droplets,
	Eye,
	FileCheck2,
	FlaskConical,
	Info,
	Leaf,
	MapPin,
	Menu,
	RotateCcw,
	ShieldCheck,
	Sparkles,
	Waves,
	X,
} from 'lucide-react';
import './styles.css';

const initialSymptoms = { clarity: 'cloudy', smell: 'earthy', foam: 'some', flow: 'normal', wildlife: 'fewer' };
const symptomOptions = {
	clarity: [['clear', 'Clear'], ['cloudy', 'Cloudy'], ['brown', 'Brown / murky']],
	smell: [['none', 'No unusual smell'], ['earthy', 'Earthy'], ['sewage', 'Sewage / chemical']],
	foam: [['none', 'None'], ['some', 'Some patches'], ['lots', 'Lots of foam']],
	flow: [['low', 'Lower than usual'], ['normal', 'About normal'], ['high', 'Fast / high']],
	wildlife: [['many', 'Lots of life'], ['usual', 'About usual'], ['fewer', 'Fewer than usual']],
};

function App() {
	const [symptoms, setSymptoms] = useState(initialSymptoms);
	const [photo, setPhoto] = useState(null);
	const [aiStatus, setAiStatus] = useState('pending');
	const [trustLens, setTrustLens] = useState(true);
	const [audience, setAudience] = useState('citizens');
	const [submitted, setSubmitted] = useState(false);
	const riskSignals = useMemo(() => [symptoms.clarity === 'brown', symptoms.smell === 'sewage', symptoms.foam === 'lots', symptoms.wildlife === 'fewer'].filter(Boolean).length, [symptoms]);
	const trustScore = aiStatus === 'rejected' ? 48 : Math.max(64, 94 - riskSignals * 6 - (aiStatus === 'pending' ? 4 : 0));
	const health = trustLens ? (riskSignals > 1 ? 'yellow' : 'green') : 'yellow';
	function updateSymptom(key, value) { setSymptoms((current) => ({ ...current, [key]: value })); setSubmitted(false); }
	function handlePhoto(event) { const file = event.target.files?.[0]; if (file) { setPhoto(URL.createObjectURL(file)); setAiStatus('pending'); setSubmitted(false); } }
	function resetCheckup() { setSymptoms(initialSymptoms); setPhoto(null); setAiStatus('pending'); setTrustLens(true); setSubmitted(false); }

	return (
		<div className="app-shell">
			<aside className="sidebar">
				<div className="brand"><span className="brand-mark"><Waves size={21} /></span><span>StreamDoctor</span></div>
				<div className="location-chip"><MapPin size={15} /><span>Riverside County</span><ChevronDown size={14} /></div>
				<nav className="nav-list" aria-label="Main navigation"><a className="nav-item active" href="#checkup"><FlaskConical size={18} />New check-up</a><a className="nav-item" href="#overview"><Eye size={18} />Stream overview</a><a className="nav-item" href="#reports"><FileCheck2 size={18} />My reports <span className="nav-count">12</span></a></nav>
				<div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={18} /><div><strong>Your data matters</strong><span>Verified reports help protect local water.</span></div></div><div className="profile"><div className="avatar">JM</div><div><strong>Jordan Miller</strong><span>Volunteer observer</span></div><ChevronDown size={15} /></div></div>
			</aside>
			<main className="main-content">
				<header className="topbar"><button className="mobile-menu" aria-label="Open menu"><Menu size={21} /></button><div className="crumbs"><span>New check-up</span><span>/</span><strong>Mill Creek</strong></div><div className="top-actions"><span className="sync-status"><span className="status-dot" />Saved locally</span><button className="help-button" aria-label="Help"><CircleHelp size={20} /></button></div></header>
				<div className="page-wrap">
					<section className="hero-row"><div><p className="eyebrow">FIELD CHECK · OCTOBER 4, 2026</p><h1>How is Mill Creek feeling today?</h1><p className="hero-copy">A quick check helps build a clearer picture of the water we share.</p></div><div className="hero-weather"><CloudRain size={23} /><div><strong>After rain</strong><span>Last 24 hours</span></div></div></section>
					<div className="workflow" id="checkup"><div className="step active"><span>1</span><div><strong>Observe</strong><small>Tell us what you see</small></div></div><div className="step-line" /><div className={`step ${aiStatus !== 'pending' ? 'active' : ''}`}><span>2</span><div><strong>Review</strong><small>Check the AI's second opinion</small></div></div><div className="step-line" /><div className={`step ${submitted ? 'active' : ''}`}><span>3</span><div><strong>Diagnose</strong><small>See the stream's health</small></div></div></div>
					<div className="dashboard-grid">
						<section className="panel checkup-panel"><div className="panel-heading"><div><span className="section-kicker">STEP 1 · YOUR OBSERVATION</span><h2>What are you noticing?</h2></div><button className="icon-button" onClick={resetCheckup} aria-label="Reset check-up"><RotateCcw size={17} /></button></div><div className="question-list"><Question icon={<Droplets size={18} />} label="Water clarity" hint="Look through the water, not at the reflection." value={symptoms.clarity} options={symptomOptions.clarity} onChange={(value) => updateSymptom('clarity', value)} /><Question icon={<Sparkles size={18} />} label="Unusual smell" hint="A healthy stream can smell earthy after rain." value={symptoms.smell} options={symptomOptions.smell} onChange={(value) => updateSymptom('smell', value)} /><Question icon={<Waves size={18} />} label="Foam or surface film" hint="Small bubbles from rain are normal." value={symptoms.foam} options={symptomOptions.foam} onChange={(value) => updateSymptom('foam', value)} /><div className="question-pair"><Question icon={<ArrowRight size={18} />} label="Water flow" value={symptoms.flow} options={symptomOptions.flow} onChange={(value) => updateSymptom('flow', value)} /><Question icon={<Leaf size={18} />} label="Visible life" value={symptoms.wildlife} options={symptomOptions.wildlife} onChange={(value) => updateSymptom('wildlife', value)} /></div></div><div className="photo-upload"><div className="photo-copy"><span className="upload-icon"><Camera size={18} /></span><div><strong>Add a photo <span>Optional</span></strong><small>A photo lets the AI offer a second opinion.</small></div></div><label className="upload-button">{photo ? 'Change photo' : 'Choose photo'}<input type="file" accept="image/*" onChange={handlePhoto} /></label>{photo && <img className="photo-thumb" src={photo} alt="Your stream observation" />}</div></section>
						<section className="panel ai-panel"><div className="ai-banner"><span className="ai-spark"><Sparkles size={17} /></span><div><span className="section-kicker">STEP 2 · AI SECOND OPINION</span><h2>Does this look right?</h2></div><span className="beta-tag">BETA</span></div><div className="ai-visual">{photo ? <img src={photo} alt="Uploaded stream" /> : <div className="stream-illustration"><div className="sun" /><div className="ridge ridge-back" /><div className="ridge ridge-front" /><div className="water-line" /><div className="water-shine" /></div>}<div className="confidence-badge"><span className="mini-dot" />{photo ? 'Photo analyzed' : 'Example view'}</div></div><div className="suggestion"><div className="suggestion-title"><strong>AI sees: moderate turbidity</strong><span>72% confident</span></div><p>The water looks a little cloudy, which can happen after rain. I also notice a small patch of surface foam.</p><div className="highlight-row"><span><span className="highlight teal" />Cloudy water</span><span><span className="highlight gold" />Possible foam</span></div></div><div className="review-actions"><button className={`review-button accept ${aiStatus === 'accepted' ? 'selected' : ''}`} onClick={() => setAiStatus('accepted')}><Check size={16} />Looks right</button><button className={`review-button edit ${aiStatus === 'edited' ? 'selected' : ''}`} onClick={() => setAiStatus('edited')}><FlaskConical size={16} />Edit suggestion</button><button className={`review-button reject ${aiStatus === 'rejected' ? 'selected' : ''}`} onClick={() => setAiStatus('rejected')}><X size={16} />Not right</button></div><div className="ai-footnote"><Info size={15} />You stay in control. AI suggestions never change your report automatically.</div></section>
					</div>
					<section className="trust-strip"><div className="trust-score"><div className="score-ring" style={{ '--score': `${trustScore * 3.6}deg` }}><strong>{trustScore}</strong><span>/100</span></div><div><span className="section-kicker">REPORT TRUST SCORE</span><h3>{aiStatus === 'rejected' ? 'Needs a closer look' : 'Good signal quality'}</h3><p>Based on 4 explainable signals</p></div></div><div className="trust-signals"><Signal label="Photo agreement" value={aiStatus === 'rejected' ? 'Needs review' : 'Strong'} tone={aiStatus === 'rejected' ? 'warn' : 'good'} /><Signal label="Plausibility checks" value="Passed" tone="good" /><Signal label="Nearby reports" value="3 recent" tone="neutral" /><Signal label="Your track record" value="Reliable" tone="good" /></div></section>
					<section className="diagnosis-section" id="overview"><div className="diagnosis-heading"><div><span className="section-kicker">STEP 3 · STREAM DIAGNOSIS</span><h2>Mill Creek health snapshot</h2></div><label className="lens-toggle"><span>Trust Lens</span><button className={trustLens ? 'on' : ''} onClick={() => setTrustLens((value) => !value)} aria-label="Toggle Trust Lens"><span /></button><span className="toggle-state">{trustLens ? 'On' : 'Off'}</span></label></div><div className="lens-note"><ShieldCheck size={16} /><span>{trustLens ? 'Showing trusted observations only' : 'Showing all observations, including reports under review'}</span><button aria-label="About Trust Lens"><CircleHelp size={15} /></button></div><div className="diagnosis-grid"><div className={`health-card ${health}`}><div className="health-top"><span className="traffic-light"><span /></span><span>{health === 'green' ? 'HEALTHY SIGNAL' : 'WATCH CLOSELY'}</span></div><h3>{health === 'green' ? 'Looking good, with a note' : 'A few things need attention'}</h3><p>{health === 'green' ? 'Mill Creek is showing mostly healthy signs today. Recent rain may explain the slight cloudiness.' : 'Cloudiness and fewer visible signs of life are worth watching after the recent rain.'}</p><div className="health-meter"><span style={{ width: health === 'green' ? '68%' : '44%' }} /></div><small>Confidence in this snapshot: {trustLens ? 'high' : 'moderate'}</small></div><AudienceCard audience={audience} setAudience={setAudience} trustLens={trustLens} /></div></section>
					<div className="submit-row" id="reports"><div><ShieldCheck size={19} /><span>Your report will be checked before it joins the stream's story.</span></div><button className="primary-button" onClick={() => setSubmitted(true)}>{submitted ? 'Report saved' : 'Save this check-up'}<ArrowRight size={17} /></button></div>{submitted && <div className="success-toast"><Check size={17} /> Check-up saved. Thank you for looking out for Mill Creek.</div>}
				</div>
			</main>
		</div>
	);
}

function Question({ icon, label, hint, value, options, onChange }) { return <div className="question"><div className="question-label"><span className="question-icon">{icon}</span><div><strong>{label}</strong>{hint && <small>{hint}</small>}</div><button className="question-help" aria-label={`Explain ${label}`}><CircleHelp size={15} /></button></div><div className="option-row">{options.map(([key, text]) => <button key={key} className={value === key ? 'option selected' : 'option'} onClick={() => onChange(key)}>{text}</button>)}</div></div>; }
function Signal({ label, value, tone }) { return <div className="signal"><span className={`signal-dot ${tone}`} /><div><span>{label}</span><strong>{value}</strong></div></div>; }
function AudienceCard({ audience, setAudience, trustLens }) {
	const contentByAudience = {
		citizens: { label: 'For citizens', title: 'A good day for a riverside walk', body: 'The water looks mostly healthy. Keep children and pets out if the water becomes brown or smells unusual.', icon: <Leaf size={18} /> },
		researchers: { label: 'For researchers', title: 'A mild post-rain anomaly', body: 'Turbidity is elevated against nearby observations. This report is a high-quality addition to the current trend.', icon: <FlaskConical size={18} /> },
		planners: { label: 'For planners', title: 'Monitor the upper reach', body: 'Cloudiness is concentrated after rainfall. Compare the upper reach with downstream reports over the next 24 hours.', icon: <MapPin size={18} /> },
	};
	const content = contentByAudience[audience];
	return <div className="audience-card"><div className="audience-tabs">{Object.keys(contentByAudience).map((key) => <button key={key} className={audience === key ? 'selected' : ''} onClick={() => setAudience(key)}>{contentByAudience[key].label.replace('For ', '')}</button>)}</div><div className="audience-content"><span className="audience-icon">{content.icon}</span><div><span className="section-kicker">{content.label.toUpperCase()} · {trustLens ? 'TRUSTED VIEW' : 'ALL DATA'}</span><h3>{content.title}</h3><p>{content.body}</p></div></div></div>;
}
export default App;
