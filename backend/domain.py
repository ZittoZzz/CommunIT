"""Conservative identity, date precision, and lifecycle rules. No date guessing."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone, date, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

MANILA = ZoneInfo('Asia/Manila')


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def canonical_url(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        return None
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
    # Keep semantic Facebook identifiers, e.g. story_fbid, fbid, id.
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urlencode(sorted(query)), ''))


def publisher_url(url, rules=None):
    """Apply only publisher URL conventions verified during source setup.

    Trailing slashes are not generally interchangeable. Exact hosts and path
    prefixes limit this rule to a publisher's observed canonical article URLs.
    """
    canonical = canonical_url(url)
    if not canonical or not rules:
        return canonical
    parsed = urlsplit(canonical)
    if (parsed.hostname not in rules.get('hosts', []) or
            not any(parsed.path.startswith(prefix) for prefix in rules.get('path_prefixes', []))):
        return canonical
    if rules.get('trailing_slash') is True and '.' not in parsed.path.rstrip('/').rsplit('/', 1)[-1]:
        return urlunsplit(parsed._replace(path=parsed.path.rstrip('/') + '/'))
    return canonical


def facebook_post(url):
    """Identify linked post URLs without requesting Facebook or inferring ownership."""
    canonical = canonical_url(url)
    if not canonical:
        return None
    p = urlsplit(canonical)
    if p.hostname not in ('facebook.com', 'www.facebook.com', 'm.facebook.com'):
        return None
    query = dict(parse_qsl(p.query))
    if p.path in ('/story.php', '/permalink.php') and query.get('story_fbid') and query.get('id'):
        return {'url': canonical, 'account': query['id'], 'post': query['story_fbid']}
    if p.path in ('/photo.php', '/photo') and query.get('fbid'):
        return {'url': canonical, 'account': query.get('id'), 'post': query['fbid']}
    match = re.match(r'^/([^/]+)/(?:posts|photos|videos)/(?:[^/]+/)*([^/]+)/?$', p.path)
    if match:
        return {'url': canonical, 'account': match[1], 'post': match[2]}
    return None


def norm(text):
    text = unicodedata.normalize('NFKC', str(text)).lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


def event_key(identity):
    # Dates and registration URLs are deliberately not identity components.
    parts = [identity.get(k, '') for k in ('organizer_key', 'series', 'edition', 'region', 'stage')]
    if not all(parts):
        raise ValueError('Identity requires organizer, series, edition, region, and stage')
    return hashlib.sha256('|'.join(norm(x) for x in parts).encode()).hexdigest()[:24]


def moment(raw, value=None, precision='text', tz=None):
    return {'raw': raw.strip(), 'value': value, 'precision': precision, 'timezone': tz}


def in_window(value, now, days):
    """Pilot window shared by organizer calendars; date-only boundaries are unresolved."""
    end = now + timedelta(days=days)
    dt = instant(value)
    if dt:
        return now <= dt < end
    if value and value['precision'] == 'date':
        return now.astimezone(MANILA).date().isoformat() < value['value'] < end.astimezone(MANILA).date().isoformat()
    return False


def parse_moment(raw):
    """Only convert explicit ISO or unambiguous named-month dates; never infer year/zone."""
    raw = raw.strip()
    try:
        iso = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if 'T' in raw and iso.tzinfo:
            return moment(raw, iso.isoformat(), 'datetime', 'UTC' if iso.utcoffset().total_seconds() == 0 else str(iso.tzinfo))
    except ValueError:
        pass
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        try:
            datetime.strptime(raw, '%Y-%m-%d')
            return moment(raw, raw, 'date')
        except ValueError:
            pass
    cleaned = re.sub(r'(?<=\d)(?:st|nd|rd|th)\b', '', raw, flags=re.I)
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'):
        try:
            d = datetime.strptime(cleaned, fmt)
            return moment(raw, d.date().isoformat(), 'date')
        except ValueError:
            pass
    match = re.fullmatch(r'(.+?)\s+(?:at\s+)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*(PHT|Asia/Manila|UTC|GMT|UTC\+0?8(?::00)?)', cleaned, re.I)
    if match:
        date_part, time_part, zone = match.groups()
        d = parse_moment(date_part)
        if d['precision'] == 'date':
            for fmt in ('%H:%M', '%I:%M%p', '%I:%M %p'):
                try:
                    t = datetime.strptime(time_part.upper(), fmt).time()
                    z = timezone.utc if zone.upper() in ('UTC', 'GMT') else MANILA
                    value = datetime.combine(datetime.fromisoformat(d['value']).date(), t, z)
                    return moment(raw, value.isoformat(), 'datetime', 'UTC' if z == timezone.utc else 'Asia/Manila')
                except ValueError:
                    pass
    return moment(raw)


def parse_date_range(raw):
    """Expand only explicit same-month day ranges; never borrow the posting year."""
    match = re.fullmatch(r'([A-Za-z]+)\s+(\d{1,2})\s*[-–—]\s*(\d{1,2})(?:,?\s+(20\d{2}))?', raw.strip())
    if not match:
        return None
    month, first, last, year = match.groups()
    if not year:
        # Keep the complete organizer wording, including its missing year.
        return moment(raw), None
    start = parse_moment(f'{month} {first}, {year}')
    end = parse_moment(f'{month} {last}, {year}')
    if start['precision'] != 'date' or end['precision'] != 'date' or end['value'] < start['value']:
        return None
    return start, end


def instant(value):
    if not value or value.get('precision') != 'datetime' or not value.get('timezone'):
        return None
    try:
        dt = datetime.fromisoformat(value['value'].replace('Z', '+00:00'))
        return dt if dt.tzinfo else None
    except (ValueError, TypeError, KeyError):
        return None


def expired(value, now):
    dt = instant(value)
    if dt:
        return now > dt
    if value and value.get('precision') == 'date' and value.get('timezone'):
        return calendar_day_passed(value, now)
    return False


def manila_day(value):
    """The listing's calendar day; a date-only fact stays a date, not an instant."""
    if not value:
        return None
    dt = instant(value)
    if dt:
        return dt.astimezone(MANILA).date()
    if value.get('precision') != 'date':
        return None
    try:
        return date.fromisoformat(value['value'])
    except (ValueError, TypeError, KeyError):
        return None


