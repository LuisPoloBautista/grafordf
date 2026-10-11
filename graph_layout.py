"""Visual-only layouts: rooted shells and weighted Louvain communities."""
import math
import networkx as nx


def positions_for(records, relations, root=None):
    graph = nx.Graph()
    graph.add_nodes_from(r['id'] for r in records)
    for edge in relations:
        graph.add_edge(edge['from'], edge['to'], weight=edge['weight'])
    if not graph:
        return {}
    if root is not None:
        root = str(root)
        positions = {root: {'x': 0, 'y': 0, 'fixed': {'x': True, 'y': True}}}
        distances = nx.single_source_shortest_path_length(graph, root)
        radius = 0
        for depth in sorted(set(distances.values()) - {0}):
            ring = sorted(n for n, d in distances.items() if d == depth)
            radius = max(radius + 230, len(ring) * 75 / (2 * math.pi))
            for i, node in enumerate(ring):
                angle = 2 * math.pi * i / len(ring)
                positions[node] = {'x': radius * math.cos(angle), 'y': radius * math.sin(angle)}
        return positions
    groups = sorted(nx.community.louvain_communities(graph, seed=42, weight='weight'),
                    key=lambda group: (-len(group), min(group)))
    # Pack communities without overlapping their bounding boxes. Within each
    # community spring forces place connected vertices near one another.
    columns = max(1, math.ceil(math.sqrt(len(groups))))
    positions, x, y, row_height = {}, 0, 0, 0
    for index, group in enumerate(groups):
        if index and index % columns == 0:
            x, y, row_height = 0, y + row_height + 260, 0
        radius = max(170, math.sqrt(len(group)) * 85)
        layout = nx.spring_layout(graph.subgraph(sorted(group)), seed=42,
                                  iterations=100, scale=radius, weight='weight', method='force')
        for node, point in layout.items():
            positions[node] = {'x': x + radius + float(point[0]),
                               'y': y + radius + float(point[1]), 'community': index + 1}
        x += radius * 2 + 260
        row_height = max(row_height, radius * 2)
    return positions
