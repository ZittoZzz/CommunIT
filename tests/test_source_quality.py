"""Source qualification contracts; all fixtures are fictional, no network."""
from copy import deepcopy
from datetime import timedelta
import json
import sys

import pytest

from backend import db
from backend.adapters import Result
from backend.app import create_app
from backend.collect import collect
from backend.public_directory import public_event, listings_updated_at
from backend.source_index import load_sources, SourceConfigurationError
from test_event_review import SOURCE
from test_opportunity_pages import NOW, page, verify


def payload():
    ann, _ = verify(page())
    return ann


def test_profile_exclusion_preserves_event_citations_and_history(tmp_path, monkeypatch):
    database = tmp_path / 'test.sqlite3'
    config = tmp_path / 'community.json'
    config.write_text(json.dumps({'sources': []}))
    monkeypatch.setenv('CTF_SOURCES', str(config))
    conn = db.connect(database)
    db.register_sources(conn, [SOURCE])
    ann = payload(); db.ingest(conn, SOURCE['id'], ann, NOW.isoformat()); conn.commit()
    before = conn.execute('SELECT count(*) FROM revisions').fetchone()[0]
    client = create_app(database).test_client()
    assert db.source_states(conn, profile=str(config.resolve()), active_only=True) == []
    assert len(db.source_states(conn)) == 1
    data = client.get('/api/events').json
    assert len(data['events']) == 1
    assert data['events'][0]['announcement_url'] == ann['url']
    assert data['events'][0]['field_evidence']['name']['url'] == ann['field_evidence']['name']['url']
    assert conn.execute('SELECT count(*) FROM revisions').fetchone()[0] == before
    assert 'sources' not in data and 'manual_collection' not in data
    assert client.get('/api/sources').status_code == 404
    conn.close()


def test_partial_cli_run_reconciles_complete_profile(tmp_path, monkeypatch):
    import backend.collect as module
    config = tmp_path / 'community.json'; database = tmp_path / 'test.sqlite3'
    second = {**SOURCE, 'id': 'other'}
    config.write_text(json.dumps({'sources': [SOURCE, second]}))
    monkeypatch.setattr(sys, 'argv', ['collect', '--database', str(database), '--config', str(config), '--source', SOURCE['id']])
    def run(conn, sources):
        assert [s['id'] for s in sources] == [SOURCE['id']]
        return {'sources': [{'status': 'ok'}]}
    monkeypatch.setattr(module, 'collect', run)
    assert module.main() == 0
    conn = db.connect(database)
    assert {s['id'] for s in db.source_states(conn, profile=str(config.resolve()), active_only=True)} == {SOURCE['id'], 'other'}
    db.reconcile_sources(conn, [{**SOURCE,'enabled':False}], 'another-profile')
    assert len(db.source_states(conn, profile=str(config.resolve()), active_only=True)) == 2
    assert all(s['enabled'] for s in db.source_states(conn, profile=str(config.resolve()), active_only=True))
    conn.close()


def test_missing_directory_entry_does_not_cancel_saved_event():
    conn = db.connect(':memory:'); db.register_sources(conn, [SOURCE])
    db.ingest(conn, SOURCE['id'], payload(), NOW.isoformat()); conn.commit()
    collect(conn, [SOURCE], adapters={'rss': lambda *args: Result()}, now=NOW + timedelta(hours=1))
    event, = db.events(conn, NOW)
    assert event['status'] == 'scheduled'
    assert conn.execute('SELECT withdrawn FROM announcements').fetchone()[0] == 0


def test_meetup_identity_keeps_both_discovery_paths_internally():
    conn = db.connect(':memory:'); second = {**SOURCE, 'id': 'second'}
    db.register_sources(conn, [SOURCE, second]); ann = payload()
    ann['discovery_path'] = [SOURCE['url'], ann['url']]
    db.ingest(conn, SOURCE['id'], ann, NOW.isoformat())
    newer = deepcopy(ann); newer['url'] = ann['url'].replace('/example-', '/new-')
    newer['discovery_path'] = ['https://directory.example/events', newer['url']]
    newer['discovery_query'] = 'generic regional technology communities'
    db.ingest(conn, 'second', newer, (NOW + timedelta(hours=1)).isoformat())
    assert len(db.events(conn, NOW)) == 1
    paths = [json.loads(r['path_json']) for r in conn.execute('SELECT * FROM announcement_discovery')]
    assert ann['discovery_path'] in paths and newer['discovery_path'] in paths
    public = json.dumps(public_event(db.events(conn, NOW)[0]))
    assert 'generic regional technology communities' not in public
    assert SOURCE['url'] not in public


