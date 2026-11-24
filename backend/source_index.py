"""Load the publisher index into the existing daily source configuration.

The index contains recurring publisher monitors, never individual event URLs.
Research examples belong in documentation and are not consumed by this loader.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


class SourceConfigurationError(ValueError):
    pass


def _validate_source(source, supported):
    if not isinstance(source, dict):
        raise SourceConfigurationError('Every source must be an object')
    for field in ('id', 'name', 'kind', 'url'):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise SourceConfigurationError(f'Source requires a nonempty {field}')
    if source['kind'] not in supported:
        raise SourceConfigurationError(f"Unknown source adapter: {source['kind']}")
    if 'enabled' in source and not isinstance(source['enabled'], bool):
        raise SourceConfigurationError(f"Source {source['id']}: enabled must be boolean")


def _overrides(sources, config):
    """Profile-local scheduling decisions; inherited/default routes stay intact."""
    overrides = config.get('source_overrides', {})
    if not isinstance(overrides, dict) or set(overrides) - {s['id'] for s in sources}:
        raise SourceConfigurationError('source_overrides requires known source IDs')
    for source in sources:
        patch = overrides.get(source['id'], {})
        if not isinstance(patch, dict) or set(patch) - {'enabled', 'reason'}:
            raise SourceConfigurationError('Source overrides support enabled and reason only')
        if 'enabled' in patch and not isinstance(patch['enabled'], bool):
            raise SourceConfigurationError('Source override enabled must be boolean')
        if 'reason' in patch and not isinstance(patch['reason'], str):
            raise SourceConfigurationError('Source override reason must be text')
        source.update(patch)
        if patch.get('reason'):
            source['index_reason'] = patch['reason']
    return sources


def load_sources(config_path, *, supported_adapters=None, _parents=()):
    """Merge legacy sources with enabled and disabled publisher index records.

    An index entry references one legacy source using ``source_id``, or defines
    one new recurring monitor using ``monitor``. Unreferenced legacy sources are
    retained. Disabled monitors are returned too, so health can explain why no
    request was made instead of making the source disappear.
    """
    if supported_adapters is None:
        from .adapters import ADAPTERS
        supported_adapters = ADAPTERS
    supported = set(supported_adapters) | {'restricted'}
    config_path = Path(config_path).resolve()
    if config_path in _parents:
        raise SourceConfigurationError('Source configuration inheritance cycle')
    config = json.loads(config_path.read_text())
    if not isinstance(config.get('sources'), list):
        raise SourceConfigurationError('Configuration requires a sources list')
    sources = deepcopy(config['sources'])
    if config.get('extends'):
        if not isinstance(config['extends'], str):
            raise SourceConfigurationError('extends must be a configuration path')
        parent = load_sources(config_path.parent / config['extends'], supported_adapters=supported,
                              _parents=(*_parents, config_path))
        excluded = config.get('exclude_sources', [])
        if not isinstance(excluded, list) or not all(isinstance(s, str) for s in excluded):
            raise SourceConfigurationError('exclude_sources must be a list of source IDs')
        if set(excluded) - {s['id'] for s in parent}:
            raise SourceConfigurationError('exclude_sources contains an unknown source ID')
        sources = [s for s in parent if s['id'] not in excluded] + sources
    by_id = {}
    for source in sources:
        _validate_source(source, supported)
        if source['id'] in by_id:
            raise SourceConfigurationError(f"Duplicate source ID: {source['id']}")
        by_id[source['id']] = source
    index_name = config.get('publisher_index')
    if not index_name:
        return sorted(_overrides(sources, config), key=lambda source: 2 if source['kind'] in ('tavily', 'brave') else
                      1 if source['kind'] == 'opportunity_search' else 0)
    if not isinstance(index_name, str):
        raise SourceConfigurationError('publisher_index must be a file path')
    index_path = config_path.parent / index_name
    index = json.loads(index_path.read_text())
    if not isinstance(index.get('publishers'), list):
        raise SourceConfigurationError('Publisher index requires a publishers list')
    seen_publishers, claimed_sources = set(), set()
    for entry in index['publishers']:
        if not isinstance(entry, dict):
            raise SourceConfigurationError('Every publisher must be an object')
        for field in ('id', 'name'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise SourceConfigurationError(f'Publisher requires a nonempty {field}')
        if entry['id'] in seen_publishers:
            raise SourceConfigurationError(f"Duplicate publisher ID: {entry['id']}")
        seen_publishers.add(entry['id'])
        if entry.get('role') not in ('organizer', 'resharer', 'both'):
            raise SourceConfigurationError(f"Publisher {entry['id']}: invalid role")
        if not isinstance(entry.get('enabled'), bool):
            raise SourceConfigurationError(f"Publisher {entry['id']}: enabled must be boolean")
        coverage = entry.get('coverage', [])
        if isinstance(coverage, str):
            coverage = [coverage]
        if not isinstance(coverage, list) or not all(isinstance(value, str) for value in coverage):
            raise SourceConfigurationError(f"Publisher {entry['id']}: coverage must be text or a list of text")
        if ('source_id' in entry) == ('monitor' in entry):
            raise SourceConfigurationError(f"Publisher {entry['id']}: provide exactly one source_id or monitor")
        if 'source_id' in entry:
            if entry['source_id'] not in by_id:
                raise SourceConfigurationError(f"Publisher {entry['id']}: unknown source_id")
            source = by_id[entry['source_id']]
        else:
            source = deepcopy(entry['monitor'])
            _validate_source(source, supported)
            if source['id'] in by_id:
                raise SourceConfigurationError(f"Duplicate source ID: {source['id']}")
            sources.append(source)
            by_id[source['id']] = source
        if source['id'] in claimed_sources:
            raise SourceConfigurationError(f"Source {source['id']} belongs to more than one publisher entry")
        claimed_sources.add(source['id'])
        source.update({
            'index_id': entry['id'], 'publisher_name': entry['name'],
            'publisher_role': entry['role'], 'coverage': coverage,
            'enabled': entry['enabled'], 'index_status': entry.get('status', ''),
            'index_reason': entry.get('reason', ''),
        })
    # Direct recurring publishers run before supplemental search, including
    # when monitors were appended from the index.
    return sorted(_overrides(sources, config), key=lambda source: source['kind'] in ('tavily', 'brave', 'opportunity_search'))
