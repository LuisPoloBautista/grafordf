# Catálogo de autoridades de actores en el campo de la botánica XVIII

Aplicación FastAPI para explorar actores y publicaciones sobre un grafo RDF,
con fichas bibliográficas BIBFRAME y visualizaciones dinámicas PyVis.

## Ejecutar

Requiere Python 3.12.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abrir http://localhost:8000. Después de modificar los CSV o el mapeo, reiniciar
el servidor. No requiere bases de datos ni servicios externos durante el uso.

## Datos y mapeo

- `comunidades.csv`: autoridades; 110 actores.
- `dataset/bibliografica.csv`: registros bibliográficos; cada fila conserva una edición.
- `ontology.py`: correspondencia entre columnas y vocabularios, y etiquetas de interfaz.
- `actors.py`: conversión de actores, autoridades compartidas y eventos biográficos.
- `bibliography.py`: BIBFRAME y reconciliación de títulos.
- `catalog_graph.py`: proyección semántica e índice de metadatos compartidos.
- `graph_tools.py`: búsqueda indexada y representación PyVis.

La explicación de cada correspondencia, las excepciones y las referencias
oficiales están en [el perfil RDF](docs/mapeo-rdf.md).

Los CSV se convierten a RDF al arrancar. La búsqueda y las fichas se obtienen de
ese grafo. `python rdf_pipeline.py` genera `data/grafo.ttl`; `/api/grafo.ttl`
descarga el RDF completo cargado por el servidor.

`rdfs:label` da nombre a los nodos, sin dibujarse como relación. Se eliminó
`sourceType`. Los nodos estructurales de BIBFRAME se conservan en RDF y se
simplifican en la vista. Las notas usan `dcterms:description` para actores y
`bf:note` para bibliografía. `bf:agent` identifica correctamente al agente de
una contribución y se presenta como autoría.

## Consultar

La búsqueda devuelve fichas de actores y publicaciones, con filtro de tipo.
Una consulta por título devuelve la publicación, sin convertir al autor en su
resultado sustituto. El índice de n-gramas se construye sobre los nombres,
títulos y metadatos propios de cada registro. Soporta acentos y palabras en
cualquier orden. Los resultados se ordenan por coincidencia en nombre o título.

En la ficha de actor, pulsar un metadato recupera los registros asociados, con paginación. Si existe
una fuente externa se ofrece un enlace ↗ separado. Las URI locales representan
instituciones, lugares o conceptos sin identificador externo documentado.

La reconciliación bibliográfica reconoce listas de títulos respetando comas
internas, coincidencias normalizadas, abreviaciones únicas y variantes
ortográficas de alta confianza. Se conserva en RDF el título original, el
criterio y la puntuación. Las coincidencias ambiguas no se asignan. La agrupación
por título, autoría e idioma no sustituye una revisión catalográfica de obras homónimas.

## Grafo

El botón del grafo abre la proyección de actores, publicaciones y metadatos.
Los registros que comparten adscripción, formación, publicaciones u otros datos
se conectan al mismo nodo. Compartir un dato no implica colaboración histórica.

- Actores verdes, publicaciones naranjas, metadatos violetas.
- Tamaño según vecinos distintos; grosor según relaciones de origen agrupadas.
- Zoom, arrastre, búsqueda de nodo, filtro de entorno y pausa de movimiento.
- Doble clic para abrir fichas o los registros que comparten un metadato.

La vista no es un dibujo de cada triple: omite etiquetas, clases y procedencia,
y acorta los recorridos estructurales. La descarga mantiene el RDF completo.
El grafo completo inicia con la física pausada por su tamaño. Los subgrafos
incluyen publicaciones del actor y actores conectados a sus metadatos compartidos.
Los recursos de PyVis se sirven dentro del HTML, sin CDN.

## API

| Ruta | Uso |
| --- | --- |
| `/api/buscar?q=historia&kind=todos&limit=20&offset=0` | Actores y publicaciones; tipos `todos`, `actor`, `publicacion` |
| `/api/personas?q=jose` | Compatibilidad: solo actores |
| `/api/personas/{id}` | Ficha de actor |
| `/api/recursos?uri=...` | Ficha bibliográfica o descripción RDF |
| `/api/metadatos?id=...&limit=30&offset=0` | Registros que comparten un dato |
| `/api/vocabulario` | Mapeo de autoridades y etiquetas de presentación |
| `/api/personas/{id}/grafo` | Subgrafo PyVis |
| `/grafo` | Proyección completa PyVis |
| `/api/grafo.ttl` | RDF completo |
| `/api/stats` | Recuentos |
| `/health` | Salud del servidor |

## Verificar

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Prueba opcional de navegador con Playwright y Edge: iniciar el servidor en el
puerto 8011 y ejecutar `python tests/browser_check.py`. La variable
`CATALOG_TEST_URL` permite indicar otro puerto.

## Desplegar en Render

`render.yaml` instala `requirements.txt` y ejecuta
`uvicorn app:app --host 0.0.0.0 --port $PORT`. Incluir los dos CSV fuente.
No requiere disco persistente. Después de actualizar el código se debe
reiniciar o desplegar nuevamente el servicio.

## BIBFRAME 2.0 y auditoría

Las publicaciones se muestran únicamente por título en ambos grafos. Sus
metadatos completos están en la ficha bibliográfica, sin navegación a metadatos
compartidos ni repetición entre obra y edición. Las etiquetas de los grafos
mantienen tamaño fijo aunque cambie el grado.

La conversión conserva cada celda original del CSV en entidades de procedencia.
Consulta [el perfil y la auditoría](docs/auditoria-bibframe.md).

```powershell
python rdf_pipeline.py
python bibframe_quality.py
python bibliographic_audit.py
```

Los dos últimos comandos generan informes separados en `reports/`:
validación sintáctica/semántica y conservación de datos/revisión catalográfica.
La ontología oficial se incluye en `vocab/` para validar sin conexión.

### Distribución de los grafos

El subgrafo coloca al actor fijo en el origen y organiza sus vecinos en anillos
por distancia. El global excluye nodos sin conexiones: solo muestra actores y
sus atributos y títulos vinculados. Esta selección visual no elimina registros
del catálogo, de la búsqueda ni del RDF.

`graph_layout.py` calcula comunidades Louvain con pesos de las relaciones y
semilla fija, y distribuye cada grupo con Fruchterman–Reingold. Las comunidades
son agrupaciones visuales, no afirmaciones históricas añadidas al RDF. Se
mantienen los colores por tipo de nodo. Ambos grafos inician pausados para
conservar su distribución; se puede activar el movimiento, arrastrar y ampliar.
El actor central permanece fijo aun al activar el movimiento.

Referencias: [Louvain](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html)
y [distribución por fuerzas](https://networkx.org/documentation/stable/reference/generated/networkx.drawing.layout.spring_layout.html).
