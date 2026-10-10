"""Perfil de aplicación: columnas, propiedades RDF y etiquetas de presentación.

Los términos locales conservan distinciones del CSV sin atribuirles una
equivalencia externa que no existe. Véase docs/mapeo-rdf.md.
"""
from dataclasses import dataclass
from rdflib import Namespace, RDF, RDFS, Literal
from rdflib.namespace import FOAF, SKOS, DCTERMS, XSD

AHCM = Namespace('http://ahcm/')
AHCMO = Namespace('http://ahcm/ontology/')
PERSON = Namespace('http://ahcm/persona/')
WORK = Namespace('http://ahcm/publicacion/')
PLACE = Namespace('http://ahcm/lugar/')
INSTITUTION = Namespace('http://ahcm/institucion/')
ROLE = Namespace('http://ahcm/rol/')
BIO = Namespace('http://purl.org/vocab/bio/0.1/')
ORG = Namespace('http://www.w3.org/ns/org#')
PROV = Namespace('http://www.w3.org/ns/prov#')
SCHEMA = Namespace('https://schema.org/')
VIVO = Namespace('http://vivoweb.org/ontology/core#')
BIBFRAME = Namespace('http://id.loc.gov/ontologies/bibframe/')


@dataclass(frozen=True)
class Field:
    predicate: object
    kind: str
    parent: object = None


ACTOR_FIELDS = {
    'Nombre firma': Field(AHCMO.signatureName, 'text', SCHEMA.alternateName),
    'Abreviatura': Field(SCHEMA.alternateName, 'text'),
    'Nombre completo': Field(FOAF.name, 'text'),
    'Rol principal': Field(AHCMO.primaryRole, 'occupation', SCHEMA.hasOccupation),
    'Rol adquirido': Field(AHCMO.acquiredRole, 'occupation', SCHEMA.hasOccupation),
    'Género': Field(SCHEMA.gender, 'text'),
    'Comunidad': Field(AHCMO.community, 'topic', SCHEMA.knowsAbout),
    'Subcomunidad': Field(AHCMO.subcommunity, 'topic', SCHEMA.knowsAbout),
    'Lugar de nacimiento': Field(SCHEMA.birthPlace, 'place'),
    'Lugar de muerte': Field(SCHEMA.deathPlace, 'place'),
    'Formación': Field(SCHEMA.alumniOf, 'organization'),
    'Profesión': Field(SCHEMA.hasOccupation, 'occupation'),
    # The source contains both degrees and positions (e.g. catedrático).
    'Grado': Field(AHCMO.academicStatus, 'concept'),
    'Adscripción': Field(ORG.memberOf, 'organization'),
    'Cargo': Field(SCHEMA.jobTitle, 'text'),
    'Afiliación': Field(SCHEMA.affiliation, 'organization'),
    # The source mixes organizations and awards: do not assert award types.
    'Reconocido': Field(AHCMO.recognition, 'concept'),
    'Movilidad': Field(AHCMO.mobility, 'place'),
    'Linaje científico': Field(AHCMO.scientificPredecessor, 'person'),
    'Linaje descendiente': Field(AHCMO.scientificSuccessor, 'person'),
    'Epónimo recibido': Field(AHCMO.receivedEponym, 'concept'),
    'Otorgado por': Field(AHCMO.eponymGivenBy, 'person'),
    'Epónimo asignado': Field(AHCMO.assignedEponym, 'concept'),
    'Otorgado a': Field(AHCMO.eponymGivenTo, 'person'),
    'Aportación / Descubrimiento': Field(FOAF.made, 'contribution'),
    'Notas': Field(DCTERMS.description, 'text'),
}

LABELS = {str(field.predicate): column for column, field in ACTOR_FIELDS.items()}
LABELS.update({str(FOAF.made): 'Publicación o aportación', str(BIO.birth): 'Nacimiento',
              str(BIO.death): 'Muerte', str(BIO.date): 'Año', str(RDFS.seeAlso): 'Identificador externo',
              str(BIBFRAME.contribution): 'Autoría', str(BIBFRAME.agent): 'Autor de la contribución',
              str(BIBFRAME.title): 'Título', str(BIBFRAME.mainTitle): 'Título principal',
              str(BIBFRAME.provisionActivity): 'Publicación', str(BIBFRAME.date): 'Año de publicación',
              str(BIBFRAME.language): 'Idioma', str(BIBFRAME.genreForm): 'Tipo de documento',
              str(BIBFRAME.subject): 'Área temática', str(BIBFRAME.extent): 'Extensión',
              str(BIBFRAME.note): 'Notas', str(BIBFRAME.editionStatement): 'Edición',
              str(BIBFRAME.identifiedBy): 'Identificador', str(BIBFRAME.electronicLocator): 'Acceso al documento',
              str(BIBFRAME.instanceOf): 'Obra', str(RDF.value): 'Valor',
              str(AHCMO.matchMethod): 'Criterio de coincidencia', str(AHCMO.matchScore): 'Confianza',
              str(AHCMO.sourceFile): 'Archivo fuente', str(AHCMO.sourceRow): 'Fila del CSV',
              str(AHCMO.originalTitle): 'Título registrado por el actor'})

# Structured bibliographic fields: property, value class and RDF level.
BIBLIOGRAPHIC_FIELDS = {
    'Idioma': (BIBFRAME.language, BIBFRAME.Language, 'work'),
    'Tipo de documento': (BIBFRAME.genreForm, BIBFRAME.GenreForm, 'work'),
    'Área temática/campo': (BIBFRAME.subject, BIBFRAME.Topic, 'work'),
    'No páginas': (BIBFRAME.extent, BIBFRAME.Extent, 'instance'),
    'Notas': (BIBFRAME.note, BIBFRAME.Note, 'instance'),
}


def predicate_label(predicate):
    return LABELS.get(str(predicate), str(predicate).rsplit('/', 1)[-1].rsplit('#', 1)[-1])


def bind_profile(graph):
    for prefix, ns in {'ahcm': AHCM, 'ahcmo': AHCMO, 'person': PERSON, 'work': WORK,
                       'foaf': FOAF, 'bio': BIO, 'org': ORG, 'prov': PROV, 'schema': SCHEMA,
                       'bf': BIBFRAME, 'skos': SKOS, 'dcterms': DCTERMS, 'xsd': XSD}.items():
        graph.bind(prefix, ns)
    for column, field in ACTOR_FIELDS.items():
        if str(field.predicate).startswith(str(AHCMO)):
            graph.add((field.predicate, RDF.type, RDF.Property))
            graph.add((field.predicate, RDFS.label, Literal(column, lang='es')))
            if field.parent:
                graph.add((field.predicate, RDFS.subPropertyOf, field.parent))
