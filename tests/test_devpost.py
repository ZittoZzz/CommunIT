"""Synthetic Devpost overviews and normal collector integration, with no network."""
from datetime import datetime, timezone
import json

import pytest

from backend.collect import collect
from backend.db import connect, events
from backend.devpost import parse_event
from backend.network import FetchError


URL = 'https://example-ai-build.devpost.com/'
NOW = datetime(2037, 11, 22, 12, tzinfo=timezone.utc)
TITLE = 'Example AI Build 2037'
JOIN = '<a data-main-register-button="true" href="/register?flow%5Bdata%5D%5Bchallenge_id%5D=52000&amp;flow%5Bname%5D=register_for_challenge">Join hackathon</a>'
ELIGIBILITY = '''<ul id="eligibility-list"><li>Ages 13+ only</li><li>Students only</li>
<li>All countries/territories, excluding <span data-tooltip title="Cuba, Iran">standard exceptions</span></li></ul>'''
BODY = '''<p>Build artificial intelligence applications. Participation is free.</p>
<p>The event starts November 21, 2037, at 12:00 a.m. PST (America/Los_Angeles).</p>
<p>The submission deadline is November 28, 2037, at 3:00 p.m. PST (America/Los_Angeles).</p>'''


def schema(**changes):
    return {'@type': ['Event', 'Hackathon'], 'url': URL, 'name': TITLE,
            'organizer': {'@type': 'Organization', 'name': 'Example Students'},
            'eventAttendanceMode': 'https://schema.org/OnlineEventAttendanceMode',
            'startDate': '2037-11-21T03:00:00-05:00', 'endDate': '2037-11-28T18:00:00-05:00',
            'isAccessibleForFree': True, 'offers': {'price': 0, 'url': URL + 'register'}, **changes}


def page(node=None, body=BODY, eligibility=ELIGIBILITY, join=JOIN, sidebar=True):
    node = schema() if node is None else node
    return ('<h1>' + TITLE + '</h1><script type="application/ld+json">' + json.dumps(node) + '</script>'
            + eligibility + join + '<article id="challenge-description">' + body + '</article>'
            + ('<div id="challenge-information"><span data-dates-text data-iso-date="2037-11-28T18:00:00-05:00">Deadline: Nov 28, 2037 @ 3:00pm PST</span></div>' if sidebar else ''))


def parse(raw=None):
    return parse_event(raw or page(), URL, {'url': URL}, NOW)


def test_primary_facts_keep_signup_cutoff_and_account_requirement_separate():
    ann, reason = parse()
    assert ann, reason
    facts, proof = ann['facts'], ann['field_evidence']
    assert facts['name'] == TITLE and facts['topic'] == 'ai'
    assert facts['organizer'] == 'Example Students' and facts['format'] == 'online'
    assert facts['geography'] == 'international_online'
    assert facts['start']['value'] == '2037-11-21T16:00:00+08:00'
    assert facts['submission_deadline']['value'] == '2037-11-29T07:00:00+08:00'
    assert facts['submission_deadline']['timezone'] == 'Asia/Manila'
    assert facts['deadline'] is facts['registration_opens'] is facts['account_required'] is None
    assert facts['registration_state'] == 'open' and facts['registration_url'].startswith(URL + 'register?')
    assert facts['price'] == {'kind': 'free', 'amount': 0}
    assert all(word in facts['eligibility'] for word in ('Ages 13+', 'Students only', 'Cuba, Iran'))
    assert ann['posted_at'] is None and ann['identity']['edition'] == '52000'
    assert 'submission deadline' in proof['submission_deadline']['quote']
    assert 'data-iso-date=' in proof['submission_deadline']['quote']
    assert proof['registration_state']['basis'] == 'live_registration_widget'
    assert all(p['url'] == URL and p['quote'] for p in proof.values())
    assert 'deadline' not in proof and 'account_required' not in proof


