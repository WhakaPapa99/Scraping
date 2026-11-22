# Scraping de libros con BeautifulSoup y Streamlit

Proyecto educativo para extraer el catálogo de [Books to Scrape](https://books.toscrape.com/), guardar los datos en CSV y explorarlos en un dashboard.

## Requisitos

- Python 3.10 o posterior.
- Conexión a Internet al ejecutar el scraper.

## Instalación

Desde esta carpeta, crea y activa un entorno virtual e instala las dependencias:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 1. Extraer los datos

El scraper usa Books to Scrape por defecto, así que no necesitas indicar una URL para la práctica:

```powershell
python scraper.py
```

El programa empieza en la portada, obtiene los enlaces de categorías y recorre la paginación de cada categoría. Guarda el resultado en `data/books.csv`. La URL se puede especificar explícitamente con `--base-url`:

```powershell
python scraper.py --base-url "https://books.toscrape.com/"
```

`--base-url` debe ser la portada de un sitio con una estructura compatible: enlaces de categorías en el menú y listados de libros con paginación. No se debe pasar la URL de una ficha de libro ni de una categoría individual, porque el scraper necesita la portada para descubrir las categorías.

### Opciones del scraper

| Opción | Valor predeterminado | Descripción |
|---|---|---|
| `--base-url URL` | `https://books.toscrape.com/` | Portada del sitio que se va a recorrer. |
| `--output RUTA` | `data/books.csv` | Ubicación del CSV de salida. |
| `--delay SEGUNDOS` | `1.0` | Pausa mínima entre peticiones. |
| `--max-categories N` | Sin límite | Limita la cantidad de categorías, útil para una prueba rápida. |

Por ejemplo, para procesar solo las primeras tres categorías y guardar el CSV en otra ubicación:

```powershell
python scraper.py --max-categories 3 --output "data/prueba.csv"
```

Sin `--max-categories`, se recorren todas las categorías descubiertas desde la portada. Por defecto se espera un segundo entre peticiones; para cambiar esa pausa:

```powershell
python scraper.py --delay 1.5
```

El programa consulta `robots.txt` antes de extraer contenido. Si devuelve 404, informa de que el sitio no publica reglas en esa ruta y continúa, dado que Books to Scrape se presenta como sitio de demostración para practicar scraping. Si hay un error de servidor o de red, detiene la ejecución. Las solicitudes incluyen un `User-Agent` identificable y una pausa configurable.

## 2. Abrir el dashboard

Después de generar el CSV:

```powershell
streamlit run app.py
```

El dashboard permite filtrar por categoría, puntuación y precio, consultar la tabla de resultados y comparar precios y valoraciones mediante gráficos.

## Estructura del proyecto

```text
scraping/
├── app.py              # Dashboard de Streamlit
├── scraper.py          # Extracción con Requests y BeautifulSoup
├── requirements.txt    # Dependencias de Python
└── data/
    └── books.csv       # Se genera al ejecutar el scraper
```

## Columnas del CSV

| Columna | Contenido |
|---|---|
| `title` | Título del libro. |
| `category` | Categoría de la que se obtuvo el libro. |
| `price_gbp` | Precio numérico en libras esterlinas. |
| `rating_stars` | Valoración numérica de una a cinco estrellas. |
| `book_url` | Enlace a la ficha del libro. |
| `cover_url` | Enlace a la imagen de portada. |
| `scraped_at_utc` | Fecha y hora UTC de extracción. |

Los precios y las puntuaciones del sitio son aleatorios y solo sirven para practicar; no representan precios ni valoraciones comerciales reales.
