"""Conservative normalization; original cells are stored separately and verbatim."""
import re
from urllib.parse import urlsplit
from rdf_pipeline import slug

LANGUAGES = {
    'espanol': ('spa', 'Español'), 'latin': ('lat', 'Latín'), 'frances': ('fre', 'Francés'),
    'ingles': ('eng', 'Inglés'), 'aleman': ('ger', 'Alemán'), 'italiano': ('ita', 'Italiano'),
    'danes': ('dan', 'Danés'), 'sueco': ('swe', 'Sueco'), 'holandes': ('dut', 'Neerlandés'),
    'neerlandes': ('dut', 'Neerlandés'), 'noruego': ('nor', 'Noruego'),
    'portugues': ('por', 'Portugués'), 'rumano': ('rum', 'Rumano'),
}
GENRES = {'monografia': 'Monografía', 'monografria': 'Monografía',
          'articulo': 'Artículo', 'cartas': 'Carta', 'notas': 'Nota', 'noticias': 'Noticia'}
MISSING = {'', '-', '--', 'nan'}


def missing(text):
    return text.strip().lower() in MISSING


def urls(text):
    # Semicolons are valid in HathiTrust URLs; do not split them.
    return re.findall(r'https?://[^\s<>"{}|\\^`]+', text)


def doi(text):
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)', '', text.strip(), flags=re.I)
    return value if re.fullmatch(r'10\.\d{4,9}/[^\s]+', value) else None


def isbn(text):
    value = re.sub(r'[-\s]', '', text).upper()
    if re.fullmatch(r'\d{9}[\dX]', value):
        return value if sum((10 - i) * (10 if c == 'X' else int(c)) for i, c in enumerate(value)) % 11 == 0 else None
    if re.fullmatch(r'97[89]\d{10}', value):
        return value if sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0 else None
    return None


def normalized_genre(text):
    return GENRES.get(slug(text), text.strip().capitalize())


def bhl_copy(text, genre):
    """Only an explicit BHL item for a monograph identifies a candidate whole copy.

    Article links can point to a host volume and are NOT treated as copies of the
    article. A bibliography/title URI is NOT an item. Conflicting instances are
    handled by the caller.
    """
    parts = urlsplit(text)
    if normalized_genre(genre) == 'Monografía' and parts.hostname in ('www.biodiversitylibrary.org', 'biodiversitylibrary.org'):
        match = re.fullmatch(r'/item/(\d+)/?', parts.path)
        if match:
            return 'https://www.biodiversitylibrary.org/item/' + match[1]
    return None
