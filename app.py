from pathlib import Path
from contextlib import asynccontextmanager
import unicodedata

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from rdflib import RDF, RDFS, URIRef
from rdflib.namespace import FOAF

from rdf_pipeline import PERSON, BIBFRAME, SCHEMA, BIO, build_graph

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
        aliases = [str(value) for predicate in (FOAF.name, BIO.NameChange, SCHEMA.alternateName)
                   for value in graph.objects(person, predicate)]
        aliases.extend(label(graph, value) for value in graph.objects(person, BIO.NameChange))
        app.state.people.append(({
            **compact(graph, person), 'slug': str(person).rsplit('/', 1)[-1]
        }, normalize(' '.join(aliases))))
    app.state.stats = {
        'triples': len(graph), 'personas': len(app.state.people),
        'publicaciones': len(set(graph.subjects(RDF.type, BIBFRAME.Work)))
    }
    app.state.turtle = graph.serialize(format='turtle', encoding='utf-8')
    yield


app = FastAPI(title='Grafo prosopográfico AHCM', lifespan=lifespan,
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


@app.get('/api/personas')
def people(request: Request, q: str = Query('', max_length=120),
           limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    query = normalize(q.strip())
    matches = [entry for entry, aliases in request.app.state.people if query in aliases]
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
    properties = {}
    for predicate, obj in sorted(graph.predicate_objects(person), key=lambda pair: (str(pair[0]), str(pair[1]))):
        properties.setdefault(key(predicate), []).append(
            compact(graph, obj) if isinstance(obj, URIRef) else str(obj))
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


@app.get('/api/grafo.ttl')
def download_graph(request: Request):
    return Response(request.app.state.turtle, media_type='text/turtle',
                    headers={'Content-Disposition': 'attachment; filename="grafo.ttl"'})


if __name__ == '__main__':
    import os
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
