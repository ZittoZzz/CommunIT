"""Topic projection uses saved event evidence, including pre-existing records."""
import copy
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from backend import db
from backend.app import create_app
from backend.topics import project_topics
from backend.event_text import project_content


URL = 'https://organizer.example/events/workshop'
NOW = datetime(2035, 11, 22, 14, tzinfo=timezone.utc)


def announcement(quote, *, name='Community workshop', **overrides):
    return {
        'url': URL, 'title': name, 'access': 'full', 'official': True,
        'identity': {'organizer_key': 'community', 'series': 'Workshop',
                     'edition': '2035', 'region': 'NCR', 'stage': 'main'},
        'facts': {'name': name, 'organizer': 'Example Community', 'topic': 'ai'},
        'field_evidence': {'topic': {'url': URL, 'quote': quote}},
        **overrides,
    }


@pytest.mark.parametrize(('quote', 'expected'), [
    ('Cybersecurity workshop and digital forensics exercises.', ['cybersecurity']),
    ('Participants will build AI apps in this hands-on workshop.', ['ai_data', 'software_development']),
    ('AI app-building workshop.', ['ai_data', 'software_development']),
    ('Data science and data analytics workshop.', ['ai_data']),
    ('Learn cloud computing, DevOps and Kubernetes.', ['cloud', 'devops']),
    ('Software development and web development workshop.', ['software_development']),
    ('Computer networks, TCP/IP and system administration.', ['networking_systems']),
    ('A technology conference covering a broad range of tech topics.', ['general_it']),
    ('A multi-topic technology meetup.', ['general_it']),
    ('An AI technology conference.', ['ai_data']),
    ('An information technology meetup.', ['general_it']),
    ('Websites, mobile apps, games, AI tools, and low-code builds are welcome.', ['ai_data', 'software_development']),
    ('ExampleCTF 2035', ['cybersecurity']),
])
def test_explicit_subjects_have_stable_labels_and_source_quotes(quote, expected):
    topics, proof = project_topics([announcement(quote)])
    assert topics == expected
    assert list(proof) == expected
    assert all(value == {'url': URL, 'quote': quote} for value in proof.values())


@pytest.mark.parametrize('quote', [
    'Community hackathon. Bring a friend.',
    'AWS Student Community Day',
    'Meet the Google Cloud community.',
    'Networking with other students and making new friends.',
    'Hackathon teams can include students.',
    'An open source community gathering.',
    'DevFest 2035',
    'A student community event.',
    'Complete technical challenges, join live sessions, and build technical projects.',
    'Information technology students welcome.',
    'Hosted by the Cloud Computing Student Club.',
    'This session does not discuss AI.',
    'AI is not covered in this meetup.',
    'Cloud computing is not part of this event.',
    'No software development is planned.',
])
def test_ambiguous_legacy_topic_is_not_a_fallback_or_keyword_guess(quote):
    payload = announcement(quote)
    payload['facts']['topic'] = 'general_it'
    assert project_topics([payload]) == ([], {})


def test_organizer_name_metadata_and_search_queries_are_not_subjects():
    payload = announcement('Join Global AI Manila for a community gathering.')
    payload['facts']['organizer'] = 'Global AI Manila'
    payload['discovery_query'] = 'cloud development AI software conference'
    payload['field_evidence']['organizer'] = {'url': URL, 'quote': 'AWS cloud computing and AI'}
    payload['field_evidence']['eligibility'] = {'url': URL, 'quote': 'Information technology students welcome.'}
    assert project_topics([payload]) == ([], {})


def test_citation_retains_exact_sentence_before_organizer_name_masking():
    quote = 'Join Global AI Manila for a software development workshop.'
    payload = announcement(quote)
    payload['facts']['organizer'] = 'Global AI Manila'
    topics, proof = project_topics([payload])
    assert topics == ['software_development']
    assert proof['software_development']['quote'] == quote


def test_sponsor_list_does_not_add_topics_to_an_event():
    payload = announcement('Software development workshop.\nSponsors: AI Cloud Computing Network Security Partners')
    assert project_topics([payload])[0] == ['software_development']


