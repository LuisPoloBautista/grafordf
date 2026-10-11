"""Indexed semantic-record search and a clean PyVis projection of RDF."""
import html
import json
import re
import unicodedata
from urllib.parse import quote
from collections import defaultdict
from rdflib import URIRef
from rdflib.namespace import FOAF
from pyvis.network import Network
from catalog_graph import CatalogGraph
from graph_layout import positions_for


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold()
                   if not unicodedata.combining(c))


class GraphSearch:
    """Inverted n-grams over each record and its own semantic neighbors."""
    def __init__(self, graph, people, projection):
        self.entries, self.names, self.documents = {}, {}, {}
        self.index = defaultdict(set)
        for identity, entry in projection.nodes.items():
            if entry['kind'] == 'metadato':
                continue
            self.entries[identity] = dict(entry, slug=identity.rsplit('/', 1)[-1])
            names = [entry['label']]
            if entry['kind'] == 'actor':
                names.extend(str(value) for predicate in (FOAF.name,) for value in graph.objects(URIRef(identity), predicate))
            self.names[identity] = normalize(' '.join(names))
            texts = [self.names[identity]]
            for field, items in projection.properties[identity].items():
                if field == 'made':
                    continue  # A publication query must retrieve its record, not its author.
                texts.extend(normalize(item['label'] if isinstance(item, dict) else item) for item in items)
            document = ' '.join(texts)
            self.documents[identity] = document
            for length in (1, 2, 3):
                for i in range(len(document) - length + 1):
                    self.index[document[i:i + length]].add(identity)

    def search(self, query, kind=None):
        tokens = re.findall(r'\w+', normalize(query))
        candidates = None
        for token in tokens:
            size = min(3, len(token))
            for i in range(len(token) - size + 1):
                hits = self.index.get(token[i:i + size], set())
                candidates = set(hits) if candidates is None else candidates & hits
        if candidates is None:
            candidates = set(self.entries)
        candidates = [p for p in candidates if (kind is None or self.entries[p]['kind'] == kind) and all(t in self.documents[p] for t in tokens)]
        candidates.sort(key=lambda p: (-sum(t in self.names[p] for t in tokens), self.entries[p]['kind'] != 'actor' if not tokens else False, normalize(self.entries[p]['label']), p))
        return [self.entries[p] for p in candidates]


def graph_html(graph, label, root=None, projection=None):
    projection = projection or CatalogGraph(graph)
    records, relations = projection.visual_data(root)
    net = Network(height='80vh', width='100%', directed=True, cdn_resources='in_line')
    colors = {'actor': '#246b68', 'publicacion': '#c65d3a', 'metadato': '#7963ad'}
    positions = positions_for(records, relations, root)
    for entry in records:
        identity, text, kind = entry['id'], entry.get('graph_label', entry['label']), entry['kind']
        href = ('/#persona=' + quote(identity.rsplit('/', 1)[-1]) if kind == 'actor'
                else '/#recurso=' + quote(identity, safe='') if kind == 'publicacion'
                else '/#metadato=' + quote(identity, safe=''))
        net.nodes.append({'id': identity, 'label': text[:65], 'title': html.escape(f"{text} — {entry['degree']} conexiones"),
                          'color': colors[kind], 'shape': 'dot', 'font': {'size': 12}, 'value': max(1, entry['degree']),
                          'degree': entry['degree'], 'kind': kind, 'href': href,
                          **positions.get(identity, {})})
    net.edges = [{'from': e['from'], 'to': e['to'], 'arrows': 'to', 'value': e['weight'],
                  'title': html.escape('; '.join(e['predicates']) + f" · {e['weight']} relaciones de origen"),
                  'label': '; '.join(e['predicates']) if root else '',
                  'relation': '; '.join(e['predicates']),
                  'color': {'color': '#87929a', 'opacity': .45 if root else .25, 'highlight': '#c65d3a'}} for e in relations]
    net.set_options(json.dumps({'physics': {'enabled': False, 'solver': 'barnesHut',
                                           'stabilization': {'iterations': 120}},
                                'layout': {'improvedLayout': False, 'randomSeed': 42},
                                'interaction': {'hover': True, 'navigationButtons': True, 'hideEdgesOnDrag': True},
                                'edges': {'smooth': False, 'font': {'size': 9}, 'scaling': {'min': 1, 'max': 8, 'label': {'enabled': False}}},
                                'nodes': {'font': {'size': 12}, 'scaling': {'min': 7, 'max': 42, 'label': {'enabled': False}}}}))
    page = net.generate_html()
    # PyVis includes optional Bootstrap CDN tags even with in_line assets.
    page = re.sub(r'<link\b[^>]*href="https://[^>]*>', '', page)
    page = re.sub(r'<script\b[^>]*src="https://[^>]*>\s*</script>', '', page)
    center_action = 'network.fit();network.moveTo({position:{x:0,y:0}})' if root is not None else 'network.fit()'
    toolbar = f'''<div style="font:14px system-ui;padding:12px">
    {len(records)} nodos · {len(relations)} relaciones visibles · Verde: actores · Naranja: publicaciones · Violeta: metadatos.
    Tamaño: número de vecinos; grosor: cantidad de relaciones agrupadas. Doble clic para abrir la ficha o los registros relacionados.
    Arrastra los nodos y usa la rueda para acercar.
    <button onclick="{center_action}">Centrar</button>
    <button onclick="network.setOptions({{physics:{{enabled:true}}}})">Activar movimiento</button>
    <button onclick="network.setOptions({{physics:{{enabled:false}}}})">Pausar</button>
    <button onclick="const selected=network.getSelectedNodes();if(selected.length){{const keep=new Set([...selected,...selected.flatMap(id=>network.getConnectedNodes(id))]);nodes.update(nodes.get().map(n=>({{id:n.id,hidden:!keep.has(n.id)}})));network.fit()}}">Ver entorno seleccionado</button>
    <button onclick="nodes.update(nodes.get().map(n=>({{id:n.id,hidden:false}})));network.fit()">Mostrar todo</button>
    <label>Buscar nodo <input id="node-query" type="search"></label>
    <button onclick="const q=document.getElementById('node-query').value.toLowerCase();const n=nodes.get().find(n=>n.label.toLowerCase().includes(q));if(n){{network.selectNodes([n.id]);network.focus(n.id,{{scale:1.3}})}}">Localizar</button>
    </div>'''
    navigation = '''<script>network.on('doubleClick', function(event) {
      if (event.nodes.length) { const node = nodes.get(event.nodes[0]);
        if (node.href) { if (node.href.startsWith('/')) window.top.location.href = node.href;
          else window.open(node.href, '_blank', 'noopener,noreferrer'); }
      }
    });</script>'''
    if root is not None:
        navigation += "<script>network.once('afterDrawing',()=>network.moveTo({position:{x:0,y:0}}));</script>"
    return page.replace('<body>', '<body>' + toolbar).replace('</body>', navigation + '</body>')
