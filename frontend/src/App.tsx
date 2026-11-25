import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import './styles.css';

type Moment = { raw: string; value: string | null; precision: 'datetime' | 'date' | 'text'; timezone: string | null };
type Price = { kind: 'free' | 'paid' | 'unknown'; amount?: number; minimum_amount?: number; currency?: string };
type TicketOption = { name: string; access: 'public' | 'restricted' | 'unknown'; eligibility: string | null; attendance: 'onsite' | 'online' | null; registration_state: string; price: Price; deadline: Moment | null };
type FieldEvidence = Record<string, { url: string; quote: string }>;
type Announcement = { url: string; kind: string; access: 'full' | 'search_only'; first_seen?: string | null };
type Review = { required: boolean; reasons: string[]; expired: boolean; expires_at: string | null };
type Verification = { last_observed_at: string; last_content_fetched_at: string | null; last_event_page_checked_at: string | null; basis: string };
type Competition = { organizer_event_url?: string | null; lifecycle?: string | null; review?: Review; verification?: Verification; parent_event_start?: Moment | null; parent_event_end?: Moment | null; id: string; name: string; organizer: string; region: string; format: string; eligibility: string | null; announcement_url: string; announcement_label?: string; registration_url: string | null; registration_status: string; status: string; section: 'upcoming' | 'past' | 'finished' | 'unconfirmed' | 'watchlist' | 'archived'; competition_date?: Moment | null; start: Moment | null; end: Moment | null; deadline: Moment | null; registration_opens: Moment | null; posted_at: string | null; first_seen: string; last_checked: string; summary: string | null; description?: string | null; stage: string; edition: string; notices: string[]; announcements: Announcement[]; field_evidence?: FieldEvidence; geography?: string; topic?: string; topics?: string[]; price?: Price; account_required?: boolean | null; submission_deadline?: Moment | null; attendance_options?: string[]; ticket_options?: TicketOption[] };
type Directory = { events: Competition[]; listings_updated_at?: string | null; generated_at: string };

const savedBoardKey = 'communit:board:v1';
const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const optionalText = (value: unknown) => value == null || typeof value === 'string';
const textArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string');
const usableMoment = (value: unknown) => value == null || (isRecord(value) && optionalText(value.raw) && optionalText(value.value) && optionalText(value.timezone) && ['date', 'datetime', 'text'].includes(String(value.precision)));
const usablePrice = (value: unknown) => value == null || (isRecord(value) && ['free', 'paid', 'unknown'].includes(String(value.kind)) && optionalText(value.currency) && ['amount', 'minimum_amount'].every(key => value[key] == null || typeof value[key] === 'number'));
function usableDirectory(value: unknown): value is Directory {
  if (!isRecord(value) || !Array.isArray(value.events) || !optionalText(value.generated_at) || !optionalText(value.listings_updated_at)) return false;
  const ids = new Set<string>();
  return value.events.every(event => {
    if (!isRecord(event) || typeof event.id !== 'string' || !event.id || ids.has(event.id) || typeof event.name !== 'string' || !event.name.trim()) return false;
    ids.add(event.id);
    return ['upcoming', 'past', 'finished', 'unconfirmed', 'watchlist', 'archived'].includes(String(event.section)) &&
      ['organizer', 'region', 'format', 'status', 'registration_status', 'eligibility', 'summary', 'description', 'posted_at', 'first_seen', 'announcement_url', 'organizer_event_url', 'registration_url'].every(key => optionalText(event[key])) &&
      ['start', 'end', 'competition_date', 'parent_event_start', 'parent_event_end', 'deadline', 'submission_deadline', 'registration_opens'].every(key => usableMoment(event[key])) &&
      textArray(event.notices) && ['topics', 'attendance_options'].every(key => event[key] == null || textArray(event[key])) &&
      Array.isArray(event.announcements) && event.announcements.every(ann => isRecord(ann) && typeof ann.url === 'string' && optionalText(ann.kind) && ['full', 'search_only'].includes(String(ann.access))) &&
      (event.review == null || (isRecord(event.review) && (event.review.reasons == null ? !event.review.required : textArray(event.review.reasons)))) &&
      (event.field_evidence == null || (isRecord(event.field_evidence) && Object.values(event.field_evidence).every(proof => isRecord(proof) && typeof proof.url === 'string' && typeof proof.quote === 'string'))) &&
      usablePrice(event.price) && (event.ticket_options == null || (Array.isArray(event.ticket_options) && event.ticket_options.every(ticket => isRecord(ticket) && ['name', 'eligibility', 'attendance', 'registration_state', 'access'].every(key => optionalText(ticket[key])) && usablePrice(ticket.price) && usableMoment(ticket.deadline))));
  });
}
function readSavedBoard(): Directory | null {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(savedBoardKey) || 'null');
    return isRecord(saved) && saved.version === 1 && usableDirectory(saved.data) ? saved.data : null;
  } catch { return null; }
}
function saveBoard(data: Directory) {
  // Persist only the public board, never collection tokens or other API metadata.
  try { sessionStorage.setItem(savedBoardKey, JSON.stringify({version: 1, data: {events: data.events, generated_at: data.generated_at, listings_updated_at: data.listings_updated_at}})); }
  catch { /* Storage may be blocked or full; the live board still works. */ }
}

function OpeningTicket({error, retry}: {error: string; retry: () => void}) {
  return <div className="opening-space"><section className="opening-ticket" aria-labelledby="opening-title" data-failed={!!error}>
    <span className="opening-stamp">CommunIT</span>
    <h2 id="opening-title">{error ? 'Couldn’t open the board' : 'Opening the board'}</h2>
    <p>{error ? 'Couldn’t load event listings. Please try again.' : 'Loading event listings…'}</p>
    {error && <button className="button primary" onClick={retry}>Retry</button>}
  </section></div>;
}

