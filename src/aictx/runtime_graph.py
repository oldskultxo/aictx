from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr

    return cr


def graph_node_id(node_type: str, raw_id: str) -> str:
    return f"{node_type}:{_cr().slugify(raw_id)}"


def edge_identity(from_id: str, to_id: str, relation: str) -> str:
    return f'{from_id}|{relation}|{to_id}'


def infer_repository_area(row: dict[str, Any]) -> str | None:
    if row.get('project') and row.get('subproject'):
        return f"{row['project']}/{row['subproject']}"
    if row.get('project'):
        return str(row['project'])
    path = str(row.get('path', ''))
    if path.startswith('projects/'):
        parts = path.split('/')
        if len(parts) >= 3:
            return f"{parts[1]}/{parts[2]}"
    return None


def graph_node_type_for_record(row: dict[str, Any]) -> str:
    if row.get('type') == 'architecture_decision':
        return 'architecture_decision'
    return 'memory_entry'


def graph_label_index_key(label: str) -> str:
    return _cr().slugify(label).replace('_', ' ')


def ensure_memory_graph_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    if not cr.MEMORY_GRAPH_STATUS_PATH.exists():
        cr.write_json(
            cr.MEMORY_GRAPH_STATUS_PATH,
            {
                'version': 1,
                'installed_iteration': 9,
                'generated_at': date.today().isoformat(),
                'nodes_total': 0,
                'edges_total': 0,
                'expansion_events': 0,
                'last_seed_count': 0,
                'last_expansion_depth': 0,
                'last_packet_path': '',
                'last_graph_hit_count': 0,
            },
        )
    for path in [cr.MEMORY_GRAPH_NODES_PATH, cr.MEMORY_GRAPH_EDGES_PATH]:
        if not path.exists():
            cr.write_jsonl(path, [])
    for path in [cr.MEMORY_GRAPH_LABEL_INDEX_PATH, cr.MEMORY_GRAPH_TYPE_INDEX_PATH, cr.MEMORY_GRAPH_RELATION_INDEX_PATH]:
        if not path.exists():
            cr.write_json(path, {})
    if not cr.MEMORY_GRAPH_SNAPSHOT_PATH.exists():
        cr.write_json(
            cr.MEMORY_GRAPH_SNAPSHOT_PATH,
            {
                'version': 1,
                'generated_at': date.today().isoformat(),
                'nodes_sample': [],
                'edges_sample': [],
            },
        )


def graph_add_node(nodes: dict[str, dict[str, Any]], *, node_id: str, node_type: str, label: str, source: str, confidence: float = 0.7, tags: list[str] | None = None, metadata: dict[str, Any] | None = None) -> None:
    cr = _cr()
    if node_type not in cr.GRAPH_NODE_TYPES:
        node_type = 'concept'
    current = nodes.get(node_id)
    payload = {
        'id': node_id,
        'type': node_type,
        'label': label,
        'source': source,
        'last_updated_at': date.today().isoformat(),
        'confidence': round(confidence, 2),
        'tags': sorted({tag for tag in (tags or []) if tag}),
        'metadata': metadata or {},
    }
    if current:
        payload['confidence'] = round(max(float(current.get('confidence', 0.5)), payload['confidence']), 2)
        payload['tags'] = sorted(set(current.get('tags', [])) | set(payload['tags']))
        payload['metadata'] = {**current.get('metadata', {}), **payload['metadata']}
    nodes[node_id] = payload


def graph_add_edge(edges: dict[str, dict[str, Any]], *, from_id: str, to_id: str, relation: str, source: str, confidence: float = 0.65) -> None:
    cr = _cr()
    if relation not in cr.GRAPH_RELATIONS:
        relation = 'relates_to'
    identity = edge_identity(from_id, to_id, relation)
    current = edges.get(identity)
    payload = {
        'id': identity,
        'from': from_id,
        'to': to_id,
        'relation': relation,
        'source': source,
        'confidence': round(confidence, 2),
        'timestamp': date.today().isoformat(),
    }
    if current:
        payload['confidence'] = round(max(float(current.get('confidence', 0.5)), payload['confidence']), 2)
    edges[identity] = payload


