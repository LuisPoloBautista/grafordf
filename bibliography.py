"""CSV to BIBFRAME 2: title reconciliation, works and separate instances."""
import hashlib
import re
from collections import defaultdict
from difflib import SequenceMatcher
from rdflib import Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF
from rdf_pipeline import BIBFRAME as BF, AHCMO, PERSON, WORK, read_csv, slug, values
from ontology import BIBLIOGRAPHIC_FIELDS


def title_key(text):
    return slug(text).replace('-', ' ')


class TitleMatcher:
    """Exact titles, catalogue-aware comma segmentation and conservative fuzziness."""
    def __init__(self, titles):
        self.titles = titles
        self.tokens = defaultdict(set)
        for title in titles:
            for token in set(title.split()):
                self.tokens[token].add(title)

    def split(self, text):
        if title_key(text) in self.titles:
            return [text]
        parts = re.split(r'\s*,\s*', text)
        output, pending, i = [], [], 0
        while i < len(parts):
            end = next((j for j in range(len(parts), i, -1)
                        if title_key(', '.join(parts[i:j])) in self.titles), None)
            if end is None:
                pending.append(parts[i])
                i += 1
            else:
                if pending:
                    output.append(', '.join(pending))
                    pending = []
                output.append(', '.join(parts[i:end]))
                i = end
        if pending:
            output.append(', '.join(pending))
        return output

    def match(self, text):
        key = title_key(text)
        exact = self.titles.get(key, set())
        if len(exact) == 1:
            return next(iter(exact)), 'Título normalizado exacto', 1.0
        explicit_abbreviation = text.rstrip().endswith(('...', '…')) and len(key.split()) >= 3 and len(key) >= 20
        if len(key.split()) < 5 and not explicit_abbreviation:
            return None, 'Sin coincidencia bibliográfica única', 0.0
        prefixes = {work for candidate, works in self.titles.items()
                    if candidate.startswith(key + ' ') for work in works}
        if len(prefixes) == 1:
            return next(iter(prefixes)), 'Título abreviado único', 0.98
        if explicit_abbreviation:
            return None, 'Sin coincidencia bibliográfica única', 0.0
        candidates = set().union(*(self.tokens.get(t, set()) for t in key.split()))
        scores = sorted(((SequenceMatcher(None, key, candidate, autojunk=False).ratio(), candidate)
                         for candidate in candidates if .85 <= len(key) / max(len(candidate), 1) <= 1.18), reverse=True)
        if scores and scores[0][0] >= .94 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= .05):
            score, candidate = scores[0]
            works = self.titles[candidate]
            if len(works) == 1:
                return next(iter(works)), 'Variante ortográfica de alta confianza', round(score, 4)
        return None, 'Sin coincidencia bibliográfica única', 0.0


def add_bibliography(graph, actors, path):
    titles = defaultdict(set)
    author_aliases = defaultdict(set)

    def name_key(name):
        return ' '.join(sorted(word for word in title_key(name).split() if not word.isdigit()))

    for person in graph.subjects(RDF.type, FOAF.Person):
        for predicate in (RDFS.label, FOAF.name, AHCMO.signatureName):
            for name in graph.objects(person, predicate):
                author_aliases[name_key(str(name))].add(person)

    def resource(parent, field, kind, text):
        if kind in (BF.Agent, BF.Language, BF.GenreForm, BF.Topic):
            node = URIRef(f'http://ahcm/metadato/{str(kind).rsplit("/", 1)[-1]}/{slug(text)}')
        else:
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
                for author_index, author in enumerate(filter(None, (a.strip() for a in text.split(';')))):
                    known = author_aliases.get(name_key(author), set())
                    agent = next(iter(known)) if len(known) == 1 else resource(instance, 'autor', BF.Agent, author)
                    contribution = resource(instance, f'contribucion-{author_index}', BF.Contribution, author)
                    graph.add((work, BF.contribution, contribution))
                    graph.add((contribution, BF.agent, agent))
                    graph.add((contribution, BF.role, URIRef('http://id.loc.gov/vocabulary/relators/aut')))
                    if agent in known:
                        graph.add((agent, FOAF.made, work))
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
            elif column in BIBLIOGRAPHIC_FIELDS:
                pred, kind, level = BIBLIOGRAPHIC_FIELDS[column]
                target = instance if level == 'instance' else work
                graph.add((target, pred, resource(instance, slug(column), kind, text)))
            elif column == 'Edición':
                graph.add((instance, BF.editionStatement, Literal(text)))
            else:
                # Preserve source fields without inventing BIBFRAME properties.
                pred = AHCMO['bibliografia-' + slug(column)]
                graph.add((pred, RDFS.label, Literal(column)))
                graph.add((instance, pred, Literal(text)))

    matcher = TitleMatcher(titles)
    for row in actors:
        name = row.get('Autor normalizado', '').split(':', 1)[0]
        if not name:
            continue
        person = PERSON[slug(name)]
        for title in [part for raw in values(row.get('Trabajo')) for part in matcher.split(raw)]:
            work, method, score = matcher.match(title)
            if work is None:
                work = work_for(title)
            graph.add((person, FOAF.made, work))
            contribution = resource(work, 'actor-' + slug(name), BF.Contribution, name)
            graph.add((work, BF.contribution, contribution))
            graph.add((contribution, BF.agent, person))
            graph.add((contribution, BF.role, URIRef('http://id.loc.gov/vocabulary/relators/aut')))
            graph.add((contribution, AHCMO.matchMethod, Literal(method)))
            graph.add((contribution, AHCMO.matchScore, Literal(score)))
            graph.add((contribution, AHCMO.originalTitle, Literal(title)))