type RequestState = 'pending' | 'success' | 'error' | 'idle';
function RefreshSlip({state, retry}: {state: RequestState; retry: () => void}) {
  const [leaving, setLeaving] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    setLeaving(false); setHidden(false);
    if (state !== 'success' || focused) return;
    const fade = setTimeout(() => setLeaving(true), 1400);
    const hide = setTimeout(() => setHidden(true), 1700);
    return () => { clearTimeout(fade); clearTimeout(hide); };
  }, [state, focused]);
  if (state === 'idle') return null;
  return <div className="refresh-slip" data-state={state} data-leaving={leaving} hidden={hidden && state === 'success'}
    onFocusCapture={() => setFocused(true)} onBlurCapture={e => { if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false); }}>
    {state === 'pending' ? <span className="refresh-stack" aria-hidden="true"><i/><i/><i/></span> : <span className="refresh-seal" aria-hidden="true">{state === 'success' ? '✓' : '!'}</span>}
    <span>{state === 'pending' ? 'Checking listings…' : state === 'success' ? 'Board up to date' : 'Couldn’t refresh · Showing saved listings'}</span>
    {(state === 'error' || focused) && <button className="text-button" aria-disabled={state === 'pending'}
      onClick={() => { if (state === 'error') retry(); else if (state === 'success') setHidden(true); }}>
      {state === 'success' ? 'Dismiss' : 'Retry'}
    </button>}
  </div>;
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
    link: <><path d="m10 13 4-4m-5 7-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 0 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.info}</svg>;
}
const sections = ['upcoming', 'finished', 'confirmation', 'archived'] as const;
type Section = typeof sections[number];
const sectionLabels = { upcoming: 'Upcoming', finished: 'Past', confirmation: 'Needs confirmation', archived: 'Archive' };
function inSection(event: Competition, section: Section) {
  return section === 'confirmation' ? ['unconfirmed', 'watchlist'].includes(event.section)
    : section === 'finished' ? ['past', 'finished'].includes(event.section) : event.section === section;
}
const states: Record<string, string> = { date_conflict: 'Conflicting dates', scheduled: 'Upcoming', live: 'Live now', finished: 'Finished', cancelled: 'Cancelled', postponed: 'Postponed', schedule_tba: 'Schedule TBA', end_unconfirmed: 'End unconfirmed', past_date: 'Past date · completion unconfirmed', undated_lead: 'Undated search lead' };
const formats: Record<string, string> = { online: 'Online', in_person: 'In person', hybrid: 'Hybrid', unknown: 'Format unconfirmed' };
const topics: Record<string, string> = { cybersecurity: 'Cybersecurity', ai_data: 'AI & Data', cloud: 'Cloud', devops: 'DevOps', software_development: 'Software Development', networking_systems: 'Networking & Systems', community: 'Community', general_it: 'General IT' };
const registrations: Record<string, string> = { open: 'Registration open', approval_required: 'Approval required', waitlisted: 'Waitlisted', closed: 'Registration closed', not_yet_open: 'Not open yet', unknown: 'Registration unconfirmed' };

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
// Omit absent display facts without changing the saved evidence or inferring values.
function detailText(value?: string | null): string | null {
  const text = value?.trim();
  return !text || /^(unknown|unspecified|n\/?a|none|null|tbd|tba|[-–—]|(?:not |un)(?:confirmed|announced|specified|available)|(?:organizer|format|eligibility|description) (?:unknown|unconfirmed|not announced))[.!]?$/i.test(text) ? null : text;
}
function eligibilityText(value?: string | null) {
  const text = detailText(value);
  if (!text || /^(Public ticket options are listed; check their current availability\.|Standard public tickets are available; organizer approval required\.|Public student eligibility is unconfirmed\.|Eligibility not announced\.)/i.test(text)) return null;
  return text;
}
function knownMoment(value?: Moment | null): string | null {
  return value ? detailText(moment(value)) : null;
}
function priceLabel(price?: Price) {
  if (price?.kind === 'free') return 'Free';
  if (price?.kind !== 'paid') return null;
  if (price.amount === 0) return 'Free';
  if (typeof price.minimum_amount === 'number' && price.currency) return `From ${price.currency} ${price.minimum_amount.toLocaleString('en-PH')}`;
  return typeof price.amount === 'number' && price.currency ? `${price.currency} ${price.amount.toLocaleString('en-PH')}` : 'Paid · amount not announced';
}
function communityRegistration(state: string) {
  return state === 'approval_required' ? 'Applications open · approval required' : state !== 'unknown' ? registrations[state] || null : null;
}