def test_date_only_body_corroborates_explicit_sidebar_without_inventing_midnight():
    ann, reason = parse(page(body='<p>Build software applications.</p><p>Project Submission Deadline: November 28, 2037</p>'))
    assert ann, reason
    assert ann['facts']['submission_deadline']['value'] == '2037-11-29T07:00:00+08:00'
    assert ann['facts']['deadline'] is None
    assert ann['facts']['price'] == {'kind': 'unknown'}


def test_schema_end_and_untyped_sidebar_are_not_submission_or_registration_cutoffs():
    ann, reason = parse(page(body='<p>Build software applications.</p>'))
    assert ann, reason
    assert ann['facts']['submission_deadline'] is ann['facts']['deadline'] is None
    assert ann['facts']['end']['value']


def test_separately_labelled_registration_and_submission_deadlines_are_not_conflated():
    ann, reason = parse(page(body=BODY + '<p>Registration deadline: 2037-11-24T18:00:00Z</p>'))
    assert ann, reason
    assert ann['facts']['deadline']['value'] == '2037-11-25T02:00:00+08:00'
    assert ann['facts']['submission_deadline']['value'] == '2037-11-29T07:00:00+08:00'


@pytest.mark.parametrize('body', [
    BODY.replace('submission deadline is November 28', 'submission deadline is November 20'),
    BODY + '<p>Submit here on Devpost by November 23, 2037 at 6:00 PM EST.</p>',
    BODY.replace('event starts November 21', 'event starts November 20'),
])
def test_conflicting_primary_dates_are_rejected_with_original_quotes(body):
    ann, reason = parse(page(body=body))
    assert ann is None and reason.startswith('Conflicting primary')
    assert '2037' in reason and ('data-iso-date=' in reason or 'startDate=' in reason)


@pytest.mark.parametrize('change', [
    {'eventAttendanceMode': ''}, {'startDate': '2037-11-21T03:00:00'},
    {'url': 'https://different-edition.devpost.com/'}, {'organizer': {}}, {'name': 'Another edition'},
])
def test_unverified_format_time_identity_and_organizer_do_not_become_empty_success(change):
    with pytest.raises(FetchError):
        parse(page(node=schema(**change)))


def test_date_only_schema_retains_date_precision_when_no_explicit_clock_exists():
    ann, reason = parse(page(node=schema(startDate='2037-11-21', endDate='2037-11-28'),
                             body='<p>Build software applications.</p>', sidebar=False))
    assert ann, reason
    assert ann['facts']['start']['precision'] == 'date' and ann['facts']['start']['timezone'] is None


def test_date_only_reversed_schedule_is_rejected():
    ann, reason = parse(page(node=schema(startDate='2037-11-29', endDate='2037-11-28'),
                             body='<p>Build software applications.</p>', sidebar=False))
    assert ann is None and 'end precedes' in reason


@pytest.mark.parametrize('eligibility', [
    ELIGIBILITY.replace('Cuba, Iran', 'Cuba, Iran, Philippines'),
    ELIGIBILITY.replace('All countries/territories, excluding', 'Only specific countries/territories included'),
])
def test_country_exclusions_and_non_ph_specific_country_lists_are_respected(eligibility):
    ann, reason = parse(page(eligibility=eligibility))
    assert ann is None and 'Philippines' in reason


def test_explicit_country_inclusion_can_establish_ph_eligibility():
    eligibility = ELIGIBILITY.replace('All countries/territories, excluding', 'Only specific countries/territories included').replace('Cuba, Iran', 'Philippines, Singapore')
    ann, reason = parse(page(eligibility=eligibility))
    assert ann, reason
    assert 'Philippines, Singapore' in ann['facts']['eligibility']


def test_unreadable_standard_exceptions_are_unverified():
    with pytest.raises(FetchError, match='country exceptions'):
        parse(page(eligibility=ELIGIBILITY.replace('title="Cuba, Iran"', 'title=""')))


