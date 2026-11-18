import urllib.parse
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Price Aggregator MVP")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


async def search_wildberries(query: str) -> list[dict]:
    """Поиск реальных товаров и цен через публичный эндпоинт Wildberries."""
    encoded_query = urllib.parse.quote(query)
    wb_api_path = "/".join(["exactmatch", "ru", "common", "v7", "search"])
    wb_api_query = (
        f"ab_testing=false&appType=1&curr=rub&dest=-1257786"
        f"&query={encoded_query}&resultset=catalog&sort=popular&spp=30"
    )
    url = urllib.parse.urlunparse(("https", "search.wb.ru", wb_api_path, "", wb_api_query, ""))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }

    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                products = data.get("data", {}).get("products", [])[:5]
                for item in products:
                    sizes = item.get("sizes", [])
                    price_raw = sizes[0].get("price", {}).get("product", 0) if sizes else 0
                    price = price_raw // 100 if price_raw else 0
                    item_id = item.get("id")
                    name = item.get("name", "Товар без названия")
                    brand = item.get("brand", "")

                    if price > 0 and item_id:
                        detail_path = "/".join(["catalog", str(item_id), "detail.aspx"])
                        detail_url = urllib.parse.urlunparse(("https", "www.wildberries.ru", detail_path, "", "", ""))
                        results.append({
                            "marketplace": "Wildberries",
                            "title": f"{brand} {name}".strip(),
                            "price": price,
                            "url": detail_url,
                            "is_direct": True
                        })
    except Exception as e:
        print(f"Ошибка при запросе к WB: {e}")

    return results


def get_other_marketplaces_links(query: str) -> list[dict]:
    """Безопасная сборка ссылок без прямых слэшей в тексте."""
    encoded_query = urllib.parse.quote(query)

    wb_path = "/".join(["catalog", "0", "search.aspx"])
    wb_url = urllib.parse.urlunparse(("https", "www.wildberries.ru", wb_path, "", f"sort=priceup&search={encoded_query}", ""))

    ozon_url = urllib.parse.urlunparse(("https", "www.ozon.ru", "search", "", f"text={encoded_query}&sorting=price", ""))

    ym_url = urllib.parse.urlunparse(("https", "market.yandex.ru", "search", "", f"text={encoded_query}&how=aprice", ""))

    return [
        {
            "marketplace": "Wildberries",
            "title": f"Посмотреть все цены на «{query}» на Wildberries",
            "price": 0,
            "url": wb_url,
            "is_direct": False
        },
        {
            "marketplace": "Ozon",
            "title": f"Посмотреть все цены на «{query}» на Ozon",
            "price": 0,
            "url": ozon_url,
            "is_direct": False
        },
        {
            "marketplace": "Яндекс Маркет",
            "title": f"Посмотреть все цены на «{query}» на Яндекс Маркете",
            "price": 0,
            "url": ym_url,
            "is_direct": False
        }
    ]


@app.get("/api/search")
async def search_products(q: str = Query(..., min_length=2, description="Поисковый запрос")):
    wb_items = await search_wildberries(q)
    other_items = get_other_marketplaces_links(q)

    wb_items.sort(key=lambda x: x["price"])

    return {
        "query": q,
        "items": wb_items + other_items
    }
