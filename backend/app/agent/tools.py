"""Travel-planning tools for the Yatra AI agent.

Design rules:
- Only free, keyless, public APIs are used (Open-Meteo, Nominatim/OSM,
  OSRM, Frankfurter, Wikipedia REST). Every tool result is prefixed
  VERIFIED or ESTIMATED so the model can label information honestly in
  the final plan.
- All I/O is async (httpx.AsyncClient) so tool batches run concurrently
  inside the LangGraph tool node.
- Tools never raise into the graph; failures return readable strings the
  planner can reason over.
- The calculator is an AST walker — no eval/exec — inherited from the
  project's security-hardened design.
"""

import ast
import math
import operator
from datetime import UTC, datetime

import httpx
from langchain_core.tools import tool

_HTTP_HEADERS = {"User-Agent": "YatraAI/1.0 (travel planning demo)"}
_TIMEOUT = httpx.Timeout(15.0)


# ── Calculator (AST-safe) ────────────────────────────────────────────────

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

_MAX_EXPONENT = 1000


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported unary operator")
        return op(_evaluate(node.operand))

    if isinstance(node, ast.BinOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported binary operator")
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"Exponent too large (max {_MAX_EXPONENT})")
        return op(left, right)

    raise ValueError("Unsupported expression")


@tool
def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression, e.g. budget splits or cost totals.

    Use for all arithmetic so totals reconcile exactly.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_evaluate(tree.body))
    except Exception as exc:
        return f"Calculation error: {exc}"


# ── Time ─────────────────────────────────────────────────────────────────

@tool
def get_current_time() -> str:
    """Get the current UTC time (ISO-8601)."""
    return f"VERIFIED: {datetime.now(UTC).isoformat()}"


# ── Geocoding helper ─────────────────────────────────────────────────────

async def _geocode(place: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, display_name) via OSM Nominatim, or None."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": place, "format": "json", "limit": 1},
            )
            data = resp.json()
    except Exception:
        return None
    if not data:
        return None
    top = data[0]
    return float(top["lat"]), float(top["lon"]), top.get("display_name", place)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


# ── Weather (Open-Meteo, no key) ─────────────────────────────────────────

@tool
async def get_weather_forecast(city: str, days: int = 5) -> str:
    """Get a real daily weather forecast for a city (up to 16 days ahead).

    Returns daily max/min temperature, precipitation probability and a plain
    condition summary — use before scheduling outdoor activities.
    """
    geo = await _geocode(city)
    if not geo:
        return f"Could not geocode '{city}'. Weather unavailable."

    lat, lon, name = geo
    days = max(1, min(int(days), 16))

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,weathercode",
                    "timezone": "auto",
                    "forecast_days": days,
                },
            )
            data = resp.json()
    except Exception as exc:
        return f"Weather lookup failed: {exc}"

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_probability_max", [])

    if not dates:
        return f"No forecast data for {name}."

    lines = [f"VERIFIED forecast for {name} (Open-Meteo):"]
    for i, d in enumerate(dates):
        rain = precip[i] if i < len(precip) else "?"
        lines.append(
            f"  {d}: {tmin[i]}°C – {tmax[i]}°C, rain chance {rain}%"
        )
    return "\n".join(lines)


# ── Route distance (OSRM + haversine fallback) ───────────────────────────

@tool
async def get_route_distance(origin: str, destination: str) -> str:
    """Get road distance and driving time between two places.

    Falls back to a straight-line estimate if routing is unavailable.
    """
    src = await _geocode(origin)
    dst = await _geocode(destination)
    if not src or not dst:
        return f"Could not geocode '{origin}' or '{destination}'."

    lat1, lon1, name1 = src
    lat2, lon2, name2 = dst

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://router.project-osrm.org/route/v1/driving/"
                f"{lon1},{lat1};{lon2},{lat2}",
                params={"overview": "false"},
            )
            data = resp.json()
        route = data["routes"][0]
        km = route["distance"] / 1000
        hours = route["duration"] / 3600
        return (
            f"VERIFIED road route {name1} → {name2}: "
            f"{km:.0f} km, ~{hours:.1f} h driving (OSRM)"
        )
    except Exception:
        km = _haversine_km(lat1, lon1, lat2, lon2) * 1.3  # road factor
        return (
            f"ESTIMATED distance {name1} → {name2}: ~{km:.0f} km "
            f"(straight-line ×1.3; routing service unavailable)"
        )


# ── Places / POI search (Overpass + Nominatim) ───────────────────────────

