# Perfil RDF del catálogo

El mapeo ejecutable está en `ontology.py`: `ACTOR_FIELDS` define las columnas
prosopográficas y `BIBLIOGRAPHIC_FIELDS` los metadatos bibliográficos estructurados.
`actors.py` aplica el primer mapeo y `bibliography.py` crea obras, ediciones,
títulos, contribuciones, fechas e identificadores. `/api/vocabulario` expone
las correspondencias y las etiquetas utilizadas por la interfaz.

## Autoridades

| Columna | Propiedad o recorrido | Criterio |
| --- | --- | --- |
| Autor normalizado | `rdfs:label`; enlaces externos en `rdfs:seeAlso` | Nombre visible e identificadores documentales; no se afirma identidad con una página web mediante `owl:sameAs`. |
| Nombre completo | `foaf:name` | Nombre literal. |
| Nombre firma | `ahcmo:signatureName`, subpropiedad de `schema:alternateName` | Conserva la distinción entre firma y abreviatura. `bio:NameChange` es una clase de evento, no una propiedad de nombre. |
| Abreviatura | `schema:alternateName` | Variante del nombre. |
| Género | `schema:gender` | Texto original. |
| Rol principal / adquirido | `ahcmo:primaryRole` / `ahcmo:acquiredRole`, subpropiedades de `schema:hasOccupation` | Recursos `schema:Occupation`; conserva el matiz de la fuente sin inventar una relación `org:role` directa entre persona y ocupación. |
| Profesión | `schema:hasOccupation` | Ocupación compartida. |
| Comunidad / Subcomunidad | `ahcmo:community` / `ahcmo:subcommunity`, subpropiedades de `schema:knowsAbout` | La fuente contiene disciplinas y temas, no necesariamente organizaciones con membresía. |
| Formación | `schema:alumniOf` | Institución donde se formó; no un nodo `vivo:EducationalTraining` confundido con una institución. |
| Adscripción | `org:memberOf` | Pertenencia a una organización. |
| Afiliación | `schema:affiliation` | Afiliación institucional. |
| Cargo | `schema:jobTitle` | Denominación del cargo, sin inventar un puesto institucional fechado. |
| Lugar de nacimiento / muerte | `schema:birthPlace` / `schema:deathPlace` | Recurso de lugar. |
| Año de nacimiento / muerte | `bio:birth` / `bio:death` → `bio:date` | Eventos `bio:Birth` y `bio:Death`; valor `xsd:gYear`, sin inventar día y mes. La vista los presenta como Año de nacimiento / muerte. |
| Notas | `dcterms:description` | Descripción documental de la entidad, no comentario sobre el esquema. |
| Aportación / Descubrimiento; Trabajo | `foaf:made` | Aportación o publicación relacionada. Las obras bibliográficas son `bf:Work`. |
| Grado | `ahcmo:academicStatus` | La columna mezcla grados y rangos, como «catedrático»: no se convierte todo en una credencial académica. |
| Reconocido | `ahcmo:recognition` | Mezcla instituciones y reconocimientos: no se inventa un premio para cada valor. |
| Movilidad | `ahcmo:mobility` | Lugar de movilidad documentada, sin inferir residencia permanente. |
| Linaje científico / descendiente | `ahcmo:scientificPredecessor` / `ahcmo:scientificSuccessor` | No se afirma una tutoría doctoral que el CSV no acredita. |
| Epónimo recibido / asignado | `ahcmo:receivedEponym` / `ahcmo:assignedEponym` | Epónimos, no etiquetas alternativas de la persona. |
| Otorgado por / a | `ahcmo:eponymGivenBy` / `ahcmo:eponymGivenTo` | Conserva el sentido del bloque de epónimos, sin usar procedencia como si fuera una concesión. |

`schema:` utiliza el espacio `https://schema.org/`. Los términos locales se
declaran como propiedades y las especializaciones compatibles tienen
`rdfs:subPropertyOf`. No se fuerza una equivalencia cuando cambia el significado.
Las instituciones, lugares y conceptos sin enlace externo reciben una URI local
estable. Una variante sin URI reutiliza una autoridad externa del mismo tipo y
nombre normalizado solo cuando esa correspondencia es única.