@pytest.mark.parametrize('quote', [
    'Learn software development. Sponsored by Cloud Computing Community.',
    'A software development workshop sponsored by Cloud Computing Community.',
    'Learn software development. Organizer: Cloud Computing Community.',
])
def test_inline_sponsor_sentence_is_not_event_subject_evidence(quote):
    payload = announcement(quote)
    assert project_topics([payload])[0] == ['software_development']


def test_not_only_subject_list_is_affirmative():
    payload = announcement('Not only AI but software development will be covered.')
    assert project_topics([payload])[0] == ['ai_data', 'software_development']


@pytest.mark.parametrize('change', [
    {'access': 'search_only'},
    {'official': False},
    {'official': None, 'publisher_role': 'discovery'},
    {'access': 'blocked'},
])
def test_unverified_ai_title_or_search_only_result_does_not_establish_topics(change):
    assert project_topics([announcement('Build an AI app.', **change)]) == ([], {})


def test_fetched_organizer_announcement_without_new_topic_field_still_gets_tag():
    payload = announcement('ExampleCTF competition', name='ExampleCTF 2035', official=None, publisher_role='organizer')
    payload['facts'].pop('topic')
    payload['field_evidence']['name'] = payload['field_evidence'].pop('topic')
    assert project_topics([payload])[0] == ['cybersecurity']


def test_fetched_partner_notice_can_corroborate_a_named_actual_ctf():
    payload = announcement('Join the Capture the Flag (CTF) competition.', name='Community CTF 2035', official=False)
    assert project_topics([payload])[0] == ['cybersecurity']
    payload['access'] = 'search_only'
    assert project_topics([payload]) == ([], {})


def test_multiple_announcements_produce_one_of_each_supported_tag_without_mutation():
    payloads = [announcement('Build AI apps.'), announcement('AI and data science workshop.')]
    original = copy.deepcopy(payloads)
    assert project_topics(payloads)[0] == ['ai_data', 'software_development']
    assert payloads == original


def test_topic_value_alone_is_insufficient_and_unsupported_quote_has_no_evidence():
    payload = announcement('AI workshop')
    payload['field_evidence'] = {}
    assert project_topics([payload]) == ([], {})
    payload['field_evidence'] = {'topic': {'url': 'javascript:alert(1)', 'quote': 'AI workshop'}}
    assert project_topics([payload]) == ([], {})


def _seed(conn, payload):
    db.register_sources(conn, [{'id': 'sample', 'name': 'Sample', 'kind': 'html', 'url': URL}])
    db.ingest(conn, 'sample', payload, NOW.isoformat())
    conn.commit()


def test_existing_database_projects_topics_read_only_without_reprocessing(tmp_path):
    path = tmp_path / 'stored.sqlite3'
    conn = db.connect(path)
    payload = announcement('Build AI applications in this workshop.')
    _seed(conn, payload)
    _seed(conn, announcement('', name='Legacy gathering', identity={**payload['identity'], 'edition': 'legacy'}))
    before = list(conn.iterdump())
    conn.close()

    # Use SQLite's immutable reader: this projection cannot migrate or rewrite
    # a record, even when run over an old stored payload with no topics array.
    reader = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)
    reader.row_factory = sqlite3.Row
    rows = db.events(reader, NOW)
    assert {row['name']: row['topics'] for row in rows} == {
        'Community workshop': ['ai_data', 'software_development'], 'Legacy gathering': []}
    assert list(reader.iterdump()) == before
    assert all(row['first_seen'] == NOW.isoformat() for row in rows)
    reader.close()


