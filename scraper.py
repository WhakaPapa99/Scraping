from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import Session


DEFAULT_BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "MonlauBooksScraper/1.0 (educational project)"
STAR_VALUES = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
CSV_COLUMNS = [
    "title",
    "category",
    "price_gbp",
    "rating_stars",
    "book_url",
    "cover_url",
    "scraped_at_utc",
]


class ScrapeError(RuntimeError):
    """Error legible para el usuario durante la extracción."""


def parse_price(value: str) -> float:
    """Convierte un precio con símbolo de moneda a un número en libras."""
    normalized = re.sub(r"[^\d.,]", "", value).replace(",", "")
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError) as exc:
        raise ScrapeError(f"No se pudo interpretar el precio: {value!r}") from exc


def check_robots(session: Session, base_url: str, user_agent: str) -> RobotFileParser:
    """Carga robots.txt y falla de forma cerrada ante errores 5xx o de red."""
    robots_url = urljoin(base_url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        response = session.get(robots_url, timeout=20)
    except requests.RequestException as exc:
        raise ScrapeError(f"No se pudo consultar {robots_url}: {exc}") from exc

    if response.status_code == 404:
        print(
            "Aviso: robots.txt devuelve 404; no hay reglas publicadas en esa ruta. "
            "Se continuará con pausas porque Books to Scrape es un sitio de práctica."
        )
        parser.parse([])
        return parser
    if 400 <= response.status_code < 500:
        raise ScrapeError(
            f"robots.txt respondió HTTP {response.status_code}; no se inicia el scraping."
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ScrapeError(f"Error al consultar robots.txt: {exc}") from exc

    parser.parse(response.text.splitlines())
    if not parser.can_fetch(user_agent, base_url):
        raise ScrapeError(f"robots.txt no permite acceder a {base_url} para {user_agent}.")
    return parser


def fetch_soup(
    session: Session,
    url: str,
    robots: RobotFileParser,
    user_agent: str,
    delay: float,
    last_request_at: list[float | None],
) -> BeautifulSoup:
    if not robots.can_fetch(user_agent, url):
        raise ScrapeError(f"robots.txt no permite acceder a {url}.")

    previous_request = last_request_at[0]
    if previous_request is not None:
        wait_seconds = delay - (time.monotonic() - previous_request)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapeError(f"Error al descargar {url}: {exc}") from exc
    finally:
        last_request_at[0] = time.monotonic()

    return BeautifulSoup(response.content, "html.parser")


def get_categories(home_soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    categories: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in home_soup.select("ul.nav-list ul li a"):
        label = link.get_text(" ", strip=True)
        href = link.get("href")
        if not href:
            continue
        category_url = urljoin(base_url, href)
        if category_url in seen_urls:
            continue
        seen_urls.add(category_url)
        categories.append((label, category_url))
    return categories


def extract_books(soup: BeautifulSoup, category: str, page_url: str) -> list[dict[str, object]]:
    books: list[dict[str, object]] = []
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for card in soup.select("article.product_pod"):
        title_link = card.select_one("h3 a")
        price_element = card.select_one(".price_color")
        rating_element = card.select_one(".star-rating")
        image = card.select_one(".image_container img")
        if not title_link or not price_element or not rating_element:
            continue

        title = title_link.get("title") or title_link.get_text(" ", strip=True)
        href = title_link.get("href")
        rating_class = next(
            (name for name in rating_element.get("class", []) if name in STAR_VALUES), None
        )
        if not href or rating_class is None:
            continue

        image_src = None
        if image:
            image_src = image.get("src") or image.get("data-src")

        books.append(
            {
                "title": title.strip(),
                "category": category,
                "price_gbp": parse_price(price_element.get_text(" ", strip=True)),
                "rating_stars": STAR_VALUES[rating_class],
                "book_url": urljoin(page_url, href),
                "cover_url": urljoin(page_url, image_src) if image_src else "",
                "scraped_at_utc": scraped_at,
            }
        )
    return books


def scrape_category(
    session: Session,
    category: str,
    first_page_url: str,
    robots: RobotFileParser,
    user_agent: str,
    delay: float,
    last_request_at: list[float | None],
) -> list[dict[str, object]]:
    books: list[dict[str, object]] = []
    next_url: str | None = first_page_url
    visited_pages: set[str] = set()

    while next_url and next_url not in visited_pages:
        visited_pages.add(next_url)
        soup = fetch_soup(session, next_url, robots, user_agent, delay, last_request_at)
        page_books = extract_books(soup, category, next_url)
        books.extend(page_books)
        print(f"  {category}: {len(page_books)} libros en {next_url}")

        next_link = soup.select_one("li.next a")
        next_url = urljoin(next_url, next_link.get("href")) if next_link else None

    return books


def scrape(
    base_url: str = DEFAULT_BASE_URL,
    output_path: Path | str = Path("data/books.csv"),
    delay: float = 1.0,
    max_categories: int | None = None,
) -> int:
    if delay < 0:
        raise ValueError("La pausa no puede ser negativa.")
    if max_categories is not None and max_categories < 1:
        raise ValueError("--max-categories debe ser un entero mayor que cero.")

    base_url = base_url.rstrip("/") + "/"
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL base debe comenzar con http:// o https://.")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    robots = check_robots(session, base_url, USER_AGENT)
    last_request_at: list[float | None] = [time.monotonic()]

    home = fetch_soup(session, base_url, robots, USER_AGENT, delay, last_request_at)
    categories = get_categories(home, base_url)
    if not categories:
        raise ScrapeError("No se encontraron enlaces de categorías en la portada.")
    if max_categories is not None:
        categories = categories[:max_categories]

    print(f"Se procesarán {len(categories)} categorías; pausa entre peticiones: {delay:g} s.")
    all_books: list[dict[str, object]] = []
    for category, category_url in categories:
        all_books.extend(
            scrape_category(
                session,
                category,
                category_url,
                robots,
                USER_AGENT,
                delay,
                last_request_at,
            )
        )

    # La misma ficha podría aparecer más de una vez; se conserva su primera aparición.
    dataframe = pd.DataFrame(all_books, columns=CSV_COLUMNS)
    if not dataframe.empty:
        dataframe = dataframe.drop_duplicates(subset="book_url", keep="first")
        dataframe["price_gbp"] = pd.to_numeric(dataframe["price_gbp"], errors="coerce")
        dataframe["rating_stars"] = pd.to_numeric(
            dataframe["rating_stars"], errors="coerce"
        ).astype("Int64")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Guardados {len(dataframe)} libros en {output.resolve()}")
    return len(dataframe)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae libros de Books to Scrape y crea un CSV para el dashboard."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="URL base del catálogo.")
    parser.add_argument(
        "--output", default="data/books.csv", help="Ruta del CSV de salida."
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Segundos mínimos entre solicitudes."
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=None,
        help="Límite opcional para una prueba corta (por ejemplo, 3).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        scrape(args.base_url, args.output, args.delay, args.max_categories)
    except (ScrapeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
