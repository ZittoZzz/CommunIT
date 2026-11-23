import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import './styles.css';

type Moment = { raw: string; value: string | null; precision: 'datetime' | 'date' | 'text'; timezone: string | null };
type Price = { kind: 'free' | 'paid' | 'unknown'; amount?: number; currency?: string };
type TicketOption = { name: string; access: 'public' | 'restricted' | 'unknown'; eligibility: string | null; attendance: 'onsite' | 'online' | null; registration_state: string; price: Price; deadline: Moment | null };
type FieldEvidence = Record<string, { url: string; quote: string }>;
type RelatedLink = { url: string; label: string; access: 'linked_only'; discovered_on: string };
type Announcement = { url: string; title: string; kind: string; posted_at: string | null; first_seen: string; last_seen: string; access: 'full' | 'search_only'; source_name: string; evidence: string | null; revision_count: number; related_links?: RelatedLink[]; discovery_path?: string[]; discovery_query?: string | null; discovery_queries?: string[]; field_evidence?: FieldEvidence };
type Competition = { id: string; name: string; organizer: string; region: string; format: string; eligibility: string | null; announcement_url: string; announcement_label?: string; registration_url: string | null; registration_status: string; status: string; section: 'upcoming' | 'past' | 'finished' | 'unconfirmed' | 'watchlist'; competition_date?: Moment | null; start: Moment | null; end: Moment | null; deadline: Moment | null; registration_opens: Moment | null; posted_at: string | null; first_seen: string; last_checked: string; summary: string | null; description?: string | null; stage: string; edition: string; notices: string[]; announcements: Announcement[]; field_evidence?: FieldEvidence; geography?: string; topic?: string; topics?: string[]; price?: Price; account_required?: boolean | null; submission_deadline?: Moment | null; attendance_options?: string[]; ticket_options?: TicketOption[] };
type Source = { id: string; name: string; url: string; kind: string; status: string; last_success: string | null; last_attempt: string | null; message: string; discovered: number; accepted: number };
type Directory = { events: Competition[]; sources: Source[]; generated_at: string; manual_collection?: { enabled: boolean; token?: string } };
type CollectionStatus = { enabled: boolean; state: 'idle' | 'running' | 'completed' | 'failed'; started_at: string | null; finished_at: string | null; completed_sources: number; total_sources: number; events?: number; announcements?: number; warning_count?: number; message: string };

function collectionStatus(value: unknown): value is CollectionStatus {
  if (!value || typeof value !== 'object') return false;
  const status = value as CollectionStatus;
  return typeof status.enabled === 'boolean' && ['idle', 'running', 'completed', 'failed'].includes(status.state)
    && Number.isInteger(status.completed_sources) && Number.isInteger(status.total_sources)
    && status.completed_sources >= 0 && status.total_sources >= 0 && typeof status.message === 'string';
}

