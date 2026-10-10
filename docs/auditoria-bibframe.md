# Perfil bibliográfico BIBFRAME 2.0

Revisión del 10 de octubre de 2026. Fuente: `dataset/bibliografica.csv`,
1.479 registros y 20 columnas. `bibliographic_audit.py` comprueba las 29.580
celdas contra el RDF: ninguna perdida. Las celdas vacías y los marcadores de
ausencia se conservan como originales, pero no generan afirmaciones descriptivas.

## Revisión y correcciones

El informe previo `reports/bibframe-before.json` registra 2.367 problemas de
rango y 1.034 de dominio del perfil anterior. Entre ellos, enlaces colocados
en Instance mediante `bf:electronicLocator`, cuyo dominio es Item, y recursos
sin tipos explícitos compatibles con los rangos de BIBFRAME.

El modelo nuevo usa los términos de la ontología oficial incluida en
`vocab/bibframe.rdf`, versión 2.0.1 de BIBFRAME 2.0. No sustituye propiedades
locales por equivalencias externas no acreditadas.

| Fuente | Modelo y criterio |
| --- | --- |
| Titulo | Work → `bf:title` → Title → `bf:mainTitle`; la Instance referencia ese título |
| Autor | Work → Contribution → Agent, rol MARC `aut`; Person solo para actores identificados como personas; anonimato conservado localmente |
| Idioma | Work → Language, URI LC y `bf:code` según los códigos MARC verificados |
| Referentes; Área temática/campo | Work → `bf:subject` → Topic local; separación por `;`, sin atribuir autoridades externas |
| Tipo de documento | Work → GenreForm local; se normalizan variantes ortográficas; fuentes secundarias/terciarias quedan como clasificación local |
| Año de publicación | Instance → Publication → `bf:date`; año exacto como `xsd:gYear`, intervalos como literal; otros valores locales |
| No páginas | Instance → Extent para cantidades positivas; valores no interpretables se conservan locales |
| Edición; Notas | `bf:editionStatement`; `bf:note` → Note |
| Volumen, Tomo, Número | `bf:part` como enunciado literal, sin inventar una obra contenedora |
| DOI; ISBN | `bf:identifiedBy` → Doi/Isbn → `rdf:value`; DOI con estructura reconocida e ISBN con dígito de control válido |
| Página inicial/final; No referencias; PDF sí/no | Propiedades locales descriptivas |
| URL; enlaces en DOI/PDF | Se conservan como enlaces; `rdfs:seeAlso` en Instance salvo ejemplar identificable |

Las 23 celdas DOI no reconocidas incluyen enlaces a repositorios y referencias
que no son DOI. Cinco ISBN no cumplen estructura o control (incluyen años y
notación científica). Se conservan en propiedades locales «original sin validar».
La validación de formato no demuestra el registro ni la pertenencia de un
identificador a una publicación. No se corrigen contenidos por conjetura.
También se señalan 35 celdas URL sin un enlace HTTP reconocible y una extensión
no interpretable como cantidad positiva. Todas permanecen en el RDF local y
en las celdas originales; el informe distingue estas incidencias de la ausencia.

## Obra, instancia y ejemplar

La identidad local de Work combina título, autores e idioma normalizados.
Esto evita fusionar automáticamente títulos homónimos con autoría diferente.
La misma combinación puede agrupar varias filas como instancias separadas;
no prueba por sí sola su identidad intelectual y admite revisión catalográfica.
Cada fila titulada genera una Instance con `bf:instanceOf` y su inversa
`bf:hasInstance`. No se inventan editoriales, fechas, materias o ISBN.

Solo se crea Item cuando una monografía enlaza explícitamente a un identificador
BHL `/item/N` y ese ejemplar no está atribuido a varias filas. Se conecta con
`bf:itemOf`/`bf:hasItem`; `bf:electronicLocator` conserva el enlace original.
Un enlace a título, catálogo, página o volumen contenedor de un artículo no
basta para generar un Item. La evidencia procede del identificador en la fuente;
no se afirma haber cotejado el contenido digital de cada ejemplar. Los demás
enlaces siguen accesibles mediante `rdfs:seeAlso`. Se conservan los puntos y
coma internos de las URL de HathiTrust.

## Procedencia y vocabulario local

Cada fila tiene una entidad `prov:Entity`, `prov:wasDerivedFrom` al archivo,
número de fila CSV (incluida la cabecera) y 20 propiedades `ahcmo:original-*`
con el contenido literal exacto, incluidos vacíos. El archivo lleva SHA-256.
`ahcmo:describes` relaciona la fila con la instancia. Las instancias mantienen
sus identificadores anteriores; `ahcmo:previousIdentifier` conserva el antiguo
identificador de obra basado solo en título, sin afirmar `owl:sameAs`.

`ahcmo:bibliografia-*` conserva datos descriptivos sin transformación segura
y distingue columnas de referentes y área en la ficha. Tanto esas propiedades
como `ahcmo:original-*` se declaran `rdf:Property` y llevan como etiqueta la
columna original. `sourceFile`, `sourceRow` y `sha256` describen procedencia;
`matchMethod`, `matchScore` y `originalTitle` documentan la reconciliación de
títulos de actores. El score es heurístico, no una probabilidad.

## Validación reproducible y límites

`python bibframe_quality.py` genera `reports/rdf-validation.json`:

- Sintaxis: serialización Turtle y lectura RDFLib, comparación de grafos isomorfos.
- Semántica: términos BIBFRAME existentes, propiedades obsoletas, recursos frente
  a literales, dominios/rangos explícitos con jerarquía de subclases y relaciones
  Work/Instance/Item, contribuciones y títulos del perfil local.

`python bibliographic_audit.py` genera `reports/bibliographic-audit.json`:
conservación de cada celda, recuentos de ausencia, entidades y valores que requieren
revisión con su número de fila. La auditoría inicial produce 1.478 Work, 1.479
Instance, 82 Item, 104 Doi y 1 Isbn. Las obras incluyen los títulos aportados
por actores que no tienen instancia reconciliada.

La sintaxis y la semántica se verifican por separado. El validador no es un
razonador OWL completo ni certifica la exactitud histórica de los registros.
La salida es Turtle estándar para RDFLib, Jena y repositorios SPARQL; en este
entorno se ha probado con RDFLib, no con una instalación de Jena.

## Referencias oficiales

- [Modelo BIBFRAME 2.0](https://www.loc.gov/bibframe/docs/bibframe2-model.html).
- [Ontología oficial LC](https://github.com/lcnetdev/bibframe-ontology).
- [Códigos MARC de idiomas](https://www.loc.gov/marc/languages/language_name.html).
- [Correspondencias ISO 639-2](https://www.loc.gov/standards/iso639-2/php/code_list2.php).
- [Roles BIBFRAME](https://www.loc.gov/bibframe/docs/pdf/bf2-roles-march2017.pdf).

Los códigos usados son spa, lat, fre, eng, ger, ita, dan, swe, dut, nor, por
y rum. Holandés y neerlandés comparten dut. El idioma desconocido usa recurso
local. Las materias, géneros y agentes sin autoridad acreditada mantienen URI
local; no se fabrican equivalencias con autoridades externas.