def test_normal_api_includes_topics_for_old_and_new_rows_without_changing_legacy_field(tmp_path, monkeypatch):
    config = tmp_path / 'sources.json'
    config.write_text(json.dumps({'sources': []}))
    monkeypatch.setenv('CTF_SOURCES', str(config))
    path = tmp_path / 'events.sqlite3'
    conn = db.connect(path)
    payload = announcement('Build AI apps in this workshop.')
    _seed(conn, payload)
    unknown = announcement('', name='Legacy gathering', identity={**payload['identity'], 'edition': 'legacy'})
    _seed(conn, unknown)
    conn.close()
    app = create_app(path).test_client()
    original_rows = app.get('/api/events').json['events']
    assert len(original_rows) == 2
    by_name = {event['name']: event for event in original_rows}
    assert by_name['Community workshop']['topics'] == ['ai_data', 'software_development']
    assert by_name['Community workshop']['topic'] == 'ai'
    assert by_name['Legacy gathering']['topics'] == []

    conn = db.connect(path)
    _seed(conn, announcement('Computer networks workshop.', name='Systems meetup',
        identity={**payload['identity'], 'edition': 'systems'}))
    conn.close()
    rows = app.get('/api/events').json['events']
    assert next(row for row in rows if row['name'] == 'Systems meetup')['topics'] == ['networking_systems']
    assert [row['id'] for row in rows if row['name'] != 'Systems meetup'] == [row['id'] for row in original_rows]


def program_announcement(text, *, field='description', **kwargs):
    payload = announcement('', **kwargs)
    payload['facts'][field] = text
    payload['field_evidence'][field] = {'url': URL, 'quote': text}
    return payload


@pytest.mark.parametrize('text', [
    'A developer social to meet peers and share projects.',
    'We bring local developers together to share their projects.',
    'Our user-group social is a chance to meet other developers and connect with the community.',
    'The program includes a community-building session.',
])
def test_organizer_described_community_purpose_has_exact_topic(text):
    topics, proof = project_topics([program_announcement(text)])
    assert topics == ['community']
    assert proof['community'] == {'url': URL, 'quote': text}


def test_ai_workshop_with_explicit_community_showcase_matches_each_once():
    payload = program_announcement('Join an AI workshop followed by a community showcase.')
    assert project_topics([payload, payload])[0] == ['ai_data', 'community']


@pytest.mark.parametrize(('text', 'expected'), [
    ('Cloud computing workshop with a networking break.', ['cloud']),
    ('Cloud computing workshop. Networking break: meet fellow developers and share projects.', ['cloud']),
    ('We bring developers together at our recruitment-only job fair.', []),
    ('This is a job fair. Bring developers together to meet peers and share projects.', []),
    ('Meet local developers and employers to discuss job opportunities.', []),
    ('Our AWS sponsor supports this student gathering.', []),
    ('Hosted by the AWS Training Club.', []),
    ('A community showcase is not part of this event.', []),
    ('A workshop on computer networking and system administration.', ['networking_systems']),
])
def test_community_does_not_mean_break_recruitment_sponsor_or_technical_networking(text, expected):
    assert project_topics([program_announcement(text)])[0] == expected


def test_community_title_and_organizer_alone_are_not_program_evidence():
    title = 'Developer Social and Community Showcase'
    payload = announcement(title, name=title)
    payload['facts']['organizer'] = 'Community Builders'
    assert 'community' not in project_topics([payload])[0]
    payload['field_evidence']['topic']['quote'] = 'Schema.org Event name=' + title
    assert 'community' not in project_topics([payload])[0]
    assert project_content(payload)[0].get('description') is None
    payload['field_evidence']['topic']['quote'] = '  DEVELOPER social and COMMUNITY showcase. '
    assert 'community' not in project_topics([payload])[0]
    assert project_content(payload)[0].get('description') is None


def test_retained_program_topic_excerpt_can_describe_event_but_title_cannot():
    text = 'Join a hands-on session to build intelligent AI agents.'
    payload = announcement(text)
    facts, proof = project_content(payload)
    assert facts['description'] == text
    assert proof['description'] == {'url': URL, 'quote': text}
    payload = announcement('Hands-on AI Workshop', name='Hands-on AI Workshop')
    assert project_content(payload)[0].get('description') is None


def test_retained_full_description_does_not_repeat_contained_topic_sentence():
    payload = program_announcement('Build AI apps. Open to everyone.')
    payload['field_evidence']['topic']['quote'] = 'Build AI apps.'
    assert project_content(payload)[0]['description'] == 'Build AI apps. Open to everyone.'