function TicketOptions({ tickets, event }: { tickets: TicketOption[]; event: Competition }) {
  // A single generic ticket that repeats the event status adds no decision detail.
  const useful = tickets.filter(ticket => eligibilityText(ticket.eligibility) || priceLabel(ticket.price) || knownMoment(ticket.deadline) || detailText(ticket.attendance) || (communityRegistration(ticket.registration_state) && ticket.registration_state !== event.registration_status) || (detailText(ticket.name) && !/^(standard|general admission|default)$/i.test(ticket.name)));
  if (!useful.length) return null;
  const groups = [{access:'public',label:'Standard public tickets'}, {access:'restricted',label:'Restricted tickets'}, {access:'unknown',label:'Other tickets'}];
  return <div className="ticket-options">{groups.map(group => {
    const options = useful.filter(ticket => ticket.access === group.access);
    return options.length > 0 && <div key={group.access}><h4>{group.label}</h4><ul>{options.map((ticket, index) => <li key={`${ticket.name}-${index}`}>
      {detailText(ticket.name) && <strong>{ticket.name}</strong>}{eligibilityText(ticket.eligibility) && <p>{eligibilityText(ticket.eligibility)}</p>}
      {ticket.attendance && <p>{ticket.attendance === 'onsite' ? 'In person' : 'Online'}</p>}
      {communityRegistration(ticket.registration_state) && <p>{communityRegistration(ticket.registration_state)}</p>}
      {priceLabel(ticket.price) && <p>Price: {priceLabel(ticket.price)}</p>}{knownMoment(ticket.deadline) && <p>Registration deadline: {knownMoment(ticket.deadline)}</p>}
    </li>)}</ul></div>;
  })}</div>;
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
function eventDay(event: Competition): string | null {
  return event.status === 'date_conflict' ? null : calendarDay(event.start || event.competition_date || event.parent_event_start);
}
function DayGroups({events, geography, selectedId, onSelect}: {events: Competition[]; geography: string; selectedId?: string; onSelect: (id: string) => void}) {
  // Input is already filtered and stably sorted by eventDay. Never group by a cutoff.
  const groups = new Map<string | null, Competition[]>();
  for (const event of events) {
    const day = eventDay(event);
    const group = groups.get(day);
    if (group) group.push(event);
    else groups.set(day, [event]);
  }
  return <>{Array.from(groups, ([day, listings]) => {
    const id = `${geography}-day-${day || 'unconfirmed'}`;
    const label = day && new Intl.DateTimeFormat('en-US', {timeZone:'Asia/Manila', weekday:'short', month:'short', day:'numeric'}).format(new Date(`${day}T00:00:00+08:00`));
    return <section className="event-day-group" key={day || 'unconfirmed'} aria-labelledby={id}>
      <h4 className="event-day-heading" id={id}>{day ? <time dateTime={day}>{label}</time> : 'Date to confirm'}</h4>
      <div className="event-grid">{listings.map(event => <EventCard event={event} key={event.id} selected={selectedId === event.id} onSelect={onSelect}/>)}</div>
    </section>;
  })}</>;
}
function clockTime(value?: Moment | null): string | null {
  if (value?.precision !== 'datetime' || !calendarDay(value)) return null;
  return new Intl.DateTimeFormat('en-US', {timeZone:'Asia/Manila', hour:'numeric', minute:'2-digit', hour12:true}).format(new Date(value.value!));
}
function scheduleLabel(start?: Moment | null, end?: Moment | null): string | null {
  const endpoint = (value?: Moment | null) => {
    const day = calendarDay(value), time = clockTime(value);
    return day ? `${recorded(day)}${time ? ` · ${time} PHT` : ''}` : knownMoment(value);
  };
  const from = endpoint(start), to = endpoint(end);
  if (!from) return to ? `Ends ${to}` : null;
  if (!to) return from;
  const day = calendarDay(start), endDay = calendarDay(end);
  if (day && day === endDay) {
    const first = clockTime(start), last = clockTime(end);
    if (first && last) {
      const samePeriod = first.slice(-2) === last.slice(-2);
      return `${recorded(day)} · ${samePeriod ? first.slice(0, -3) : first}–${last} PHT`;
    }
    // A date-only start never acquires an invented time from the end.
    return `${recorded(day)}${first ? ` · ${first} PHT` : last ? ` · ends ${last} PHT` : ''}`;
  }
  return `${from} – ${to}`;
}
function locationLabel(event: Competition, includeAttendance = true): string | null {
  const attendanceKey = (text: string) => /^(onsite|on[- ]site|in[-_ ]person)$/i.test(text) ? 'in_person' : /^(online|virtual)$/i.test(text) ? 'online' : /^hybrid$/i.test(text) ? 'hybrid' : text.toLowerCase();
  const parts = [eventVenue(event)?.city || detailText(event.region), event.format === 'unknown' ? null : formats[event.format], ...(event.attendance_options || []).flatMap(option => option.split(/\s+[·/]\s+/)).map(detailText)].filter((part): part is string => !!part);
  const seen = new Set<string>();
  if (event.format === 'hybrid') { seen.add('online'); seen.add('in_person'); }
  const locationParts = includeAttendance ? parts : parts.filter(part => !['in_person', 'online', 'hybrid'].includes(attendanceKey(part))).map(part => part.replace(/^(?:onsite|on[- ]site|in[- ]person|online|virtual|hybrid)\s*[—–:]\s*/i, ''));
  return locationParts.filter(part => { const key = attendanceKey(part); if (seen.has(key)) return false; seen.add(key); return true; }).map(part => ({in_person:'In person', online:'Online', hybrid:'Hybrid'}[attendanceKey(part)] || part)).join(' · ') || null;
}
function attendanceLabel(event: Competition): string | null {
  if (event.format !== 'unknown' && formats[event.format]) return formats[event.format];
  const labels = (event.attendance_options || []).flatMap(option => option.split(/\s+[·/]\s+/)).map(option => {
    const mode = option.split(/\s*[—–:]\s*/)[0].trim();
    return /^(onsite|on[- ]site|in[-_ ]person)$/i.test(mode) ? 'In person' : /^(online|virtual)$/i.test(mode) ? 'Online' : /^hybrid$/i.test(mode) ? 'Hybrid' : null;
  }).filter(label => label !== null);
  return [...new Set(labels)].join(' · ') || null;
}
function safeEventUrl(value?: string | null): string | null {
  try {
    const url = new URL(value || '');
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
function originalEventUrl(event: Competition): string | null {
  return safeEventUrl(event.organizer_event_url) || safeEventUrl(event.announcement_url);
}
function sameEventPage(first?: string | null, second?: string | null): boolean {
  const key = (value?: string | null) => {
    const safe = safeEventUrl(value);
    if (!safe) return null;
    const url = new URL(safe);
    const host = url.hostname.replace(/^www\./, '').replace(/^lu\.ma$/, 'luma.com');
    const meetupId = host === 'meetup.com' && url.pathname.match(/\/events\/(\d+)(?:\/|$)/)?.[1];
    if (meetupId) return `meetup.com/events/${meetupId}`;
    // Remove only tracking parameters; functional query parameters can identify another event.
    for (const key of [...url.searchParams.keys()]) if (/^(utm_|fbclid$|gclid$)/i.test(key)) url.searchParams.delete(key);
    url.searchParams.sort();
    return `${host}${url.port ? ':' + url.port : ''}${url.pathname.replace(/\/$/, '')}${url.search}`;
  };
  const a = key(first), b = key(second);
  return !!a && a === b;
}
function confirmedProof(event: Competition, field: string) {
  const proof = event.field_evidence?.[field];
  return proof && event.announcements.some(announcement => announcement.access === 'full' && sameEventPage(announcement.url, proof.url)) ? proof : null;
}
function confirmedReschedule(event: Competition): boolean {
  const proof = confirmedProof(event, 'lifecycle');
  return event.lifecycle === 'scheduled' && !!proof && !!eventDay(event) && /\brescheduled\b/i.test(proof.quote) && !/\b(if|unless|not|never|may|might|could|whether)\b/i.test(proof.quote) && event.announcements.some(announcement => announcement.access === 'full' && announcement.kind === 'reschedule' && sameEventPage(announcement.url, proof.url));
}
function eventVenue(event: Competition): {city: string | null; detail: string; address: string | null} | null {
  if (!['in_person', 'hybrid'].includes(event.format)) return null;
  // Read only the CURRENT Event location retained by opportunity_pages.py.
  // Never mine descriptions, organizer addresses or older announcement revisions.
  const proof = confirmedProof(event, 'format');
  if (!proof || !sameEventPage(proof.url, originalEventUrl(event))) return null;
  const match = proof.quote.match(/^Schema\.org eventAttendanceMode=[^;]+; location=(.+)$/s);
  if (!match) return null;
  let locations: unknown;
  try { locations = JSON.parse(match[1]); } catch { return null; } // truncated evidence stays broad
  const object = (value: unknown): Record<string, unknown> | null => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
  const text = (value: unknown) => typeof value === 'string' ? detailText(value)?.replace(/\s+([,.;])/g, '$1') || null : null;
  const places = (Array.isArray(locations) ? locations : [locations]).map(object).filter(place => place?.['@type'] === 'Place');
  const venues = places.map(place => {
    const address = object(place!.address);
    const city = text(address?.addressLocality);
    const name = text(place!.name);
    const street = text(address?.streetAddress) || text(place!.address);
    // Split only at the explicitly supplied locality; retain earlier address parts.
    // The final prefix is displayed verbatim, never geocoded or guessed as a city.
    const parts = street?.split(',').map(part => part.trim()).filter(Boolean) || [];
    const cityIndex = city ? parts.findIndex(part => part.toLowerCase() === city.toLowerCase()) : -1;
    const prefix = cityIndex >= 0 ? parts.slice(0, cityIndex) : [];
    const area = prefix.length > 1 ? prefix.pop() : null;
    const locality = [area, city].filter(Boolean).join(', ');
    const detail = [name, locality].filter(Boolean).join(' · ') || street;
    const remaining = cityIndex >= 0 ? prefix.join(', ') : street;
    return detail ? {city, detail, address: remaining && remaining !== detail ? remaining : null} : null;
  }).filter((venue): venue is {city: string | null; detail: string; address: string | null} => !!venue);
  const unique = (values: (string | null)[]) => [...new Set(values.filter((value): value is string => !!value))].join(' / ') || null;
  return venues.length ? {city: unique(venues.map(venue => venue.city)), detail: unique(venues.map(venue => venue.detail))!, address: unique(venues.map(venue => venue.address))} : null;
}
function EventDate({ event }: { event: Competition }) {
  const day = eventDay(event);
  if (!day) return <span className="event-date date-unconfirmed"><Icon name="clock" size={19}/><span>{event.status === 'finished' ? 'Finished · dates unconfirmed' : 'Date unconfirmed'}</span></span>;
  const month = new Intl.DateTimeFormat('en-PH', {month:'short',timeZone:'Asia/Manila'}).format(new Date(day));
  return <time className="event-date" dateTime={day} aria-label={`${!event.start && !event.competition_date && event.parent_event_start ? 'Parent event date' : 'Starts'} ${recorded(day)} (Asia/Manila)`}>
    {!event.start && !event.competition_date && event.parent_event_start && <span className="date-context">Event date</span>}<span className="date-month">{month}</span><strong className="date-day">{Number(day.slice(8,10))}</strong><span className="date-year">{day.slice(0,4)}</span>
  </time>;
}
function EventCard({ event, selected, onSelect }: { event: Competition; selected: boolean; onSelect: (id: string) => void }) {
  const supportedTopics = [...new Set(event.topics || [])].filter(topic => topic in topics);
  const registerBy = calendarDay(event.deadline);
  const submitBy = calendarDay(event.submission_deadline);
  const previewState = !['scheduled','schedule_tba','undated_lead'].includes(event.status) ? states[event.status] : null;
  const location = locationLabel(event);
  const price = priceLabel(event.price);
  const registration = communityRegistration(event.registration_status);
  const hasFacts = event.notices.length > 0 || event.review?.required || event.review?.expired || previewState || price || event.account_required === true || registerBy || submitBy;
  return <article className={`event-card event-${event.status}${selected ? ' is-selected' : ''}`}>
    <div className="event-preview">
      <EventDate event={event}/>
      <div className="event-overview">
        <h3><button className="notice-select" id={`notice-${event.id}`} aria-pressed={selected} aria-controls="pinned-paper" onClick={() => onSelect(event.id)}>{event.name}</button></h3>{detailText(event.organizer) && <p className="organizer">{event.organizer}</p>}
        {(location || supportedTopics.length > 0 || registration) && <div className="event-metadata">
          {location && <p className="event-location"><Icon name={event.format === 'online' ? 'globe' : 'pin'} size={15}/><span>{location}</span></p>}
          {supportedTopics.length > 0 && <div className="event-topics" aria-label="Topics">{supportedTopics.map(topic => <span className="topic-tag" key={topic}>{topics[topic]}</span>)}</div>}
          {registration && <span className={`badge signup-fact registration-${event.registration_status}`}>{registration}</span>}
        </div>}
        {hasFacts && <div className="preview-facts">
          {!event.review?.required && event.notices.length > 0 && <span className="badge notes-flag"><Icon name="info" size={13}/> Notes to check</span>}
          {event.review?.required && <span className="badge review-flag">Flagged for review</span>}
          {event.review?.expired && <span className="badge review-flag">Verification expired</span>}
          {previewState && <span className={`badge state-${event.status}`}>{previewState}</span>}
          {price && <span className={`badge price-fact${price === 'Free' ? ' price-free' : ''}`}>{price === 'Free' || price.startsWith('Paid') ? price : `Paid · ${price}`}</span>}
          {event.account_required === true && <span className="join-fact">Account required</span>}
          {registerBy && <span className="join-fact deadline-fact">Register by <time dateTime={registerBy}>{recorded(registerBy)}</time></span>}
          {submitBy && <span className="join-fact deadline-fact">Submit by <time dateTime={submitBy}>{recorded(submitBy)}</time></span>}
        </div>}
      </div>
    </div>
    <span className="card-arrow" aria-hidden="true">›</span>
  </article>;
}

function FoundNote({event, children}: {event: Competition; children: ReactNode}) {
  const start = event.start || event.competition_date;
  const venue = eventVenue(event);
  const missing = [
    (!calendarDay(start) || event.status === 'date_conflict') && 'confirmed event date',
    (!clockTime(start) || event.status === 'date_conflict') && 'time',
    ['in_person', 'hybrid'].includes(event.format) && (!venue || (venue.detail === venue.city && !venue.address)) && 'exact venue',
    !attendanceLabel(event) && 'attendance format',
    !priceLabel(event.price) && 'cost',
    !communityRegistration(event.registration_status) && 'signup status',
  ].filter(Boolean);
  return <section className="found-note" aria-labelledby="found-note-title">
    <h3 id="found-note-title">What we found</h3>
    {children}
    <p className="missing-fields"><strong>Missing:</strong> {missing.length ? missing.join(', ') : 'None of the tracked fields.'}<span>Based on the saved details; the organizer may have more information.</span></p>
  </section>;
}

// The same evidence-backed detail content now lives on one pinned paper.
function EventPaper({ event }: { event: Competition }) {
  const interests = [...new Set(event.topics || [])].filter(topic => topic in topics).map(topic => topics[topic]);
  const description = detailText(event.description) || detailText(event.summary);
  const organizer = detailText(event.organizer);
  const schedule = event.status === 'date_conflict' ? null : scheduleLabel(event.start || event.competition_date, event.end);
  const parentSchedule = event.status === 'date_conflict' ? null : scheduleLabel(event.parent_event_start, event.parent_event_end);
  const location = locationLabel(event, false);
  const attendance = attendanceLabel(event);
  const eligibility = eligibilityText(event.eligibility);
  const price = priceLabel(event.price);
  const account = event.account_required === true ? 'Required to register' : event.account_required === false ? 'Not required' : null;
  const registration = communityRegistration(event.registration_status);
  const deadlines = [
    ['Registration deadline', knownMoment(event.deadline)],
    ['Submission deadline', knownMoment(event.submission_deadline)],
    ['Registration opens', knownMoment(event.registration_opens)],
  ].filter((row): row is [string, string] => !!row[1]);
  const provenance = [['Posted', detailText(event.posted_at)], ['First seen', detailText(event.first_seen)]].filter((row): row is [string, string] => !!row[1]);
  const originalUrl = originalEventUrl(event);
  const registrationUrl = safeEventUrl(event.registration_url);
  const venue = eventVenue(event);
  const status = event.status !== 'scheduled' ? states[event.status] : confirmedReschedule(event) ? 'Rescheduled' : null;
  const hasCollectedDetails = !!(attendance || interests.length || eligibility || price || account || registration || deadlines.length);
  return <article className="paper" aria-labelledby="paper-title">
      <p className="eyebrow">Pinned notice · {event.geography === 'international_online' ? 'International online' : 'Philippines'}</p>
      <h2 id="paper-title" tabIndex={-1}>{event.name}</h2>
      {organizer && <p className="organizer">{organizer}</p>}
      {(event.review?.required || event.notices.length > 0) && <section className="event-alerts" aria-label="Important event notes"><h3><Icon name="info" size={20}/> Important notes</h3>
        {event.review?.required && <div className="review-note"><p><Icon name="flag" size={16}/><strong>Flagged for review</strong></p>{event.review.reasons.map(reason => <p key={reason}>{reason}</p>)}<p>This listing remains visible while these details are unresolved.</p></div>}
        {event.notices.length > 0 && <div className="notices">{event.notices.map(n => <p key={n}><Icon name="info" size={16}/><span>{n}</span></p>)}</div>}
      </section>}
      <div className="notice-lead">
        <EventDate event={event}/>
        <div className="notice-lead-facts">
          {status && <p className="paper-status">{status}</p>}
          {(schedule || parentSchedule || venue || location) && <dl>
            {schedule && <div className="schedule-detail"><dt>When</dt><dd className="event-schedule">{event.parent_event_start && <span>CTF schedule · </span>}{schedule}</dd></div>}
            {parentSchedule && <div className="parent-schedule"><dt>Parent event schedule</dt><dd><p>{parentSchedule}</p><p className="detail-context">These dates do not establish the complete CTF schedule.</p></dd></div>}
            {(venue || location) && <div className="location-detail"><dt>Where</dt><dd><p className="paper-location">{venue?.detail || location}</p>{venue?.address && <p className="venue-address">{venue.address}</p>}</dd></div>}
          </dl>}
        </div>
      </div>
      <div className="event-detail-body">
        <FoundNote event={event}>
        {hasCollectedDetails && <section className="collected-details" aria-labelledby="collected-details-title">
        <h3 id="collected-details-title" className="sr-only">Event facts</h3>
        <dl className="collected-grid">
          {attendance && <div className="attendance-detail"><dt>How to attend</dt><dd>{attendance}</dd></div>}
          {interests.length > 0 && <div className="interests-detail"><dt>Interests</dt><dd>{interests.join(' · ')}</dd></div>}
          {price && <div className="fact-extra price-detail"><dt>Price</dt><dd>{price}</dd></div>}
          {registration && <div className="signup-detail"><dt>Signup</dt><dd>{registration}</dd></div>}
          {deadlines.map(([label, value]) => <div className="deadline-detail" key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          {eligibility && <div className="fact-extra eligibility-detail"><dt>Who can join</dt><dd>{eligibility}</dd></div>}
          {account && <div className="fact-extra account-detail"><dt>Account</dt><dd>{account}</dd></div>}
        </dl>
        </section>}
        </FoundNote>
        {(originalUrl || registrationUrl) && <div className="actions">
          {originalUrl && <Link href={originalUrl} className="button primary"><span className="organizer-link-label">View organizer’s page</span><span aria-hidden="true">↗</span></Link>}
          {registrationUrl && !sameEventPage(registrationUrl, originalUrl) && <Link href={registrationUrl} className="button secondary">Register <span aria-hidden="true">↗</span></Link>}
        </div>}
        {description && <section className="event-description"><h4>Description</h4><p>{description}</p></section>}
        {!!event.ticket_options?.length && <TicketOptions tickets={event.ticket_options} event={event}/>}
        {provenance.length > 0 && <div className="provenance">{provenance.map(([label, value]) => <span key={label}>{label} <b>{recorded(value)}</b></span>)}</div>}

      </div>
  </article>;
}
function BoardFilters({topic, format, onTopic, onFormat}: {topic: string; format: string; onTopic: (value: string) => void; onFormat: (value: string) => void}) {
  type Filter = 'interest' | 'attendance';
  const [open, setOpen] = useState<Filter | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const triggers = useRef<Partial<Record<Filter, HTMLButtonElement | null>>>({});
  const groups = {
    interest: {label: 'Browse by interest', prefix: 'Interest', all: 'All interests', value: topic, options: topics, change: onTopic},
    attendance: {label: 'How to attend', prefix: 'Attend', all: 'All attendance options', value: format, options: formats, change: onFormat},
  };
  const close = () => { if (open) triggers.current[open]?.focus({preventScroll: true}); setOpen(null); };
  useLayoutEffect(() => {
    if (open) panel.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus({preventScroll: true});
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const dismiss = (event: Event) => { if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(null); };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('focusin', dismiss);
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('focusin', dismiss); };
  }, [open]);
  const group = open ? groups[open] : null;
  return <div className="filters" ref={root} onKeyDown={event => {
    if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); close(); }
  }}>
    {(Object.keys(groups) as Filter[]).map(key => {
      const item = groups[key];
      const text = item.value ? `${item.prefix} · ${item.options[item.value]}` : item.label;
      return <button type="button" key={key} ref={element => { triggers.current[key] = element; }}
        className={`filter-trigger${item.value ? ' is-active' : ''}`} aria-label={item.value ? `${item.label}: ${text}` : item.label}
        aria-expanded={open === key} aria-controls={`filter-${key}-panel`} title={text}
        onClick={() => setOpen(current => current === key ? null : key)}
        onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          if (open === key) panel.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus({preventScroll: true});
          else setOpen(key);
        } }}>
        <span>{text}</span><Icon name="chevron" size={16}/>
      </button>;
    })}
    {open && group && <div key={open} id={`filter-${open}-panel`} ref={panel} className={`filter-panel filter-panel-${open}`} role="group" aria-labelledby={`filter-${open}-heading`}
      onKeyDown={event => {
        const buttons = Array.from(panel.current?.querySelectorAll<HTMLButtonElement>('.filter-chip') || []);
        const index = buttons.indexOf(event.target as HTMLButtonElement);
        if (index < 0) return;
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
          : ['ArrowRight', 'ArrowDown'].includes(event.key) ? (index + 1) % buttons.length
          : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? (index + buttons.length - 1) % buttons.length : null;
        if (next !== null) { event.preventDefault(); buttons[next]?.focus(); }
      }}>
      <h2 id={`filter-${open}-heading`}>{group.label}</h2>
      <div className="filter-chips">{[['', group.all], ...Object.entries(group.options)].map(([value, label]) =>
        <button type="button" className="filter-chip" key={value} aria-pressed={group.value === value}
          onClick={() => { group.change(value); close(); }}>
          {group.value === value && <span aria-hidden="true">✓ </span>}{label}
        </button>
      )}</div>
    </div>}
    <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">{topic ? `Interest: ${topics[topic]}.` : 'All interests.'} {format ? `Attendance: ${formats[format]}.` : 'All attendance options.'}</span>
  </div>;
}