function useManualCollection(enabled: boolean, token: string | undefined, reload: (signal?: AbortSignal) => Promise<void>) {
  const [status, setStatus] = useState<CollectionStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [check, setCheck] = useState(0);
  const previous = useRef<CollectionStatus | null>(null);
  const postRequest = useRef<AbortController | null>(null);
  useEffect(() => () => { postRequest.current?.abort(); }, [enabled]);
  useEffect(() => {
    if (!enabled) {
      previous.current = null; setStatus(null); setError(''); setChecking(false); setSubmitting(false);
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setChecking(true);
    const poll = async () => {
      try {
        const response = await fetch('/api/collection', { signal: controller.signal });
        if (!response.ok) throw new Error(`Server returned ${response.status}.`);
        const next: unknown = await response.json();
        if (!collectionStatus(next)) throw new Error('Unexpected fetch status.');
        if (controller.signal.aborted) return;
        const finished = previous.current?.state === 'running' && ['completed', 'failed'].includes(next.state);
        previous.current = next; setStatus(next); setError(''); setChecking(false);
        if (finished) void reload(controller.signal);
        if (next.enabled && next.state === 'running') timer = setTimeout(() => void poll(), 2000);
      } catch (failure) {
        if (controller.signal.aborted) return;
        setChecking(false);
        setError(`Couldn’t check fetch status. ${failure instanceof Error ? failure.message : 'Connection failed.'} Check status before starting another fetch.`);
      }
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [enabled, check, reload]);
  const start = async () => {
    if (!enabled || !token || !status?.enabled || checking || submitting || error || status.state === 'running' || postRequest.current) return;
    const controller = new AbortController();
    postRequest.current = controller; setSubmitting(true); setError('');
    try {
      const response = await fetch('/api/collection', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Collection-Token': token },
        body: JSON.stringify({}), signal: controller.signal,
      });
      const body: unknown = await response.json().catch(() => null);
      if (![202, 409].includes(response.status)) {
        const message = body && typeof body === 'object' && 'message' in body && typeof body.message === 'string' ? body.message : `Server returned ${response.status}.`;
        throw new Error(message);
      }
      if (controller.signal.aborted) return;
      // A successful start or conflict means a job may already be running.
      // Reconcile through GET before allowing another POST, even if its body is incomplete.
      const running: CollectionStatus = { enabled: true, state: 'running', started_at: null, finished_at: null, completed_sources: 0, total_sources: 0, message: 'Checking event fetch progress…' };
      previous.current = running; setStatus(running); setCheck(value => value + 1);
    } catch (failure) {
      if (!controller.signal.aborted) setError(`Couldn’t confirm the event fetch. ${failure instanceof Error ? failure.message : 'Connection failed.'} Check status before trying again.`);
    } finally {
      if (postRequest.current === controller) postRequest.current = null;
      if (!controller.signal.aborted) setSubmitting(false);
    }
  };
  return { status, checking, submitting, error, start, retryStatus: () => setCheck(value => value + 1) };
}

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
const sections = ['upcoming', 'all', 'finished', 'unconfirmed', 'watchlist'] as const;
type Section = typeof sections[number];
const sectionLabels = { upcoming: 'Upcoming & live', all: 'All events', finished: 'Past & finished', unconfirmed: 'Date unconfirmed', watchlist: 'Watchlist' };
function inSection(event: Competition, section: Section) {
  return section === 'all' || (section === 'finished' ? ['past', 'finished'].includes(event.section) : event.section === section);
}
const states: Record<string, string> = { date_conflict: 'Conflicting dates', scheduled: 'Upcoming', live: 'Live now', finished: 'Finished', cancelled: 'Cancelled', postponed: 'Postponed', schedule_tba: 'Schedule TBA', end_unconfirmed: 'End unconfirmed', past_date: 'Past date · completion unconfirmed', undated_lead: 'Undated search lead' };
const formats: Record<string, string> = { online: 'Online', in_person: 'In person', hybrid: 'Hybrid', unknown: 'Format unconfirmed' };
const topics: Record<string, string> = { cybersecurity: 'Cybersecurity', ai_data: 'AI & Data', cloud_devops: 'Cloud & DevOps', software_development: 'Software Development', networking_systems: 'Networking & Systems', community: 'Community', general_it: 'General IT' };
const registrations: Record<string, string> = { open: 'Registration open', approval_required: 'Approval required', waitlisted: 'Waitlisted', closed: 'Registration closed', not_yet_open: 'Not open yet', unknown: 'Registration unconfirmed' };
const health: Record<string, string> = { ok: 'Working', partial: 'Partial coverage', error: 'Fetch failed', blocked: 'Access blocked', rate_limited: 'Rate limited', disabled: 'Disabled', needs_credentials: 'Needs credentials', policy_restricted: 'Policy restricted', not_run: 'Not checked yet' };
const evidenceLabels: Record<string, string> = { name: 'Event name', organizer: 'Organizer', region: 'Region', format: 'Format', eligibility: 'Who can join', date_conflicts: 'Conflicting date evidence', competition_date: 'Tournament date', start: 'Starts', end: 'Ends', deadline: 'Registration deadline', registration_opens: 'Registration opens', registration_url: 'Registration link', registration_state: 'Organizer registration statement', lifecycle: 'Organizer event status', posted_at: 'Announcement posted', summary: 'Summary', description: 'Description' };

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
function priceLabel(price?: Price) {
  if (price?.kind === 'free') return 'Free';
  if (price?.kind !== 'paid') return 'Unknown';
  return typeof price.amount === 'number' && price.currency ? `${price.currency} ${price.amount.toLocaleString('en-PH')}` : 'Paid · amount not announced';
}
function communityRegistration(state: string) {
  return state === 'approval_required' ? 'Applications open · approval required' : registrations[state] || registrations.unknown;
}

function TicketOptions({ tickets }: { tickets: TicketOption[] }) {
  const groups = [{access:'public',label:'Standard public tickets'}, {access:'restricted',label:'Restricted tickets'}, {access:'unknown',label:'Other tickets · eligibility unconfirmed'}];
  return <div className="ticket-options">{groups.map(group => {
    const options = tickets.filter(ticket => ticket.access === group.access);
    return options.length > 0 && <div key={group.access}><h4>{group.label}</h4><ul>{options.map((ticket, index) => <li key={`${ticket.name}-${index}`}>
      <strong>{ticket.name}</strong>{ticket.eligibility && <p>{ticket.eligibility}</p>}
      <p>{communityRegistration(ticket.registration_state)}</p><p>Price: {priceLabel(ticket.price)} · Deadline: {moment(ticket.deadline, 'Unknown')}</p>
    </li>)}</ul></div>;
  })}</div>;
}

function DiscoveryTrace({ announcement }: { announcement: Announcement }) {
  const queries = [...new Set([announcement.discovery_query, ...(announcement.discovery_queries || [])].filter((query): query is string => !!query))];
  const path = announcement.discovery_path || [];
  if (!queries.length && !path.length) return null;
  return <details className="discovery-path"><summary>How this announcement was found</summary>
    {queries.map(query => <p key={query}><strong>Search query: </strong><q>{query}</q></p>)}
    {path.map((url, step) => <p key={`${url}-${step}`}><span>{step + 1}. </span><Link href={url}>{url}</Link></p>)}
  </details>;
}

// Calendar labels never add a time to date-only evidence. Datetimes must have
// an explicit zone before converting their calendar day to Asia/Manila.
function calendarDay(value?: Moment | null): string | null {
  if (!value?.value) return null;
  if (value.precision === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(value.value)) return value.value;
  if (value.precision !== 'datetime' || !value.timezone || !/(Z|[+-]\d{2}:?\d{2})$/i.test(value.value)) return null;
  const date = new Date(value.value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Manila',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
  const part = (type: string) => parts.find(p => p.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}
function EventDate({ event }: { event: Competition }) {
  const day = event.status === 'date_conflict' ? null : calendarDay(event.start || event.competition_date);
  if (!day) return <span className="event-date date-unconfirmed"><Icon name="clock" size={19}/><span>Date unconfirmed</span></span>;
  const month = new Intl.DateTimeFormat('en-PH', {month:'short',timeZone:'Asia/Manila'}).format(new Date(day));
  return <time className="event-date" dateTime={day} aria-label={`Starts ${recorded(day)} (Asia/Manila)`}>
    <span className="date-month">{month}</span><strong className="date-day">{Number(day.slice(8,10))}</strong><span className="date-year">{day.slice(0,4)}</span>
  </time>;
}
function EventCard({ event }: { event: Competition }) {
  const supportedTopics = [...new Set(event.topics || [])].filter(topic => topic in topics);
  const labels: Record<string, string> = {...evidenceLabels, competition_date:'Event date', topic:'Topic', geography:'Opportunity geography', price:'Price', account_required:'Account requirement', submission_deadline:'Submission deadline', attendance_options:'Attendance options', ticket_options:'Ticket options'};
  const registerBy = calendarDay(event.deadline);
  const submitBy = calendarDay(event.submission_deadline);
  const description = event.description || event.summary;
  const previewState = !['scheduled','schedule_tba','undated_lead'].includes(event.status) ? states[event.status] : null;
  return <article className={`event-card event-${event.status}`}>
    <div className="event-preview">
      <EventDate event={event}/>
      <div className="event-overview">
        <h3>{event.name}</h3><p className="organizer">{event.organizer}</p>
        <p className="event-location"><Icon name={event.format === 'online' ? 'globe' : 'pin'} size={15}/><span>{event.region} · {formats[event.format]}{!!event.attendance_options?.length && ` · ${event.attendance_options.join(' / ')}`}</span></p>
        {supportedTopics.length > 0 && <div className="event-topics" aria-label="Topics">{supportedTopics.map(topic => <span className="topic-tag" key={topic}>{topics[topic]}</span>)}</div>}
        <div className="preview-facts">
          {previewState && <span className={`badge state-${event.status}`}>{previewState}</span>}
          {event.price?.kind === 'free' && <span className="badge price-fact price-free">Free</span>}
          {event.price?.kind === 'paid' && <span className="badge price-fact">Paid{typeof event.price.amount === 'number' && event.price.currency ? ` · ${priceLabel(event.price)}` : ''}</span>}
          {event.registration_status !== 'unknown' && registrations[event.registration_status] && <span className={`badge signup-fact registration-${event.registration_status}`}>{communityRegistration(event.registration_status)}</span>}
          {event.account_required === true && <span className="join-fact">Account required</span>}
          {registerBy && <span className="join-fact deadline-fact">Register by <time dateTime={registerBy}>{recorded(registerBy)}</time></span>}
          {submitBy && <span className="join-fact deadline-fact">Submit by <time dateTime={submitBy}>{recorded(submitBy)}</time></span>}
        </div>
      </div>
    </div>
    <details className="event-details"><summary><span>Details<span className="sr-only"> for {event.name}</span></span><Icon name="chevron" size={16}/></summary>
      <div className="event-detail-body">
        <section className="event-description"><h4>Description</h4><p>{description || 'Description not announced.'}</p></section>
        <dl className="dates"><div><dt>Starts</dt><dd>{moment(event.start || event.competition_date || null, 'Not confirmed')}</dd></div><div><dt>Ends</dt><dd>{moment(event.end, 'Not confirmed')}</dd></div></dl>
        <dl className="facts"><div><dt><Icon name="pin" size={17}/> Location</dt><dd>{event.region} · {formats[event.format]}</dd></div>{!!event.attendance_options?.length && <div><dt>Attendance</dt><dd>{event.attendance_options.join(' · ')}</dd></div>}<div><dt><Icon name="users" size={17}/> Who can join</dt><dd>{event.eligibility || 'Eligibility not announced. Check with the organizer.'}</dd></div><div><dt>Price</dt><dd>{priceLabel(event.price)}</dd></div><div><dt>Account</dt><dd>{event.account_required === true ? 'Required to register' : event.account_required === false ? 'Not required' : 'Unknown'}</dd></div></dl>
        <div className={`registration registration-${event.registration_status}`}><strong>{communityRegistration(event.registration_status)}</strong><dl><div><dt>Registration deadline</dt><dd>{moment(event.deadline, 'Unknown')}</dd></div><div><dt>Submission deadline</dt><dd>{moment(event.submission_deadline || null, 'Unknown')}</dd></div>{event.registration_opens && <div><dt>Registration opens</dt><dd>{moment(event.registration_opens)}</dd></div>}</dl></div>
        {!!event.ticket_options?.length && <TicketOptions tickets={event.ticket_options}/>}
        {event.notices.length > 0 && <div className="notices">{event.notices.map(n => <p key={n}><Icon name="info" size={16}/><span>{n}</span></p>)}</div>}
        <div className="actions"><Link href={event.announcement_url} className="button primary"><Icon name="link"/>{event.announcement_label || 'Official announcement'}</Link>{event.registration_url && <Link href={event.registration_url} className="button secondary">Registration</Link>}</div>
        <div className="provenance"><span>Posted <b>{recorded(event.posted_at)}</b></span><span>First seen <b>{recorded(event.first_seen)}</b></span></div>
    <details className="history"><summary><span><Icon name="layers" size={16}/> Sources & updates <b>{event.announcements.length}</b></span><Icon name="chevron" size={16}/></summary>
    {Object.keys(event.field_evidence || {}).length > 0 && <div className="field-evidence"><h4>Evidence for listed details</h4><dl>{Object.entries(event.field_evidence || {}).map(([field, evidence]) => <div key={field}><dt>{labels[field] || title(field)}</dt><dd><Link href={evidence.url}>Source</Link>{evidence.quote && <q>{evidence.quote}</q>}</dd></div>)}</dl></div>}
    <ol>{event.announcements.map((a, i) => <li key={`${a.url}-${i}`}>
      <div className="history-meta"><span>{title(a.kind)}</span>{a.access === 'search_only' && <span>Search result only</span>}{a.revision_count > 1 && <span>Revision {a.revision_count}</span>}</div>
      <Link href={a.url} className="history-link">{a.title}</Link><p>{a.source_name}</p><p>Posted {recorded(a.posted_at)} · First seen {recorded(a.first_seen)}</p>{a.evidence && <blockquote>{a.evidence}</blockquote>}
      {a.field_evidence?.philippine_connection && <div className="field-evidence"><h4>Philippine connection · source evidence</h4><p><Link href={a.field_evidence.philippine_connection.url}>Source</Link></p><blockquote>{a.field_evidence.philippine_connection.quote}</blockquote></div>}
      {!!a.related_links?.length && <div className="related-links"><p><strong>Links found in this announcement</strong></p>{a.related_links.map(link => <div key={link.url}><Link href={link.url} className="history-link">{link.label || link.url}</Link><p>Linked only · Full post not accessed</p><p>Found on <Link href={link.discovered_on}>the source page</Link></p></div>)}</div>}
      <DiscoveryTrace announcement={a}/>
    </li>)}</ol><p className="checked">Last checked {recorded(event.last_checked, true)}</p></details>
      </div>
    </details>
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
  const [section, setSection] = useState<Section>('upcoming');
  const [query, setQuery] = useState('');
  const [topic, setTopic] = useState('');
  const [format, setFormat] = useState('');
  const [registration, setRegistration] = useState('');
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('');
    try { const r = await fetch('/api/events', {signal}); if (!r.ok) throw new Error(`Server returned ${r.status}.`); const d = await r.json(); if (!Array.isArray(d.events) || !Array.isArray(d.sources)) throw new Error('Unexpected server response.'); setData(d); }
    catch (e) { if (!signal?.aborted) setError(e instanceof Error ? e.message : 'Could not load listings.'); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  const canCollect = data?.manual_collection?.enabled === true;
  const collection = useManualCollection(canCollect, data?.manual_collection?.token, load);
  const collecting = collection.submitting || collection.status?.state === 'running';
  const events = data?.events || [];
  const totalUpcoming = events.filter(e => e.section === 'upcoming').length;
  const open = events.filter(e => e.section === 'upcoming' && e.registration_status === 'open').length;
  const hasFilters = !!(query.trim() || topic || format || registration);
  const clear = () => { setQuery(''); setTopic(''); setFormat(''); setRegistration(''); };
  const matching = useMemo(() => (data?.events || []).filter(e =>
    (!topic || e.topics?.includes(topic)) &&
    (!format || e.format === format) && (!registration || e.registration_status === registration) &&
    [e.name, e.organizer, e.eligibility, e.region, e.summary, e.description].join(' ').toLowerCase().includes(query.trim().toLowerCase())
  ), [data, topic, format, registration, query]);
  const counts = { all: matching.length, upcoming: matching.filter(e => e.section === 'upcoming').length, finished: matching.filter(e => ['past', 'finished'].includes(e.section)).length, unconfirmed: matching.filter(e => e.section === 'unconfirmed').length, watchlist: matching.filter(e => e.section === 'watchlist').length };
  const filtered = useMemo(() => matching.filter(e => inSection(e, section)).sort((a, b) => {
    const priority = (e: Competition) => ['open', 'approval_required'].includes(e.registration_status) ? 0 : e.status === 'live' ? 1 : e.status === 'cancelled' ? 4 : e.status === 'postponed' ? 3 : 2;
    const freeFirst = priority(a) === 0 && priority(b) === 0
      ? Number(a.price?.kind !== 'free') - Number(b.price?.kind !== 'free') : 0;
    return priority(a) - priority(b) || freeFirst || (a.start?.value || a.competition_date?.value || 'z').localeCompare(b.start?.value || b.competition_date?.value || 'z');
  }), [matching, section]);
  // Group after the existing filter and sort, preserving each group's order.
  const international = filtered.filter(event => event.geography === 'international_online');
  const local = filtered.filter(event => event.geography !== 'international_online');
  return <><a href="#events" className="skip">Skip to events</a>
    <header><nav className="shell topbar" aria-label="Main navigation"><a className="brand" href="#top"><span className="brand-icon"><Icon name="flag" size={25}/></span><span>IT_Community_PH</span></a><div className="nav-links"><a href="#events">Events</a><a href="#coverage" onClick={() => { const el = document.getElementById('coverage') as HTMLDetailsElement; if (el) el.open = true; }}>Our sources</a><span className="country"><Icon name="globe" size={15}/> Philippines</span></div></nav>
    <div className="shell hero" id="top"><div><p className="eyebrow">YOUR TECH COMMUNITY DIRECTORY</p><h1>Find your next <br/><em>tech event.</em></h1><p className="hero-description">Explore tech meetups, competitions, and conferences in the Philippines, plus online events you can join from here.</p><p className="hero-note"><Icon name="refresh" size={16}/> Public sources · Official event links</p></div><aside className="radar" aria-label="Directory overview"><div className="radar-top"><span>ON THE RADAR</span><Icon name="flag" size={24}/></div><div className="radar-stat"><strong>{data ? open : '—'}</strong><span>with registration<br/>confirmed open</span></div><p><b>{data ? totalUpcoming : '—'}</b> upcoming & live events</p><small>From the sources we can verify.<br/>An unknown status is not an open slot.</small></aside></div></header>
    <main id="events" className="shell"><section className="controls" aria-label="Find events"><div className="control-top"><div className="tabs" role="tablist" aria-label="Event section">{sections.map(tab => <button key={tab} id={`tab-${tab}`} role="tab" aria-selected={section === tab} aria-controls="results" tabIndex={section === tab ? 0 : -1} className={section === tab ? 'active' : ''} onClick={() => setSection(tab)} onKeyDown={e => { if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) { e.preventDefault(); const next = e.key === 'Home' ? sections[0] : e.key === 'End' ? sections[sections.length - 1] : sections[(sections.indexOf(tab) + (e.key === 'ArrowRight' ? 1 : sections.length - 1)) % sections.length]; setSection(next); document.getElementById(`tab-${next}`)?.focus(); } }}>{sectionLabels[tab]}<span>{data ? counts[tab] : '—'}</span></button>)}</div><span className="timezone"><Icon name="clock" size={16}/> Asia/Manila · PHT</span></div>
    <div className="filters"><label className="filter search-filter"><span>Search events</span><span className="search-wrap"><Icon name="search"/><input type="search" placeholder="Event, organizer, or school" value={query} onChange={e => setQuery(e.target.value)}/></span></label><Select label="Topic" value={topic} onChange={setTopic}><option value="">All topics</option>{Object.entries(topics).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</Select><Select label="Format" value={format} onChange={setFormat}><option value="">All formats</option>{Object.entries(formats).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</Select><Select label="Registration" value={registration} onChange={setRegistration}><option value="">Any status</option>{Object.entries(registrations).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</Select></div></section>
    {error && <div role="alert" className="error"><p><strong>Couldn’t {data ? 'refresh' : 'load'} listings.</strong> {error} {data && 'Previous results are still shown.'}</p><button className="button secondary" disabled={loading} onClick={() => void load()}>Try again</button></div>}
    <section id="results" role="tabpanel" aria-labelledby={`tab-${section}`} aria-busy={loading}><div className="results-heading"><div><h2>{sectionLabels[section]}</h2><p aria-live="polite">{data ? `${filtered.length} ${filtered.length === 1 ? 'event' : 'events'}${hasFilters ? ' matching your filters' : ''}` : loading ? 'Checking the directory…' : 'Listings unavailable'}</p></div><div className="result-tools">{hasFilters && <button className="text-button" onClick={clear}>Clear filters</button>}{canCollect && <button className="button secondary fetch-events" disabled={loading || collecting || collection.checking || !!collection.error || !collection.status?.enabled || !data?.manual_collection?.token} onClick={() => void collection.start()}><Icon name="refresh"/>{collecting ? 'Fetching events…' : 'Fetch events'}</button>}<button className="refresh" aria-label="Refresh saved listings" title="Refresh saved listings" disabled={loading} onClick={() => void load()}><Icon name="refresh"/></button></div></div>
    {canCollect && <div className="collection-status" role="status" aria-live="polite" aria-atomic="true">
      {collection.error ? <><p role="alert">{collection.error} Saved events are still shown.</p><button className="text-button" disabled={collection.checking} onClick={collection.retryStatus}>Check fetch status</button></> : collection.checking && !collecting ? <p>Checking fetch status…</p> : collection.status && <>
        {collection.status.state !== 'idle' && <p><strong>{collection.status.state === 'running' ? 'Fetching events' : collection.status.state === 'completed' ? 'Fetch complete' : 'Fetch failed'}.</strong> Checked {collection.status.completed_sources} of {collection.status.total_sources} sources.</p>}
        <p role={collection.status.state === 'failed' ? 'alert' : undefined}>{collection.status.message}{collection.status.state === 'failed' && ' Saved events are still shown. You can retry Fetch events.'}</p>
        {!!collection.status.warning_count && <p>{collection.status.warning_count} source {collection.status.warning_count === 1 ? 'warning' : 'warnings'}. See source coverage below.</p>}
      </>}
    </div>}
    {loading && !data ? <div className="empty" role="status">Loading verified announcements…</div> : data && filtered.length ? <>{local.length > 0 && <section className="opportunity-group" aria-labelledby="ph-opportunities-title"><h3 id="ph-opportunities-title">PH opportunities</h3><div className="event-grid">{local.map(e => <EventCard event={e} key={e.id}/>)}</div></section>}{international.length > 0 && <section className="opportunity-group" aria-labelledby="international-online-title"><h3 id="international-online-title">International online opportunities</h3><div className="event-grid">{international.map(e => <EventCard event={e} key={e.id}/>)}</div></section>}</> : data ? <div className="empty"><span className="empty-icon"><Icon name={hasFilters ? 'search' : 'flag'} size={30}/></span><h3>{hasFilters ? 'No matches for these filters.' : section === 'all' ? 'No events recorded yet.' : `No ${section === 'finished' ? 'past or finished' : section === 'unconfirmed' ? 'date-unconfirmed' : section === 'watchlist' ? 'watchlist' : 'upcoming'} events recorded yet.`}</h3><p>{hasFilters ? 'Try another topic, format, registration status, or search term.' : 'Only collected announcements appear here. Check source coverage below to see what has been verified.'}</p>{hasFilters && <button onClick={clear} className="button primary">Clear filters</button>}</div> : null}
    <p className="date-note"><Icon name="clock" size={16}/> Confirmed times use Manila time. Ambiguous dates stay as the organizer wrote them.</p></section>
    <SourcePanel sources={data?.sources || []}/><p className="directory-time">{data && `Directory loaded ${recorded(data.generated_at, true)}. Source check times are shown above.`}</p>
    </main><footer className="shell"><span><Icon name="flag" size={19}/> Built for the Philippine tech community.</span><a href="#top">Back to top</a></footer></>;
}
