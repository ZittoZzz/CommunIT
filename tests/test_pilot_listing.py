"""The optional pilot view places only evidenced window entries in Upcoming."""
from datetime import datetime, timezone, timedelta
import json
from backend import db
from backend.app import create_app
from backend.domain import parse_moment

NOW=datetime(2035,11,22,14,tzinfo=timezone.utc)

def sample(conn, **facts):
    db.register_sources(conn,[{'id':'sample','name':'Example','kind':'html','url':'https://example.org/'}])
    db.ingest(conn,'sample',{'url':'https://example.org/event','title':'Example','posted_at':None,'access':'full','official':True,
      'identity':{'organizer_key':'example','series':'Example','edition':'2035','region':'NCR','stage':'main'},
      'facts':{'name':'Example','organizer':'Example','registration_state':'unknown',**facts},'field_evidence':{}},NOW.isoformat());conn.commit()

def test_undated_lead_is_watchlisted_without_changing_stored_facts():
    conn=db.connect(':memory:');sample(conn)
    assert db.events(conn,NOW)[0]['section']=='upcoming'
    assert db.events(conn,NOW,window_days=45)[0]['section']=='watchlist'
    assert db.events(conn,NOW)[0]['section']=='upcoming'

def test_out_of_window_and_end_alone_do_not_qualify():
    conn=db.connect(':memory:');sample(conn,start=parse_moment((NOW+timedelta(days=45)).isoformat()),end=parse_moment((NOW+timedelta(days=46)).isoformat()))
    assert db.events(conn,NOW,window_days=45)[0]['section']=='watchlist'

def test_started_contest_qualifies_by_submission_not_end():
    conn=db.connect(':memory:');sample(conn,start=parse_moment((NOW-timedelta(days=1)).isoformat()),end=parse_moment((NOW+timedelta(days=2)).isoformat()),submission_deadline=parse_moment((NOW+timedelta(days=2)).isoformat()))
    assert db.events(conn,NOW,window_days=45)[0]['section']=='upcoming'

def test_date_only_today_preserves_precision_until_next_manila_day():
    conn=db.connect(':memory:');sample(conn,start=parse_moment('2035-11-22'))
    event=db.events(conn,NOW,window_days=45)[0]
    assert event['section']=='upcoming' and event['start']['value']=='2035-11-22' and event['start']['precision']=='date'
    assert db.events(conn,datetime(2035,11,22,16,tzinfo=timezone.utc),window_days=45)[0]['section']=='past'

def test_configured_pilot_is_used_by_normal_api(tmp_path,monkeypatch):
    config=tmp_path/'sources.json';config.write_text(json.dumps({'sources':[],'listing_window_days':45}))
    monkeypatch.setenv('CTF_SOURCES',str(config))
    path=tmp_path/'events.db';conn=db.connect(path);sample(conn);conn.close()
    event=create_app(path).test_client().get('/api/events').json['events'][0]
    assert event['section']=='watchlist'

def test_ctftime_primary_proof_is_labeled_official_but_legacy_directory_is_not():
    conn=db.connect(':memory:')
    db.register_sources(conn,[{'id':'ctftime','name':'CTFtime','kind':'ctftime','url':'https://ctftime.org/api/v1/events/'}])
    payload={'url':'https://organizer.example/event','title':'Example','posted_at':None,'access':'full','official':True,
      'directory_provenance':{'url':'https://ctftime.org/event/123/'},
      'identity':{'organizer_key':'example','series':'Example','edition':'2035','region':'Worldwide','stage':'main'},
      'facts':{'name':'Example','organizer':'Example','registration_state':'unknown'},'field_evidence':{}}
    db.ingest(conn,'ctftime',payload,NOW.isoformat())
    assert db.events(conn,NOW)[0]['announcement_label']=='Official announcement'
    payload.pop('directory_provenance')
    db.ingest(conn,'ctftime',payload,(NOW+timedelta(seconds=1)).isoformat())
    assert db.events(conn,NOW)[0]['announcement_label']=='CTFtime listing'