function verifiedTimestamp(value?: string | null): string | null {
  if (typeof value !== 'string') return null;
  const parts = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i);
  if (!parts || !Number.isFinite(Date.parse(value))) return null;
  const [, year, month, day, hour, minute, second] = parts.map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return month >= 1 && month <= 12 && day >= 1 && day <= lastDay && hour < 24 && minute < 60 && second < 60 ? value : null;
}

function useActivityScrollbar() {
  const [active, setActive] = useState(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reveal = useCallback(() => {
    setActive(true);
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setActive(false), 1000);
  }, []);
  useEffect(() => () => { if (idleTimer.current) clearTimeout(idleTimer.current); }, []);
  return { 'data-scrolling': active, onPointerEnter: reveal, onPointerMove: reveal, onPointerDown: reveal, onPointerUp: reveal,
    onTouchStart: reveal, onTouchMove: reveal, onKeyDown: reveal, onFocus: reveal, onWheel: reveal, onScroll: reveal };
}

// Decorative reference notes enter only after scrolling, below the working area.
// They never reserve space in the initial view or intercept an interaction.
function BoardDoodles() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const update = () => {
      const distance = Math.max(window.scrollY, document.getElementById('pinned-paper')?.scrollTop || 0);
      setStage(distance >= 110 ? 2 : distance >= 12 ? 1 : 0);
    };
    document.addEventListener('scroll', update, { capture: true, passive: true });
    return () => document.removeEventListener('scroll', update, true);
  }, []);
  if (!stage) return null;
  return <div className="board-doodles" data-revealed="true" data-stage={stage} aria-hidden="true">
    <svg viewBox="0 0 96 95" focusable="false"><path d="M3 3h90v78L81 92H3z" fill="#f6dd88"/><path d="M80 92l2-13 11 2" fill="#8d7b4933"/><path d="m33 1 29 1-1 9-29-2z" fill="#f3e6be" opacity=".83"/><g fill="none" stroke="#364035" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="46" cy="38" r="6"/><path d="M45 45l-2 16m1-11-9 5-5-7m14 1 9-4 6-9M43 61l-9 11-8 1m17-12 8 9 7 1M59 36l5-4m1-4 3-2M23 77q21 2 41-1"/><path d="m60 29 5-12 12 5-5 12z" fill="#fff5ce"/><path d="m64 23 7 3m-8 0 6 3"/></g></svg>
    <svg viewBox="0 0 96 95" focusable="false"><path d="M3 3h90v78L81 92H3z" fill="#d5e3b4"/><path d="M80 92l2-13 11 2" fill="#8d7b4933"/><path d="m33 1 29 1-1 9-29-2z" fill="#f3e6be" opacity=".83"/><g fill="none" stroke="#364035" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="49" cy="38" r="6"/><path d="m48 45-2 16 10 2 5 11m-15-13-8 2-2 10m10-23 10 5 8-2m-23 2-6 6M32 64h20m-18 1-2 12m18-12 2 11M55 59h22m-4 1v18M58 57l4-11 12 1-3 10zM20 78q28 2 58 0"/><path d="m29 30-4-4m9 0-1-6"/></g></svg>
  </div>;
}

