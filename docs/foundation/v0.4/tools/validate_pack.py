#!/usr/bin/env python3
"""Check the text-only Desk documentation pack, not a running application."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_graph(graph: dict) -> None:
    """Small fixture consistency check; not a production access/graph validator."""
    ranks = {name: i for i, name in enumerate(['umbrella', 'topic', 'subtopic', 'granular'])}
    kinds = {'concept', 'skill', 'misconception', 'example'}
    relations = {'contains', 'prerequisite', 'application', 'related'}
    nodes = {n['id']: n for n in graph['nodes']}
    require(len(nodes) == len(graph['nodes']), 'Duplicate graph node ID')
    seen_slugs: set[tuple] = set()
    for n in nodes.values():
        require(n['conceptLevel'] in ranks and n['nodeKind'] in kinds, 'Unknown graph level/kind')
        key = (n['workspaceId'], n['scopeId'], n['slug'])
        require(key not in seen_slugs, 'Duplicate scoped slug')
        seen_slugs.add(key)
    seen_edges: set[str] = set()
    seen_related: set[tuple] = set()
    adjacency: dict[str, dict[str, list[str]]] = {'contains': {}, 'prerequisite': {}}
    for e in graph['edges']:
        require(e['id'] not in seen_edges, 'Duplicate graph edge ID')
        seen_edges.add(e['id'])
        require(e['relationType'] in relations, 'Unknown graph relation')
        require(e['sourceId'] in nodes and e['targetId'] in nodes, 'Dangling graph endpoint')
        s, t = nodes[e['sourceId']], nodes[e['targetId']]
        require(s['id'] != t['id'], 'Self edge')
        require(s['workspaceId'] == t['workspaceId'] == e['workspaceId'], 'Cross-workspace edge')
        require(s['scopeId'] == t['scopeId'] == e['scopeId'], 'Cross-scope edge')
        if e['relationType'] == 'contains':
            require(ranks[s['conceptLevel']] < ranks[t['conceptLevel']], 'Invalid containment order')
        if e['relationType'] == 'related':
            key = tuple(sorted((s['id'], t['id'])))
            require(key not in seen_related, 'Duplicate symmetric relation')
            seen_related.add(key)
        if e['relationType'] in adjacency:
            adjacency[e['relationType']].setdefault(s['id'], []).append(t['id'])
    for relation, neighbours in adjacency.items():
        visiting: set[str] = set()
        done: set[str] = set()
        def visit(node: str) -> None:
            require(node not in visiting, f'{relation} cycle')
            if node in done:
                return
            visiting.add(node)
            for target in neighbours.get(node, []):
                visit(target)
            visiting.remove(node)
            done.add(node)
        for node in nodes:
            visit(node)


def expect_bad_graph(graph: dict) -> None:
    try:
        validate_graph(graph)
    except ValueError:
        return
    raise ValueError('Deliberately invalid graph fixture was accepted')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--typecheck', action='store_true', help='Use installed tsc; install nothing.')
    parser.add_argument('--schema', action='store_true', help='Use installed jsonschema; install nothing.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks: list[str] = []
    required = [
        'START_HERE.md', 'HANDOFF.md', 'AGENTS.md', 'CLAUDE.md', 'CODEX.md',
        'docs/PRODUCT.md', 'docs/DECISIONS.md', 'docs/MCP_APPS.md', 'docs/DECISION_LAYER.md',
        'docs/GRAPH_MODEL.md', 'docs/MOBILE_INTERACTION.md', 'docs/NAVIGATION_AND_BRAND.md',
        'docs/THEME_BRIEF.md', 'docs/NOTES_AND_ACTIVITIES.md', 'docs/DEPLOYMENT_AND_PORTABILITY.md',
        'docs/VISUAL_SELECTION.md', 'prompts/FIRST_TASK.md', 'prompts/CLAUDE_FIRST_TASK.md',
        'prompts/CODEX_FIRST_TASK.md', 'prompts/DECISION_LAYER_SPIKE.md',
        'contracts/desk-contracts.ts', 'contracts/graph-contracts.ts', 'contracts/decision-contracts.ts',
        'fixtures/paper-session.synthetic.json', 'fixtures/mcp-app.synthetic.json',
        'fixtures/graph.synthetic.json', 'fixtures/decision-routing.synthetic.json',
    ]
    for name in required:
        require((root / name).is_file(), f'Missing {name}')
    checks.append('Required product, handoff, contracts and prompt files present')

    all_files = sorted(p for p in root.rglob('*') if p.is_file())
    allowed_suffixes = {'.md', '.json', '.ts', '.py'}
    for p in all_files:
        require(not p.is_symlink(), f'Symlink not allowed: {p}')
        require(p.suffix in allowed_suffixes, f'Non-text file type: {p}')
        text = p.read_text(encoding='utf-8')
        require('\x00' not in text, f'Binary-like content: {p}')
        if p.suffix in {'.md', '.json'}:
            require(not re.search(r'!\[[^\]]*\]\s*[\[(]|<\s*(?:img|svg)\b|data:image/', text, flags=re.I),
                    f'Embedded image/mockup: {p}')
    checks.append('All packaged files are UTF-8 text; no raster/vector/media files or embedded images')

    md_files = list(root.rglob('*.md'))
    ledger = (root / 'docs/SOURCES.md').read_text()
    source_ids = set(re.findall(r'\*\*([RMDLGUS]\d+)\s*[—–-]', ledger))
    for path in md_files:
        text = path.read_text(encoding='utf-8')
        require(text.count('```') % 2 == 0, f'Unbalanced code fence: {path}')
        for match in re.findall(r'\]\(([^)]+)\)', text):
            target = match.split('#', 1)[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            resolved = (path.parent / target).resolve()
            require(resolved.is_relative_to(root), f'Link outside package: {path}: {target}')
            require(resolved.exists(), f'Broken local link: {path}: {target}')
        for cite in re.findall(r'\[((?:[RMDLGUS]\d+)(?:,\s*[RMDLGUS]\d+)*)\]', text):
            for label in re.split(r',\s*', cite):
                require(label in source_ids, f'Missing source {label} in {path}')
    checks.append(f'{len(md_files)} Markdown files: local file links, fences and cited source IDs checked')
    for path in root.rglob('*.json'):
        json.loads(path.read_text())
    checks.append('JSON files parse')

    f = json.loads((root / 'fixtures/paper-session.synthetic.json').read_text())
    require(f['fixtureVersion'] == '2' and 'SYNTHETIC' in f['label'], 'Wrong fixture version/label')
    desks = {x['id'] for x in f['desks']}
    documents = {x['id']: x for x in f['documents']}
    activities = {(x['id'], x['revision']) for x in f['activities']}
    for link in f['documentLinks']:
        require(link['deskId'] in desks and link['documentId'] in documents, 'Dangling note link')
    for attempt in f['attempts']:
        require((attempt['activityId'], attempt['activityRevision']) in activities, 'Missing task revision')
        require(documents[attempt['responseDocumentId']]['revision'] == attempt['responseRevision'], 'Response revision mismatch')
    for case in f['expectedCalculations']:
        require(case['a'] * case['x'] + case['b'] == case['y'], 'Incorrect fixture arithmetic')
    for card in f['cards']:
        require(card['contractVersion'] == '2' and bool(card['textFallback']), 'Card contract/fallback missing')
    checks.append('Retained synthetic card/document references, task/response revisions and arithmetic consistent')

    m = json.loads((root / 'fixtures/mcp-app.synthetic.json').read_text())
    seq = [x['sequence'] for x in m['contextUpdates']]
    require(seq == sorted(set(seq)) and m['expectedPolicy']['retainLatestViewContextSequence'] == max(seq), 'Context fixture order mismatch')
    checks.append('MCP fixture order/latest-context expectation consistent; no runtime enforcement claimed')

    graph = json.loads((root / 'fixtures/graph.synthetic.json').read_text())
    validate_graph(graph)
    invalid = json.loads(json.dumps(graph))
    invalid['edges'][0]['relationType'] = 'magically_understands'
    expect_bad_graph(invalid)
    invalid = json.loads(json.dumps(graph))
    invalid['edges'].append({**invalid['edges'][3], 'id': 'cycle', 'sourceId': 'c-compute', 'targetId': 'c-slope'})
    expect_bad_graph(invalid)
    invalid = json.loads(json.dumps(graph))
    invalid['edges'][0]['targetId'] = 'missing'
    expect_bad_graph(invalid)
    invalid = json.loads(json.dumps(graph))
    invalid['nodes'][0]['conceptLevel'] = 'related'
    expect_bad_graph(invalid)
    checks.append('Graph fixture level/kind/scope/edge checks pass; invalid type, level, endpoint and prerequisite cycle rejected')

    decision = json.loads((root / 'fixtures/decision-routing.synthetic.json').read_text())
    require(decision['featureDefault'] == 'disabled' and 'SYNTHETIC' in decision['label'], 'Decision fixture falsely live/enabled')
    required_cases = {'explicit-example', 'saved-note', 'unclear-message', 'private-document',
                      'unknown-choice', 'revoked-context', 'local-timeout', 'write-note'}
    require({c['id'] for c in decision['cases']} == required_cases, 'Missing decision policy cases')
    require(len(decision['cases']) == len(required_cases), 'Duplicate decision case')
    checks.append('Decision fixture contains eight expected-policy cases; no provider results or benchmark assertions')

    nav = json.loads((root / 'design/navigation.proposed.json').read_text())
    require(nav['status'] == 'proposed_not_approved', 'Navigation proposal wrongly approved')
    require(nav['images'] == [] and nav['brandAsset'] is None, 'Navigation references an unapproved image/brand')
    checks.append('Navigation registry is explicitly proposed with no image or approved brand asset')

    if args.schema:
        import jsonschema
        schema = json.loads((root / 'contracts/mcp-app-binding.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(m['binding'], schema)
        invalid_binding = dict(m['binding']); invalid_binding['noteWritePermission'] = True
        require(not jsonschema.Draft202012Validator(schema).is_valid(invalid_binding), 'Extra binding property accepted')
        checks.append('Candidate MCP binding schema accepts fixture and rejects an extra permission property')
    if args.typecheck:
        types = [str(p) for p in sorted((root / 'contracts').glob('*.ts'))]
        subprocess.run(['tsc', '--noEmit', '--strict', '--target', 'ES2022', '--module', 'ESNext', *types],
                       check=True, capture_output=True, text=True)
        checks.append('All three standalone TypeScript draft modules pass strict tsc (not runtime validation)')

    manifest = root / 'MANIFEST.json'
    if manifest.exists():
        data = json.loads(manifest.read_text())
        expected = {str(p.relative_to(root)) for p in all_files if p != manifest}
        actual = {x['path'] for x in data['files']}
        require(actual == expected and len(actual) == len(data['files']), 'Manifest file set mismatch')
        for item in data['files']:
            path = root / item['path']
            require(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], f'Checksum mismatch: {path}')
            require(path.stat().st_size == item['bytes'], f'Size mismatch: {path}')
        checks.append('Manifest exact file set, sizes and SHA-256 checksums match')
    print(json.dumps({'status': 'pass', 'scope': 'documentation and fixture checks only', 'checks': checks}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, ImportError) as exc:
        print(f'Validation failed: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stdout or '', file=sys.stderr)
            print(exc.stderr or '', file=sys.stderr)
        sys.exit(1)
