"""Partner search discovery uses fictional future editions, never target data."""
import json
from pathlib import Path

import pytest

from backend.tavily import search_announcement


@pytest.fixture
def source():
    config = json.loads((Path(__file__).parents[1] / 'sources.json').read_text())
    return next(item for item in config['sources'] if item['kind'] == 'tavily')


@pytest.mark.parametrize('host', ['crest-approved.org', 'www.crest-approved.org'])
def test_verified_partner_can_identify_configured_series_without_promoting_snippet_facts(source, host):
    title = 'ROOTCON 99 Philippines 2099 | CREST CTF Prize Sponsor'
    url = f'https://{host}/event/fictional-future-edition/'
    announcement, reason = search_announcement({
        'url': url, 'title': title,
        'content': 'Registration open. Competition dates: January 1–4, 2099. Format: online.',
    }, source)
    assert announcement is not None, reason
    assert announcement['facts']['name'] == 'ROOTCON 99 CTF'
    assert announcement['facts']['organizer'] == 'ROOTCON'
    assert announcement['access'] == 'search_only'
    assert announcement['official'] is False
    assert announcement['posted_at'] is None
    for field in ('start', 'end', 'deadline', 'registration_url', 'registration_state', 'eligibility'):
        assert announcement['facts'][field] is None
    assert announcement['facts']['format'] == 'unknown'
    assert announcement['field_evidence']['name'] == {'url': url, 'quote': title}


@pytest.mark.parametrize('title,host', [
    ('Overseas CTF 2099', 'crest-approved.org'),
    ('Japanese University hosts Overseas CTF 2099', 'www.crest-approved.org'),
    ('ROOTCON 99 CTF 2099', 'crest-approved.org.foreign.example'),
    ('ROOTCON 99 CTF 2099', 'fake-crest-approved.org'),
    ('ROOTCON 99 CTF 2099', 'unconfigured.crest-approved.org'),
])
def test_partner_host_alone_or_lookalike_domain_does_not_establish_ownership(source, title, host):
    announcement, reason = search_announcement({'url': f'https://{host}/event/', 'title': title}, source)
    assert announcement is None
    assert reason == 'Philippine organizer or venue not established by title/source'


def test_partner_mapping_can_omit_facebook_accounts_and_require_explicit_named_host(source):
    source['organizers'] = [{
        'publisher_hosts': ['partner.example'],
        'organizer': 'Kestrel University', 'organizer_key': 'kestrel-university',
        'philippine_connection': 'Fictional Philippine university.',
    }]
    announcement, reason = search_announcement({
        'url': 'https://partner.example/event/',
        'title': 'Kestrel University hosts Nebula CTF 2099',
    }, source)
    assert announcement is not None, reason
    assert announcement['facts']['organizer'] == 'Kestrel University'
    rejected, _ = search_announcement({
        'url': 'https://partner.example/event/', 'title': 'Nebula CTF 2099',
    }, source)
    assert rejected is None