export default function App() {
  // Synchronous hydration chooses the first rendered screen, including on Reload.
  const [data, setData] = useState<Directory | null>(readSavedBoard);
  const hasBoard = useRef(data !== null);
  const activeRequest = useRef<AbortController | null>(null);
  const [requestState, setRequestState] = useState<RequestState>('pending');
  const loading = requestState === 'pending';
  const [error, setError] = useState('');
  const [section, setSection] = useState<Section>('upcoming');
  const [query, setQuery] = useState('');
  const [topic, setTopic] = useState('');
  const [format, setFormat] = useState('');
  const load = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const refreshing = hasBoard.current;
    setRequestState('pending'); setError('');
    try {
      const response = await fetch('/api/events', {signal: controller.signal});
      if (!response.ok) throw new Error(`Server returned ${response.status}.`);
      const next: unknown = await response.json();
      if (!usableDirectory(next)) throw new Error('Unexpected server response.');
      if (controller.signal.aborted || activeRequest.current !== controller) return;
      saveBoard(next);
      hasBoard.current = true;
      setData(next);
      setRequestState(refreshing ? 'success' : 'idle');
    } catch (e) {
      if (!controller.signal.aborted && activeRequest.current === controller) {
        setError(e instanceof Error ? e.message : 'Could not load listings.');
        setRequestState('error');
      }
    }
  }, []);
  useEffect(() => { void load(); return () => activeRequest.current?.abort(); }, [load]);
  const lastUpdated = verifiedTimestamp(data?.listings_updated_at);
  // Only public browse controls affect visibility. Legacy URL/storage registration
  // values are not read or applied; signup facts remain part of each notice.
  const hasFilters = !!(query.trim() || topic || format);
  const clear = () => { setQuery(''); setTopic(''); setFormat(''); };
  const browseable = useMemo(() => (data?.events || []).filter(e =>
    (!format || e.format === format) &&
    [e.name, e.organizer, e.eligibility, e.region, e.summary, e.description].join(' ').toLowerCase().includes(query.trim().toLowerCase())
  ), [data, format, query]);
  const matching = useMemo(() => browseable.filter(event => !topic || event.topics?.includes(topic)), [browseable, topic]);
  const counts = Object.fromEntries(sections.map(key => [key, matching.filter(event => inSection(event, key)).length]));
  const filtered = useMemo(() => matching.filter(e => inSection(e, section)).sort((a, b) => {
    const aDay = eventDay(a), bDay = eventDay(b);
    // Unresolved dates stay last in either direction; same-day ties stay stable.
    if (!aDay) return bDay ? 1 : 0;
    if (!bDay) return -1;
    return section === 'finished' ? bDay.localeCompare(aDay) : aDay.localeCompare(bDay);
  }), [matching, section]);
  // Match the Manila calendar date shown on each card; undated cards come last.
  // Stable ties preserve source order without inventing times for date-only facts.
  // Group after sorting to keep PH and international-online opportunities separate.
  const international = filtered.filter(event => event.geography === 'international_online');
  const local = filtered.filter(event => event.geography !== 'international_online');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const paperRef = useRef<HTMLDivElement>(null);
  const scrollbar = useActivityScrollbar();
  const listScrollbar = useActivityScrollbar();
  const returnPosition = useRef<{ y: number; id: string } | null>(null);
  const selected = filtered.find(event => event.id === selectedId) || local[0] || international[0];
  const selectEvent = (id: string) => {
    setSelectedId(id);
    if (window.matchMedia('(max-width: 760px)').matches) {
      returnPosition.current = { y: window.scrollY, id };
      setReading(true);
    }
  };
  const backToBoard = useCallback(() => setReading(false), []);
  useLayoutEffect(() => {
    if (reading) {
      document.getElementById('paper-title')?.focus({ preventScroll: true });
      paperRef.current?.closest('.pinned-detail')?.scrollIntoView({ block: 'start', behavior: 'instant' });
    } else if (returnPosition.current) {
      const { y, id } = returnPosition.current;
      returnPosition.current = null;
      document.getElementById(`notice-${id}`)?.focus({ preventScroll: true });
      window.scrollTo({ top: y, behavior: 'instant' });
    }
  }, [reading]);
  useLayoutEffect(() => {
    // A filter edit returns to results without stealing focus from the filter.
    // Explicit Back/Escape, in contrast, restores the captured card and scroll.
    returnPosition.current = null;
    setReading(false);
  }, [query, topic, format, section]);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)');
    const resize = () => setReading(false);
    media.addEventListener('change', resize);
    return () => media.removeEventListener('change', resize);
  }, []);
  useEffect(() => {
    if (!reading) return;
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') backToBoard(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [reading, backToBoard]);
  // Only the paper scroll resets on desktop selection. The list DOM and page stay put.
  useLayoutEffect(() => { if (paperRef.current) paperRef.current.scrollTop = 0; }, [selected?.id]);
  const announcement = loading ? data ? 'Checking listings…' : 'Loading event listings…'
    : error ? data ? 'Couldn’t refresh · Showing saved listings' : 'Couldn’t load event listings. Please try again.'
    : requestState === 'success' ? 'Board up to date' : 'Event board ready.';
  return <><a href="#events" className="skip">Skip to events</a>
    <header id="top"><nav className="shell topbar" aria-label="Main navigation">
      <a className="brand" href="#top" aria-label="CommunIT">
        <svg className="board-logo" width="28" height="24" viewBox="0 0 80 64" aria-hidden="true" focusable="false"><rect x="0" y="1" width="80" height="62" rx="10" fill="#735038"/><rect x="7.5" y="8" width="65" height="48" rx="3.5" fill="#B98254"/><rect x="17.6" y="18.5" width="21" height="27" rx="1.4" fill="#FDF1D2"/><rect x="46.4" y="29" width="17" height="16" rx="1.4" fill="#245643"/><circle cx="28" cy="23" r="2" fill="#245643"/><path d="M22 32h12m-12 5h9" stroke="#735038" strokeWidth="1.8" strokeLinecap="round"/></svg>
        <span>Commun<strong>IT</strong></span>
      </a>
      <label className="nav-search"><span className="sr-only">Search events</span><span className="search-wrap"><Icon name="search"/><input type="search" placeholder="Event, organizer, or school" value={query} onChange={e => setQuery(e.target.value)}/></span></label>
      <div className="nav-links"><a href="#events">Events</a><span className="country" role="img" aria-label="Philippines, Philippine Time" title="All dates and times use Asia/Manila (Philippine Time)"><Icon name="globe" size={15}/><span aria-hidden="true">Philippines · PHT</span></span></div>
    </nav></header>
    <div className="refresh-rail shell">{data && <RefreshSlip state={requestState} retry={() => void load()}/>}</div>
    <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</p>
    <main id="events" className="shell">
      <h1 className="sr-only">Tech events</h1>
      {!data ? <OpeningTicket error={error} retry={() => void load()}/> : <>
      <div className={`board-split${reading && selected ? ' is-reading' : ''}`}>
        <div className="browse-column">
          <section className="controls" aria-label="Find events">
            <BoardFilters topic={topic} format={format} onTopic={setTopic} onFormat={setFormat}/>
            {lastUpdated && <p className="directory-updated" role="status"><Icon name="clock" size={16}/><span><strong>Listings last updated: </strong><time dateTime={lastUpdated} title="Latest verified event-page check among saved listings; not every listing was checked at this time.">{recorded(lastUpdated, true)}</time></span></p>}
            {hasFilters && <div className="filter-footer"><button className="text-button" onClick={clear}>Clear filters</button></div>}
          </section>
          <div className="board-section" data-section={section}>
            <div className="control-top">
              <div className="tabs" role="tablist" aria-label="Event section">{sections.map(tab => <button key={tab} data-section={tab} id={`tab-${tab}`} role="tab" aria-selected={section === tab} aria-controls="results" tabIndex={section === tab ? 0 : -1} className={section === tab ? 'active' : ''} onClick={() => setSection(tab)} onKeyDown={e => {
                if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {
                  e.preventDefault();
                  const next = e.key === 'Home' ? sections[0] : e.key === 'End' ? sections[sections.length - 1] : sections[(sections.indexOf(tab) + (e.key === 'ArrowRight' ? 1 : sections.length - 1)) % sections.length];
                  setSection(next); document.getElementById(`tab-${next}`)?.focus();
                }
              }}>{sectionLabels[tab]}{(tab !== 'archived' || !data || counts[tab] > 0) && <span>{data ? counts[tab] : '—'}</span>}</button>)}</div>
            </div>
            <section id="results" className="board" role="tabpanel" aria-labelledby={`tab-${section}`}>
              <p className="results-count sr-only" aria-live="polite">{data ? `${filtered.length} ${filtered.length === 1 ? 'event' : 'events'}${hasFilters ? ' matching your filters' : ''}` : loading ? 'Checking the directory…' : 'Listings unavailable'}</p>
              {filtered.length ?
                <div className="board-list activity-scroll" key={section} role="region" aria-label="Event listings" tabIndex={0} {...listScrollbar}>
                  {local.length > 0 && <section className="opportunity-group" aria-labelledby="ph-opportunities-title"><h3 id="ph-opportunities-title">PH opportunities</h3><DayGroups events={local} geography="ph" selectedId={selected?.id} onSelect={selectEvent}/></section>}
                  {international.length > 0 && <section className="opportunity-group" aria-labelledby="international-online-title"><h3 id="international-online-title">International online opportunities</h3><DayGroups events={international} geography="international" selectedId={selected?.id} onSelect={selectEvent}/></section>}
                </div> : data ? <div className="empty" key={section}><span className="empty-icon"><Icon name={hasFilters ? 'search' : 'flag'} size={30}/></span><h3>{hasFilters ? 'No matches for these filters.' : section === 'confirmation' ? 'No events needing confirmation.' : section === 'archived' ? 'No archived leads.' : `No ${section === 'finished' ? 'past' : 'upcoming'} events recorded yet.`}</h3><p>{hasFilters ? 'Try another interest, attendance option, or search term.' : 'Only collected announcements appear here. Check back later for more events.'}</p>{hasFilters && <button onClick={clear} className="button primary">Clear filters</button>}</div> : null}
            </section>
          </div>
        </div>
        {selected && <aside className="pinned-detail" aria-label="Pinned event details">
          <button className="back-to-board" onClick={backToBoard}>← Back to the board</button>
          <div id="pinned-paper" ref={paperRef} className="paper-scroll activity-scroll" role="region" aria-label="Selected event notice" tabIndex={0} {...scrollbar}>
            <EventPaper event={selected} key={selected.id}/>
          </div>
        </aside>}
      </div>
      <p className="date-note"><Icon name="clock" size={16}/> Confirmed times use Manila time. Ambiguous dates stay as the organizer wrote them.</p>
      <BoardDoodles/>
    <section className="directory-tools" aria-labelledby="directory-tools-title">
      <div className="directory-tools-heading"><div><h2 id="directory-tools-title">Directory updates</h2><p>Reload the saved event list.</p></div><div className="result-tools"><button className="button secondary refresh" aria-label="Refresh saved listings" title="Refresh saved listings" disabled={loading} onClick={() => void load()}><Icon name="refresh"/>Refresh saved listings</button></div></div>
      <p className="directory-time">{data && `Directory loaded ${recorded(data.generated_at, true)}.`}</p>
    </section>
    </>}
    </main><footer className="shell"><span><Icon name="flag" size={19}/> Built for the Philippine tech community.</span><a href="#top">Back to top</a></footer></>;
}