def test_independent_community_program_is_not_lost_to_a_recruiting_booth_or_break():
    payload = program_announcement('AI workshops and a community showcase followed by a coffee break. A recruiting booth is also present.')
    assert project_topics([payload])[0] == ['ai_data', 'community']


@pytest.mark.parametrize('field', ['description', 'agenda', 'learning_objectives', 'eligibility'])
def test_saved_program_fields_support_multiple_technical_subjects(field):
    text = 'Hands-on workshops equip student builders with practical AWS skills, AI, and software engineering.'
    payload = program_announcement(text, field=field)
    facts, proof = project_content(payload)
    assert facts['description'] == text
    assert proof['description']['quote'] == text
    assert project_topics([payload])[0] == ['ai_data', 'cloud', 'software_development']
    if field == 'eligibility':
        assert facts['eligibility'] == 'Intended audience: student builders.'
        assert proof['eligibility']['quote'] == text


def test_legacy_program_recovery_keeps_real_requirements_without_writing_payload():
    text = 'Students only. Learn AWS in hands-on workshops. Attendees must bring a laptop.'
    payload = program_announcement(text, field='eligibility')
    original = copy.deepcopy(payload)
    facts, _ = project_content(payload)
    assert facts['description'] == 'Learn AWS in hands-on workshops.'
    assert facts['eligibility'] == 'Students only.\nAttendees must bring a laptop.'
    assert project_topics([payload])[0] == ['cloud']
    assert payload == original


def test_audience_subjects_are_not_program_topics_and_unverified_program_is_not_promoted():
    payload = program_announcement('AI students are welcome. AWS developers only.', field='eligibility')
    assert project_topics([payload]) == ([], {})
    payload = program_announcement('Learn AWS, AI, and software engineering.', field='eligibility', access='search_only')
    assert project_topics([payload]) == ([], {})
    assert project_content(payload)[0].get('description') is None


def test_saved_legacy_program_recovery_through_normal_api_preserves_storage(tmp_path, monkeypatch):
    config = tmp_path / 'sources.json'; config.write_text(json.dumps({'sources': []}))
    monkeypatch.setenv('CTF_SOURCES', str(config))
    path = tmp_path / 'events.sqlite3'
    conn = db.connect(path)
    payload = program_announcement('Workshops equip student builders with practical AWS skills, AI, and software engineering.', field='eligibility')
    _seed(conn, payload)
    before = conn.execute('SELECT payload, first_seen FROM announcements').fetchone()
    conn.close()
    row = create_app(path).test_client().get('/api/events').json['events'][0]
    assert row['topics'] == ['ai_data', 'cloud', 'software_development']
    assert row['description'] == payload['facts']['eligibility']
    assert row['eligibility'] == 'Intended audience: student builders.'
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    assert tuple(conn.execute('SELECT payload, first_seen FROM announcements').fetchone()) == tuple(before)
    conn.close()


def test_later_program_only_announcement_does_not_erase_known_admission_requirement():
    conn = db.connect(':memory:')
    first = program_announcement('Students only.', field='eligibility')
    _seed(conn, first)
    later = program_announcement('Learn AWS in hands-on workshops.', field='eligibility')
    later['url'] += '/update'
    later['field_evidence']['eligibility']['url'] = later['url']
    db.ingest(conn, 'sample', later, '2035-11-23T14:00:00+00:00')
    conn.commit()
    row = db.events(conn, NOW)[0]
    assert row['eligibility'] == 'Students only.'
    assert row['field_evidence']['eligibility']['quote'] == 'Students only.'
    assert row['description'] == 'Learn AWS in hands-on workshops.'
    assert row['topics'] == ['cloud']
    conn.close()


