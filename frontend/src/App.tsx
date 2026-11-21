import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import './styles.css';

type Moment = { raw: string; value: string | null; precision: 'datetime' | 'date' | 'text'; timezone: string | null };
type FieldEvidence = Record<string, { url: string; quote: string }>;
type RelatedLink = { url: string; label: string; access: 'linked_only'; discovered_on: string };
type Announcement = { url: string; title: string; kind: string; posted_at: string | null; first_seen: string; last_seen: string; access: 'full' | 'search_only'; source_name: string; evidence: string | null; revision_count: number; related_links?: RelatedLink[]; discovery_path?: string[]; discovery_query?: string | null; discovery_queries?: string[]; field_evidence?: FieldEvidence };
type Competition = { id: string; name: string; organizer: string; region: string; format: string; eligibility: string | null; announcement_url: string; announcement_label?: string; registration_url: string | null; registration_status: string; status: string; section: 'upcoming' | 'finished'; start: Moment | null; end: Moment | null; deadline: Moment | null; registration_opens: Moment | null; posted_at: string | null; first_seen: string; last_checked: string; summary: string | null; stage: string; edition: string; notices: string[]; announcements: Announcement[]; field_evidence?: FieldEvidence };
type Source = { id: string; name: string; url: string; kind: string; status: string; last_success: string | null; last_attempt: string | null; message: string; discovered: number; accepted: number };
type Directory = { events: Competition[]; sources: Source[]; generated_at: string };

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    flag: <><path d="M5 21V4"/><path d="M5 4c5-4 9 4 14 0v11c-5 4-9-4-14 0"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></>,
    chevron: <path d="m6 9 6 6 6-6"/>,
    clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/></>,
    pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2m2-15a3 3 0 0 1 0 6m4 9v-2a6 6 0 0 0-3-5"/></>,
    globe: <><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 6.1A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.9 5.9"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></>,
    layers: <><path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/></>,
    link: <><path d="m10 13 4-4m-5 7-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 0 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.info}</svg>;
}
const states: Record<string, string> = { scheduled: 'Upcoming', live: 'Live now', finished: 'Finished', cancelled: 'Cancelled', postponed: 'Postponed', schedule_tba: 'Schedule TBA', end_unconfirmed: 'End unconfirmed' };
const formats: Record<string, string> = { online: 'Online', in_person: 'In person', hybrid: 'Hybrid', unknown: 'Format unconfirmed' };
const registrations: Record<string, string> = { open: 'Registration open', closed: 'Registration closed', not_yet_open: 'Not open yet', unknown: 'Registration unconfirmed' };
const health: Record<string, string> = { ok: 'Working', partial: 'Partial coverage', error: 'Fetch failed', needs_credentials: 'Needs credentials', policy_restricted: 'Policy restricted', not_run: 'Not checked yet' };
const evidenceLabels: Record<string, string> = { name: 'Competition name', organizer: 'Organizer', region: 'Region', format: 'Format', eligibility: 'Who can join', start: 'Competition starts', end: 'Competition ends', deadline: 'Registration deadline', registration_opens: 'Registration opens', registration_url: 'Registration link', registration_state: 'Organizer registration statement', lifecycle: 'Organizer event status', posted_at: 'Announcement posted', summary: 'Summary' };

function Link({ href, children, className = '' }: { href?: string | null; children: ReactNode; className?: string }) {
  let safe: URL | null = null;
  try { const url = new URL(href || ''); if (['https:', 'http:'].includes(url.protocol)) safe = url; } catch { /* unsupported link */ }
  return safe ? <a href={safe.href} target="_blank" rel="noopener noreferrer" className={className}>{children}<span className="sr-only"> (opens in a new tab)</span></a> : <span className={className}>{children} · unavailable</span>;
}
function recorded(value: string | null, time = false): string {
  if (!value) return 'Unknown';
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  if (!dateOnly && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value)) return value;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const showTime = time && !dateOnly;
  return new Intl.DateTimeFormat('en-PH', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'Asia/Manila', ...(showTime ? { hour: 'numeric', minute: '2-digit' } : {}) }).format(d) + (showTime ? ' PHT' : '');
}
function moment(value: Moment | null, fallback = 'Not announced') {
  return value ? value.precision === 'datetime' && value.timezone && value.value ? recorded(value.value, true) : value.raw : fallback;
}
function title(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, c => c.toUpperCase()); }