@pytest.mark.parametrize('restriction', [
    'The event is for Canadian undergraduate students currently studying in Korea.',
    'US residents only.', 'Participation is not open to residents of the Philippines.',
    'Participants must reside in Example Country.', 'Applicants must be enrolled at Example University.',
])
def test_organizer_body_overrides_broad_platform_country_default(restriction):
    ann, reason = parse(page(body=BODY + '<p>' + restriction + '</p>'))
    assert ann is None and 'restricts participation' in reason


@pytest.mark.parametrize('requirement', ['Participation is for university students only.',
                                       'Only professional developers may participate.'])
def test_primary_body_audience_requirements_are_retained(requirement):
    ann, reason = parse(page(body=BODY + '<p>' + requirement + '</p>'))
    assert ann, reason
    assert requirement in ann['facts']['eligibility']


def test_conflicting_primary_age_claims_remain_unverified():
    eligibility = ELIGIBILITY.replace('Ages 13+ only', 'Above legal age of majority in country of residence')
    ann, reason = parse(page(eligibility=eligibility, body=BODY + '<p>Open to students aged 13 and above.</p>'))
    assert ann is None and 'Conflicting primary age' in reason


@pytest.mark.parametrize('control', [
    JOIN.replace('<a ', '<a disabled '), JOIN.replace('<a ', '<a aria-disabled="true" '),
    JOIN.replace('<a ', '<a hidden '), '<div hidden>' + JOIN + '</div>',
    '<footer>' + JOIN + '</footer>', JOIN.replace('<a ', '<a aria-hidden="true" '),
    JOIN.replace('Join hackathon', 'Learn more') + '<a href="https://secure.devpost.com/users/register">Sign up</a>',
])
def test_disabled_or_generic_account_controls_do_not_prove_live_entry(control):
    ann, reason = parse(page(join=control))
    assert ann, reason
    assert ann['facts']['registration_state'] == 'unknown'
    assert ann['facts']['registration_url'] is None


def test_account_requirement_is_explicit_and_not_assumed_from_join_button():
    ann, _ = parse(page(body=BODY + '<p>Participants must create a Devpost account.</p>'))
    assert ann['facts']['account_required'] is True
    assert ann['field_evidence']['account_required']['url'] == URL
    ann, _ = parse(page(body=BODY + '<p>No Devpost account is required.</p>'))
    assert ann['facts']['account_required'] is None


@pytest.mark.parametrize('terms', ['Participation is not free.', 'Participation is free only for alumni.',
                                  'Receive free cloud credits.', 'If accepted, participation is free.',
                                  'Registration is free for members.'])
def test_free_platform_defaults_prizes_and_conditional_claims_do_not_establish_entry_price(terms):
    ann, reason = parse(page(body='<p>Build software applications.</p><p>' + terms + '</p>'))
    assert ann, reason
    assert ann['facts']['price'] == {'kind': 'unknown'}


@pytest.mark.parametrize('answer', ['', 'No, participation is not free.'])
def test_free_price_question_does_not_establish_price(answer):
    ann, reason = parse(page(body='<p>Build software applications.</p>'
                                 '<p>Is it free to participate? ' + answer + '</p>'))
    assert ann, reason
    assert ann['facts']['price'] == {'kind': 'unknown'}
    assert 'price' not in ann['field_evidence']


@pytest.mark.parametrize('separator', [' ', '</p><p>'])
def test_free_price_evidence_quotes_faq_answer_instead_of_question(separator):
    ann, reason = parse(page(body='<p>Build software applications.</p>'
                                 '<p>Is it free to participate?' + separator +
                                 'Yes! Participation is free.</p>'))
    assert ann, reason
    assert ann['facts']['price'] == {'kind': 'free', 'amount': 0}
    assert ann['field_evidence']['price']['quote'] == 'Participation is free'


def test_explicit_paid_fee_is_preserved_even_if_schema_default_says_free():
    ann, _ = parse(page(body=BODY + '<p>Registration fee: USD 25.</p>'))
    assert ann['facts']['price'] == {'kind': 'paid', 'amount': 25, 'currency': 'USD'}


