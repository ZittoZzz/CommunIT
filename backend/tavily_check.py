"""Print unfiltered keyless search results without opening or writing a database."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .network import Client
from .tavily import post_identity, search_queries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(Path(__file__).resolve().parent.parent / 'sources.json'))
    parser.add_argument('--report', help='Optional audit file containing URLs/titles, not full responses')
    parser.add_argument('--title', help='Optional comparison only; never sent to the search API')
    parser.add_argument('--post-id', help='Optional comparison only; never sent to the search API')
    args = parser.parse_args()
    source = next(s for s in json.loads(Path(args.config).read_text())['sources'] if s['kind'] == 'tavily')
    started = datetime.now(timezone.utc).isoformat()
    hits, searches, warnings = search_queries(source, Client())
    report = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
              'access': 'keyless', 'organizer_filters_applied': False, 'searches': searches,
              'warnings': warnings, 'comparisons': []}
    normalize = lambda text: re.sub(r'\s+', ' ', text).casefold()
    for search in searches:
        if search['status'] != 'ok':
            report['comparisons'].append({'query': search['query'], 'result_count': None})
            continue
        results = [hit for hit, query in hits if query == search['query']]
        facebook = [hit for hit in results if (urlsplit(hit.get('url', '')).hostname or '') in
                    ('facebook.com', 'www.facebook.com', 'm.facebook.com')]
        matches = []
        for hit in results:
            if not args.title:
                continue
            matched = 'title' if normalize(args.title) in normalize(hit.get('title', '')) else (
                'snippet' if normalize(args.title) in normalize(hit.get('content', '')) else None)
            if matched:
                matches.append({'url': hit.get('url'), 'matched_in': matched})
        report['comparisons'].append({'query': search['query'], 'result_count': len(results),
            'facebook_results': len(facebook), 'title_or_snippet_matches': matches,
            'numeric_post_matches': [hit['url'] for hit in facebook if args.post_id and
                post_identity(hit['url']) == 'facebook:post:' + args.post_id]})
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.report:
        Path(args.report).write_text(rendered + '\n')
    return 0 if any(s['status'] == 'ok' for s in searches) else 1


if __name__ == '__main__':
    raise SystemExit(main())
