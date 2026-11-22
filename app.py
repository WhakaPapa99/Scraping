from pathlib import Path

import pandas as pd
import streamlit as st


CSV_PATH = Path(__file__).resolve().parent / "data" / "books.csv"

st.set_page_config(page_title="Books to Scrape | Análisis", page_icon="📚", layout="wide")
st.title("📚 Catálogo Books to Scrape")
st.caption("Explora precios y valoraciones del catálogo de demostración.")

if not CSV_PATH.exists():
    st.info("Aún no existe el CSV. Primero ejecuta `python scraper.py`.")
    st.stop()

try:
    books = pd.read_csv(CSV_PATH)
except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(f"No se pudo leer el archivo {CSV_PATH}: {exc}")
    st.stop()

required_columns = {"title", "category", "price_gbp", "rating_stars", "book_url"}
missing_columns = required_columns.difference(books.columns)
if missing_columns:
    st.error("Al CSV le faltan estas columnas: " + ", ".join(sorted(missing_columns)))
    st.stop()

books["price_gbp"] = pd.to_numeric(books["price_gbp"], errors="coerce")
books["rating_stars"] = pd.to_numeric(books["rating_stars"], errors="coerce")
books = books.dropna(subset=["price_gbp", "rating_stars"])

if books.empty:
    st.warning("El CSV no contiene libros con precio y valoración válidos.")
    st.stop()

st.sidebar.header("Filtros")
categories = sorted(books["category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Categorías", categories, default=categories
)
min_rating = int(books["rating_stars"].min())
max_rating = int(books["rating_stars"].max())
if min_rating == max_rating:
    rating_range = (min_rating, max_rating)
    st.sidebar.caption(f"Todas las valoraciones son de {min_rating} estrellas.")
else:
    rating_range = st.sidebar.slider(
        "Valoración (estrellas)", min_rating, max_rating, (min_rating, max_rating)
    )
min_price = float(books["price_gbp"].min())
max_price = float(books["price_gbp"].max())
if min_price == max_price:
    price_range = (min_price, max_price)
    st.sidebar.caption(f"Todos los libros cuestan £{min_price:.2f}.")
else:
    price_range = st.sidebar.slider(
        "Precio (£)",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        step=0.5,
        format="£%.2f",
    )

filtered = books[
    books["category"].isin(selected_categories)
    & books["rating_stars"].between(rating_range[0], rating_range[1])
    & books["price_gbp"].between(price_range[0], price_range[1])
]

metric1, metric2, metric3 = st.columns(3)
metric1.metric("Libros filtrados", f"{len(filtered):,}")
metric2.metric(
    "Precio medio", f"£{filtered['price_gbp'].mean():.2f}" if not filtered.empty else "—"
)
metric3.metric(
    "Valoración media",
    f"{filtered['rating_stars'].mean():.2f} / 5" if not filtered.empty else "—",
)

if filtered.empty:
    st.warning("No hay libros que coincidan con esos filtros.")
    st.stop()

left, right = st.columns(2)
with left:
    st.subheader("Precio medio por categoría")
    category_prices = (
        filtered.groupby("category", as_index=True)["price_gbp"]
        .mean()
        .sort_values(ascending=False)
    )
    st.bar_chart(category_prices, y_label="Precio (£)")
with right:
    st.subheader("Distribución de valoraciones")
    rating_counts = (
        filtered["rating_stars"].value_counts().sort_index().rename_axis("Estrellas")
    )
    st.bar_chart(rating_counts, y_label="Número de libros")

st.subheader("Libros coincidentes")
display_columns = [
    column
    for column in [
        "title",
        "category",
        "price_gbp",
        "rating_stars",
        "book_url",
        "cover_url",
        "scraped_at_utc",
    ]
    if column in filtered.columns
]
st.dataframe(
    filtered[display_columns].sort_values("title"),
    use_container_width=True,
    hide_index=True,
    column_config={
        "price_gbp": st.column_config.NumberColumn("Precio (£)", format="£%.2f"),
        "rating_stars": st.column_config.NumberColumn("Valoración", format="%d / 5"),
        "book_url": st.column_config.LinkColumn("Ficha", display_text="Abrir ficha"),
        "cover_url": st.column_config.ImageColumn("Portada"),
    },
)

st.caption(
    "Books to Scrape es un sitio de demostración. Sus precios y valoraciones son aleatorios."
)