function DiscoveryTrace({ announcement }: { announcement: Announcement }) {
  const queries = [...new Set([announcement.discovery_query, ...(announcement.discovery_queries || [])].filter((query): query is string => !!query))];
  const path = announcement.discovery_path || [];
  if (!queries.length && !path.length) return null;
  return <details className="discovery-path"><summary>How this announcement was found</summary>
    {queries.map(query => <p key={query}><strong>Search query: </strong><q>{query}</q></p>)}
    {path.map((url, step) => <p key={`${url}-${step}`}><span>{step + 1}. </span><Link href={url}>{url}</Link></p>)}
  </details>;
}

function EventCard({ event }: { event: Competition }) {
  return <article className={`event-card event-${event.status}`}>
    <div className="card-top"><span className={`badge state-${event.status}`}>{states[event.status]}</span><span className="format"><Icon name={event.format === 'online' ? 'globe' : 'pin'} size={16}/>{formats[event.format]}</span></div>
    <h3>{event.name}</h3><p className="organizer">{event.organizer}</p>
    {event.summary && <p className="event-summary">{event.summary}</p>}
    <div className={`registration registration-${event.registration_status}`}><strong>{registrations[event.registration_status]}</strong><dl><div><dt>Registration deadline</dt><dd>{moment(event.deadline)}</dd></div>{event.registration_opens && <div><dt>Registration opens</dt><dd>{moment(event.registration_opens)}</dd></div>}</dl></div>
    <dl className="dates"><div><dt>Competition starts</dt><dd>{moment(event.start, event.status === 'schedule_tba' ? 'Schedule TBA' : 'Not confirmed')}</dd></div><div><dt>Competition ends</dt><dd>{moment(event.end, 'Not confirmed')}</dd></div></dl>
    <dl className="facts"><div><dt><Icon name="pin" size={17}/> Region</dt><dd>{event.region}</dd></div><div><dt><Icon name="users" size={17}/> Who can join</dt><dd>{event.eligibility || 'Eligibility not announced. Check with the organizer.'}</dd></div></dl>
    {event.notices.length > 0 && <div className="notices">{event.notices.map(n => <p key={n}><Icon name="info" size={16}/><span>{n}</span></p>)}</div>}
    <div className="actions"><Link href={event.announcement_url} className="button primary"><Icon name="link"/>{event.announcement_label || 'Official announcement'}</Link>{event.registration_url && <Link href={event.registration_url} className="button secondary">Registration</Link>}</div>
    <div className="provenance"><span>Posted <b>{recorded(event.posted_at)}</b></span><span>First seen <b>{recorded(event.first_seen)}</b></span></div>
    <details className="history"><summary><span><Icon name="layers" size={16}/> Sources & updates <b>{event.announcements.length}</b></span><Icon name="chevron" size={16}/></summary>
    {Object.keys(event.field_evidence || {}).length > 0 && <div className="field-evidence"><h4>Evidence for listed details</h4><dl>{Object.entries(event.field_evidence || {}).map(([field, evidence]) => <div key={field}><dt>{evidenceLabels[field] || title(field)}</dt><dd><Link href={evidence.url}>Source</Link>{evidence.quote && <q>{evidence.quote}</q>}</dd></div>)}</dl></div>}
    <ol>{event.announcements.map((a, i) => <li key={`${a.url}-${i}`}>
      <div className="history-meta"><span>{title(a.kind)}</span>{a.access === 'search_only' && <span>Search result only</span>}{a.revision_count > 1 && <span>Revision {a.revision_count}</span>}</div>
      <Link href={a.url} className="history-link">{a.title}</Link><p>{a.source_name}</p><p>Posted {recorded(a.posted_at)} · First seen {recorded(a.first_seen)}</p>{a.evidence && <blockquote>{a.evidence}</blockquote>}
      {a.field_evidence?.philippine_connection && <div className="field-evidence"><h4>Philippine connection · source evidence</h4><p><Link href={a.field_evidence.philippine_connection.url}>Source</Link></p><blockquote>{a.field_evidence.philippine_connection.quote}</blockquote></div>}
      {!!a.related_links?.length && <div className="related-links"><p><strong>Links found in this announcement</strong></p>{a.related_links.map(link => <div key={link.url}><Link href={link.url} className="history-link">{link.label || link.url}</Link><p>Linked only · Full post not accessed</p><p>Found on <Link href={link.discovered_on}>the source page</Link></p></div>)}</div>}
      <DiscoveryTrace announcement={a}/>
    </li>)}</ol><p className="checked">Last checked {recorded(event.last_checked, true)}</p></details>
  </article>;
}
function SourcePanel({ sources }: { sources: Source[] }) {
  const working = sources.filter(s => ['ok', 'partial'].includes(s.status)).length;
  return <details id="coverage" className="coverage"><summary><span className="coverage-heading"><span className="coverage-icon"><Icon name="layers" size={24}/></span><span><strong>Follow the source.</strong><small>Coverage & collection health</small></span></span><span className="coverage-count">{working} of {sources.length} responding <Icon name="chevron"/></span></summary>
    <div className="coverage-body"><p>Listings come from automatically collected announcements. A failed fetch keeps earlier listings intact. Coverage is limited to these sources.</p><div className="source-list">{sources.map(s => <article className="source-row" key={s.id}><div><Link href={s.url} className="source-name">{s.name}</Link><p>{s.message}</p></div><dl><div><dt>Last success</dt><dd>{s.last_success ? recorded(s.last_success, true) : 'Not yet successful'}</dd></div><div><dt>Last attempt</dt><dd>{recorded(s.last_attempt, true)}</dd></div><p>{s.discovered} checked · {s.accepted} announcements</p></dl><span className={`badge health-${s.status}`}>{health[s.status]}</span></article>)}</div><p className="coverage-note">Facebook search discovery needs a configured search API. Finding a post URL does not give access to the full post. Details available only in images or inaccessible posts may be missing.</p></div>
  </details>;
}
function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (s: string) => void; children: ReactNode }) {
  return <label className="filter"><span>{label}</span><span className="select-wrap"><select value={value} onChange={e => onChange(e.target.value)}>{children}</select><Icon name="chevron" size={16}/></span></label>;
}

