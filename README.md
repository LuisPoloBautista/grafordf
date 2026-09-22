# Grafo prosopográfico AHCM

Aplicación para consultar las personas, publicaciones y relaciones del Archivo Histórico de Ciencias de México. Un único proceso de Python sirve la API, la interfaz y el grafo RDF construido desde los CSV locales.

No requiere Fuseki, Java, Node.js, bases de datos, claves de API, fuentes remotas ni servicios externos durante su ejecución. La interfaz usa HTML, CSS y JavaScript nativos del navegador. Las dependencias Python se instalan una sola vez; después se puede trabajar localmente sin internet. Los enlaces de las fuentes son opcionales y solo se abren al pulsarlos.

## Ejecutar localmente

Requiere Python 3.12.

```sh
python -m venv .venv
```

Activar el entorno en Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

En Linux/macOS:

```sh
source .venv/bin/activate
```

Instalar y arrancar:

```sh
python -m pip install -r requirements.txt
python app.py
```

Abrir http://localhost:8000. Para desarrollo con recarga automática: `python -m uvicorn app:app --reload`.

## Funciones

- Catálogo paginado y búsqueda por nombre, firma o abreviatura, sin distinguir mayúsculas ni acentos.
- Fichas con atributos, publicaciones y enlaces a las fuentes.
- Vista SVG de hasta 16 relaciones por persona, acompañada de la lista completa.
- Descarga del grafo completo en Turtle desde la interfaz.
- Errores de conexión visibles y protección contra respuestas de búsquedas anteriores.

## Datos y criterios

`comunidades.csv` contiene los datos prosopográficos; `tesis raquel/bibliografica.csv` contiene los bibliográficos. Ambos deben incluirse en GitHub. El lector acepta UTF-8 y los CSV originales con codificación Windows-1252.

El servidor reconstruye el grafo en memoria al arrancar: después de editar un CSV, reiniciar el servidor o desplegar de nuevo. No necesita disco persistente ni depende de `data/grafo.ttl`. Para generar un archivo local de manera opcional: `python rdf_pipeline.py`.

Los autores bibliográficos se enlazan automáticamente cuando su nombre coincide, sin acentos ni puntuación, con un único nombre o firma registrado. Los demás se conservan como texto; no se asignan por semejanza para evitar atribuciones incorrectas. Los registros bibliográficos y las obras de la columna Trabajo se conservan como registros separados, sin deduplicación automática. Las cifras de publicaciones cuentan estos registros, no necesariamente obras únicas. La aplicación muestra las comunidades declaradas en los datos; no calcula agrupaciones estadísticas.

## Desplegar en Render

El repositorio contiene `render.yaml`. En Render, crea un **Blueprint**, conecta el repositorio y revisa y aplica la configuración del servicio.

Alternativamente, crea un **Web Service** con estos valores:

| Campo | Valor |
| --- | --- |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Variable `PYTHON_VERSION` | `3.12.10` |

Selecciona en Render el plan que quieras utilizar. No hace falta añadir una base de datos ni un disco persistente. El despliegue real requiere conectar tu cuenta y repositorio; no se ha realizado desde esta carpeta.

Referencias oficiales: [FastAPI en Render](https://render.com/docs/deploy-fastapi), [Blueprints](https://render.com/docs/blueprint-spec) y [comprobaciones de salud](https://render.com/docs/health-checks).

## API

| Ruta | Resultado |
| --- | --- |
| `/health` | Estado del servidor |
| `/api/stats` | Recuento de personas, publicaciones y triples |
| `/api/personas?q=jose&limit=20&offset=0` | Búsqueda paginada; límite máximo 100 |
| `/api/personas/jose-de-acosta` | Ficha individual |
| `/api/personas/jose-de-acosta/relaciones` | Relaciones de la persona |
| `/api/grafo.ttl` | Descarga RDF |
| `/openapi.json` | Esquema de la API |

Las páginas Swagger y ReDoc están desactivadas porque por defecto descargan recursos externos.

## Verificar

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Las pruebas cubren el arranque sin conexiones salientes, archivos estáticos, búsqueda, paginación, las 110 fichas, respuestas de error, valores ausentes, caracteres y exportación RDF. No requieren servidores adicionales.

Los scripts, HTML y RDF antiguos se conservan localmente como material de investigación y están excluidos del repositorio preparado; no forman parte de la aplicación ni se ejecutan al arrancar.