def build_memory_graph_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cr = _cr()
    ensure_memory_graph_artifacts()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    normalized_rows = [cr.normalize_record(row) for row in rows] + cr.manual_task_memory_records()
    for task_type in cr.TASK_TYPES:
        task_node_id = graph_node_id('task_type', task_type)
        graph_add_node(nodes, node_id=task_node_id, node_type='task_type', label=task_type, source='task_taxonomy', confidence=0.95, tags=[task_type])
    for row in normalized_rows:
        node_type = graph_node_type_for_record(row)
        record_node_id = graph_node_id(node_type, str(row.get('id', '')))
        graph_add_node(
            nodes,
            node_id=record_node_id,
            node_type=node_type,
            label=str(row.get('title') or row.get('id') or 'memory entry'),
            source=str(row.get('source', 'record')),
            confidence=float(row.get('relevance_score', 0.65)),
            tags=list(row.get('tags', [])),
            metadata={
                'record_id': row.get('id'),
                'record_type': row.get('type'),
                'path': row.get('path'),
                'task_type': row.get('task_type'),
            },
        )
        task_type = cr.normalize_task_type(row.get('task_type'))
        graph_add_edge(edges, from_id=record_node_id, to_id=graph_node_id('task_type', task_type), relation='belongs_to_task_type', source='record_task_type', confidence=0.9)
        repo_area = infer_repository_area(row)
        if repo_area:
            area_node_id = graph_node_id('repository_area', repo_area)
            graph_add_node(nodes, node_id=area_node_id, node_type='repository_area', label=repo_area, source='path_heuristic', confidence=0.78, tags=[repo_area])
            graph_add_edge(edges, from_id=record_node_id, to_id=area_node_id, relation='associated_with', source='record_area', confidence=0.78)
        for path in row.get('files_involved', [])[:6]:
            file_node_id = graph_node_id('file', path)
            graph_add_node(nodes, node_id=file_node_id, node_type='file', label=path, source='files_involved', confidence=0.85, tags=[task_type] if task_type else [])
            graph_add_edge(edges, from_id=record_node_id, to_id=file_node_id, relation='referenced_by', source='record_file', confidence=0.85)
            module_label = str(Path(path).parent.as_posix() or '.')
            module_node_id = graph_node_id('module', module_label)
            graph_add_node(nodes, node_id=module_node_id, node_type='module', label=module_label, source='path_parent', confidence=0.72, tags=[repo_area] if repo_area else [])
            graph_add_edge(edges, from_id=file_node_id, to_id=module_node_id, relation='located_in', source='path_parent', confidence=0.72)
        for tag in row.get('tags', [])[:6]:
            concept_node_id = graph_node_id('concept', tag)
            graph_add_node(nodes, node_id=concept_node_id, node_type='concept', label=tag, source='record_tag', confidence=0.68, tags=[tag])
            graph_add_edge(edges, from_id=record_node_id, to_id=concept_node_id, relation='associated_with', source='record_tag', confidence=0.68)
    for failure in cr.read_json(cr.FAILURE_MEMORY_INDEX_PATH, {}).get('records', []):
        full = cr.read_json(cr.FAILURE_MEMORY_RECORDS_DIR / f"{failure['id']}.json", {})
        if not full:
            continue
        failure_node_id = graph_node_id('failure_pattern', str(full.get('id', '')))
        solution_node_id = graph_node_id('solution', str(full.get('id', '')))
        graph_add_node(nodes, node_id=failure_node_id, node_type='failure_pattern', label=str(full.get('title', full.get('id', 'failure'))), source='failure_memory', confidence=float(full.get('confidence', 0.75)), tags=[str(full.get('category', 'unknown'))])
        graph_add_node(nodes, node_id=solution_node_id, node_type='solution', label=f"solution:{full.get('title', full.get('id', 'failure'))}", source='failure_memory', confidence=float(full.get('confidence', 0.75)), tags=['solution'])
        graph_add_edge(edges, from_id=failure_node_id, to_id=solution_node_id, relation='fixed_by', source='failure_solution', confidence=float(full.get('confidence', 0.75)))
        category_node_id = graph_node_id('concept', str(full.get('category', 'unknown')))
        graph_add_node(nodes, node_id=category_node_id, node_type='concept', label=str(full.get('category', 'unknown')), source='failure_category', confidence=0.7, tags=['failure'])
        graph_add_edge(edges, from_id=failure_node_id, to_id=category_node_id, relation='associated_with', source='failure_category', confidence=0.7)
        for path in full.get('files_involved', [])[:6]:
            file_node_id = graph_node_id('file', path)
            graph_add_node(nodes, node_id=file_node_id, node_type='file', label=path, source='failure_memory', confidence=0.72, tags=['failure'])
            graph_add_edge(edges, from_id=failure_node_id, to_id=file_node_id, relation='affects', source='failure_file', confidence=0.74)
        source_record_id = full.get('source_record_id')
        if source_record_id:
            candidate_memory_nodes = [graph_node_id('memory_entry', str(source_record_id)), graph_node_id('architecture_decision', str(source_record_id))]
            for candidate in candidate_memory_nodes:
                if candidate in nodes:
                    graph_add_edge(edges, from_id=failure_node_id, to_id=candidate, relation='derived_from', source='failure_source_record', confidence=0.86)
                    break
    node_rows = sorted(nodes.values(), key=lambda row: (row['type'], row['label'], row['id']))
    edge_rows = sorted(edges.values(), key=lambda row: (row['relation'], row['from'], row['to']))
    cr.write_jsonl(cr.MEMORY_GRAPH_NODES_PATH, node_rows)
    cr.write_jsonl(cr.MEMORY_GRAPH_EDGES_PATH, edge_rows)
    label_index: dict[str, list[str]] = defaultdict(list)
    type_index: dict[str, list[str]] = defaultdict(list)
    relation_index: dict[str, list[str]] = defaultdict(list)
    for node in node_rows:
        label_index[graph_label_index_key(str(node.get('label', '')))].append(node['id'])
        type_index[str(node.get('type', 'concept'))].append(node['id'])
    for edge in edge_rows:
        relation_index[str(edge.get('relation', 'relates_to'))].append(edge['id'])
    cr.write_json(cr.MEMORY_GRAPH_LABEL_INDEX_PATH, dict(sorted(label_index.items())))
    cr.write_json(cr.MEMORY_GRAPH_TYPE_INDEX_PATH, dict(sorted(type_index.items())))
    cr.write_json(cr.MEMORY_GRAPH_RELATION_INDEX_PATH, dict(sorted(relation_index.items())))
    previous = cr.read_json(cr.MEMORY_GRAPH_STATUS_PATH, {})
    status = {
        **previous,
        'version': 1,
        'installed_iteration': 9,
        'generated_at': date.today().isoformat(),
        'nodes_total': len(node_rows),
        'edges_total': len(edge_rows),
        'node_types': {node_type: len(type_index.get(node_type, [])) for node_type in sorted(cr.GRAPH_NODE_TYPES)},
        'relation_types': {relation: len(relation_index.get(relation, [])) for relation in sorted(cr.GRAPH_RELATIONS)},
    }
    cr.write_json(cr.MEMORY_GRAPH_STATUS_PATH, status)
    cr.write_json(
        cr.MEMORY_GRAPH_SNAPSHOT_PATH,
        {
            'version': 1,
            'generated_at': date.today().isoformat(),
            'nodes_sample': node_rows[:12],
            'edges_sample': edge_rows[:12],
        },
    )
    return status


