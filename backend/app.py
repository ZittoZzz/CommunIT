from __future__ import annotations

import json
import os
import atexit
import signal
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
import secrets
from .db import connect, events, register_sources, source_states
from .domain import utcnow
from .source_index import load_sources
from .manual_collection import ManualCollection, local_request

ROOT = Path(__file__).resolve().parent.parent


def create_app(database=None):
    app = Flask(__name__, static_folder=None)
    selected_database = database if database is not None else os.environ.get('CTF_DATABASE')
    app.config['DATABASE'] = selected_database
    db = connect(selected_database)
    config = Path(os.environ.get('CTF_SOURCES', str(ROOT / 'sources.json')))
    app.config['LISTING_WINDOW_DAYS'] = None
    if config.exists():
        register_sources(db, load_sources(config))
        window = json.loads(config.read_text()).get('listing_window_days')
        if window is not None and (not isinstance(window, int) or isinstance(window, bool) or window <= 0):
            raise ValueError('listing_window_days must be a positive integer')
        app.config['LISTING_WINDOW_DAYS'] = window
    db.close()
    manual = ManualCollection(selected_database, config, enabled=os.environ.get('CTF_ENABLE_MANUAL_FETCH') == '1')
    app.extensions['manual_collection'] = manual
    if manual.enabled:
        atexit.register(manual.close)

    @app.get('/api/events')
    def event_list():
        db = connect(app.config['DATABASE'])
        try:
            return jsonify(events=events(db, window_days=app.config['LISTING_WINDOW_DAYS']), sources=source_states(db), generated_at=utcnow(), timezone='Asia/Manila',
                           manual_collection=manual.capabilities() if local_request(request) else {'enabled': False})
        finally:
            db.close()

    @app.get('/api/sources')
    def source_list():
        db = connect(app.config['DATABASE'])
        try:
            return jsonify(sources=source_states(db))
        finally:
            db.close()

    @app.get('/api/health')
    def health():
        return jsonify(status='ok')

    @app.route('/api/collection', methods=['GET', 'POST'])
    def collection():
        if not manual.enabled:
            return jsonify(enabled=False, message='Manual collection is disabled.'), 404
        if not local_request(request):
            return jsonify(message='Manual collection is available only on this computer.'), 403
        if request.method == 'GET':
            return jsonify(manual.snapshot())
        if not secrets.compare_digest(request.headers.get('X-Collection-Token', '').encode(), manual.token.encode()):
            return jsonify(message='Invalid collection token. Reload the directory.'), 403
        if not request.is_json or request.get_json(silent=True) != {}:
            return jsonify(message='Send an empty JSON object; database and sources are configured by the server.'), 400
        try:
            started = manual.start()
        except (OSError, ValueError, TypeError, KeyError):
            return jsonify(enabled=True, state='failed', message='Collection configuration is unavailable or has no enabled sources.'), 400
        return jsonify(manual.snapshot()), 202 if started else 409

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if response.mimetype == 'application/json':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def index():
        dist = ROOT / 'frontend/dist'
        if not (dist / 'index.html').exists():
            return 'Frontend is not built yet. Run npm --prefix frontend run build.', 503
        return send_from_directory(dist, 'index.html')

    @app.get('/<path:path>')
    def assets(path):
        return send_from_directory(ROOT / 'frontend/dist', path)

    return app


if __name__ == '__main__':
    def stop_preview(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop_preview)
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
