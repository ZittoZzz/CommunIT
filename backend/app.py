from __future__ import annotations

import json
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from .db import connect, events, register_sources, source_states
from .domain import utcnow
from .source_index import load_sources

ROOT = Path(__file__).resolve().parent.parent


def create_app(database=None):
    app = Flask(__name__, static_folder=None)
    app.config['DATABASE'] = database
    db = connect(database)
    config = Path(os.environ.get('CTF_SOURCES', str(ROOT / 'sources.json')))
    if config.exists():
        register_sources(db, load_sources(config))
    db.close()

    @app.get('/api/events')
    def event_list():
        db = connect(app.config['DATABASE'])
        try:
            return jsonify(events=events(db), sources=source_states(db), generated_at=utcnow(), timezone='Asia/Manila')
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
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
