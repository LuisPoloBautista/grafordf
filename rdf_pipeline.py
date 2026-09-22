from __future__ import annotations

import ast
import csv
import io
import re
import unicodedata
from pathlib import Path
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import FOAF, SKOS, XSD

ROOT = Path(__file__).parent
PROSOPOGRAPHIC_CSV = ROOT / "comunidades.csv"
BIBLIOGRAPHIC_CSV = ROOT / "tesis raquel" / "bibliografica.csv"
OUTPUT = ROOT / "data" / "grafo.ttl"

AHCM = Namespace("http://ahcm/")
PERSON = Namespace("http://ahcm/persona/")
WORK = Namespace("http://ahcm/publicacion/")
PLACE = Namespace("http://ahcm/lugar/")
INSTITUTION = Namespace("http://ahcm/institucion/")
ROLE = Namespace("http://ahcm/rol/")
AHCMO = Namespace("http://ahcm/ontology/")
BIO = Namespace("http://purl.org/vocab/bio/0.1/")
ORG = Namespace("http://www.w3.org/ns/org#")
PROV = Namespace("http://www.w3.org/ns/prov#")
SCHEMA = Namespace("http://schema.org/")
VIVO = Namespace("http://vivoweb.org/ontology/core#")
BIBFRAME = Namespace("http://id.loc.gov/ontologies/bibframe/")


def read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(io.StringIO(text)))


def values(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, tuple)):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (ValueError, SyntaxError):
            pass
    # Separate linked values only at a comma following a URL. Names and
    # places containing commas remain intact.
    return re.split(r"(?<=\S)\s*,\s+(?=[^,]+:\s*https?://)", text) if "http" in text else [text]


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "recurso"


def external_value(graph: Graph, value: str, kind: str) -> URIRef | Literal:
    match = re.match(r"^(.+?):\s*(https?://\S+)$", value)
    if not match:
        return Literal(value, lang="es")
    label, url = match.groups()
    uri = URIRef(url.rstrip(".,;"))
    graph.add((uri, RDFS.label, Literal(label.strip(), lang="es")))
    graph.add((uri, AHCMO.sourceType, Literal(kind, lang="es")))
    return uri


def uri_or_literal(value: str) -> URIRef | Literal:
    match = re.search(r"https?://[^\s]+", value)
    if match:
        return URIRef(match.group(0).rstrip(".,;"))
    return Literal(value, lang="es")


def add_literal_or_uri(graph: Graph, subject: URIRef, predicate: URIRef, value: str, kind: str) -> None:
    graph.add((subject, predicate, external_value(graph, value, kind)))


