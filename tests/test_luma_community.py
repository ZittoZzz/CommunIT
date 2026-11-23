"""Synthetic public Luma calendar pages exercise the normal storage/read path."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
import json

import pytest

from backend.collect import collect
from backend.db import connect, events, source_states
from backend.luma import parse_event
from backend.network import FetchError


NOW = datetime(2035, 11, 22, 13, tzinfo=timezone.utc)
CALENDAR = 'https://luma.com/example-ai?k=c'
EVENT = 'https://luma.com/sample-ai'
SOURCE = {'id': 'luma-ai-test', 'name': 'Example AI', 'kind': 'luma',
          'url': CALENDAR, 'page_kind': 'calendar', 'event_scope': 'community',
          'topic': 'ai', 'window_days': 45}


def page(data, kind='event', controls=True):
    payload = {'props': {'pageProps': {'initialData': {'kind': kind, 'data': data}}}}
    tickets = ''.join('<div>' + escape(ticket['name']) + '</div>'
                      for ticket in data.get('ticket_types', []))
    button = '<button type="button">Request to Join</button>' if controls else ''
    return ('<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload)
            + '</script>' + tickets + button)


def calendar(*slugs):
    return {'calendar': {'api_id': 'cal-example', 'name': 'Example AI'},
            'upcoming': {'entries': [{'event': {'url': slug}} for slug in slugs],
                         'has_more': False},
            'upcoming_event_count': len(slugs)}


def detail():
    return {
        'calendar': {'api_id': 'cal-example', 'name': 'Example AI'},
        'event': {'api_id': 'evt-sample', 'calendar_api_id': 'cal-example',
                  'name': 'Community AI Project Showcase',
                  'start_at': '2035-11-29T07:00:00Z', 'end_at': '2035-11-29T10:00:00Z',
                  'timezone': 'Asia/Manila', 'location_type': 'offline',
                  'geo_address_info': {'country_code': 'PH', 'country': 'Philippines',
                                       'city': 'Quezon City'}},
        'description_mirror': 'Explore responsible artificial intelligence with our community. '
                              'Public standard tickets allow onsite or online attendance. '
                              'Fellow tickets require completion of the training program.',
        'hosts': [{'api_id': 'usr-example', 'name': 'Example AI'}],
        'registration_availability': 'open',
        'ticket_info': {'require_approval': True, 'is_free': True},
        'ticket_types': [
            {'api_id': 'ticket-onsite', 'name': 'Standard - Onsite',
             'description': 'Public onsite attendance.', 'require_approval': True,
             'is_hidden': False, 'is_disabled': False, 'type': 'free', 'cents': None,
             'valid_end_at': '2035-11-29T10:00:00Z'},
            {'api_id': 'ticket-online', 'name': 'Standard - Online',
             'description': 'Public online attendance.', 'require_approval': True,
             'is_hidden': False, 'is_disabled': False, 'type': 'free', 'cents': None,
             'valid_end_at': '2035-11-29T10:00:00Z'},
            {'api_id': 'ticket-fellow', 'name': 'Fellow - Onsite',
             'description': 'Only fellows who completed the training program may apply.',
             'require_approval': True, 'is_hidden': False, 'is_disabled': False,
             'type': 'free', 'cents': None},
        ],
    }


class Pages:
    """Unknown URLs fail locally: no search, event seeds, or network fallback."""
    def __init__(self, overrides=None):
        self.values = {CALENDAR: page(calendar('sample-ai'), 'calendar'), EVENT: page(detail())}
        self.values.update(overrides or {})
        self.requests = []

    def public_page(self, url, allowed_hosts=None):
        self.requests.append(url)
        value = self.values[url]
        if isinstance(value, Exception):
            raise value
        return value.encode()


def run(pages=None, *, db=None, at=NOW, source=None):
    db = db or connect(':memory:')
    return db, collect(db, [source or SOURCE], client=pages or Pages(), now=at)


def stored_payload(db):
    return json.loads(db.execute('SELECT payload FROM announcements').fetchone()[0])


def attendance_modes(event):
    return {label.split()[0].lower() for label in event['attendance_options']}


def test_calendar_only_discovery_reaches_normal_listing_with_separate_field_evidence():
    pages = Pages()
    db, report = run(pages)
    assert pages.requests == [CALENDAR, EVENT]
    result, = report['sources']
    assert result['status'] == 'ok' and result['discovered'] == result['accepted'] == 1
    event, = events(db, NOW)
    assert event['name'] == 'Community AI Project Showcase'
    assert event['organizer'] == 'Example AI'
    assert event['topic'] == 'ai' and event['geography'] == 'PH'
    assert event['format'] == 'hybrid' and event['section'] == 'upcoming'
    assert event['registration_status'] == 'approval_required'
    assert event['registration_url'] == EVENT and event['announcement_url'] == EVENT
    assert event['price'] == {'kind': 'unknown'}
    assert event['deadline'] is None
    assert event['start']['value'] == '2035-11-29T15:00:00+08:00'
    assert event['end']['value'] == '2035-11-29T18:00:00+08:00'
    assert attendance_modes(event) == {'onsite', 'online'}
    assert event['announcements'][0]['discovery_path'] == [CALENDAR, EVENT]
    payload = stored_payload(db)
    assert payload['facts']['submission_deadline'] is None and payload['posted_at'] is None
    for field in ('organizer', 'start', 'end', 'geography', 'format', 'price', 'eligibility', 'registration_state'):
        assert payload['field_evidence'][field]['url'] in (CALENDAR, EVENT)
        assert payload['field_evidence'][field]['quote']
    db.close()


def test_public_and_restricted_ticket_conditions_are_not_conflated():
    db, _ = run()
    event, = events(db, NOW)
    tickets = {ticket['name']: ticket for ticket in event['ticket_options']}
    assert tickets['Standard - Onsite']['access'] == tickets['Standard - Online']['access'] == 'public'
    assert tickets['Fellow - Onsite']['access'] == 'restricted'
    assert tickets['Fellow - Onsite']['eligibility'] == 'Only fellows who completed the training program may apply.'
    assert tickets['Standard - Onsite']['attendance'] == 'onsite'
    assert tickets['Standard - Online']['attendance'] == 'online'
    assert all(ticket['price'] == {'kind': 'unknown'} for ticket in tickets.values())
    assert 'standard' in event['eligibility'].lower() or 'public' in event['eligibility'].lower()
    db.close()


def test_approval_requirement_is_not_a_membership_restriction():
    data = detail()
    for ticket in data['ticket_types'][:2]:
        ticket['description'] = 'Organizer approval required.'
    db, _ = run(Pages({EVENT: page(data)}))
    event, = events(db, NOW)
    assert event['registration_status'] == 'approval_required'
    assert all(ticket['access'] == 'public' for ticket in event['ticket_options'][:2])
    db.close()


def test_structured_membership_restriction_overrides_standard_ticket_name():
    data = detail()
    for ticket in data['ticket_types'][:2]:
        ticket['membership_restriction'] = {'membership_type': 'active_member'}
    db, _ = run(Pages({EVENT: page(data)}))
    event, = events(db, NOW)
    assert all(ticket['access'] == 'restricted' for ticket in event['ticket_options'])
    assert event['registration_status'] not in ('open', 'approval_required')
    db.close()


def test_identical_saved_response_replay_keeps_first_seen_and_one_record():
    pages = Pages()
    db, first = run(pages)
    before = events(db, NOW)[0]
    original = stored_payload(db)
    _, second = run(Pages(deepcopy(pages.values)), db=db, at=NOW + timedelta(hours=1))
    after = events(db, NOW)[0]
    assert first['events'] == second['events'] == 1
    assert first['announcements'] == second['announcements'] == 1
    assert second['sources'][0]['new_announcements'] == 0
    assert before['id'] == after['id'] and before['first_seen'] == after['first_seen']
    assert before['announcements'][0]['first_seen'] == after['announcements'][0]['first_seen']
    assert after['announcements'][0]['revision_count'] == 1
    assert stored_payload(db) == original
    db.close()


@pytest.mark.parametrize('availability,waitlist,expected', [
    ('closed', False, 'closed'), ('sold_out', False, 'closed'),
    ('open', True, 'waitlisted'), ('waitlist', False, 'waitlisted'),
])
def test_closed_or_waitlist_cannot_become_open_applications(availability, waitlist, expected):
    data = detail()
    data.update(registration_availability=availability, waitlist_active=waitlist)
    db, _ = run(Pages({EVENT: page(data)}))
    assert events(db, NOW)[0]['registration_status'] == expected
    db.close()


@pytest.mark.parametrize('reason', ['disabled', 'hidden', 'restricted_only', 'no_control', 'disabled_control'])
def test_no_available_public_application_route_is_not_actionable(reason):
    data = detail()
    if reason in ('disabled', 'hidden'):
        for ticket in data['ticket_types'][:2]:
            ticket['is_' + reason] = True
    if reason == 'restricted_only':
        data['ticket_types'] = data['ticket_types'][2:]
    raw = page(data, controls=reason != 'no_control')
    if reason == 'disabled_control':
        raw = raw.replace('<button type=', '<button disabled type=')
    db, _ = run(Pages({EVENT: raw}))
    assert events(db, NOW)[0]['registration_status'] not in ('open', 'approval_required')
    db.close()


@pytest.mark.parametrize('attendance,expected', [('onsite', 'in_person'), ('online', 'online')])
def test_one_public_attendance_mode_does_not_inherit_restricted_mode(attendance, expected):
    data = detail()
    chosen = next(t for t in data['ticket_types'][:2] if t['name'].lower().endswith(attendance))
    data['ticket_types'] = [chosen, data['ticket_types'][2]]
    db, _ = run(Pages({EVENT: page(data)}))
    event, = events(db, NOW)
    assert event['format'] == expected
    assert attendance_modes(event) == {attendance}
    db.close()


def test_ai_calendar_support_is_opt_in_and_legacy_ctf_filter_is_preserved():
    source = {key: value for key, value in SOURCE.items() if key != 'event_scope'}
    ann, reason = parse_event(page(detail()), EVENT, source, NOW)
    assert ann is None and 'CTF' in reason
    data = detail()
    data['event']['name'] = 'Student Security Challenge'
    data['description_mirror'] = 'A cybersecurity Capture the Flag competition for teams.'
    ann, _ = parse_event(page(data), EVENT, source, NOW)
    assert ann is not None and 'CTF' in ann['facts']['name']
    assert ann['facts']['registration_state'] == 'approval_required'


@pytest.mark.parametrize('raw,status', [
    ('<title>Challenge required</title>', 'error'),
    (page({'calendar': {'api_id': 'cal-example', 'name': 'Example AI'}}, 'calendar'), 'error'),
    (FetchError('HTTP 403'), 'blocked'),
    (page(calendar(), 'calendar'), 'ok'),
])
def test_unreadable_or_blocked_calendar_is_distinct_from_successful_empty(raw, status):
    pages = Pages({CALENDAR: raw})
    db, report = run(pages)
    source, = report['sources']
    assert source['status'] == status
    assert source['accepted'] == source['discovered'] == 0
    assert pages.requests == [CALENDAR]
    assert bool(source_states(db)[0]['last_success']) is (status == 'ok')
    db.close()


@pytest.mark.parametrize('raw', [FetchError('HTTP 403'), FetchError('ReadTimeout'), '<title>Unreadable</title>'])
def test_unreadable_event_does_not_count_as_a_successful_zero_match(raw):
    db, report = run(Pages({EVENT: raw}))
    source, = report['sources']
    assert source['status'] == 'partial'
    assert source['discovered'] == 1 and source['accepted'] == 0
    assert source['decisions'][0]['decision'] in ('blocked', 'error', 'unverified')
    assert source['decisions'][0]['reason']
    db.close()


def test_robots_denied_event_is_a_blocked_check_and_partial_source():
    db, report = run(Pages({EVENT: FetchError('robots.txt disallows automated access')}))
    source, = report['sources']
    assert source['status'] == 'partial'
    assert source['discovered'] == 1 and source['accepted'] == 0
    assert source['decisions'][0]['decision'] == 'blocked'
    assert 'robots' in source['decisions'][0]['reason']
    db.close()


@pytest.mark.parametrize('start,accepted', [
    (NOW, 1), (NOW + timedelta(days=45), 0), (NOW - timedelta(days=1), 0),
])
def test_half_open_window_qualifies_event_start_not_end(start, accepted):
    data = detail()
    data['event']['start_at'] = start.isoformat()
    data['event']['end_at'] = (start + timedelta(days=3)).isoformat()
    db, report = run(Pages({EVENT: page(data)}))
    source, = report['sources']
    assert source['status'] == 'ok' and source['accepted'] == accepted
    if not accepted:
        assert source['decisions'][0]['decision'] == 'rejected'
    db.close()


def test_date_only_event_stays_date_only_in_manila_listing():
    data = detail()
    data['event']['start_at'] = '2035-11-29'
    data['event']['end_at'] = '2035-11-29'
    db, _ = run(Pages({EVENT: page(data)}))
    event, = events(db, NOW)
    for field in ('start', 'end'):
        assert event[field]['precision'] == 'date' and event[field]['value'] == '2035-11-29'
    assert events(db, datetime(2035, 11, 29, 15, 59, tzinfo=timezone.utc))[0]['section'] == 'upcoming'
    assert events(db, datetime(2035, 11, 29, 16, tzinfo=timezone.utc))[0]['section'] != 'upcoming'
    db.close()


def test_ticket_validity_or_event_end_does_not_invent_registration_cutoff():
    db, _ = run()
    payload = stored_payload(db)
    assert payload['facts']['deadline'] is None
    assert all(ticket['deadline'] is None for ticket in payload['facts']['ticket_options'])
    db.close()


@pytest.mark.parametrize('same_cutoff', [True, False])
def test_only_agreed_explicit_public_ticket_end_at_supplies_cutoff(same_cutoff):
    data = detail()
    data['ticket_types'][0]['end_at'] = '2035-11-28T11:00:00Z'
    data['ticket_types'][1]['end_at'] = '2035-11-28T11:00:00Z' if same_cutoff else '2035-11-28T12:00:00Z'
    db, _ = run(Pages({EVENT: page(data)}))
    event, = events(db, NOW)
    if same_cutoff:
        assert event['deadline']['value'] == '2035-11-28T19:00:00+08:00'
    else:
        assert event['deadline'] is None
    db.close()


def test_multiple_editions_in_one_year_have_distinct_identity():
    second = detail()
    second['event']['api_id'] = 'evt-another'
    second['event']['start_at'] = '2035-12-06T07:00:00Z'
    second['event']['end_at'] = '2035-12-06T10:00:00Z'
    pages = Pages({CALENDAR: page(calendar('sample-ai', 'sample-ai-next'), 'calendar'),
                   'https://luma.com/sample-ai-next': page(second)})
    db, report = run(pages)
    assert report['events'] == report['announcements'] == 2
    assert len({event['id'] for event in events(db, NOW)}) == 2
    db.close()


def test_linked_event_must_belong_to_discovered_organizer_calendar():
    data = detail()
    data['calendar']['api_id'] = 'cal-somebody-else'
    data['event']['calendar_api_id'] = 'cal-somebody-else'
    db, report = run(Pages({EVENT: page(data)}))
    assert report['events'] == 0 and report['sources'][0]['accepted'] == 0
    assert report['sources'][0]['decisions'][0]['reason']
    db.close()
