"""CSV to BIBFRAME 2: title reconciliation, works and separate instances."""
import hashlib
import re
from collections import defaultdict
from difflib import SequenceMatcher
from rdflib import Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF
from rdf_pipeline import BIBFRAME as BF, AHCMO, PERSON, WORK, read_csv, slug, values
from ontology import PROV
from rdflib.namespace import XSD
from bibliographic_normalization import LANGUAGES, missing, urls, doi, isbn, normalized_genre, bhl_copy


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
    titles, aliases = defaultdict(set), defaultdict(set)
    rows = read_csv(path)
    for person in list(graph.subjects(RDF.type, FOAF.Person)):
        for predicate in (RDFS.label, FOAF.name, AHCMO.signatureName):
            for name in graph.objects(person, predicate):
                aliases[name_key(str(name))].add(person)
    role = URIRef('http://id.loc.gov/vocabulary/relators/aut')
    graph.add((role, RDF.type, BF.Role))
    graph.add((role, RDFS.label, Literal('Autor')))
    source_file = URIRef('http://ahcm/fuente/bibliografia')
    graph.add((source_file, RDF.type, PROV.Entity))
    graph.add((source_file, AHCMO.sha256, Literal(hashlib.sha256(path.read_bytes()).hexdigest())))
    copy_rows = defaultdict(set)
    for index, row in enumerate(rows, 1):
        for column in ('URL', 'DOI', 'PDF'):
            for url in urls(row.get(column, '')):
                copy = bhl_copy(url, row.get('Tipo de documento', ''))
                if copy:
                    copy_rows[copy].add(index)

    def resource(uri, kind, text):
        graph.add((uri, RDF.type, kind))
        graph.add((uri, RDFS.label, Literal(text)))
        return uri

    def shared(kind, text):
        return resource(URIRef(f'http://ahcm/bibliografia/{str(kind).rsplit("/", 1)[-1]}/{digest(title_key(text))}'), kind, text)

    def work_for(title, discriminator='unmatched'):
        work = WORK['obra-' + digest(title_key(title) + '\0' + discriminator)]
        resource(work, BF.Work, title)
        title_node = resource(URIRef(f'{work}/titulo'), BF.Title, title)
        graph.add((work, BF.title, title_node))
        graph.add((title_node, BF.mainTitle, Literal(title)))
        # Trace the former title-only identifier without asserting owl:sameAs.
        graph.add((work, AHCMO.previousIdentifier, WORK['titulo-' + digest(title_key(title))]))
        return work

    def local(subject, column, text):
        predicate = AHCMO['bibliografia-' + slug(column)]
        graph.add((predicate, RDF.type, RDF.Property))
        graph.add((predicate, RDFS.label, Literal(column)))
        graph.add((subject, predicate, Literal(text)))

    def add_author(work, author, source=None, actor=None):
        known = aliases.get(name_key(author), set())
        agent = actor or (next(iter(known)) if len(known) == 1 else shared(BF.Agent, author))
        graph.add((agent, RDF.type, BF.Person if (agent, RDF.type, FOAF.Person) in graph else BF.Agent))
        contribution = resource(URIRef(f'{work}/contribucion-{digest(str(agent))}'), BF.Contribution, author)
        graph.add((work, BF.contribution, contribution))
        graph.add((contribution, BF.agent, agent))
        graph.add((contribution, BF.role, role))
        if source:
            graph.add((contribution, PROV.wasDerivedFrom, source))
        if (agent, RDF.type, FOAF.Person) in graph:
            graph.add((agent, FOAF.made, work))
        return contribution

    for index, row in enumerate(rows, 1):
        source = URIRef(f'{source_file}/fila-{index + 1}')
        graph.add((source, RDF.type, PROV.Entity))
        graph.add((source, PROV.wasDerivedFrom, source_file))
        graph.add((source, AHCMO.sourceRow, Literal(index + 1)))
        for column, original in row.items():
            pred = AHCMO['original-' + slug(column)]
            graph.add((pred, RDF.type, RDF.Property))
            graph.add((pred, RDFS.label, Literal(column)))
            graph.add((source, pred, Literal(original or '')))
        title = row.get('Titulo', '').strip()
        if not title:
            continue  # Row remains losslessly represented, not an invented title.
        authors = sorted(name_key(a) for a in row.get('Autor', '').split(';') if a.strip())
        discriminator = '|'.join(authors) + '\0' + slug(row.get('Idioma', ''))
        if not authors or authors == ['anonimo']:
            discriminator += f'\0fila-{index + 1}'
        work = work_for(title, discriminator)
        titles[title_key(title)].add(work)
        instance = resource(URIRef(f'http://ahcm/instancia/{index}'), BF.Instance, title)
        graph.add((work, BF.hasInstance, instance))
        graph.add((instance, BF.instanceOf, work))
        graph.add((instance, BF.title, URIRef(f'{work}/titulo')))
        graph.add((instance, PROV.wasDerivedFrom, source))
        graph.add((work, PROV.wasDerivedFrom, source))
        graph.add((source, AHCMO.describes, instance))
        graph.add((instance, AHCMO.sourceFile, Literal('dataset/bibliografica.csv')))
        graph.add((instance, AHCMO.sourceRow, Literal(index + 1)))
        for column, original in row.items():
            text = (original or '').strip()
            if missing(text) or column == 'Titulo':
                continue
            if column == 'Autor':
                for author in filter(None, (a.strip() for a in text.split(';'))):
                    if slug(author) in ('anonimo', 'sin-autor', 'desconocido'):
                        local(work, 'Autor declarado', author)
                    else:
                        add_author(work, author, source)
            elif column == 'Idioma':
                known = LANGUAGES.get(slug(text))
                if known:
                    code, label = known
                    node = resource(URIRef('http://id.loc.gov/vocabulary/languages/' + code), BF.Language, label)
                    graph.add((node, BF.code, Literal(code)))
                else:
                    node = shared(BF.Language, text)
                graph.add((work, BF.language, node))
            elif column in ('Referentes', 'Área temática/campo'):
                for term in filter(None, (v.strip() for v in text.split(';'))):
                    topic = shared(BF.Topic, term)
                    graph.add((work, BF.subject, topic))
                    if column == 'Referentes':
                        local(work, 'Referentes', term)
                    else:
                        local(work, 'Área temática/campo', term)
            elif column == 'Tipo de documento':
                if slug(text).startswith(('fuente-', 'fuentes-')):
                    local(work, column, text)  # Source classification is not genre.
                else:
                    graph.add((work, BF.genreForm, shared(BF.GenreForm, normalized_genre(text))))
            elif column == 'Año de publicación':
                if re.fullmatch(r'\d{4}(?:-\d{4})?', text):
                    publication = resource(URIRef(f'{instance}/publicacion'), BF.Publication, text)
                    graph.add((instance, BF.provisionActivity, publication))
                    graph.add((publication, BF.date, Literal(text, datatype=XSD.gYear) if text.isdigit() else Literal(text)))
                else:
                    local(instance, column, text)
            elif column == 'No páginas':
                if text.isdigit() and int(text) > 0:
                    extent = resource(URIRef(f'{instance}/extension'), BF.Extent, text + ' páginas')
                    graph.add((instance, BF.extent, extent))
                else:
                    local(instance, column, text)
            elif column == 'Notas':
                graph.add((instance, BF.note, resource(URIRef(f'{instance}/nota'), BF.Note, text)))
            elif column == 'Edición':
                graph.add((instance, BF.editionStatement, Literal(text)))
            elif column in ('DOI', 'ISBN'):
                normalized = doi(text) if column == 'DOI' else isbn(text)
                if normalized:
                    identifier = resource(URIRef(f'{instance}/{column.lower()}'), BF.Doi if column == 'DOI' else BF.Isbn, normalized)
                    graph.add((instance, BF.identifiedBy, identifier))
                    graph.add((identifier, RDF.value, Literal(normalized)))
                else:
                    local(instance, column + ' original sin validar', text)
            elif column in ('URL', 'PDF') and urls(text):
                pass  # Process source URLs below, including URLs misplaced in DOI.
            elif column in ('Volumen', 'Tomo', 'Número'):
                # A statement about the described part, without inventing its host.
                graph.add((instance, BF.part, Literal(f'{column}: {text}')))
            else:
                local(instance, column, text)
        for column in ('URL', 'DOI', 'PDF'):
            for url in urls(row.get(column, '')):
                copy = bhl_copy(url, row.get('Tipo de documento', ''))
                if copy and len(copy_rows[copy]) == 1:
                    item = resource(URIRef(f'http://ahcm/ejemplar/bhl-{digest(copy)}'), BF.Item, 'Ejemplar digital en BHL')
                    graph.add((instance, BF.hasItem, item))
                    graph.add((item, BF.itemOf, instance))
                    graph.add((item, BF.electronicLocator, URIRef(url)))
                    graph.add((item, PROV.wasDerivedFrom, source))
                else:
                    # A catalog/title/host/DOI link does not identify an actual copy.
                    graph.add((instance, RDFS.seeAlso, URIRef(url)))

    matcher = TitleMatcher(titles)
    for row in actors:
        name = row.get('Autor normalizado', '').split(':', 1)[0]
        if not name:
            continue
        person = PERSON[slug(name)]
        for title in [part for raw in values(row.get('Trabajo')) for part in matcher.split(raw)]:
            work, method, score = matcher.match(title)
            if work is None:
                work = work_for(title, 'actor-' + str(person))
            graph.add((person, FOAF.made, work))
            contribution = add_author(work, name, actor=person)
            graph.add((contribution, AHCMO.matchMethod, Literal(method)))
            graph.add((contribution, AHCMO.matchScore, Literal(score)))
            graph.add((contribution, AHCMO.originalTitle, Literal(title)))


def name_key(name):
    return ' '.join(sorted(word for word in title_key(name).split() if not word.isdigit()))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:20]