_CATEGORY_FILTERS = [
    (
        ("restaurant", "food", "eat", "cafe", "dining", "street food"),
        '["amenity"~"restaurant|cafe|fast_food|food_court"]',
    ),
    (
        ("hotel", "hostel", "stay", "accommodation", "guest"),
        '["tourism"~"hotel|guest_house|hostel|resort"]',
    ),
    (
        ("park", "garden", "nature", "lake", "viewpoint"),
        '["leisure"~"park|garden|nature_reserve"]["name"]',
    ),
    (
        ("shop", "market", "bazaar", "mall"),
        '["amenity"~"marketplace"]["name"]',
    ),
]
_DEFAULT_FILTER = '["tourism"~"attraction|museum|viewpoint|gallery|theme_park|zoo|fort"]["name"]'


def _osm_filter_for(category: str) -> str:
    cat = category.lower()
    for keywords, filt in _CATEGORY_FILTERS:
        if any(k in cat for k in keywords):
            return filt + '["name"]' if '["name"]' not in filt else filt
    return _DEFAULT_FILTER


@tool
async def search_places(city: str, category: str) -> str:
    """Find real named places in a city via OpenStreetMap, including any
    recorded opening hours.

    category examples: 'tourist attractions', 'restaurants', 'parks',
    'hotels', 'markets'. Returns up to 8 named places.
    """
    geo = await _geocode(city)
    if not geo:
        return f"Could not geocode '{city}'. Place search unavailable."

    lat, lon, name = geo
    filt = _osm_filter_for(category)

    query = (
        "[out:json][timeout:12];"
        f'nwr{filt}(around:25000,{lat},{lon});'
        "out tags 8;"
    )

    try:
        async with httpx.AsyncClient(
            timeout=20.0, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                content=query,
            )
            elements = resp.json().get("elements", [])
    except Exception:
        elements = []

    seen = set()
    places = []
    for el in elements:
        tags = el.get("tags") or {}
        n = tags.get("name")
        if n and n not in seen:
            seen.add(n)
            hours = tags.get("opening_hours")
            places.append(f"{n} (hours: {hours})" if hours else n)

    if places:
        lines = [f"VERIFIED {category} near {name.split(',')[0]} (OpenStreetMap):"]
        lines += [f"  - {p}" for p in places[:8]]
        return "\n".join(lines)

    # Fallback: free-text search when Overpass has nothing/is unreachable.
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": f"{category} {name.split(',')[0]}",
                    "format": "json",
                    "limit": 6,
                },
            )
            data = resp.json()
    except Exception as exc:
        return f"Place search failed: {exc}"

    if not data:
        return f"No {category} results found for {city}."

    lines = [f"VERIFIED places for '{category}' in {city} (OpenStreetMap):"]
    for item in data:
        n = item.get("display_name", "").split(",")[0]
        lines.append(f"  - {n} ({item.get('type', 'place')})")
    return "\n".join(lines)


# ── Destination guide (Wikipedia REST, no key) ───────────────────────────

@tool
async def get_city_guide(city: str) -> str:
    """Get a real destination summary from Wikipedia/Wikivoyage.

    Use to ground destination choices — highlights, climate context and
    notable facts from an editable-encyclopedia source.
    """
    title = city.strip().replace(" ", "_")
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + title
            )
            data = resp.json()
    except Exception as exc:
        return f"Guide lookup failed: {exc}"

    extract = data.get("extract")
    if resp.status_code >= 400 or not extract:
        return f"No guide entry found for '{city}'."

    url = (data.get("content_urls") or {}).get("desktop", {}).get("page", "")
    return (
        f"VERIFIED guide for {data.get('title', city)} (Wikipedia{': ' + url if url else ''}):\n"
        f"  {extract[:800]}"
    )


# ── Currency (Frankfurter / ECB rates, no key) ───────────────────────────

@tool
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies at live ECB reference rates."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, headers=_HTTP_HEADERS
        ) as client:
            resp = await client.get(
                "https://api.frankfurter.dev/v1/latest",
                params={
                    "amount": amount,
                    "from": from_currency.upper(),
                    "to": to_currency.upper(),
                },
            )
            data = resp.json()
    except Exception as exc:
        return f"Currency conversion failed: {exc}"

    rate = data.get("rates", {}).get(to_currency.upper())
    if rate is None:
        return f"Could not convert {from_currency} to {to_currency}."
    return (
        f"VERIFIED: {amount} {from_currency.upper()} ≈ "
        f"{rate} {to_currency.upper()} (ECB rate, {data.get('date')})"
    )


def get_tools():
    return [
        calculate,
        get_current_time,
        get_weather_forecast,
        get_route_distance,
        search_places,
        get_city_guide,
        convert_currency,
    ]