def test_legacy_conference_agenda_heading_does_not_classify_whole_conference():
    payload = announcement('', name='Student Community Day · CTF 2035', publisher_role='organizer')
    payload.update(title='Student Community Day 2035 · CTF', evidence='Capture The Flag')
    payload['field_evidence'] = {'name': {'url': URL, 'quote': payload['title']}}
    original = copy.deepcopy(payload)
    facts, _ = project_content(payload)
    assert facts['name'] == 'Student Community Day 2035'
    assert project_topics([payload]) == ([], {})
    assert payload == original
    # Supported program evidence can still supply topics; the organizer alone cannot.
    payload['field_evidence']['description'] = {'url': URL, 'quote': 'Learn cloud computing in hands-on workshops.'}
    assert project_topics([payload])[0] == ['cloud']


@pytest.mark.parametrize('series_name', ['HackForGov', 'Hack4Gov', 'Hack for Gov'])
@pytest.mark.parametrize('access', ['search_only', 'full'])
def test_hackforgov_series_topic_does_not_upgrade_search_evidence(series_name, access):
    payload = announcement('', name=f'{series_name} 2035', access=access, official=False)
    payload['identity']['series'] = 'HackForGov'
    payload['field_evidence'] = {'name': {'url': URL, 'quote': f'DICT: {series_name} 2035 regional competition'}}
    original = copy.deepcopy(payload)
    topics, proof = project_topics([payload])
    assert topics == ['cybersecurity']
    assert proof['cybersecurity']['access'] == access
    assert proof['cybersecurity']['basis'] == 'event_series'
    assert payload == original


@pytest.mark.parametrize('change', ['no_quote', 'wrong_identity', 'query_only', 'blocked', 'lookalike'])
def test_hackforgov_tag_needs_matching_retained_series_identity(change):
    payload = announcement('', name='HackForGov 2035', access='search_only', official=False)
    payload['identity']['series'] = 'HackForGov'
    payload['field_evidence'] = {'name': {'url': URL, 'quote': 'HackForGov 2035'}}
    if change == 'no_quote': payload['field_evidence'] = {}
    if change == 'wrong_identity': payload['identity']['series'] = 'Unknown event'
    if change == 'query_only':
        payload['field_evidence']['name']['quote'] = 'Student gathering'
        payload['discovery_query'] = 'HackForGov cybersecurity'
    if change == 'blocked': payload['access'] = 'blocked'
    if change == 'lookalike': payload['field_evidence']['name']['quote'] = 'HackForGovernment 2035'
    assert project_topics([payload]) == ([], {})


def test_normal_api_repairs_stored_topics_without_reprocessing_or_verifying_leads(tmp_path, monkeypatch):
    config = tmp_path / 'sources.json'
    config.write_text(json.dumps({'sources': [], 'listing_window_days': 45}))
    monkeypatch.setenv('CTF_SOURCES', str(config))
    path = tmp_path / 'preview.sqlite3'
    conn = db.connect(path)
    conference = announcement('', name='Student Community Day · CTF 2035')
    conference.update(title='Student Community Day 2035 · CTF', evidence='Capture The Flag')
    conference['field_evidence'] = {'name': {'url': URL, 'quote': conference['title']}}
    lead = announcement('', name='HackForGov 2035', access='search_only', official=False)
    lead['url'] = URL + '/lead'
    lead['identity']['series'] = 'HackForGov'
    lead['field_evidence'] = {'name': {'url': lead['url'], 'quote': 'Hack4Gov 2035'}}
    _seed(conn, conference); _seed(conn, lead)
    before = list(conn.execute('SELECT payload,first_seen FROM announcements ORDER BY id'))
    conn.close()
    client = create_app(path).test_client()
    rows = client.get('/api/events').json['events']
    by_name = {row['name']: row for row in rows}
    assert by_name['Student Community Day 2035']['topics'] == []
    event = by_name['HackForGov 2035']
    assert event['topics'] == ['cybersecurity']
    assert event['section'] == 'watchlist'
    assert event['registration_status'] == 'unknown'
    assert event['start'] is None and event['deadline'] is None
    assert event['announcements'][0]['access'] == 'search_only'
    with sqlite3.connect(path) as reader:
        assert [tuple(r) for r in before] == reader.execute('SELECT payload,first_seen FROM announcements ORDER BY id').fetchall()
