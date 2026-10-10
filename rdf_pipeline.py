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
BIBLIOGRAPHIC_CSV = ROOT / "dataset" / "bibliografica.csv"
OUTPUT = ROOT / "data" / "grafo.ttl"

from ontology import (AHCM, AHCMO, PERSON, WORK, PLACE, INSTITUTION, ROLE,
                      BIO, ORG, PROV, SCHEMA, VIVO, BIBFRAME, bind_profile)


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
    if 'http' in text:
        separated = re.sub(r'(https?://\S+)\s*,\s*(?=[^:]+:\s*https?://)',
                           lambda match: match[1] + '\x1f', text)
        return separated.split('\x1f')
    return [text]


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "recurso"


def external_value(graph: Graph, value: str, kind: str) -> URIRef | Literal:
    match = re.match(r"^(.+?):\s*(https?://\S+)$", value)
    if not match:
        if re.fullmatch(r"https?://\S+", value):
            return URIRef(value.rstrip(".,;"))
        return Literal(value, lang="es")
    label, url = match.groups()
    uri = URIRef(url.rstrip(".,;"))
    graph.add((uri, RDFS.label, Literal(label.strip(), lang="es")))
    return uri


def uri_or_literal(value: str) -> URIRef | Literal:
    match = re.search(r"https?://[^\s]+", value)
    if match:
        return URIRef(match.group(0).rstrip(".,;"))
    return Literal(value, lang="es")


def add_literal_or_uri(graph: Graph, subject: URIRef, predicate: URIRef, value: str, kind: str) -> None:
    graph.add((subject, predicate, external_value(graph, value, kind)))


def build_graph() -> Graph:
    from actors import add_actors
    from bibliography import add_bibliography
    graph = Graph()
    bind_profile(graph)
    rows = read_csv(PROSOPOGRAPHIC_CSV)
    add_actors(graph, rows)
    add_bibliography(graph, rows, BIBLIOGRAPHIC_CSV)
    return graph


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    graph = build_graph()
    graph.serialize(destination=OUTPUT, format="turtle", encoding="utf-8")
    print(f"RDF generado: {OUTPUT}")
    print(f"Triples: {len(graph)}")


if __name__ == "__main__":
    main()
