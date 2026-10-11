"""Semantic projection of RDF for browsing; the original RDF remains lossless.

Descriptive wrappers (Title, Contribution, Publication, Birth...) are flattened
for display only. Labels and classes never become visual vertices.
"""
import hashlib
from collections import defaultdict
from rdflib import Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF
from ontology import ACTOR_FIELDS, AHCMO, BIBFRAME as BF, BIO, predicate_label


def resource_label(graph, resource):
    for predicate in (RDFS.label, FOAF.name, BF.mainTitle, RDF.value):
        labels = sorted((str(v) for v in graph.objects(resource, predicate)), key=lambda s: (len(s), s.casefold(), s))
        if labels:
            return labels[0]
    if str(resource).startswith(('http://', 'https://')) and not str(resource).startswith('http://ahcm/'):
        return str(resource)
    return str(resource).rsplit('/', 1)[-1].rsplit('#', 1)[-1].replace('-', ' ')


def key(predicate):
    return str(predicate).rsplit('/', 1)[-1].rsplit('#', 1)[-1]


class CatalogGraph:
    def __init__(self, graph):
        self.graph = graph
        self.nodes, self.properties = {}, defaultdict(lambda: defaultdict(list))
        self.edges, self.related = {}, defaultdict(set)
        self.actors = set(graph.subjects(RDF.type, FOAF.Person))
        self.works = set(graph.subjects(RDF.type, BF.Work))
        self.labels = {}
        for subject in sorted(self.actors | self.works, key=str):
            self.node(subject)
        actor_predicates = {f.predicate for f in ACTOR_FIELDS.values()} | {BIO.birth, BIO.death}
        for person in sorted(self.actors, key=str):
            for pred, obj in sorted(graph.predicate_objects(person), key=lambda t: tuple(map(str, t))):
                if pred not in actor_predicates:
                    continue
                self.add(person, pred, obj)
        from bibliographic_view import describe_work
        for work in sorted(self.works, key=str):
            common, instances = describe_work(graph, work)
            fields = self.properties[str(work)]
            for block in [common, *(instance['properties'] for instance in instances)]:
                for field, items in block.items():
                    for value in items:
                        if value not in fields[field]:
                            fields[field].append(value)
        self.degree = defaultdict(set)
        for edge in self.edges.values():
            self.degree[edge['from']].add(edge['to'])
            self.degree[edge['to']].add(edge['from'])

    def node(self, obj, predicate=None):
        if isinstance(obj, Literal):
            # Values with different meanings remain distinct (e.g. volume 1 vs page 1).
            identity = 'valor-' + hashlib.sha256((str(predicate) + '\0' + obj.n3()).encode()).hexdigest()[:24]
            label, kind = str(obj), 'metadato'
        else:
            identity, label = str(obj), resource_label(self.graph, obj)
            kind = 'actor' if obj in self.actors else 'publicacion' if obj in self.works else 'metadato'
        if identity not in self.nodes:
            self.nodes[identity] = {'id': identity, 'label': label, 'kind': kind}
        return self.nodes[identity]

    def add(self, subject, predicate, obj, evidence=None):
        graph = self.graph
        if predicate in (FOAF.name, AHCMO.signatureName) or key(predicate) == 'alternateName':
            self.properties[str(subject)][key(predicate)].append(str(obj))
            self.labels[key(predicate)] = predicate_label(predicate)
            return
        if predicate in (BIO.birth, BIO.death):
            for date in graph.objects(obj, BIO.date):
                self.add(subject, AHCMO.birthYear if predicate == BIO.birth else AHCMO.deathYear, date)
            return
        if predicate == BF.provisionActivity:
            for date in graph.objects(obj, BF.date):
                self.add(subject, BF.date, date, evidence)
            return
        if predicate in (BF.extent, BF.note, BF.identifiedBy):
            for value in graph.objects(obj, RDF.value if predicate == BF.identifiedBy else RDFS.label):
                self.add(subject, predicate, value, evidence)
            return
        source, target = self.node(subject), self.node(obj, predicate)
        field = key(predicate)
        label = {'birthYear': 'Año de nacimiento', 'deathYear': 'Año de muerte'}.get(field, predicate_label(predicate))
        if label == field:
            label = resource_label(graph, predicate)
        self.labels[field] = label
        if isinstance(obj, Literal):
            target['graph_label'] = f'{label}: {target["label"]}'
        value = dict(target)
        if target['kind'] == 'metadato':
            value['facet_id'] = target['id']
            if isinstance(obj, URIRef) and str(obj).startswith(('http://', 'https://')) and not str(obj).startswith('http://ahcm/'):
                value['external'] = str(obj)
        if value not in self.properties[source['id']][field]:
            self.properties[source['id']][field].append(value)
        # Names are attributes, not repeated nodes alongside the actor.
        if predicate in (FOAF.name, AHCMO.signatureName) or field == 'alternateName':
            return
        edge_key = (source['id'], target['id'])
        edge = self.edges.setdefault(edge_key, {'from': source['id'], 'to': target['id'],
                                               'predicates': set(), 'evidence': set()})
        edge['predicates'].add(label)
        edge['evidence'].add((str(predicate), evidence or source['id']))
        self.related[target['id']].add(source['id'])

    def matches(self, identity):
        return sorted((self.nodes[i] for i in self.related.get(identity, set())),
                      key=lambda item: (item['kind'], item['label'].casefold(), item['id']))

    def visual_data(self, root=None):
        edges = list(self.edges.values())
        if root:
            root = str(root)
            works = {edge['to'] for edge in edges if edge['from'] == root and self.nodes[edge['to']]['kind'] == 'publicacion'}
            targets = {edge['to'] for edge in edges if edge['from'] == root}
            edges = [edge for edge in edges if edge['from'] in {root, *works}
                     or (edge['to'] in targets and self.nodes[edge['from']]['kind'] == 'actor')]
        visible = {identity for e in edges for identity in (e['from'], e['to'])}
        if root:
            visible.add(str(root))
        nodes = [dict(self.nodes[i], degree=len(self.degree[i])) for i in sorted(visible)]
        return nodes, [dict(e, predicates=sorted(e['predicates']), weight=len(e['evidence'])) for e in edges]
