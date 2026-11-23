"""Synthetic primary pages only: no benchmark event or reference fixtures."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from backend.domain import event_key
from backend.luma import parse_community_event
from backend.network import FetchError
from backend.opportunity_pages import page_event_links, primary_event_url, verify_page


NOW = datetime(2035, 11, 22, 13, tzinfo=timezone.utc)
MEETUP = 'https://www.meetup.com/example-builders/events/1234567/'
GDG = 'https://gdg.community.dev/events/details/example-developer-day/'
LUMA = 'https://luma.com/example-workshop'
CALENDAR = 'https://luma.com/example-builders?k=c'


def schema(url=MEETUP):
    return {'@context': 'https://schema.org', '@type': 'Event', 'url': url,
            'name': 'Cloud Computing Workshop',
            'description': 'Learn software development and cloud computing through practical labs.',
            'startDate': '2035-11-29T04:00:00Z', 'endDate': '2035-11-29T08:00:00Z',
            'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
            'organizer': {'@type': 'Organization', 'name': 'Example Builders',
                          'url': 'https://www.meetup.com/example-builders/'},
            'location': {'@type': 'Place', 'name': 'Public Technology Hall',
                         'address': {'addressCountry': 'PH', 'addressLocality': 'Davao City'}}}


def meetup_state(yes=5, capacity=20):
    event = {'id': '1234567', 'status': 'ACTIVE', 'maxTickets': capacity,
             'rsvpSettings': {'rsvpOpenTime': None, 'rsvpCloseTime': None},
             'rsvps({"filter":{"rsvpStatus":["YES"]}})': {'totalCount': yes},
             'rsvps({"filter":{"rsvpStatus":["WAITLIST"]}})': {'totalCount': 0},
             'waitlistMode': 'OFF'}
    return {'props': {'pageProps': {'event': {'id': '1234567', 'rsvps': {'totalCount': 0}},
                                  '__APOLLO_STATE__': {'Event:1234567': event}}}}


def page(node=None, *, body='', control='', metadata=None, extra=''):
    node = schema() if node is None else node
    content = '<h1>' + node.get('name', '') + '</h1><script type="application/ld+json">' + json.dumps(node) + '</script>'
    if metadata:
        content += '<script id="__NEXT_DATA__">' + json.dumps(metadata) + '</script>'
    return content + control + '<h2>Details</h2><div>' + body + '</div><h2>Related topics</h2>' + extra


def verify(raw, url=MEETUP, client=None):
    return verify_page(raw, url, {'url': 'https://www.meetup.com/example-builders/'}, client, NOW)


def luma_data():
    return {'event': {'api_id': 'evt-example', 'calendar_api_id': 'cal-example',
                      'name': 'Community AI Workshop', 'start_at': '2035-11-29T04:00:00Z',
                      'end_at': '2035-11-29T08:00:00Z', 'timezone': 'Asia/Manila',
                      'location_type': 'offline', 'geo_address_info': {'country_code': 'PH', 'city': 'Davao City'}},
            'calendar': {'api_id': 'cal-example', 'name': 'Example Builders', 'slug': 'example-builders'},
            'description_mirror': 'Join this artificial intelligence workshop.',
            'registration_availability': 'open', 'ticket_info': {'require_approval': False},
            'ticket_types': [{'name': 'Standard', 'require_approval': False, 'cents': None,
                              'type': 'free', 'is_hidden': False, 'is_disabled': False}]}


def luma_page(data, kind='event', link=True):
    payload = {'props': {'pageProps': {'initialData': {'kind': kind, 'data': data}}}}
    return '<script id="__NEXT_DATA__">' + json.dumps(payload) + '</script><button>Register</button>' + (
        '<a href="/example-builders?k=c">Example Builders</a>' if link else '')


class CalendarPages:
    def __init__(self, calendar_id='cal-example'):
        self.requests = []
        self.raw = luma_page({'calendar': {'api_id': calendar_id, 'name': 'Example Builders'}}, 'calendar')

    def public_page(self, url, allowed_hosts=None):
        assert url == CALENDAR
        assert allowed_hosts == ['luma.com', 'lu.ma']
        self.requests.append(url)
        return self.raw


def test_primary_event_urls_are_stable_and_reject_directories():
    assert primary_event_url(MEETUP + '?eventOrigin=group_events&utm_source=x') == MEETUP
    assert primary_event_url(MEETUP.replace('/example-builders/', '/en-PH/example-builders/')) == MEETUP
    assert primary_event_url(GDG + 'cohost-other-chapter') == GDG
    assert primary_event_url('https://www.meetup.com/find/?keywords=AI') is None
    assert primary_event_url('https://gdg.community.dev/gdg-manila/') is None
    assert primary_event_url('https://luma.com/security/document.pdf') is None
    assert primary_event_url(None) is None


def test_hub_links_follow_only_actually_linked_events_and_never_detail_recommendations():
    raw = '<a href="' + MEETUP + '?eventOrigin=group_events">Workshop</a><a href="/find/">Browse</a>'
    assert page_event_links(raw, 'https://globalai.community/chapters/example/') == [MEETUP]
    assert page_event_links(raw, MEETUP) == []
    assert page_event_links(luma_page(luma_data()), LUMA) == []
    data = {'calendar': {'api_id': 'cal-example'}, 'upcoming': {'entries': [{'event': {'url': 'example-workshop'}}]}}
    assert page_event_links(luma_page(data, 'calendar', link=False), CALENDAR) == [LUMA]


def test_ph_event_preserves_dates_and_primary_evidence():
    ann, reason = verify(page(control='<button data-disabled="false">Attend event</button>'))
    assert ann, reason
    facts = ann['facts']
    assert facts['topic'] == 'general_it' and facts['geography'] == 'PH'
    assert facts['start']['value'] == '2035-11-29T12:00:00+08:00'
    assert facts['end']['value'] == '2035-11-29T16:00:00+08:00'
    assert facts['registration_state'] == 'unknown'
    assert facts['deadline'] is None and facts['price'] == {'kind': 'unknown'}
    for field in ('name', 'organizer', 'geography', 'topic', 'region', 'format', 'start', 'end', 'attendance_options'):
        assert ann['field_evidence'][field]['url'] == MEETUP
        assert ann['field_evidence'][field]['quote']


def test_date_only_is_not_upgraded_to_midnight_or_cutoff():
    node = schema(); node.update(startDate='2035-11-29', endDate='2035-11-30')
    ann, _ = verify(page(node))
    assert ann['facts']['start'] == {'raw': '2035-11-29', 'value': '2035-11-29', 'precision': 'date', 'timezone': None}
    assert ann['facts']['deadline'] is None


def test_primary_event_url_mismatch_and_missing_timezone_are_rejected():
    node = schema(); node['url'] = MEETUP.replace('1234567', '9999999')
    assert verify(page(node))[0] is None
    node = schema(); node['startDate'] = '2035-11-29T14:00:00'
    with pytest.raises(FetchError, match='precision'):
        verify(page(node))


@pytest.mark.parametrize('location,expected', [('PH', True), ('ph', True), ('Philippines', True), ('US', False), ('', False)])
def test_ph_venue_requires_primary_country_not_organizer_name(location, expected):
    node = schema(); node['location']['address']['addressCountry'] = location
    node['organizer']['name'] = 'Philippines AI Developers'
    assert bool(verify(page(node))[0]) is expected


def test_online_requires_explicit_worldwide_participation():
    node = schema(); node['location'] = {'@type': 'VirtualLocation', 'url': MEETUP}
    node['eventAttendanceMode'] = 'https://schema.org/OnlineEventAttendanceMode'
    assert verify(page(node, body='Open to everyone!'))[0] is None
    ann, _ = verify(page(node, body='Participants from anywhere in the world are welcome.'))
    assert ann['facts']['geography'] == 'international_online'
    assert ann['facts']['format'] == 'online'


def test_worldwide_cybersecurity_is_supported_but_ph_requires_competition_adapter():
    node = schema(); node.update(name='Cybersecurity Workshop', description='Practice ethical hacking.')
    assert verify(page(node))[0] is None
    node['location'] = {'@type': 'VirtualLocation', 'url': MEETUP}
    node['eventAttendanceMode'] = 'https://schema.org/OnlineEventAttendanceMode'
    ann, _ = verify(page(node, body='Open to participants worldwide.'))
    assert ann['facts']['topic'] == 'cybersecurity'


def test_related_topics_cannot_supply_event_topic_or_free_price():
    node = schema(); node.update(name='Community Picnic', description='Meet neighbors for lunch.')
    assert verify(page(node, extra='<div>Artificial intelligence. Free admission.</div>'))[0] is None


@pytest.mark.parametrize('yes,capacity,expected', [(5, 20, 'open'), (21, 20, 'unknown'), (5, 0, 'unknown')])
def test_meetup_action_needs_verified_yes_capacity(yes, capacity, expected):
    raw = page(control='<button data-disabled="false">Attend event</button>', metadata=meetup_state(yes, capacity))
    ann, _ = verify(raw)
    assert ann['facts']['registration_state'] == expected
    if expected == 'open':
        assert ann['field_evidence']['registration_state']['basis'] == 'live_registration_widget'


def test_meetup_waitlist_and_approval_are_distinct_from_open():
    ann, _ = verify(page(control='<button>Join waitlist</button>', metadata=meetup_state(20, 20)))
    assert ann['facts']['registration_state'] == 'waitlisted'
    ann, _ = verify(page(control='<button>Request to join</button>', metadata=meetup_state()))
    assert ann['facts']['registration_state'] == 'approval_required'
    ann, _ = verify(page(control='<button data-disabled="true">Attend event</button>', metadata=meetup_state()))
    assert ann['facts']['registration_state'] == 'unknown'


def test_meetup_rsvp_dates_are_explicit_registration_dates():
    metadata = meetup_state()
    metadata['props']['pageProps']['__APOLLO_STATE__']['Event:1234567']['rsvpSettings'] = {
        'rsvpOpenTime': '2035-11-20T10:00:00Z', 'rsvpCloseTime': '2035-11-28T10:00:00Z'}
    ann, _ = verify(page(metadata=metadata))
    assert ann['facts']['deadline']['value'] == '2035-11-28T18:00:00+08:00'
    assert ann['facts']['registration_opens']['value'] == '2035-11-20T18:00:00+08:00'


def test_platform_default_zero_is_not_free_and_offer_validity_is_not_deadline():
    node = schema(GDG)
    node['offers'] = [{'price': 0, 'availability': 'http://schema.org/LimitedAvailability', 'validThrough': '2035-11-28T10:00:00Z'}]
    ann, _ = verify(page(node, body='This is a paid ticketed event. Signing up for the waitlist does not guarantee a spot.',
                         control='<div role="button" aria-disabled="true">RSVP</div>'), GDG)
    assert ann['facts']['price'] == {'kind': 'paid'}
    assert ann['facts']['deadline'] is None
    assert ann['facts']['registration_state'] == 'waitlisted'
    assert 'basis' not in ann['field_evidence']['registration_state']
    ann, _ = verify(page(node), GDG)
    assert ann['facts']['price'] == {'kind': 'unknown'}


def test_gdg_offer_availability_requires_enabled_action():
    node = schema(GDG); node['offers'] = [{'availability': 'https://schema.org/InStock'}]
    ann, _ = verify(page(node, body='Free admission.', control='<button>RSVP</button>'), GDG)
    assert ann['facts']['registration_state'] == 'open'
    assert ann['facts']['price']['kind'] == 'free'
    ann, _ = verify(page(node, control='<button disabled>RSVP</button>'), GDG)
    assert ann['facts']['registration_state'] == 'unknown'


def test_typed_deadline_is_separate_from_schedule():
    ann, _ = verify(page(body='<p>Registration deadline: 2035-11-28</p><p>Submission deadline: 2035-11-30T00:00:00Z</p>'))
    assert ann['facts']['deadline']['precision'] == 'date'
    assert ann['facts']['submission_deadline']['value'] == '2035-11-30T08:00:00+08:00'


def test_luma_calendar_ownership_must_be_discovered_and_fetched():
    client = CalendarPages()
    ann, reason = verify(luma_page(luma_data()), LUMA, client)
    assert ann, reason
    assert client.requests == [CALENDAR]
    assert ann['facts']['registration_state'] == 'open'
    assert ann['facts']['price'] == {'kind': 'unknown'}
    assert ann['field_evidence']['organizer']['calendar_url'] == CALENDAR
    assert verify(luma_page(luma_data(), link=False), LUMA, CalendarPages())[0] is None
    assert verify(luma_page(luma_data()), LUMA, CalendarPages('cal-other'))[0] is None


def test_luma_generic_ai_has_same_identity_as_configured_ai():
    data = luma_data(); raw = luma_page(data)
    generic, _ = verify(raw, LUMA, CalendarPages())
    configured, _ = parse_community_event(raw, data, LUMA, {'url': CALENDAR, '_calendar_id': 'cal-example', 'topic': 'ai'}, NOW)
    assert generic['identity'] == configured['identity']
    assert event_key(generic['identity']) == event_key(configured['identity'])


def test_luma_general_it_is_opt_in_and_not_accepted_by_ai_configuration():
    data = luma_data(); data['event']['name'] = 'Cloud Computing Workshop'
    data['description_mirror'] = 'Learn software development.'
    raw = luma_page(data)
    ann, _ = verify(raw, LUMA, CalendarPages())
    assert ann['facts']['topic'] == 'general_it'
    assert parse_community_event(raw, data, LUMA, {'url': CALENDAR, '_calendar_id': 'cal-example', 'topic': 'ai'}, NOW)[0] is None


def test_luma_event_and_calendar_ids_must_agree_even_with_link():
    data = luma_data(); data['event']['calendar_api_id'] = 'cal-other'
    client = CalendarPages()
    assert verify(luma_page(data), LUMA, client)[0] is None
    assert client.requests == []


def test_personal_luma_requires_metadata_owner_to_be_a_named_linked_host():
    data = luma_data()
    data['calendar'].update(name='Personal', slug=None, is_personal=True, personal_user_api_id='usr-owner')
    data['hosts'] = [{'api_id': 'usr-owner', 'name': 'Example Public Host', 'username': 'example-host'}]
    raw = luma_page(data, link=False) + '<a href="/user/example-host">Example Public Host</a>'
    ann, reason = verify(raw, LUMA, None)
    assert ann, reason
    assert ann['facts']['organizer'] == 'Example Public Host'
    assert ann['identity']['organizer_key'] == 'luma:usr-owner'
    assert 'public hosts' in ann['field_evidence']['organizer']['quote']
    assert verify(luma_page(data, link=False), LUMA, None)[0] is None
    data['calendar']['personal_user_api_id'] = 'usr-different'
    assert verify(luma_page(data, link=False) + '<a href="/user/example-host">Example Public Host</a>', LUMA, None)[0] is None


def test_explicit_no_registration_fee_does_not_become_paid():
    ann, _ = verify(page(body='No registration fee.'))
    assert ann['facts']['price']['kind'] == 'free'


@pytest.mark.parametrize('wording', ['This event is not available worldwide.', 'Hear from speakers around the world.', 'Open worldwide except some countries.',
                                   'Open worldwide. Participation is restricted to residents of Example Country.'])
def test_incidental_or_conditional_worldwide_is_not_audience_access(wording):
    node = schema(); node['location'] = {'@type': 'VirtualLocation', 'url': MEETUP}
    node['eventAttendanceMode'] = 'https://schema.org/OnlineEventAttendanceMode'
    assert verify(page(node, body=wording))[0] is None


@pytest.mark.parametrize('wording', ['Free admission for members only.', 'Free admission for students.', 'Free entry subject to eligibility.'])
def test_conditional_free_access_is_not_public_free_price(wording):
    ann, _ = verify(page(body=wording))
    assert ann['facts']['price']['kind'] == 'unknown'


@pytest.mark.parametrize('wording', ['Registration fee: PHP 1,200.50.', 'Ticket price: $20.', 'Ticket price: EUR 19.95.'])
def test_paid_statements_keep_amount_and_currency_unconfirmed_without_price_parser(wording):
    ann, _ = verify(page(body=wording))
    assert ann['facts']['price'] == {'kind': 'paid'}


@pytest.mark.parametrize('url', [MEETUP, GDG, LUMA])
def test_js_only_event_page_is_unverified_instead_of_no_match(url):
    with pytest.raises(FetchError, match='metadata unavailable'):
        verify('<html><div id="app"></div></html>', url)


def test_url_less_jsonld_needs_matching_visible_heading():
    node = schema(GDG); node.pop('url')
    assert verify(page(node), GDG)[0]
    raw = page(node).replace('<h1>Cloud Computing Workshop</h1>', '<h1>Another Event</h1>')
    with pytest.raises(FetchError, match='visible heading'):
        verify(raw, GDG)


def test_ambiguous_primary_records_are_unverified():
    raw = page() + '<script type="application/ld+json">' + json.dumps(schema()) + '</script>'
    with pytest.raises(FetchError, match='Ambiguous'):
        verify(raw)


def test_reversed_date_only_schedule_is_unverified():
    node = schema(); node.update(startDate='2035-11-29', endDate='2035-11-28')
    with pytest.raises(FetchError, match='end precedes start'):
        verify(page(node))


@pytest.mark.parametrize('control', ['<footer><button>RSVP</button></footer>', '<aside><button>RSVP</button></aside>',
                                   '<div hidden><button>RSVP</button></div>', '<a href="https://other.example/register">Register</a>'])
def test_unrelated_or_hidden_controls_do_not_open_event_registration(control):
    node = schema(GDG); node['offers'] = [{'availability': 'https://schema.org/InStock'}]
    ann, _ = verify(page(node, control=control), GDG)
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['registration_url'] is None


def test_explicit_student_audience_and_entry_requirements_are_retained_together():
    body = '<p>The conference provides workshops to equip student builders with practical cloud computing skills.</p><p>All attendees must complete the organizer registration form.</p>'
    ann, _ = verify(page(body=body))
    assert 'Intended audience: student builders.' in ann['facts']['eligibility']
    assert 'must complete' in ann['facts']['eligibility']
    assert 'equip student builders' in ann['facts']['description']
    assert 'practical cloud computing' not in ann['facts']['eligibility']
    assert 'equip student builders' in ann['field_evidence']['eligibility']['quote']
    assert ann['field_evidence']['description']['quote'] == ann['facts']['description']


def test_nonstandard_ports_are_not_primary_events_or_calendar_verification_targets():
    assert primary_event_url(MEETUP.replace('www.meetup.com', 'www.meetup.com:8181')) is None
    raw = luma_page(luma_data(), link=False) + '<a href="https://luma.com:8181/example-builders?k=c">Calendar</a>'
    client = CalendarPages()
    assert verify(raw, LUMA, client)[0] is None
    assert client.requests == []


def test_malformed_nested_primary_metadata_is_unverified_not_crash():
    data = luma_data(); data['event'] = ['not-an-event-object']
    with pytest.raises(FetchError, match='unreadable field types'):
        verify(luma_page(data), LUMA)
    metadata = meetup_state(); metadata['props']['pageProps']['__APOLLO_STATE__']['Event:1234567'] = ['broken']
    with pytest.raises(FetchError, match='unreadable field types'):
        verify(page(metadata=metadata))
    with pytest.raises(FetchError, match='unreadable schema'):
        page_event_links(luma_page({'upcoming': ['bad-shape']}, 'calendar'), CALENDAR)
    with pytest.raises(FetchError, match='unreadable schema'):
        page_event_links(luma_page({'upcoming': {'entries': [{'event': 'bad-shape'}]}}, 'calendar'), CALENDAR)


def test_devpost_without_primary_metadata_is_unverified():
    with pytest.raises(FetchError):
        verify('<h1>Software Hackathon</h1>', 'https://example-hack.devpost.com/')