@pytest.mark.parametrize('fee,expected', [
    ('Registration fee: PHP 1,500.00', {'kind': 'paid', 'amount': 1500, 'currency': 'PHP'}),
    ('Registration fee: PHP 1,500 for students.', {'kind': 'paid'}),
    ('Registration fee: USD 10 for students. Entry fee: USD 20 for professionals.', {'kind': 'paid'}),
    ('Registration fee: $25', {'kind': 'paid', 'amount': 25}),
])
def test_paid_fee_amounts_do_not_truncate_thousands_or_flatten_conditional_tiers(fee, expected):
    ann, reason = parse(page(body='<p>Build software applications.</p><p>' + fee + '</p>'))
    assert ann, reason
    assert ann['facts']['price'] == expected


def test_closed_registration_overrides_stale_enabled_join_control():
    ann, _ = parse(page(body=BODY + '<p>Registration is closed.</p>'))
    assert ann['facts']['registration_state'] == 'closed'
    assert 'basis' not in ann['field_evidence']['registration_state']


@pytest.mark.parametrize('notice,state', [('Applications require organizer approval.', 'approval_required'),
                                       ('Applicants are placed on a waitlist.', 'waitlisted')])
def test_explicit_approval_or_waitlist_overrides_generic_join_control(notice, state):
    ann, _ = parse(page(body=BODY + '<p>' + notice + '</p>'))
    assert ann['facts']['registration_state'] == state
    assert ann['field_evidence']['registration_state']['basis'] == 'live_registration_widget'


@pytest.mark.parametrize('date', ['November 28, 2037 at 18:00 UTC+8', 'November 28, 2037 at 18:00',
                                'November 28, 2037 at 18:00 XYZ'])
def test_unsupported_or_missing_timezone_on_typed_clock_is_unverified(date):
    with pytest.raises(FetchError, match='timezone'):
        parse(page(body='<p>Build software applications.</p><p>Submission deadline: ' + date + '</p>'))


class Pages:
    def __init__(self, raw):
        self.raw, self.requests = raw, []

    def public_page(self, url, allowed_hosts=None):
        self.requests.append(url)
        assert url == URL and allowed_hosts == ['example-ai-build.devpost.com']
        return self.raw.encode()


def source(tmp_path):
    path = tmp_path / 'synthetic-search.json'
    query = 'international online software hackathons November 2037'
    path.write_text(json.dumps({'provider': 'Synthetic search', 'queries': [
        {'query': query, 'status': 'ok', 'results': [{'url': URL, 'title': 'Unverified search title'}]}]}))
    return {'id': 'search-test', 'kind': 'opportunity_search', 'name': 'Synthetic search', 'url': 'https://search.example/',
            'search_results_path': str(path), 'queries': [{'query': query}], 'window_days': 45}


def test_normal_collector_accepts_already_started_event_via_submission_cutoff_and_replay_is_idempotent(tmp_path):
    pages = Pages(page())
    with connect(':memory:') as db:
        report = collect(db, [source(tmp_path)], client=pages, now=NOW)
        assert report['sources'][0]['accepted'] == 1
        event, = events(db, NOW, window_days=45)
        assert event['name'] == TITLE and event['registration_status'] == 'open'
        assert event['submission_deadline']['value'] == '2037-11-29T07:00:00+08:00'
        assert event['deadline'] is None
        assert event['announcements'][0]['discovery_path'] == [URL]
        first_seen = event['first_seen']
        replay = collect(db, [source(tmp_path)], client=Pages(page()), now=NOW)
        assert replay['sources'][0]['new_announcements'] == 0 and replay['events'] == 1
        assert events(db, NOW)[0]['first_seen'] == first_seen
        assert pages.requests == [URL]


def test_future_schema_end_alone_cannot_admit_an_already_started_event(tmp_path):
    with connect(':memory:') as db:
        report = collect(db, [source(tmp_path)], client=Pages(page(body='<p>Build software applications.</p>')), now=NOW)
        assert report['sources'][0]['accepted'] == 0
        assert 'No confirmed start or cutoff' in report['sources'][0]['decisions'][0]['reason']
