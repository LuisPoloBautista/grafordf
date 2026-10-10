# Catálogo de autoridades de actores en el campo de la botánica XVIII

Aplicación FastAPI para consultar autoridades, publicaciones y metadatos desde un grafo RDF. La interfaz ofrece fichas en tablas, enlaces navegables, bibliografía BIBFRAME y grafos dinámicos PyVis.

## Ejecutar

Requiere Python 3.12.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abrir http://localhost:8000. Reiniciar el servidor después de cambiar los CSV.

## Fuentes identificadas

- `comunidades.csv`: 110 actores; es el CSV que alimentaba la búsqueda original y se mantiene como fuente de autoridades.
- `dataset/bibliografica.csv`: bibliografía. Este es el nombre real disponible; no existe `dataset/bibliográfico.csv`. Se corrigió la referencia anterior a `tesis raquel/bibliografica.csv`.
- `dataset/poso.csv` y `poso-csv.csv` no alimentan esta aplicación.

Los CSV se convierten al arrancar a un único grafo RDF en memoria. La búsqueda y las fichas se obtienen del grafo, no de consultas directas a las tablas CSV. `python rdf_pipeline.py` exporta también `data/grafo.ttl`; la descarga web corresponde al grafo cargado por el servidor.

## Bibliografía y vinculación

Se reconcilia `Trabajo` de los actores con `Titulo` del catálogo bibliográfico, normalizando acentos, espacios y puntuación. Un título abreviado de cinco palabras o más se acepta si es prefijo de un único título bibliográfico. No se aplican coincidencias difusas ni atribuciones por parecido del autor. Los títulos compuestos o ambiguos que no coinciden se conservan como obras sin edición bibliográfica y se identifican así en la ficha.

Los títulos normalizados iguales comparten una `bf:Work`; cada fila bibliográfica conserva su propia `bf:Instance`, vinculada mediante `bf:hasInstance` y `bf:instanceOf`. Esto agrupa por título, no constituye una revisión catalográfica de homónimos. La procedencia conserva archivo y número de fila. Las fechas, identificadores y enlaces permanecen asociados a cada edición.

Modelación: `bf:Title` / `bf:mainTitle`, `bf:Contribution` / `bf:agent`, `bf:Publication` / `bf:date`, `bf:Language`, `bf:GenreForm`, `bf:Topic`, `bf:Extent`, `bf:Note`, `bf:Isbn`, `bf:Doi` y `bf:electronicLocator`. Los campos sin equivalencia directa (páginas inicial/final, tomo, referentes y otros) se preservan con propiedades del espacio local `ahcmo`, sin inventar términos BIBFRAME.

La vinculación al actor queda expresada por `foaf:made` y una contribución BIBFRAME, con el criterio de coincidencia registrado en RDF. Los nombres de autor originales también se conservan.

## Búsqueda en el grafo

Al iniciar se recorren en anchura (BFS) las descripciones RDF salientes de cada actor, incluyendo sus obras, ediciones y metadatos; el recorrido se detiene ante otros actores. Se construye un índice invertido de n-gramas de 1–3 caracteres. Cada consulta intersecta las listas del índice, verifica sus términos y prioriza coincidencias en nombres. Admite palabras en distinto orden, fragmentos y consultas sin acentos. El coste de construir el índice se paga al arrancar, no en cada búsqueda. No usa PageRank, que clasifica centralidad y no sustituye la recuperación textual.

## Visualizaciones

PyVis representa cada triple como una arista dirigida; incluye también los valores literales. La ficha muestra el subgrafo del actor, sin límite de 16 relaciones ni lista redundante. El botón «Ver grafo RDF completo» abre todos los triples. Las vistas permiten arrastrar, acercar, centrar, localizar nodos y activar o pausar la física. El grafo completo inicia con la física pausada para reducir carga; visualizar decenas de miles de triples puede ser pesado en equipos modestos.

Los recursos JavaScript de PyVis se incluyen dentro del HTML. No se necesitan servicios remotos para usar la aplicación después de instalar las dependencias. Las páginas del grafo se generan a demanda y se guardan en memoria hasta reiniciar.

## API

- `/api/personas?q=historia&limit=20&offset=0`: búsqueda paginada de actores.
- `/api/personas/{id}`: ficha con metadatos y publicaciones.
- `/api/recursos?uri=...`: descripción de cualquier recurso RDF local y ediciones de una obra.
- `/api/personas/{id}/grafo`: subgrafo PyVis.
- `/grafo`: grafo PyVis completo.
- `/api/grafo.ttl`: descarga RDF Turtle.
- `/api/stats`: cifras y archivos fuente.
- `/health`: comprobación de servicio.

## Verificar

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

`render.yaml` conserva la configuración de despliegue: instalar `requirements.txt` y servir `uvicorn app:app --host 0.0.0.0 --port $PORT`. Incluir los dos CSV fuente en el repositorio. No requiere base de datos ni disco persistente.

Referencias: [modelo BIBFRAME 2](https://www.loc.gov/bibframe/docs/bibframe2-model.html), [mapeo oficial a BIBFRAME](https://www.loc.gov/standards/mods/modsrdf/mods3-7-bibframe2-0-mapping.html), [PyVis](https://pyvis.readthedocs.io/en/latest/documentation.html).