def build_graph() -> Graph:
    graph = Graph()
    for prefix, namespace in {
        "ahcm": AHCM,
        "ahcmo": AHCMO,
        "person": PERSON,
        "work": WORK,
        "foaf": FOAF,
        "bio": BIO,
        "org": ORG,
        "prov": PROV,
        "schema": SCHEMA,
        "vivo": VIVO,
        "bf": BIBFRAME,
        "skos": SKOS,
        "xsd": XSD,
    }.items():
        graph.bind(prefix, namespace)

    column_map = {
        "Nombre firma": (BIO.NameChange, "nombre alternativo"),
        "Abreviatura": (SCHEMA.alternateName, "abreviatura"),
        "Nombre completo": (FOAF.name, "nombre"),
        "Rol principal": (AHCMO.primaryRole, "rol"),
        "Rol adquirido": (AHCMO.acquiredRole, "rol"),
        "Género": (FOAF.gender, "genero"),
        "Comunidad": (AHCMO.community, "comunidad"),
        "Subcomunidad": (AHCMO.subcommunity, "subcomunidad"),
        "Lugar de nacimiento": (BIO.birthPlace, "lugar"),
        "Lugar de muerte": (BIO.deathPlace, "lugar"),
        "Formación": (VIVO.educationalTraining, "institucion"),
        "Profesión": (SCHEMA.hasOccupation, "profesion"),
        "Grado": (BIO.degree, "grado"),
        "Adscripción": (ORG.memberOf, "institucion"),
        "Cargo": (SCHEMA.jobTitle, "cargo"),
        "Afiliación": (SCHEMA.affiliation, "institucion"),
        "Reconocido": (VIVO.awardOrHonor, "reconocimiento"),
        "Movilidad": (VIVO.geographicFocus, "movilidad"),
        "Linaje científico": (VIVO.advisorIn, "persona"),
        "Linaje descendiente": (VIVO.adviseeIn, "persona"),
        "Epónimo recibido": (SKOS.altLabel, "eponimo"),
        "Otorgado por": (PROV.wasAttributedTo, "persona"),
        "Epónimo asignado": (AHCMO.assignedEponym, "eponimo"),
        "Otorgado a": (AHCMO.awardedTo, "persona"),
        "Aportación / Descubrimiento": (FOAF.made, "aportacion"),
        "Notas": (RDFS.comment, "nota"),
    }

    people = {}
    prosopographic = read_csv(PROSOPOGRAPHIC_CSV)
    for row in prosopographic:
        raw_name = (row.get("Autor normalizado") or "").strip()
        if not raw_name:
            continue
        person_id = slug(raw_name.split(":", 1)[0])
        person = PERSON[person_id]
        for alias in [raw_name.split(":", 1)[0], *values(row.get("Nombre completo")), *values(row.get("Nombre firma"))]:
            people.setdefault(slug(alias.split(":", 1)[0]), set()).add(person)
        graph.add((person, RDF.type, FOAF.Person))
        graph.add((person, RDFS.label, Literal(raw_name.split(":", 1)[0].strip(), lang="es")))
        graph.add((person, AHCMO.identifier, Literal(person_id)))

        for name_value in [raw_name.split(":", 1)[0].strip(), *values(row.get("Nombre completo"))]:
            if name_value:
                graph.add((person, FOAF.name, Literal(name_value, lang="es")))
        name_link = re.match(r"^(.+?):\s*(https?://\S+)$", raw_name)
        if name_link:
            graph.add((person, AHCMO.externalLink, URIRef(name_link.group(2).rstrip(".,;"))))

        for column, (predicate, kind) in column_map.items():
            for item in values(row.get(column)):
                if kind == "lugar":
                    target = PLACE[slug(item)]
                    graph.add((target, RDF.type, AHCMO.Place))
                    graph.add((target, RDFS.label, Literal(item, lang="es")))
                    graph.add((person, predicate, target))
                elif kind == "institucion":
                    target = INSTITUTION[slug(item)]
                    graph.add((target, RDF.type, ORG.Organization))
                    graph.add((target, RDFS.label, Literal(item, lang="es")))
                    graph.add((person, predicate, target))
                elif kind == "rol":
                    target = ROLE[slug(item)]
                    graph.add((target, RDF.type, AHCMO.Role))
                    graph.add((target, RDFS.label, Literal(item, lang="es")))
                    graph.add((person, predicate, target))
                else:
                    add_literal_or_uri(graph, person, predicate, item, kind)

        for column, predicate in (("Año de nacimiento", BIO.birth), ("Año de muerte", BIO.death)):
            for item in values(row.get(column)):
                try:
                    graph.add((person, predicate, Literal(int(float(item)), datatype=XSD.gYear)))
                except ValueError:
                    graph.add((person, predicate, Literal(item, lang="es")))

        for index, title in enumerate(values(row.get("Trabajo")), start=1):
            work = WORK[f"{person_id}-{index}"]
            graph.add((work, RDF.type, BIBFRAME.Work))
            graph.add((work, BIBFRAME.title, Literal(title, lang="es")))
            graph.add((work, BIBFRAME.creator, person))
            graph.add((person, FOAF.made, work))

    if BIBLIOGRAPHIC_CSV.exists():
        bibliographic = read_csv(BIBLIOGRAPHIC_CSV)
        for index, row in enumerate(bibliographic):
            title_values = values(row.get("Titulo"))
            if not title_values:
                continue
            work = WORK[f"bibliografica-{index + 1}"]
            graph.add((work, RDF.type, BIBFRAME.Work))
            graph.add((work, BIBFRAME.title, Literal(title_values[0], lang="es")))
            creator = (row.get("Autor") or "").strip()
            if creator:
                candidates = people.get(slug(creator), set())
                if len(candidates) == 1:
                    person = next(iter(candidates))
                    graph.add((work, BIBFRAME.creator, person))
                    graph.add((person, FOAF.made, work))
                else:
                    graph.add((work, BIBFRAME.creator, Literal(creator, lang="es")))
            for source_column, predicate in (("Año de publicación", BIBFRAME.publicationDate), ("Idioma", BIBFRAME.language), ("Tipo de documento", BIBFRAME.genreForm), ("URL", BIBFRAME.electronicLocator), ("DOI", BIBFRAME.identifier)):
                for item in values(row.get(source_column)):
                    if item and item != "nan":
                        graph.add((work, predicate, uri_or_literal(item)))

    return graph


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    graph = build_graph()
    graph.serialize(destination=OUTPUT, format="turtle", encoding="utf-8")
    print(f"RDF generado: {OUTPUT}")
    print(f"Triples: {len(graph)}")


if __name__ == "__main__":
    main()
