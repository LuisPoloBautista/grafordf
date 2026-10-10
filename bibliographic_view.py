"""Display Work and Instance fields once, without metadata-facet navigation."""
from collections import defaultdict
from rdflib import RDF, RDFS
from ontology import BIBFRAME as BF, AHCMO, PROV


def label(graph, node):
    return str(graph.value(node, RDFS.label) or graph.value(node, RDF.value) or node)


def describe_work(graph, work):
    common = defaultdict(list)

    def add(fields, key, value):
        if value not in fields[key]:
            fields[key].append(value)

    for contribution in graph.objects(work, BF.contribution):
        for agent in graph.objects(contribution, BF.agent):
            add(common, 'contribution', label(graph, agent))
    for pred, field in ((BF.language, 'language'), (BF.genreForm, 'genreForm')):
        for node in graph.objects(work, pred):
            add(common, field, label(graph, node))
    for predicate, obj in graph.predicate_objects(work):
        if str(predicate).startswith(str(AHCMO) + 'bibliografia-'):
            add(common, str(predicate).split('/')[-1], str(obj))
    # Keywords and subject area have distinct source columns; do not repeat
    # their bf:subject representations as another copy in the same table.
    instances = []
    for instance in sorted(graph.objects(work, BF.hasInstance), key=str):
        fields = defaultdict(list)
        for predicate, obj in sorted(graph.predicate_objects(instance), key=lambda pair: tuple(map(str, pair))):
            if predicate == BF.provisionActivity:
                for value in graph.objects(obj, BF.date):
                    add(fields, 'date', str(value))
            elif predicate in (BF.extent, BF.note):
                add(fields, 'extent' if predicate == BF.extent else 'note', label(graph, obj))
            elif predicate == BF.identifiedBy:
                field = 'isbn' if (obj, RDF.type, BF.Isbn) in graph else 'doi'
                add(fields, field, str(graph.value(obj, RDF.value)))
            elif predicate in (BF.editionStatement, BF.part):
                add(fields, 'editionStatement' if predicate == BF.editionStatement else 'part', str(obj))
            elif predicate == RDFS.seeAlso:
                add(fields, 'electronicLocator', {'label': str(obj), 'url': str(obj)})
            elif str(predicate).startswith(str(AHCMO) + 'bibliografia-'):
                add(fields, str(predicate).split('/')[-1], str(obj))
        for item in graph.objects(instance, BF.hasItem):
            for url in graph.objects(item, BF.electronicLocator):
                add(fields, 'electronicLocator', {'label': str(url), 'url': str(url)})
        instances.append({'id': str(instance), 'label': ', '.join(fields.get('date', [])) or 'Sin fecha registrada',
                          'properties': dict(fields), 'source_rows': [int(v) for v in graph.objects(instance, AHCMO.sourceRow)]})
    return dict(common), instances
