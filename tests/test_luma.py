"""Synthetic Luma pages: no evaluation event names, identifiers, or URLs."""
from datetime import datetime, timezone
import json

import pytest

from backend.luma import luma, parse_event, rich_description, subscription_links
from backend.network import FetchError, RateLimited

NOW = datetime(2032, 3, 1, tzinfo=timezone.utc)
CITY = 'https://luma.com/manila'
FEED = 'https://api.luma.com/ics/get?entity=discover&id=discplace-synthetic'
EVENT = 'https://luma.com/synthetic-challenge'
SOURCE = {'id': 'luma-test', 'name': 'Luma Manila', 'url': CITY, 'ical_url': FEED}


def page(data, kind='event'):
    body = {'props': {'pageProps': {'initialData': {'kind': kind, 'data': data}}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(body) + '</script>'


def detail(**kwargs):
    data = {'event': {'api_id': 'evt-synthetic', 'name': 'Student Challenge',
                     'start_at': '2032-03-08T01:00:00Z', 'end_at': '2032-03-08T09:00:00Z',
                     'timezone': 'Asia/Manila', 'location_type': 'offline',
                     'geo_address_info': {'country_code': 'PH', 'country': 'Philippines', 'city': 'Manila'}},
            'description_mirror': {'type': 'doc', 'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'A cybersecurity Capture the Flag competition for teams.'}]}]},
            'hosts': [{'api_id': 'usr-synthetic', 'name': 'Example Security Club'}],
            'registration_availability': 'open', 'ticket_info': {'require_approval': False},
            'ticket_types': [{'end_at': '2032-03-07T09:00:00Z', 'is_hidden': False}]}
    data.update(kwargs)
    return data


def feed():
    return 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nDESCRIPTION:Get details at https://luma.com/synthetic-\n challenge\\nA topic\nEND:VEVENT\nEND:VCALENDAR'


class Pages:
    def __init__(self, values):
        self.values, self.requests = values, []

    def public_page(self, url, allowed_hosts=None):
        self.requests.append(url)
        raw = self.values[url]
        if isinstance(raw, Exception):
            raise raw
        return raw


def test_unfolded_feed_discovers_urls_without_using_dates_or_registration():
    assert subscription_links(feed()) == ([EVENT], 1)


def test_title_without_ctf_reads_body_and_preserves_structured_host_evidence():
    ann, reason = parse_event(page(detail()), EVENT, SOURCE, NOW)
    assert ann['facts']['name'] == 'Student Challenge · CTF 2032'
    assert ann['facts']['organizer'] == 'Example Security Club'
    assert ann['facts']['start']['precision'] == 'datetime'
    assert ann['facts']['registration_state'] == 'open'
    assert ann['posted_at'] is None
    assert ann['publisher_leads'][0]['account_id'] == 'luma:usr-synthetic'
    assert ann['publisher_leads'][0]['evidence']['url'] == EVENT
    assert ann['field_evidence']['deadline']['quote'].endswith('2032-03-07T09:00:00Z')


@pytest.mark.parametrize(('availability', 'ticket_info', 'waitlist', 'expected'), [
    ('open', {'require_approval': True}, False, 'approval_required'),
    ('open', {'require_approval': False}, True, 'waitlisted'),
    ('closed', {}, False, 'closed'),
    ('sold-out', {}, False, 'closed'),
    ('unrecognized', {}, False, 'unknown'),
])
def test_registration_states_remain_distinct(availability, ticket_info, waitlist, expected):
    data = detail(registration_availability=availability, ticket_info=ticket_info, waitlist_active=waitlist)
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == expected


@pytest.mark.parametrize('location_type', ['online', 'virtual', 'meet'])
def test_publisher_subscription_without_city_page_discovers_online_competition(location_type):
    source = {**SOURCE, 'url': FEED, 'page_fallback': False}
    data = detail()
    data['event']['location_type'] = location_type
    data['event']['geo_address_info'] = {}
    data['description_mirror'] = 'A cybersecurity CTF competition hosted by the Philippine Student Security Society.'
    data['ticket_types'] = []  # An actual open control does not imply a deadline.
    pages = Pages({FEED: feed(), EVENT: page(data)})
    result = luma(source, pages, [], NOW)
    assert len(result.announcements) == 1
    ann = result.announcements[0]
    assert ann['discovery_path'] == [FEED, EVENT]
    assert ann['facts']['format'] == 'online'
    assert ann['facts']['registration_state'] == 'open'
    assert ann['facts']['deadline'] is None
    assert ann['field_evidence']['registration_state']['basis'] == 'live_registration_widget'
    assert pages.requests == [FEED, EVENT]


def test_failed_publisher_subscription_is_not_retried_as_a_city_page():
    source = {**SOURCE, 'url': FEED, 'page_fallback': False}
    pages = Pages({FEED: FetchError('HTTP 403')})
    result = luma(source, pages, [], NOW)
    assert result.failed and result.failure_status == 'blocked'
    assert pages.requests == [FEED]


def test_conference_ticket_is_not_ctf_registration_or_schedule():
    data = detail()
    data['event']['name'] = 'Student Cybersecurity Conference 2032'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['registration_url'] is None
    assert ann['facts']['deadline'] is None
    assert ann['facts']['start'] is None
    assert ann['facts']['end'] is None


def test_ordinary_events_and_training_never_generate_event_or_candidates():
    for body in ['A cybersecurity CTF workshop for beginners.', 'Practice cybersecurity CTF challenges in our training workshop.', 'Capture the flag competition with playground games.', 'A startup networking evening.']:
        data = detail(description_mirror=body)
        ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
        assert ann is None


def test_city_membership_does_not_confirm_philippine_scope():
    data = detail()
    data['event']['geo_address_info'] = {'country': 'Singapore', 'country_code': 'SG'}
    data['event']['location_type'] = 'online'
    assert parse_event(page(data), EVENT, SOURCE, NOW)[0] is None


def test_linked_sponsor_is_a_lead_with_role_not_organizer():
    data = detail()
    data['description_mirror']['content'].append({'type': 'paragraph', 'content': [
        {'type': 'text', 'text': 'Sponsored by '},
        {'type': 'text', 'text': 'Sample Learning', 'marks': [{'type': 'link', 'attrs': {'href': 'https://learning.example/'}}]}]})
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    lead = ann['publisher_leads'][1]
    assert lead['role'] == 'sponsor'
    assert lead['url'] == 'https://learning.example/'
    assert 'Sample Learning' not in ann['facts']['organizer']


def test_city_fallback_reports_blocked_feed_and_partial_slice():
    city = {'place': {'event_count': 12}, 'events': [{'event': {'url': 'synthetic-challenge'}}]}
    client = Pages({FEED: FetchError('HTTP 403'), CITY: page(city, 'discover-place'), EVENT: page(detail())})
    result = luma(SOURCE, client, [], NOW)
    assert len(result.announcements) == 1
    assert result.route_checks[0]['status'] == 'blocked'
    assert result.route_checks[1]['reported_event_count'] == 12
    assert any('1 of 12' in warning for warning in result.warnings)


def test_all_routes_blocked_is_not_successful_zero_matches():
    result = luma(SOURCE, Pages({FEED: FetchError('HTTP 403'), CITY: FetchError('HTTP 403')}), [], NOW)
    assert result.failed and result.failure_status == 'blocked'
    assert result.announcements == []


def test_rate_limit_stops_requests_and_preserves_known_announcements():
    client = Pages({FEED: RateLimited(120)})
    result = luma(SOURCE, client, [{'url': EVENT}], NOW)
    assert result.failed and result.failure_status == 'rate_limited'
    assert result.retry_after == 120
    assert client.requests == [FEED]
    assert result.deleted == []


def test_old_known_event_is_rechecked_even_when_city_is_empty():
    client = Pages({FEED: 'BEGIN:VCALENDAR\nEND:VCALENDAR', EVENT: page(detail())})
    result = luma(SOURCE, client, [{'url': EVENT}], NOW)
    assert result.discovered == 0
    assert len(result.announcements) == 1
    assert result.deleted == []


def test_detail_error_preserves_successful_discovery_and_previous_listing():
    result = luma(SOURCE, Pages({FEED: feed(), EVENT: FetchError('HTTP 403')}), [], NOW)
    assert result.discovered == 1
    assert result.decisions[0]['decision'] == 'blocked'
    assert result.deleted == []


def test_past_competition_cannot_remain_open_from_stale_ticket_flag():
    data = detail()
    data['event']['end_at'] = '2032-02-20T09:00:00Z'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == 'closed'


def test_unknown_approval_flag_does_not_claim_unrestricted_open_registration():
    ann, _ = parse_event(page(detail(ticket_info={})), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == 'unknown'
    assert 'false' not in ann['field_evidence']['registration_state']['quote']


def test_rich_description_preserves_explicit_line_breaks():
    data = {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Sponsors:'}, {'type': 'hard_break'}, {'type': 'text', 'text': 'Example School'}]}
    assert rich_description(data)[0] == 'Sponsors:\nExample School'


def test_unlinked_role_lists_keep_evidence_without_guessing_public_identity():
    data = detail()
    data['description_mirror']['content'].append({'type': 'paragraph', 'content': [
        {'type': 'text', 'text': 'Sponsors:'}, {'type': 'hard_break'},
        {'type': 'text', 'text': 'Example School'}, {'type': 'hard_break'},
        {'type': 'text', 'text': 'Example Community'}]})
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    sponsors = [p for p in ann['publisher_leads'] if p['role'] == 'sponsor']
    assert len(sponsors) == 2
    assert all('url' not in p and 'account_id' not in p for p in sponsors)
    assert all(p['evidence']['url'] == EVENT for p in sponsors)


def test_technical_ctf_event_without_competitive_cue_remains_unconfirmed():
    data = detail(description_mirror='A cybersecurity capture-the-flag technical event with hands-on challenges.')
    ann, reason = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann is None
    assert 'competition evidence' in reason


def test_multiple_activity_program_does_not_lend_its_times_to_ctf():
    data = detail(description_mirror='A cybersecurity CTF competition with an opening ceremony and workshops before the final round.')
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['start'] is None and ann['facts']['end'] is None
    assert ann['facts']['registration_state'] == 'unknown'


def test_parent_agenda_generic_start_is_not_ctf_start():
    data = detail(description_mirror='A cybersecurity CTF competition at our conference.\nStart: March 8, 2032 9:00 AM PHT')
    data['event']['name'] = 'Example Conference 2032'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['start'] is None


def test_ics_description_outbound_calendar_link_is_not_an_event():
    raw = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nDESCRIPTION:Get details at https://luma.com/synthetic-challenge\\nFollow https://luma.com/example-calendar\nEND:VEVENT\nEND:VCALENDAR'
    assert subscription_links(raw) == ([EVENT], 1)


def test_calendar_year_uses_confirmed_event_timezone_not_utc_transport_date():
    data = detail()
    data['event']['start_at'] = '2031-12-31T16:30:00Z'
    data['event']['end_at'] = '2031-12-31T20:30:00Z'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['identity']['edition'] == '2032'
    assert ann['facts']['name'].endswith('2032')
    assert 'calendar date=2032-01-01' in ann['field_evidence']['edition']['quote']
    assert ann['facts']['start']['value'] == '2031-12-31T16:30:00+00:00'
    assert ann['field_evidence']['philippine_connection'] == ann['scope_evidence']
    assert ann['facts']['summary'] is None


@pytest.mark.parametrize('zone', [None, 'Invalid/Timezone'])
def test_missing_or_invalid_event_timezone_does_not_guess_manila_date(zone):
    data = detail()
    data['event']['start_at'] = '2031-12-31T16:30:00Z'
    data['event']['timezone'] = zone
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['identity']['edition'] == '2031'
    assert 'calendar date=2031-12-31' in ann['field_evidence']['edition']['quote']


def test_date_only_calendar_schedule_is_preserved_without_midnight_conversion():
    data = detail()
    data['event']['start_at'] = '2032-01-01'
    data['event']['end_at'] = '2032-01-02'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['identity']['edition'] == '2032'
    assert ann['facts']['start']['precision'] == 'date'
    assert ann['facts']['start']['value'] == '2032-01-01'


def test_malformed_city_page_is_a_failure_not_a_successful_empty_calendar():
    client = Pages({FEED: FetchError('HTTP 403'), CITY: page({'place': {'event_count': 12}}, 'discover-place')})
    result = luma(SOURCE, client, [], NOW)
    assert result.failed is True
    assert result.failure_status == 'error'
    assert 'events schema unavailable' in result.route_checks[-1]['error']


def test_parent_conference_in_body_does_not_lend_times_or_registration():
    data = detail(description_mirror='A cybersecurity conference featuring a Capture the Flag competition for teams.')
    data['event']['name'] = 'Student Security Day'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['start'] is None and ann['facts']['end'] is None
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['registration_url'] is None


def test_ctf_title_without_edition_uses_calendar_year_over_historical_body_year():
    data = detail(description_mirror='Our club held workshops in 2029. Join this cybersecurity CTF competition for teams.')
    data['event']['name'] = 'Student CTF'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['identity']['edition'] == '2032'
    assert ann['facts']['name'] == 'Student CTF 2032'
    assert ann['title'] == 'Student CTF'
    assert ann['field_evidence']['name']['quote'] == 'Student CTF'
    assert 'start_at=2032-03-08T01:00:00Z' in ann['field_evidence']['edition']['quote']
    assert 'timezone=Asia/Manila' in ann['field_evidence']['edition']['quote']


def test_explicit_title_edition_is_not_replaced_by_calendar_year():
    data = detail()
    data['event']['name'] = 'Student CTF 2031'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['identity']['edition'] == '2031'
    assert ann['title'] == 'Student CTF 2031'
    assert ann['field_evidence']['name']['quote'] == 'Student CTF 2031'


def test_explicit_ctf_activity_and_player_challenges_are_recognized_without_keyword_title():
    data = detail(description_mirror='Lantern Night is a Capture the Flag event for digital forensics enthusiasts. Players solve encrypted puzzles.')
    data['event']['name'] = 'Lantern Night'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['recognition'] == 'declared_ctf_activity'
    assert ann['facts']['name'] == 'Lantern Night · CTF 2032'
    assert ann['title'] == 'Lantern Night'
    assert 'Players solve encrypted puzzles' in ann['field_evidence']['competition']['quote']
    assert ann['facts']['start'] is None and ann['facts']['end'] is None
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['registration_url'] is None
    assert ann['publisher_leads'][0]['role'] == 'host'


def test_declared_activity_role_list_does_not_change_recognition_to_training():
    data = detail(description_mirror='Welcome to a cybersecurity CTF game event. Teams tackle security puzzles.\nSponsors:\nTraining Works')
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['recognition'] == 'declared_ctf_activity'
    assert any(p['name'] == 'Training Works' and p['role'] == 'sponsor' for p in ann['publisher_leads'])


@pytest.mark.parametrize('body', [
    'A cybersecurity workshop teaches CTF competition techniques to beginners.',
    'This tutorial introduces a Capture the Flag event. Participants practice cybersecurity challenges.',
    'Our cybersecurity class is a Capture the Flag event. Participants solve challenges with an instructor.',
    'This event includes a guided CTF lab. Participants solve cybersecurity puzzles.',
    'A security CTF event for learning. Teams complete challenges as an exercise.',
    'A security conference without a CTF competition.',
    'Our event is a talk about Capture the Flag. Participants discuss cybersecurity challenges.',
    'We host a Capture the Flag game event. Teams solve outdoor puzzles.\nSponsors:\nCybersecurity Partners',
])
def test_teaching_or_noncyber_activity_is_not_a_competition(body):
    assert parse_event(page(detail(description_mirror=body)), EVENT, SOURCE, NOW)[0] is None


def test_separate_actual_ctf_competition_can_accompany_training():
    body = 'A cybersecurity workshop is followed by a Capture the Flag competition.'
    ann, _ = parse_event(page(detail(description_mirror=body)), EVENT, SOURCE, NOW)
    assert ann['recognition'] == 'explicit_competition'
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['start'] is None


@pytest.mark.parametrize(('require_approval', 'waitlist', 'expected'), [(False, False, 'open'), (True, False, 'approval_required'), (False, True, 'waitlisted')])
def test_only_contemporaneous_standalone_registration_widget_has_basis_marker(require_approval, waitlist, expected):
    data = detail(ticket_info={'require_approval': require_approval}, waitlist_active=waitlist)
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == expected
    assert ann['field_evidence']['registration_state']['basis'] == 'live_registration_widget'


def test_inferred_past_closure_has_no_live_widget_basis():
    data = detail()
    data['event']['end_at'] = '2032-02-20T09:00:00Z'
    ann, _ = parse_event(page(data), EVENT, SOURCE, NOW)
    assert ann['facts']['registration_state'] == 'closed'
    assert 'basis' not in ann['field_evidence']['registration_state']