## Bibliografía

El perfil actualizado, sus excepciones y la auditoría de todas las filas están
en [auditoria-bibframe.md](auditoria-bibframe.md). La transformación se implementa
en `bibliography.py`; los identificadores, idiomas y tipos documentales se
normalizan en `bibliographic_normalization.py`.

## Etiquetas y proyección visual

`rdfs:label` procede de RDF Schema y sirve para nombrar un recurso. Se conserva
en la descarga RDF, pero no genera una arista ni un segundo círculo con el mismo
nombre. `ahcmo:sourceType` era un dato auxiliar añadido por el programa anterior;
se ha eliminado del RDF. Los tipos se expresan con `rdf:type`.

`catalog_graph.py` produce una vista semántica a partir del RDF. No dibuja
clases, etiquetas, procedencia ni nodos auxiliares de títulos, fechas o
contribuciones. Conserva las relaciones de los actores con sus metadatos y publicaciones.
Las publicaciones aparecen únicamente como nodos con su título; sus metadatos
bibliográficos no se dibujan. Las ediciones siguen separadas en RDF y en la ficha. Esto no modifica la descarga RDF.

Dos actores conectados al mismo metadato o publicación comparten el mismo nodo:
no se crea una arista de colaboración que la fuente no haya documentado. Pulsar
un metadato de actor abre los registros que lo utilizan; el doble clic hace lo mismo en
PyVis. Los enlaces externos conservan un acceso separado mediante ↗.

El tamaño de los nodos se escala linealmente con su grado (vecinos distintos en
el grafo completo), dentro de un rango legible de 7–42 píxeles. El grosor de las
aristas se escala con el número de relaciones de origen agrupadas (predicados
o ediciones distintos), en un rango de 1–8 píxeles. Los valores se indican al
pasar el cursor. Actores: verde; publicaciones: naranja; metadatos: violeta.

## Coincidencia de títulos y búsqueda

1. Coincidencia exacta normalizando acentos, puntuación y espacios.
2. Separación de listas mediante títulos conocidos del catálogo, eligiendo el
   segmento más largo para conservar comas internas. Se conservan los fragmentos
   restantes y no se descartan títulos que no se reconocen.
3. Prefijo único de cinco palabras o más; también abreviaciones explícitas con
   puntos suspensivos, de al menos tres palabras y veinte caracteres.
4. Variante ortográfica con similitud de al menos 0,94, proporción de longitudes
   entre 0,85 y 1,18 y margen de 0,05 frente al segundo candidato.

El criterio, el título original y la puntuación se guardan en la contribución
RDF; la puntuación es una heurística, no una probabilidad. Los casos ambiguos
conservan una obra sin edición reconciliada. La identidad de obra combina título, autores e idioma normalizados.
Los títulos homónimos con autoría o idioma diferentes no se fusionan. Esta
heurística no sustituye la revisión catalográfica.

La búsqueda indexa nombres/títulos y metadatos propios del registro mediante
n-gramas invertidos de 1–3 caracteres. No propaga el título de una obra al
documento de búsqueda de su autor. `/api/buscar` devuelve actores y publicaciones;
permite filtrar por tipo. `/api/metadatos` consulta el índice inverso de relaciones
de la proyección, con paginación.

## Referencias de los vocabularios

- [RDF Schema: rdfs:label](https://www.w3.org/TR/rdf-schema/#ch_label).
- [Schema.org: alumniOf](https://schema.org/alumniOf), [hasOccupation](https://schema.org/hasOccupation).
- [ORG: pertenencia y organizaciones](https://www.w3.org/TR/vocab-org/).
- [BIO: eventos biográficos](https://vocab.org/bio/).
- [Dublin Core: description](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/terms/description/).
- [BIBFRAME 2: agentes y roles](https://www.loc.gov/bibframe/docs/pdf/bf2-roles-march2017.pdf).

Las etiquetas conservan tamaño fijo: nodos 12 px y aristas 9 px. Los enlaces
a Wikidata y la navegación a metadatos compartidos coexisten en la ficha del
actor. La ficha bibliográfica no tiene navegación por metadatos compartidos.
