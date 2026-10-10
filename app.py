from pathlib import Path
from contextlib import asynccontextmanager
import unicodedata

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from rdflib import RDF, RDFS, URIRef
from rdflib.namespace import FOAF

from rdf_pipeline import PERSON, BIBFRAME, SCHEMA, BIO, build_graph

from graph_tools import GraphSearch, graph_html
from catalog_graph import CatalogGraph
from ontology import AHCMO, LABELS, ACTOR_FIELDS

ROOT = Path(__file__).resolve().parent


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold()
                   if not unicodedata.combining(c))


def label(graph, resource):
    for predicate in (RDFS.label, FOAF.name, BIBFRAME.title):
        names = sorted(str(value) for value in graph.objects(resource, predicate))
        if names:
            return names[0]
    return str(resource).rsplit('/', 1)[-1].rsplit('#', 1)[-1].replace('-', ' ')


def compact(graph, resource):
    return {'id': str(resource), 'label': label(graph, resource)}


def key(predicate):
    return str(predicate).rsplit('/', 1)[-1].rsplit('#', 1)[-1]


@asynccontextmanager
async def lifespan(app):
    # CSV files are the source of truth; no stale cache or writable disk required.
    graph = build_graph()
    app.state.graph = graph
    app.state.people = []
    for person in sorted(set(graph.subjects(RDF.type, FOAF.Person)),
                         key=lambda p: normalize(label(graph, p))):
        aliases = [str(value) for predicate in (FOAF.name, AHCMO.signatureName, SCHEMA.alternateName)
                   for value in graph.objects(person, predicate)]
        aliases.extend(label(graph, value) for value in graph.objects(person, AHCMO.signatureName))
        app.state.people.append(({
            **compact(graph, person), 'slug': str(person).rsplit('/', 1)[-1]
        }, normalize(' '.join(aliases))))
    app.state.projection = CatalogGraph(graph)
    app.state.search = GraphSearch(graph, app.state.people, app.state.projection)
    app.state.graph_pages = {}
    app.state.stats = {
        'fuentes': ['comunidades.csv', 'dataset/bibliografica.csv'], 'triples': len(graph), 'personas': len(app.state.people),
        'publicaciones': len(set(graph.subjects(RDF.type, BIBFRAME.Work)))
    }
    app.state.turtle = graph.serialize(format='turtle', encoding='utf-8')
    yield


app = FastAPI(title='Catálogo de autoridades de actores en el campo de la botánica XVIII', lifespan=lifespan,
              docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.get('/health')
def health(request: Request):
    return {'status': 'ok', 'personas': request.app.state.stats['personas']}


@app.get('/api/stats')
def stats(request: Request):
    return request.app.state.stats


@app.get('/api/buscar')
def search_catalog(request: Request, q: str = Query('', max_length=120),
                   kind: str = Query('todos', pattern='^(todos|actor|publicacion)$'),
                   limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    return request.app.state.search.search(q, None if kind == 'todos' else kind)[offset:offset + limit]


@app.get('/api/vocabulario')
def vocabulary(request: Request):
    labels = {key(URIRef(uri)): value for uri, value in LABELS.items()}
    labels.update(request.app.state.projection.labels)
    return {'labels': labels, 'columns': [
        {'column': column, 'predicate': str(field.predicate), 'kind': field.kind,
         'subPropertyOf': str(field.parent) if field.parent else None}
        for column, field in ACTOR_FIELDS.items()]}


@app.get('/api/metadatos')
def metadata_records(request: Request, id: str = Query(..., max_length=3000),
                     limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    projection = request.app.state.projection
    if id not in projection.nodes:
        raise HTTPException(status_code=404, detail='Metadato no encontrado')
    matches = projection.matches(id)
    return {**projection.nodes[id], 'total': len(matches), 'records': matches[offset:offset + limit]}


@app.get('/api/personas')
def people(request: Request, q: str = Query('', max_length=120),
           limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    query = normalize(q.strip())
    matches = request.app.state.search.search(query, kind='actor')
    return matches[offset:offset + limit]


def get_person(request, person_id):
    graph = request.app.state.graph
    person = PERSON[person_id]
    if (person, RDF.type, FOAF.Person) not in graph:
        raise HTTPException(status_code=404, detail='Persona no encontrada')
    return graph, person


@app.get('/api/personas/{person_id}')
def person_detail(request: Request, person_id: str):
    graph, person = get_person(request, person_id)
    properties = dict(request.app.state.projection.properties[str(person)])
    properties['seeAlso'] = [compact(graph, value) for value in graph.objects(person, RDFS.seeAlso)]
    return {
        **compact(graph, person), 'properties': properties,
        'publications': sorted([compact(graph, work) for work in graph.objects(person, FOAF.made)
                               if (work, RDF.type, BIBFRAME.Work) in graph], key=lambda item: item['label'])
    }


@app.get('/api/personas/{person_id}/relaciones')
def person_relations(request: Request, person_id: str):
    graph, person = get_person(request, person_id)
    relations = []
    for predicate, obj in graph.predicate_objects(person):
        if isinstance(obj, URIRef) and obj != person and predicate != RDF.type:
            relations.append({'predicate': key(predicate), 'target': compact(graph, obj)})
    return sorted(relations, key=lambda item: (item['predicate'], item['target']['label']))


@app.get('/api/recursos')
def resource_detail(request: Request, uri: str = Query(..., max_length=2000)):
    graph = request.app.state.graph
    resource = URIRef(uri)
    if not any(graph.triples((resource, None, None))):
        raise HTTPException(status_code=404, detail='Recurso no encontrado')
    if (resource, RDF.type, BIBFRAME.Work) in graph:
        from bibliographic_view import describe_work
        common, instances = describe_work(graph, resource)
        return {**compact(graph, resource), 'properties': common, 'instances': instances,
                'actors': [compact(graph, actor) for actor in graph.subjects(FOAF.made, resource)]}
    properties = {}
    for predicate, obj in sorted(graph.predicate_objects(resource), key=lambda pair: tuple(map(str, pair))):
        properties.setdefault(key(predicate), []).append(compact(graph, obj) if isinstance(obj, URIRef) else str(obj))
    instances = []
    for instance in sorted(graph.objects(resource, BIBFRAME.hasInstance), key=str):
        fields = {}
        for predicate, obj in sorted(graph.predicate_objects(instance), key=lambda pair: tuple(map(str, pair))):
            fields.setdefault(key(predicate), []).append(compact(graph, obj) if isinstance(obj, URIRef) else str(obj))
        instances.append({**compact(graph, instance), 'properties': fields})
    return {**compact(graph, resource), 'properties': properties, 'instances': instances,
            'actors': [compact(graph, actor) for actor in graph.subjects(FOAF.made, resource)]}


@app.get('/grafo', response_class=HTMLResponse)
def full_graph(request: Request):
    cache = request.app.state.graph_pages
    if 'full' not in cache:
        cache['full'] = graph_html(request.app.state.graph, label, projection=request.app.state.projection)
    return cache['full']


@app.get('/api/personas/{person_id}/grafo', response_class=HTMLResponse)
def actor_graph(request: Request, person_id: str):
    graph, person = get_person(request, person_id)
    cache = request.app.state.graph_pages
    if person_id not in cache:
        cache[person_id] = graph_html(graph, label, person, request.app.state.projection)
    return cache[person_id]


@app.get('/api/grafo.ttl')
def download_graph(request: Request):
    return Response(request.app.state.turtle, media_type='text/turtle',
                    headers={'Content-Disposition': 'attachment; filename="grafo.ttl"'})


if __name__ == '__main__':
    import os
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