export default function App() {
  const [data, setData] = useState<Directory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [section, setSection] = useState<'upcoming' | 'finished'>('upcoming');
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('');
  const [format, setFormat] = useState('');
  const [registration, setRegistration] = useState('');
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('');
    try { const r = await fetch('/api/events', {signal}); if (!r.ok) throw new Error(`Server returned ${r.status}.`); const d = await r.json(); if (!Array.isArray(d.events) || !Array.isArray(d.sources)) throw new Error('Unexpected server response.'); setData(d); }
    catch (e) { if (!signal?.aborted) setError(e instanceof Error ? e.message : 'Could not load listings.'); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  const events = data?.events || [];
  const counts = { upcoming: events.filter(e => e.section === 'upcoming').length, finished: events.filter(e => e.section === 'finished').length };
  const open = events.filter(e => e.section === 'upcoming' && e.registration_status === 'open').length;
  const regions = [...new Set(events.map(e => e.region))].sort();
  const hasFilters = !!(query || region || format || registration);
  const clear = () => { setQuery(''); setRegion(''); setFormat(''); setRegistration(''); };
  const filtered = useMemo(() => (data?.events || []).filter(e => e.section === section && (!region || e.region === region) && (!format || e.format === format) && (!registration || e.registration_status === registration) && [e.name, e.organizer, e.eligibility, e.region, e.summary].join(' ').toLowerCase().includes(query.trim().toLowerCase())).sort((a, b) => {
    const priority = (e: Competition) => e.registration_status === 'open' ? 0 : e.status === 'live' ? 1 : e.status === 'cancelled' ? 4 : e.status === 'postponed' ? 3 : 2;
    return priority(a) - priority(b) || (a.start?.value || 'z').localeCompare(b.start?.value || 'z');
  }), [data, section, region, format, registration, query]);
  return <><a href="#competitions" className="skip">Skip to competitions</a>
    <header><nav className="shell topbar" aria-label="Main navigation"><a className="brand" href="#top"><span className="brand-icon"><Icon name="flag" size={25}/></span><span>ctf<span className="brand-light">finder</span><b>PH</b></span></a><div className="nav-links"><a href="#competitions">Competitions</a><a href="#coverage" onClick={() => { const el = document.getElementById('coverage') as HTMLDetailsElement; if (el) el.open = true; }}>Our sources</a><span className="country"><Icon name="globe" size={15}/> Philippines</span></div></nav>
    <div className="shell hero" id="top"><div><p className="eyebrow">THE PHILIPPINE CTF DIRECTORY</p><h1>Find your next<br/><em>challenge.</em></h1><p className="hero-description">What CTFs can your team still join? Find competitions, check your eligibility, and go straight to the official announcement.</p><p className="hero-note"><Icon name="refresh" size={16}/> Automatic discovery · Daily collection</p></div><aside className="radar" aria-label="Directory overview"><div className="radar-top"><span>ON THE RADAR</span><Icon name="flag" size={24}/></div><div className="radar-stat"><strong>{data ? open : '—'}</strong><span>with registration<br/>confirmed open</span></div><p><b>{data ? counts.upcoming : '—'}</b> upcoming & live listings</p><small>From the sources we can verify.<br/>An unknown status is not an open slot.</small></aside></div></header>
    <main id="competitions" className="shell"><section className="controls" aria-label="Find competitions"><div className="control-top"><div className="tabs" role="tablist" aria-label="Competition section">{(['upcoming', 'finished'] as const).map(tab => <button key={tab} id={`tab-${tab}`} role="tab" aria-selected={section === tab} aria-controls="results" tabIndex={section === tab ? 0 : -1} className={section === tab ? 'active' : ''} onClick={() => setSection(tab)} onKeyDown={e => { if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) { e.preventDefault(); const next = e.key === 'Home' ? 'upcoming' : e.key === 'End' ? 'finished' : tab === 'upcoming' ? 'finished' : 'upcoming'; setSection(next); document.getElementById(`tab-${next}`)?.focus(); } }}>{tab === 'upcoming' ? 'Upcoming & live' : 'Finished'}<span>{data ? counts[tab] : '—'}</span></button>)}</div><span className="timezone"><Icon name="clock" size={16}/> Asia/Manila · PHT</span></div>
    <div className="filters"><label className="filter search-filter"><span>Search competitions</span><span className="search-wrap"><Icon name="search"/><input type="search" placeholder="Event, organizer, or school" value={query} onChange={e => setQuery(e.target.value)}/></span></label><Select label="Region" value={region} onChange={setRegion}><option value="">All regions</option>{regions.map(r => <option key={r}>{r}</option>)}</Select><Select label="Format" value={format} onChange={setFormat}><option value="">All formats</option>{Object.entries(formats).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</Select><Select label="Registration" value={registration} onChange={setRegistration}><option value="">Any status</option>{Object.entries(registrations).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</Select></div></section>
    {error && <div role="alert" className="error"><p><strong>Couldn’t {data ? 'refresh' : 'load'} listings.</strong> {error} {data && 'Previous results are still shown.'}</p><button className="button secondary" disabled={loading} onClick={() => void load()}>Try again</button></div>}
    <section id="results" role="tabpanel" aria-labelledby={`tab-${section}`} aria-busy={loading}><div className="results-heading"><div><h2>{section === 'upcoming' ? 'Upcoming & live' : 'Finished competitions'}</h2><p aria-live="polite">{data ? `${filtered.length} ${filtered.length === 1 ? 'competition' : 'competitions'}${hasFilters ? ' matching your filters' : ''}` : loading ? 'Checking the directory…' : 'Listings unavailable'}</p></div><div className="result-tools">{hasFilters && <button className="text-button" onClick={clear}>Clear filters</button>}<button className="refresh" aria-label="Refresh saved listings" title="Refresh saved listings" disabled={loading} onClick={() => void load()}><Icon name="refresh"/></button></div></div>
    {loading && !data ? <div className="empty" role="status">Loading verified announcements…</div> : data && filtered.length ? <div className="event-grid">{filtered.map(e => <EventCard event={e} key={e.id}/>)}</div> : data ? <div className="empty"><span className="empty-icon"><Icon name={hasFilters ? 'search' : 'flag'} size={30}/></span><h3>{hasFilters ? 'No matches for these filters.' : `No ${section === 'finished' ? 'finished' : 'upcoming'} competitions recorded yet.`}</h3><p>{hasFilters ? 'Try another region, format, or registration status.' : 'Only collected announcements appear here. Check source coverage below to see what has been verified.'}</p>{hasFilters && <button onClick={clear} className="button primary">Clear filters</button>}</div> : null}
    <p className="date-note"><Icon name="clock" size={16}/> Confirmed times use Manila time. Ambiguous dates stay as the organizer wrote them.</p></section>
    <SourcePanel sources={data?.sources || []}/><p className="directory-time">{data && `Directory loaded ${recorded(data.generated_at, true)}. Source check times are shown above.`}</p>
    </main><footer className="shell"><span><Icon name="flag" size={19}/> Built for the next generation of Philippine CTF teams.</span><a href="#top">Back to top</a></footer></>;
}
