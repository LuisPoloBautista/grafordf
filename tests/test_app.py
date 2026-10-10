import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import FOAF

from app import app
from rdf_pipeline import BIBFRAME, PERSON, BIO, values
from ontology import AHCMO, SCHEMA, ORG, ACTOR_FIELDS
from catalog_graph import CatalogGraph
from bibliography import TitleMatcher


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Startup must work without opening any outbound connection.
        with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            cls.client = TestClient(app)
            cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_home_and_local_assets(self):
        for path, content in [('/', 'text/html'), ('/static/styles.css', 'text/css'),
                              ('/static/app.js', 'javascript')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(content, response.headers['content-type'])
        css = self.client.get('/static/styles.css').text
        self.assertNotIn('@import', css)
        self.assertNotIn('fonts.googleapis', css)

    def test_health_and_real_data(self):
        self.assertEqual(self.client.get('/health').json()['status'], 'ok')
        stats = self.client.get('/api/stats').json()
        self.assertEqual(stats['personas'], 110)
        self.assertGreater(stats['publicaciones'], 1400)

    def test_accent_insensitive_search(self):
        plain = self.client.get('/api/personas', params={'q': 'jose'}).json()
        accented = self.client.get('/api/personas', params={'q': 'José'}).json()
        self.assertTrue(plain)
        self.assertEqual(plain, accented)

    def test_pagination_covers_catalog(self):
        people = []
        for offset in range(0, 120, 20):
            page = self.client.get('/api/personas', params={'limit': 20, 'offset': offset}).json()
            people.extend(p['id'] for p in page)
        self.assertEqual(len(people), 110)
        self.assertEqual(len(set(people)), 110)

    def test_detail_relations_and_unicode(self):
        person = self.client.get('/api/personas/jose-de-acosta').json()
        self.assertIn('José', person['label'])
        self.assertTrue(person['publications'])
        self.assertEqual(person['properties']['birthYear'][0]['label'], '1540')
        relations = self.client.get('/api/personas/jose-de-acosta/relaciones').json()
        self.assertTrue(relations)
        self.assertNotIn('type', [r['predicate'] for r in relations])

    def test_missing_and_invalid_queries(self):
        self.assertEqual(self.client.get('/api/personas/no-existe').status_code, 404)
        self.assertEqual(self.client.get('/api/personas/no-existe/relaciones').status_code, 404)
        for params in ({'limit': 101}, {'offset': -1}, {'q': 'a' * 121}):
            self.assertEqual(self.client.get('/api/personas', params=params).status_code, 422)
        self.assertEqual(self.client.get('/api/personas?q=zzzzzzzzz').json(), [])

    def test_rdf_download_matches_live_graph(self):
        response = self.client.get('/api/grafo.ttl')
        graph = Graph().parse(data=response.content, format='turtle')
        self.assertEqual(len(graph), self.client.get('/api/stats').json()['triples'])
        self.assertIn('attachment', response.headers['content-disposition'])
        self.assertIn((PERSON['jose-de-acosta'], RDF.type, FOAF.Person), graph)

    def test_no_fake_missing_values(self):
        graph = app.state.graph
        self.assertFalse(any(isinstance(obj, Literal) and str(obj) == 'nan' for obj in graph.objects()))
        self.assertFalse(any('\ufffd' in str(obj) for obj in graph.objects()))

    def test_multivalue_parsing_preserves_names(self):
        self.assertEqual(values('Medina del campo, España'), ['Medina del campo, España'])
        self.assertEqual(len(values('botánico: https://example.org/1 , escritor: https://example.org/2')), 2)
        self.assertEqual(values(None), [])
        self.assertEqual(values("['uno', 'dos']"), ['uno', 'dos'])

    def test_every_person_can_be_opened(self):
        for entry, _ in app.state.people:
            response = self.client.get('/api/personas/' + entry['slug'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['id'], entry['id'])

    def test_publication_title_reconciliation_and_bibframe(self):
        person = self.client.get('/api/personas/jose-de-acosta').json()
        work = next(work for work in person['publications'] if work['label'].startswith('Historia natural'))
        response = self.client.get('/api/recursos', params={'uri': work['id']})
        self.assertEqual(response.status_code, 200)
        record = response.json()
        self.assertTrue(record['instances'])
        self.assertIn('jose-de-acosta', record['actors'][0]['id'])
        instance = record['instances'][0]
        self.assertTrue(instance['properties']['electronicLocator'])
        graph = app.state.graph
        for title in graph.objects(URIRef(work['id']), BIBFRAME.title):
            self.assertIn((title, RDF.type, BIBFRAME.Title), graph)
            self.assertTrue(list(graph.objects(title, BIBFRAME.mainTitle)))
        self.assertIn((URIRef(instance['id']), BIBFRAME.instanceOf, URIRef(work['id'])), graph)
        self.assertEqual(self.client.get('/api/recursos', params={'uri': 'http://ahcm/missing'}).status_code, 404)

    def test_search_returns_publications_not_their_authors(self):
        results = self.client.get('/api/buscar', params={'q': 'historia moral indias'}).json()
        self.assertTrue(results)
        self.assertTrue(all(p['kind'] == 'publicacion' for p in results))
        records = self.client.get('/api/buscar', params={'q': '1792', 'kind': 'publicacion'}).json()
        self.assertTrue(records)
        self.assertTrue(all(p['kind'] == 'publicacion' for p in records))
        self.assertEqual(self.client.get('/api/buscar?kind=invalid').status_code, 422)

    def test_pyvis_renders_semantic_projection_and_no_remote_scripts(self):
        import re
        for route in ('/grafo', '/api/personas/jose-de-acosta/grafo'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertIn('vis.Network', response.text)
            self.assertNotRegex(response.text, r'<script[^>]+src="https?://')
            self.assertNotRegex(response.text, r'<link[^>]+href="https?://')
        page = self.client.get('/grafo').text
        nodes, edges = app.state.projection.visual_data()
        self.assertIn(f'{len(edges)} relaciones visibles', page)
        self.assertLess(len(edges), len(app.state.graph))
        self.assertEqual(self.client.get('/api/personas/no-existe/grafo').status_code, 404)

    def test_ontology_mapping_and_labels_are_not_relations(self):
        graph = app.state.graph
        self.assertFalse(list(graph.triples((None, AHCMO.sourceType, None))))
        self.assertFalse(list(graph.triples((None, BIO.NameChange, None))))
        self.assertEqual(ACTOR_FIELDS['Formación'].predicate, SCHEMA.alumniOf)
        self.assertEqual(ACTOR_FIELDS['Adscripción'].predicate, ORG.memberOf)
        for event in graph.objects(PERSON['jose-de-acosta'], BIO.birth):
            self.assertIn((event, RDF.type, BIO.Birth), graph)
            self.assertEqual(str(graph.value(event, BIO.date)), '1540')
        nodes, edges = app.state.projection.visual_data()
        for edge in edges:
            self.assertTrue(edge['weight'] >= 1)
            self.assertFalse(set(edge['predicates']) & {'label', 'sourceType', 'type', 'agent', 'comment'})
        self.assertEqual(len({n['id'] for n in nodes}), len(nodes))
        self.assertEqual({n['kind'] for n in nodes}, {'actor', 'publicacion', 'metadato'})
        self.assertGreater(max(n['degree'] for n in nodes), min(n['degree'] for n in nodes))
        self.assertNotIn('Fuentes: comunidades.csv', self.client.get('/').text)

    def test_metadata_recovers_shared_records_and_paginates(self):
        projection = app.state.projection
        metadata = next(identity for identity, matches in projection.related.items()
                        if (URIRef(identity), RDF.type, ORG.Organization) in app.state.graph and len(matches) >= 2)
        result = self.client.get('/api/metadatos', params={'id': metadata, 'limit': 1}).json()
        self.assertGreaterEqual(result['total'], 2)
        second = self.client.get('/api/metadatos', params={'id': metadata, 'limit': 1, 'offset': 1}).json()
        self.assertNotEqual(result['records'], second['records'])
        self.assertTrue(all(r['kind'] in ('actor', 'publicacion') for r in result['records']))
        self.assertEqual(self.client.get('/api/metadatos?id=missing').status_code, 404)

    def test_local_formation_resource_is_shared_without_an_external_uri(self):
        from actors import add_actors
        graph = Graph()
        add_actors(graph, [{'Autor normalizado': name, 'Formación': 'Colegio de prueba'}
                           for name in ('Actor uno', 'Actor dos')])
        projection = CatalogGraph(graph)
        uri = 'http://ahcm/institucion/colegio-de-prueba'
        with patch.object(app.state, 'projection', projection):
            response = self.client.get('/api/metadatos', params={'id': uri}).json()
        self.assertEqual(response['total'], 2)
        nodes, edges = projection.visual_data()
        self.assertEqual(sum(n['id'] == uri for n in nodes), 1)
        self.assertEqual(sum(e['to'] == uri for e in edges), 2)

    def test_title_matching_composites_variants_and_ambiguity(self):
        matcher = TitleMatcher({'plantas de mexico animales y minerales': {'a'},
                                'flora pedemontana': {'b'},
                                'catalogo de plantas del jardin botanico de madrid': {'c'}})
        self.assertEqual(matcher.split('Plantas de México, animales y minerales, Flora pedemontana'),
                         ['Plantas de México, animales y minerales', 'Flora pedemontana'])
        self.assertEqual(matcher.match('Catálogo de plantas del jardin botánico de Madird')[0], 'c')
        ambiguous = TitleMatcher({'historia natural de plantas de mexico tomo primero': {'a'},
                                  'historia natural de plantas de mexico tomo segundo': {'b'}})
        self.assertIsNone(ambiguous.match('Historia natural de plantas de México')[0])
        self.assertIsNone(matcher.match('Flora mexicana')[0])

    def test_linked_names_keep_commas(self):
        name = 'Acosta, José de, 1540-1600.: https://viaf.org/viaf/2465365'
        self.assertEqual(values(name), [name])

    def test_unlinked_occupations_do_not_pollute_linked_labels(self):
        from actors import add_actors
        from rdflib import RDFS
        graph = Graph()
        add_actors(graph, [{'Autor normalizado': 'Actor', 'Rol adquirido':
                           'Fotógrafo, botánico: https://www.wikidata.org/wiki/Q2374149'}])
        labels = list(graph.objects(URIRef('https://www.wikidata.org/wiki/Q2374149'), RDFS.label))
        self.assertEqual([str(v) for v in labels], ['botánico'])
        self.assertEqual(len(list(graph.objects(PERSON['actor'], AHCMO.acquiredRole))), 2)

    def test_reconciliation_improves_real_composite_titles(self):
        methods = list(app.state.graph.objects(None, AHCMO.matchMethod))
        exact = sum(str(m) == 'Título normalizado exacto' for m in methods)
        self.assertGreater(exact, 200)


if __name__ == '__main__':
    unittest.main()
