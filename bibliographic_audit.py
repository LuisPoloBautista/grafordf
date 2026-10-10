"""Audit every source cell independently of Turtle/ontology validation."""
import json
import re
from collections import Counter
from rdflib import Literal, RDF, URIRef
from rdf_pipeline import read_csv, BIBLIOGRAPHIC_CSV, slug, ROOT
from ontology import BIBFRAME as BF, AHCMO
from bibliographic_normalization import missing, doi, isbn, urls, LANGUAGES, normalized_genre


def audit(graph):
    rows = read_csv(BIBLIOGRAPHIC_CSV)
    issues, losses, empty = [], [], Counter()
    for index, row in enumerate(rows, 2):
        source = URIRef(f'http://ahcm/fuente/bibliografia/fila-{index}')
        for column, value in row.items():
            if (source, AHCMO['original-' + slug(column)], Literal(value or '')) not in graph:
                losses.append({'row': index, 'column': column})
            if missing(value or ''):
                empty[column] += 1
                continue
            reason = None
            if column == 'DOI' and not doi(value):
                reason = 'Not a syntactically recognized DOI; preserved locally'
            elif column == 'ISBN' and not isbn(value):
                reason = 'ISBN structure/checksum not valid; preserved locally'
            elif column == 'Idioma' and slug(value) not in LANGUAGES:
                reason = 'No verified language equivalence; local resource'
            elif column == 'Año de publicación' and not re.fullmatch(r'\d{4}(?:-\d{4})?', value.strip()):
                reason = 'Uninterpreted date; preserved locally'
            elif column == 'URL' and not urls(value):
                reason = 'No recognizable HTTP URL; preserved locally'
            elif column == 'No páginas' and not (value.strip().isdigit() and int(value) > 0):
                reason = 'Uninterpreted extent; preserved locally'
            if reason:
                issues.append({'row': index, 'column': column, 'original': value, 'reason': reason})
    return {'source': str(BIBLIOGRAPHIC_CSV.relative_to(ROOT)), 'rows': len(rows),
            'original_cells': sum(len(row) for row in rows), 'lost_cells': losses,
            'missing_or_placeholder_by_column': dict(empty),
            'issues_requiring_catalog_review': issues,
            'review_counts': dict(Counter(i['column'] for i in issues)),
            'language_values': dict(Counter(row['Idioma'] for row in rows)),
            'document_type_normalization': {value: normalized_genre(value) for value in sorted({r['Tipo de documento'] for r in rows}) if not missing(value)},
            'entities': {name: len(set(graph.subjects(RDF.type, BF[name])))
                         for name in ('Work', 'Instance', 'Item', 'Contribution', 'Language', 'Doi', 'Isbn')},
            'limits': 'Identifier syntax/checksum is not registration verification. Missing cells are not errors. Local subjects/genres have no asserted external authority equivalence.'}


if __name__ == '__main__':
    from rdf_pipeline import build_graph
    result = audit(build_graph())
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'bibliographic-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'issues_requiring_catalog_review'}))
    if result['lost_cells']:
        raise SystemExit(1)
