"""CSV to BIBFRAME 2: title reconciliation, works and separate instances."""
import hashlib
import re
from collections import defaultdict
from rdflib import Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF
from rdf_pipeline import BIBFRAME as BF, AHCMO, PERSON, WORK, read_csv, slug, values


def title_key(text):
    return slug(text).replace('-', ' ')


def add_bibliography(graph, actors, path):
    titles = defaultdict(set)

    def resource(parent, field, kind, text):
        node = URIRef(f'{parent}/{field}')
        graph.add((node, RDF.type, kind))
        graph.add((node, RDFS.label, Literal(text)))
        return node

    def work_for(title):
        work = WORK['titulo-' + hashlib.sha256(title_key(title).encode()).hexdigest()[:20]]
        graph.add((work, RDF.type, BF.Work))
        graph.add((work, RDFS.label, Literal(title)))
        node = resource(work, 'titulo', BF.Title, title)
        graph.add((work, BF.title, node))
        graph.add((node, BF.mainTitle, Literal(title)))
        return work

    for index, row in enumerate(read_csv(path), 1):
        title = row.get('Titulo', '').strip()
        if not title:
            continue
        work = work_for(title)
        titles[title_key(title)].add(work)
        instance = URIRef(f'http://ahcm/instancia/{index}')
        graph.add((instance, RDF.type, BF.Instance))
        graph.add((instance, RDFS.label, Literal(f'{title} ({row.get("Año de publicación") or "sin fecha"})')))
        graph.add((work, BF.hasInstance, instance))
        graph.add((instance, BF.instanceOf, work))
        graph.add((instance, BF.title, URIRef(f'{work}/titulo')))
        graph.add((instance, AHCMO.sourceFile, Literal('dataset/bibliografica.csv')))
        graph.add((instance, AHCMO.sourceRow, Literal(index + 1)))
        for column, raw in row.items():
            text = (raw or '').strip()
            if not text or text.lower() == 'nan' or column == 'Titulo':
                continue
            if column == 'Autor':
                agent = resource(instance, 'autor', BF.Agent, text)
                contribution = resource(instance, 'contribucion', BF.Contribution, text)
                graph.add((work, BF.contribution, contribution))
                graph.add((contribution, BF.agent, agent))
            elif column == 'Año de publicación':
                publication = resource(instance, 'publicacion', BF.Publication, text)
                graph.add((instance, BF.provisionActivity, publication))
                graph.add((publication, BF.date, Literal(text)))
            elif column in ('URL', 'PDF') and re.match(r'https?://', text):
                graph.add((instance, BF.electronicLocator, URIRef(text)))
            elif column in ('ISBN', 'DOI'):
                node = resource(instance, column.lower(), BF.Isbn if column == 'ISBN' else BF.Doi, text)
                graph.add((instance, BF.identifiedBy, node))
                graph.add((node, RDF.value, Literal(text)))
            elif column in ('Idioma', 'Tipo de documento', 'Área temática/campo', 'No páginas', 'Notas'):
                pred, kind = {'Idioma': (BF.language, BF.Language), 'Tipo de documento': (BF.genreForm, BF.GenreForm),
                              'Área temática/campo': (BF.subject, BF.Topic), 'No páginas': (BF.extent, BF.Extent),
                              'Notas': (BF.note, BF.Note)}[column]
                target = instance if column in ('No páginas', 'Notas') else work
                graph.add((target, pred, resource(instance, slug(column), kind, text)))
            elif column == 'Edición':
                graph.add((instance, BF.editionStatement, Literal(text)))
            else:
                # Preserve source fields without inventing BIBFRAME properties.
                pred = AHCMO['bibliografia-' + slug(column)]
                graph.add((pred, RDFS.label, Literal(column)))
                graph.add((instance, pred, Literal(text)))

    for row in actors:
        name = row.get('Autor normalizado', '').split(':', 1)[0]
        if not name:
            continue
        person = PERSON[slug(name)]
        for title in values(row.get('Trabajo')):
            key = title_key(title)
            matches = titles.get(key, set())
            method = 'Título normalizado exacto'
            if not matches and len(key.split()) >= 5:
                matches = {work for candidate, works in titles.items()
                           if candidate.startswith(key + ' ') for work in works}
                method = 'Título abreviado único'
            if len(matches) == 1:
                work = next(iter(matches))
            else:
                work = work_for(title)
                method = 'Sin coincidencia bibliográfica única'
            graph.add((person, FOAF.made, work))
            contribution = resource(work, 'actor-' + slug(name), BF.Contribution, name)
            graph.add((work, BF.contribution, contribution))
            graph.add((contribution, BF.agent, person))
            graph.add((contribution, AHCMO.matchMethod, Literal(method)))
