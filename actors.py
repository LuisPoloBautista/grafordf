"""Actor CSV conversion with shared resources and correctly typed events."""
import re
from collections import defaultdict
from rdflib import Literal, URIRef, RDF, RDFS
from rdflib.namespace import FOAF, SKOS, XSD
from ontology import ACTOR_FIELDS, AHCM, PERSON, BIO, SCHEMA, ORG
from rdf_pipeline import slug, values


def split_link(text):
    match = re.match(r'^(.*?):\s*(https?://\S+)\s*$', text)
    if match:
        return match[1].strip(), URIRef(match[2].rstrip('.,;'))
    if re.fullmatch(r'https?://\S+', text):
        return text, URIRef(text.rstrip('.,;'))
    return text.strip(), None


def add_actors(graph, rows):
    def field_values(row, column, field):
        items = values(row.get(column))
        # Roles use comma lists; personal and institutional names keep their commas.
        return [part.strip() for item in items for part in item.split(',') if part.strip()] if field.kind == 'occupation' else items

    identities, external = defaultdict(set), defaultdict(set)
    for row in rows:
        name, link = split_link(row.get('Autor normalizado', ''))
        if not name:
            continue
        person = PERSON[slug(name)]
        for raw in [name, *values(row.get('Nombre completo')), *values(row.get('Nombre firma'))]:
            alias, _ = split_link(raw)
            identities[slug(alias)].add(person)
        if link:
            external[link].add(person)
    # Reuse an external identifier for unlinked spellings only when unambiguous.
    authorities = defaultdict(set)
    for row in rows:
        for column, field in ACTOR_FIELDS.items():
            for raw in field_values(row, column, field):
                text, link = split_link(raw)
                if link:
                    authorities[(field.kind, slug(text))].add(link)

    kinds = {'organization': (AHCM.institucion, ORG.Organization),
             'place': (AHCM.lugar, SCHEMA.Place), 'occupation': (AHCM.ocupacion, SCHEMA.Occupation),
             'topic': (AHCM.tema, SKOS.Concept), 'concept': (AHCM.concepto, SKOS.Concept),
             'person': (AHCM.agente, FOAF.Agent), 'contribution': (AHCM.aportacion, SCHEMA.CreativeWork)}
    for row in rows:
        name, link = split_link(row.get('Autor normalizado', ''))
        if not name:
            continue
        person = PERSON[slug(name)]
        graph.add((person, RDF.type, FOAF.Person))
        graph.add((person, RDFS.label, Literal(name, lang='es')))
        if link:
            graph.add((person, RDFS.seeAlso, link))
        for column, field in ACTOR_FIELDS.items():
            for raw in field_values(row, column, field):
                text, uri = split_link(raw)
                if not text or text.lower() == 'nan':
                    continue
                if field.kind == 'text':
                    target = Literal(text, lang='es')
                    if uri:
                        graph.add((person, RDFS.seeAlso, uri))
                else:
                    candidates = external.get(uri, set()) or identities.get(slug(text), set())
                    if field.kind == 'person' and len(candidates) == 1:
                        target = next(iter(candidates))
                    else:
                        known = authorities.get((field.kind, slug(text)), set())
                        prefix, rdf_type = kinds[field.kind]
                        target = uri or (next(iter(known)) if len(known) == 1 else URIRef(f'{prefix}/{slug(text)}'))
                        graph.add((target, RDF.type, rdf_type))
                        graph.add((target, RDFS.label, Literal(text, lang='es')))
                graph.add((person, field.predicate, target))
        for column, predicate, kind in [('Año de nacimiento', BIO.birth, BIO.Birth),
                                        ('Año de muerte', BIO.death, BIO.Death)]:
            for raw in values(row.get(column)):
                event = URIRef(f'{person}/{"nacimiento" if predicate == BIO.birth else "muerte"}')
                try:
                    date = Literal(str(int(float(raw))), datatype=XSD.gYear)
                except ValueError:
                    date = Literal(raw)
                graph.add((person, predicate, event))
                graph.add((event, RDF.type, kind))
                graph.add((event, BIO.date, date))
                graph.add((event, RDFS.label, Literal(str(date))))