def calendar_day_passed(value, now):
    """Expire calendar-day placement at the next Manila day, without a start time."""
    day = manila_day(value)
    return day is not None and now.astimezone(MANILA).date() > day


def lifecycle(event, now=None):
    now = now or datetime.now(timezone.utc)
    state = event.get('lifecycle', 'scheduled')
    if state in ('cancelled', 'postponed'):
        status = state
    elif state == 'finished':
        status = 'finished'
    elif event.get('date_conflicts'):
        status = 'date_conflict'
    elif expired(event.get('end'), now):
        status = 'finished'
    elif instant(event.get('end')) and instant(event.get('start')) and instant(event['start']) <= now:
        status = 'live'
    elif calendar_day_passed(event.get('end') or event.get('competition_date') or event.get('start'), now):
        status = 'past_date'
    elif instant(event.get('start')) and instant(event['start']) <= now:
        status = 'end_unconfirmed'
    else:
        status = 'scheduled' if event.get('start') or event.get('competition_date') else 'schedule_tba'
    reg = event.get('registration_state') or 'unknown'
    if status in ('finished', 'cancelled') or expired(event.get('deadline'), now):
        reg = 'closed'
    elif status == 'postponed':
        reg = 'unknown'
    elif status in ('past_date', 'date_conflict') and reg in ('open', 'approval_required', 'waitlisted', 'not_yet_open'):
        # Old or conflicting schedules do not establish current entry or closure.
        reg = 'unknown'
    elif instant(event.get('registration_opens')) and instant(event['registration_opens']) > now:
        reg = 'not_yet_open'
    section = {'finished': 'finished', 'past_date': 'past', 'date_conflict': 'unconfirmed'}.get(status, 'upcoming')
    return status, reg, section


REGIONS = {
    'NCR': r'\b(?:NCR|Metro Manila|National Capital Region)\b',
    'CAR': r'\b(?:Cordillera|Baguio|CAR)\b',
    'Region I — Ilocos': r'\b(?:Ilocos|Region (?:I|1))\b',
    'Region II — Cagayan Valley': r'\b(?:Cagayan Valley|Tuguegarao|Region (?:II|2))\b',
    'Region III — Central Luzon': r'\b(?:Central Luzon|Pampanga|Clark|Region (?:III|3))\b',
    'Region IV-A — CALABARZON': r'\b(?:CALABARZON|Region (?:IV-A|4A))\b',
    'MIMAROPA': r'\bMIMAROPA\b',
    'Region V — Bicol': r'\b(?:Bicol|Region (?:V|5))\b',
    'Region VI — Western Visayas': r'\b(?:Western Visayas|Region (?:VI|6))\b',
    'Region VII — Central Visayas': r'\b(?:Central Visayas|Region (?:VII|7))\b',
    'Region VIII — Eastern Visayas': r'\b(?:Eastern Visayas|Region (?:VIII|8))\b',
    'Region IX — Zamboanga': r'\b(?:Zamboanga|Region (?:IX|9))\b',
    'Region X — Northern Mindanao': r'\b(?:Northern Mindanao|Region (?:X|10))\b',
    'Region XI — Davao': r'\b(?:Davao|Region (?:XI|11))\b',
    'Region XII — SOCCSKSARGEN': r'\b(?:SOCCSKSARGEN|Region (?:XII|12))\b',
    'Region XIII — Caraga': r'\b(?:Caraga|Region (?:XIII|13))\b',
    'BARMM': r'\b(?:BARMM|Bangsamoro)\b',
    'Negros Island Region': r'\b(?:Negros Island|NIR)\b',
}


def region_from(text, default='Unspecified'):
    for region, pattern in REGIONS.items():
        if re.search(pattern, text, re.I):
            return region
    return default