def graph_nodes() -> dict[str, dict[str, Any]]:
    cr = _cr()
    ensure_memory_graph_artifacts()
    return {row['id']: row for row in cr.read_jsonl(cr.MEMORY_GRAPH_NODES_PATH) if row.get('id')}


def graph_edges() -> list[dict[str, Any]]:
    cr = _cr()
    ensure_memory_graph_artifacts()
    return cr.read_jsonl(cr.MEMORY_GRAPH_EDGES_PATH)


def graph_find_nodes(query: str) -> list[dict[str, Any]]:
    cr = _cr()
    nodes = graph_nodes()
    q = query.strip().lower()
    if not q:
        return []
    ranked = []
    for node in nodes.values():
        haystack = ' '.join([str(node.get('label', '')), str(node.get('id', '')), ' '.join(node.get('tags', []))])
        score = cr.score_match(q, haystack)
        if score > 0:
            ranked.append((score + int(float(node.get('confidence', 0.5)) * 10), node))
    ranked.sort(key=lambda item: (-item[0], item[1]['id']))
    return [node for _, node in ranked[:10]]


def graph_neighbors(node_id: str, relation: str | None = None) -> list[dict[str, Any]]:
    nodes = graph_nodes()
    results = []
    for edge in graph_edges():
        if edge.get('from') != node_id:
            continue
        if relation and edge.get('relation') != relation:
            continue
        neighbor = nodes.get(str(edge.get('to')))
        if not neighbor:
            continue
        results.append({'edge': edge, 'node': neighbor})
    results.sort(key=lambda item: (-float(item['edge'].get('confidence', 0.5)), item['node']['id']))
    return results


