"""Fictional program subjects exercise exact evidence joins, never live seeds."""
from copy import deepcopy
import json
import pytest
from backend.db import connect, ingest, register_sources, events
from backend.event_context import article_event_context, attach_article_context, context_match

ARTICLE = 'https://community.example/recap'
CALENDAR = 'https://luma.com/fictional-program'
SUBJECT = 'Lantern Protocol: Beyond the Gateway'
BODY = f'''<p>On March 8, 2032, the kickoff of <b>{SUBJECT}</b> welcomed teams to a cybersecurity CTF.</p>
<p>The event was held at Campus Hall, Seabreeze 4th Avenue.</p>
<p>A speaker at Example Company explained security.</p>'''


def recap():
    ann = {'url': ARTICLE, 'title': 'Community celebrates a successful competition', 'kind': 'recap', 'access': 'full',
           'identity': {'organizer_key': 'unconfirmed', 'series': 'Community competition report', 'edition': '2032', 'region': 'Unspecified', 'stage': 'main'},
           'facts': {'name': 'Community competition report 2032', 'lifecycle': 'finished', 'registration_state': 'closed'}, 'field_evidence': {}}
    return attach_article_context(ann, BODY)


def calendar():
    return {'url': CALENDAR, 'title': 'Research Club x ' + SUBJECT, 'kind': 'announcement', 'access': 'full',
            'identity': {'organizer_key': 'luma:usr-example', 'series': 'Research Club x ' + SUBJECT, 'edition': '2032', 'region': 'NCR', 'stage': 'main'},
            'facts': {'name': SUBJECT + ' 2032', 'registration_state': 'unknown'}, 'field_evidence': {},
            'event_context': {'kind': 'calendar', 'title': 'Research Club x ' + SUBJECT, 'calendar_date': '2032-03-08', 'region': 'NCR',
                              'venue': {'address': 'Seabreeze at Fourth Avenue'}, 'evidence': {'url': CALENDAR, 'quote': 'Public calendar: March 8, 2032; Seabreeze at Fourth Avenue'}}}


def connection():
    db = connect(':memory:')
    register_sources(db, [{'id': 'recap', 'name': 'Community', 'url': ARTICLE, 'kind': 'rss'}, {'id': 'calendar', 'name': 'Organizer', 'url': 'https://luma.com/community', 'kind': 'luma'}])
    return db


def test_explicit_subject_and_kickoff_date_have_source_evidence():
    context = article_event_context(BODY, ARTICLE)
    assert context['subject'] == SUBJECT
    assert context['calendar_date'] == '2032-03-08'
    assert context['evidence']['url'] == ARTICLE
    assert context['venue_names'] == ['Campus Hall, Seabreeze 4th Avenue']


@pytest.mark.parametrize('reverse', [False, True])
def test_exact_subject_date_and_venue_join_both_orders_and_preserve_history(reverse):
    db = connection()
    items = [('recap', recap()), ('calendar', calendar())]
    if reverse:
        items.reverse()
    first_id, _ = ingest(db, *items[0], now='2032-03-01T00:00:00+00:00')
    second_id, _ = ingest(db, *items[1], now='2032-03-02T00:00:00+00:00')
    assert first_id == second_id
    assert len(events(db)) == 1
    assert len(events(db)[0]['announcements']) == 2
    assert events(db)[0]['first_seen'] == '2032-03-01T00:00:00+00:00'
    for source, ann in items:
        ingest(db, source, ann, now='2032-03-03T00:00:00+00:00')
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
    assert db.execute('SELECT count(*) FROM announcements').fetchone()[0] == 2
    assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 2
    payloads = [json.loads(r[0]) for r in db.execute('SELECT payload FROM announcements')]
    assert any(p.get('event_match', {}).get('rule') == 'exact_program_subject_and_kickoff' for p in payloads)


@pytest.mark.parametrize('field,value', [('edition', '2033'), ('stage', 'qualifier'), ('stage', 'final'), ('stage', 'regional-final'), ('stage', 'national-final')])
def test_editions_and_rounds_stay_separate(field, value):
    first, second = recap(), calendar()
    second['identity'][field] = value
    assert context_match(first, second) is None


def test_conflicting_confirmed_regions_stay_separate():
    first, second = recap(), calendar()
    first['identity']['region'] = 'Region VII'
    assert context_match(first, second) is None


@pytest.mark.parametrize('change', ['date', 'venue', 'title', 'evidence', 'search_only'])
def test_mismatched_or_unsupported_context_is_not_joined(change):
    first, second = recap(), calendar()
    if change == 'date': second['event_context']['calendar_date'] = '2032-03-09'
    if change == 'venue': second['event_context']['venue'] = {'address': 'Different Science Education Center'}
    if change == 'title': second['event_context']['title'] = SUBJECT + ' Regional Qualifier'
    if change == 'evidence': second['event_context']['evidence'] = {}
    if change == 'search_only': second['access'] = 'search_only'
    assert context_match(first, second) is None


def test_generic_subject_with_no_geographic_confirmation_is_not_joined():
    first, second = recap(), calendar()
    first['event_context']['subject'] = 'Student CTF'
    first['event_context']['venue_names'] = []
    second['event_context'].update(title='Student CTF', venue={}, region='Unspecified')
    second['identity']['region'] = 'Unspecified'
    assert context_match(first, second) is None


def test_two_highlighted_subjects_or_kickoff_dates_are_ambiguous():
    assert article_event_context(BODY.replace('</b> welcomed', '</b> and <b>Another Community Tournament</b> welcomed'), ARTICLE) is None
    assert article_event_context(BODY.replace('On March 8, 2032,', 'Between March 8, 2032 and March 9, 2032,'), ARTICLE) is None
    assert article_event_context(BODY + BODY.replace(SUBJECT, 'Another Community Tournament'), ARTICLE) is None


def test_plain_bold_subject_without_explicit_kickoff_relation_is_not_identity():
    assert article_event_context(BODY.replace('the kickoff of', 'a talk about'), ARTICLE) is None


def test_two_existing_candidate_events_prevent_ambiguous_join():
    db = connection()
    first = recap()
    second = deepcopy(first)
    second['url'] = 'https://other.example/recap'
    second['identity']['series'] = 'A separate report with conflicting identity'
    second['event_context']['evidence']['url'] = second['url']
    ingest(db, 'recap', first)
    ingest(db, 'recap', second)
    ingest(db, 'calendar', calendar())
    assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 3


def test_unfinished_article_does_not_gain_recap_context():
    ann = recap()
    ann.pop('event_context')
    ann['kind'] = 'announcement'
    ann['facts']['lifecycle'] = None
    assert 'event_context' not in attach_article_context(ann, BODY)
