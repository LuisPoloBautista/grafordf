"""Separate syntactic round-trip, BIBFRAME ontology and application-profile checks."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from rdflib import Graph, Literal, RDF, RDFS, OWL, URIRef
from rdflib.compare import isomorphic
from ontology import BIBFRAME as BF, AHCMO, PROV

ROOT = Path(__file__).parent
ONTOLOGY = ROOT / 'vocab' / 'bibframe.rdf'


def validate_semantics(graph):
    ontology = Graph().parse(ONTOLOGY, format='xml')
    errors = []

    def error(code, subject, predicate, value):
        errors.append({'code': code, 'subject': str(subject), 'predicate': str(predicate), 'value': str(value)})

    def compatible(resource, required):
        if required == RDFS.Resource:
            return True
        for kind in graph.objects(resource, RDF.type):
            if kind == required or required in set(ontology.transitive_objects(kind, RDFS.subClassOf)):
                return True
        return False

    properties = set(ontology.subjects(RDF.type, OWL.ObjectProperty)) | set(ontology.subjects(RDF.type, OWL.DatatypeProperty))
    classes = set(ontology.subjects(RDF.type, OWL.Class))
    for subject, predicate, obj in graph:
        if predicate == RDF.type and str(obj).startswith(str(BF)) and obj not in classes:
            error('unknown_class', subject, predicate, obj)
        if predicate == RDF.type and str(obj).startswith(str(BF)) and any(
                str(v).lower() in ('true', '1') for v in ontology.objects(obj, OWL.deprecated)):
            error('deprecated_class', subject, predicate, obj)
        if not str(predicate).startswith(str(BF)):
            continue
        if predicate not in properties:
            error('unknown_property', subject, predicate, obj)
            continue
        if any(str(v).lower() in ('true', '1') for v in ontology.objects(predicate, OWL.deprecated)):
            error('deprecated_property', subject, predicate, obj)
        if (predicate, RDF.type, OWL.ObjectProperty) in ontology and isinstance(obj, Literal):
            error('object_property_literal', subject, predicate, obj)
        if (predicate, RDF.type, OWL.DatatypeProperty) in ontology and not isinstance(obj, Literal):
            error('datatype_property_resource', subject, predicate, obj)
        for domain in ontology.objects(predicate, RDFS.domain):
            if isinstance(domain, URIRef) and not compatible(subject, domain):
                error('domain', subject, predicate, domain)
        for range_ in ontology.objects(predicate, RDFS.range):
            if range_ == RDFS.Literal:
                if not isinstance(obj, Literal):
                    error('range_literal', subject, predicate, obj)
            elif isinstance(range_, URIRef) and not compatible(obj, range_):
                error('range', subject, predicate, range_)
    for instance in graph.subjects(RDF.type, BF.Instance):
        works = list(graph.objects(instance, BF.instanceOf))
        if len(works) != 1:
            error('instance_work_cardinality', instance, BF.instanceOf, len(works))
        for work in works:
            if (work, BF.hasInstance, instance) not in graph:
                error('missing_inverse', work, BF.hasInstance, instance)
    for item in graph.subjects(RDF.type, BF.Item):
        instances = list(graph.objects(item, BF.itemOf))
        if len(instances) != 1:
            error('item_instance_cardinality', item, BF.itemOf, len(instances))
        if not list(graph.objects(item, BF.electronicLocator)):
            error('item_without_copy_evidence', item, BF.electronicLocator, '')
        for instance in instances:
            if (instance, BF.hasItem, item) not in graph:
                error('missing_inverse', instance, BF.hasItem, item)
    for contribution in graph.subjects(RDF.type, BF.Contribution):
        if len(list(graph.objects(contribution, BF.agent))) != 1:
            error('contribution_agent_cardinality', contribution, BF.agent, '')
        if not list(graph.objects(contribution, BF.role)):
            error('missing_role', contribution, BF.role, '')
    for title in graph.subjects(RDF.type, BF.Title):
        if not list(graph.objects(title, BF.mainTitle)):
            error('missing_title', title, BF.mainTitle, '')
    return {'ontology_version': [str(v).strip() for v in ontology.objects(None, OWL.versionInfo)],
            'ontology_sha256': hashlib.sha256(ONTOLOGY.read_bytes()).hexdigest(),
            'errors': errors, 'error_counts': dict(Counter(e['code'] for e in errors)),
            'scope': 'BF term existence/deprecation, resource/literal kind, explicit domain/range with subclass closure, and local structural profile. Not a complete OWL reasoner.'}


def validate_syntax(graph):
    text = graph.serialize(format='turtle')
    parsed = Graph().parse(data=text, format='turtle')
    return {'format': 'Turtle 1.1', 'triples': len(graph), 'rdflib_roundtrip_isomorphic': isomorphic(graph, parsed)}


def main():
    from rdf_pipeline import build_graph
    graph = build_graph()
    result = {'syntax': validate_syntax(graph), 'semantics': validate_semantics(graph)}
    target = ROOT / 'reports' / 'rdf-validation.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'syntax': result['syntax'], 'semantic_errors': result['semantics']['error_counts']}))
    if result['semantics']['errors'] or not result['syntax']['rdflib_roundtrip_isomorphic']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
