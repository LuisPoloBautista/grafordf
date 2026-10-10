"""Indexed RDF neighborhood search and PyVis projection of every RDF triple."""
import html
import json
import re
import unicodedata
from urllib.parse import quote
from collections import defaultdict, deque
from rdflib import Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF
from pyvis.network import Network
from rdf_pipeline import BIBFRAME as BF


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold()
                   if not unicodedata.combining(c))


def neighborhood(graph, root):
    """BFS over outgoing descriptions; stop expansion at another actor."""
    seen, queue, triples = set(), deque([root]), set()
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if node != root and (node, RDF.type, FOAF.Person) in graph:
            continue
        for triple in graph.triples((node, None, None)):
            triples.add(triple)
            _, predicate, target = triple
            if isinstance(target, URIRef) and predicate != RDF.type:
                queue.append(target)
    return triples


class GraphSearch:
    """Inverted character n-grams of RDF BFS neighborhoods, ranked by name."""
    def __init__(self, graph, people):
        self.entries = {entry['id']: entry for entry, _ in people}
        self.names, self.documents = {}, {}
        self.index = defaultdict(set)
        for entry, aliases in people:
            identity = entry['id']
            self.names[identity] = normalize(entry['label'] + ' ' + aliases)
            texts = [self.names[identity]]
            for _, _, obj in neighborhood(graph, URIRef(identity)):
                if isinstance(obj, Literal):
                    texts.append(normalize(obj))
            document = ' '.join(texts)
            self.documents[identity] = document
            for length in (1, 2, 3):
                for i in range(len(document) - length + 1):
                    self.index[document[i:i + length]].add(identity)

    def search(self, query):
        tokens = re.findall(r'\w+', normalize(query))
        candidates = None
        for token in tokens:
            size = min(3, len(token))
            for i in range(len(token) - size + 1):
                hits = self.index.get(token[i:i + size], set())
                candidates = set(hits) if candidates is None else candidates & hits
        if candidates is None:
            candidates = set(self.entries)
        candidates = [p for p in candidates if all(t in self.documents[p] for t in tokens)]
        candidates.sort(key=lambda p: (-sum(t in self.names[p] for t in tokens), normalize(self.entries[p]['label'])))
        return [self.entries[p] for p in candidates]


def graph_html(graph, label, root=None):
    triples = sorted(neighborhood(graph, root) if root else graph, key=lambda t: tuple(map(str, t)))
    net = Network(height='80vh', width='100%', directed=True, cdn_resources='in_line')
    terms = sorted({term for s, _, o in triples for term in (s, o)}, key=lambda t: t.n3())
    ids = {term: i for i, term in enumerate(terms)}
    for term in terms:
        text = str(term) if isinstance(term, Literal) else label(graph, term)
        color = '#adb8b0' if isinstance(term, Literal) else '#8cabc0'
        if (term, RDF.type, FOAF.Person) in graph:
            color = '#246b68'
        elif (term, RDF.type, BF.Work) in graph:
            color = '#c65d3a'
        net.nodes.append({'id': ids[term], 'label': text[:65], 'title': html.escape(text + '\n' + term.n3()),
                          'color': color, 'shape': 'dot'})
        if isinstance(term, URIRef) and str(term).startswith('http://ahcm/'):
            net.nodes[-1]['href'] = ('/#persona=' + quote(str(term).rsplit('/', 1)[-1])
                                    if (term, RDF.type, FOAF.Person) in graph
                                    else '/#recurso=' + quote(str(term), safe=''))
        elif isinstance(term, URIRef) and str(term).startswith(('http://', 'https://')):
            net.nodes[-1]['href'] = str(term)
    # Direct insertion avoids PyVis's quadratic duplicate-edge scans on the full graph.
    net.edges = [{'from': ids[s], 'to': ids[o], 'arrows': 'to',
                  'title': html.escape(str(p)), 'label': str(p).rsplit('/', 1)[-1].rsplit('#', 1)[-1]}
                 for s, p, o in triples]
    net.set_options(json.dumps({'physics': {'enabled': root is not None, 'solver': 'barnesHut',
                                           'stabilization': {'iterations': 120}},
                                'layout': {'improvedLayout': False, 'randomSeed': 42},
                                'interaction': {'hover': True, 'navigationButtons': True, 'hideEdgesOnDrag': True},
                                'edges': {'smooth': False, 'font': {'size': 9}},
                                'nodes': {'font': {'size': 12}}}))
    page = net.generate_html()
    # PyVis includes optional Bootstrap CDN tags even with in_line assets.
    page = re.sub(r'<link\b[^>]*href="https://[^>]*>', '', page)
    page = re.sub(r'<script\b[^>]*src="https://[^>]*>\s*</script>', '', page)
    toolbar = f'''<div style="font:14px system-ui;padding:12px">
    {len(terms)} nodos · {len(triples)} triples · Verde: actores · Naranja: publicaciones · Gris: valores.
    Arrastra los nodos y usa la rueda para acercar.
    <button onclick="network.fit()">Centrar</button>
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
    return page.replace('<body>', '<body>' + toolbar).replace('</body>', navigation + '</body>')