def graph_expand(seed_ids: list[str], *, depth: int = 1, node_budget: int = 8, edge_budget: int = 12, task_type: str | None = None, repository_area: str | None = None) -> dict[str, Any]:
    cr = _cr()
    nodes = graph_nodes()
    if not nodes:
        return {'nodes': [], 'edges': [], 'connected_record_ids': [], 'depth_used': 0}
    frontier = [seed_id for seed_id in seed_ids if seed_id in nodes]
    visited_nodes: set[str] = set(frontier)
    visited_edges: list[dict[str, Any]] = []
    collected_nodes: list[dict[str, Any]] = [nodes[seed_id] for seed_id in frontier]
    current_depth = 0
    while frontier and current_depth < max(0, depth) and len(collected_nodes) < node_budget and len(visited_edges) < edge_budget:
        next_frontier: list[str] = []
        for current in frontier:
            for item in graph_neighbors(current):
                neighbor = item['node']
                edge = item['edge']
                if repository_area and neighbor.get('type') == 'repository_area' and repository_area not in str(neighbor.get('label', '')):
                    continue
                if task_type and neighbor.get('type') == 'task_type' and cr.normalize_task_type(neighbor.get('label')) != cr.normalize_task_type(task_type):
                    continue
                if neighbor['id'] not in visited_nodes:
                    visited_nodes.add(neighbor['id'])
                    collected_nodes.append(neighbor)
                    next_frontier.append(neighbor['id'])
                if len(visited_edges) < edge_budget:
                    visited_edges.append(edge)
                if len(collected_nodes) >= node_budget or len(visited_edges) >= edge_budget:
                    break
            if len(collected_nodes) >= node_budget or len(visited_edges) >= edge_budget:
                break
        frontier = next_frontier
        current_depth += 1
    connected_record_ids = []
    for node in collected_nodes:
        record_id = str(node.get('metadata', {}).get('record_id', '')).strip()
        if record_id:
            connected_record_ids.append(record_id)
    return {
        'nodes': collected_nodes[:node_budget],
        'edges': visited_edges[:edge_budget],
        'connected_record_ids': sorted(set(connected_record_ids)),
        'depth_used': current_depth,
    }


def update_memory_graph_status(packet: dict[str, Any], packet_path: Path) -> None:
    cr = _cr()
    status = cr.read_json(cr.MEMORY_GRAPH_STATUS_PATH, {})
    graph_meta = packet.get('memory_graph', {})
    updated = {
        **status,
        'version': 1,
        'installed_iteration': 9,
        'generated_at': date.today().isoformat(),
        'expansion_events': int(status.get('expansion_events', 0) or 0) + (1 if graph_meta.get('graph_used') else 0),
        'last_seed_count': int(graph_meta.get('seed_count', 0) or 0),
        'last_expansion_depth': int(graph_meta.get('expansion_depth_used', 0) or 0),
        'last_graph_hit_count': int(graph_meta.get('graph_hits', 0) or 0),
        'last_packet_path': packet_path.as_posix(),
    }
    cr.write_json(cr.MEMORY_GRAPH_STATUS_PATH, updated)
