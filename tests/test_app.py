import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient
from rdflib import Graph, Literal, RDF
from rdflib.namespace import FOAF

from app import app
from rdf_pipeline import BIBFRAME, PERSON, BIO, values


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
        self.assertIn('1540', person['properties']['birth'])
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


if __name__ == '__main__':
    unittest.main()