def test_freshness_uses_verified_page_even_for_partial_not_empty_search():
    conn = db.connect(':memory:')
    ann = payload()
    def partial(*args):
        result = Result(); result.announcements = [ann]; result.warnings = ['budget reached']; return result
    collect(conn, [SOURCE], adapters={'rss': partial}, now=NOW)
    stamp = listings_updated_at(db.events(conn, NOW))
    assert stamp == NOW.isoformat()
    assert db.source_states(conn)[0]['last_success'] is None
    search = {**SOURCE, 'id': 'search'}
    collect(conn, [search], adapters={'rss': lambda *args: Result()}, now=NOW + timedelta(days=1))
    assert listings_updated_at(db.events(conn, NOW)) == stamp
    lead = deepcopy(ann); lead['access'] = 'search_only'
    db.ingest(conn, 'search', lead, (NOW + timedelta(days=2)).isoformat())
    assert listings_updated_at(db.events(conn, NOW)) == stamp
    assert listings_updated_at([]) is None


def test_public_projection_is_allowlisted_and_keeps_useful_citations():
    conn = db.connect(':memory:'); db.register_sources(conn, [SOURCE])
    ann = payload(); ann['discovery_query'] = 'PRIVATE QUERY'; ann['discovery_path'] = [SOURCE['url'], ann['url']]
    ann['publisher'] = 'Example student association'
    ann['related_links'] = [{'url': SOURCE['url'], 'label': 'feed'}, {'url': 'https://organizer.example/register', 'label': 'Sign up', 'discovered_on': SOURCE['url']}]
    db.ingest(conn, SOURCE['id'], ann, NOW.isoformat())
    event = db.events(conn, NOW)[0]; event['internal_budget'] = 80
    event['field_evidence']['traversal_trace'] = {'url':SOURCE['url'], 'quote':'private'}
    result = public_event(event); rendered = json.dumps(result)
    assert result['announcements'][0]['publisher'] == 'Example student association'
    assert result['announcements'][0]['related_links'] == [{'url':'https://organizer.example/register','label':'Sign up','access':'linked_only'}]
    for hidden in ('PRIVATE QUERY', 'discovery_query', 'discovery_path', 'traversal_trace', 'internal_budget', 'source_name', SOURCE['url']):
        assert hidden not in rendered
    assert result['field_evidence']['name']
    assert result['eligibility'] == event['eligibility']


def test_profile_overrides_are_local_and_do_not_change_default(tmp_path):
    parent = tmp_path / 'parent.json'; child = tmp_path / 'child.json'
    parent.write_text(json.dumps({'sources': [SOURCE]}))
    child.write_text(json.dumps({'extends':'parent.json','sources':[], 'source_overrides':{SOURCE['id']:{'enabled':False,'reason':'Qualification pending'}}}))
    assert load_sources(parent)[0].get('enabled', True)
    assert load_sources(child)[0]['enabled'] is False
    assert load_sources(child)[0]['index_reason'] == 'Qualification pending'


@pytest.mark.parametrize('patch', [{'missing': {'enabled':False}}, {SOURCE['id']:{'url':'https://replacement.example'}}, {SOURCE['id']:{'enabled':'false'}}])
def test_invalid_profile_override_fails(tmp_path, patch):
    config = tmp_path / 'sources.json'; config.write_text(json.dumps({'sources':[SOURCE],'source_overrides':patch}))
    with pytest.raises(SourceConfigurationError):
        load_sources(config)


@pytest.mark.parametrize('error,status', [('Cannot verify robots.txt: HTTP 403','blocked'), ('HTTP 503','error')])
def test_unreadable_calendar_is_not_healthy_empty(error, status):
    from backend.opportunity_search import opportunity_search
    from backend.network import FetchError
    from test_opportunity_search import Client
    url = 'https://luma.com/example-calendar'
    result = opportunity_search({**SOURCE,'kind':'opportunity_calendar','url':url}, Client(pages={url:FetchError(error)}), [], NOW)
    assert result.failed and result.failure_status == status
    assert not result.announcements


def test_two_calendar_paths_share_one_fetch_and_keep_both_paths(monkeypatch):
    from backend import opportunity_search as module
    from test_opportunity_search import Client
    a, b = 'https://luma.com/calendar-a', 'https://luma.com/calendar-b'
    ann = payload(); event_url = ann['url']
    client = Client(pages={a:b'a',b:b'b',event_url:b'event'})
    monkeypatch.setattr(module, 'page_event_links', lambda raw,url,**kwargs:[event_url] if url in (a,b) else [])
    monkeypatch.setattr(module, 'verify_page', lambda *args:(deepcopy(ann),'Verified fixture'))
    source = {**SOURCE,'kind':'opportunity_calendar','url':a,'calendar_urls':[a,b],'window_days':45}
    result = module.opportunity_search(source, client, [], NOW)
    assert len(result.announcements) == 1
    assert [a,event_url] in result.announcements[0]['discovery_paths']
    assert [b,event_url] in result.announcements[0]['discovery_paths']
    assert [url for url,_ in client.requests].count(event_url) == 1


def test_legacy_structured_publisher_is_a_public_label_not_internal_object():
    event = {'id':'legacy','announcements':[{'url':'https://publisher.example/event',
        'publisher':{'id':'internal','name':'Campus Association','role':'resharer','url':'https://publisher.example/feed/'}}]}
    result = public_event(event)
    assert result['announcements'][0]['publisher'] == 'Campus Association'
    assert 'internal' not in json.dumps(result)
