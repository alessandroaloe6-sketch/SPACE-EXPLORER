"""
Space Explorer — Backend FastAPI
Consuma le API pubbliche della NASA per esplorare lo spazio:
  - APOD  : Astronomy Picture of the Day
  - NEO   : Near Earth Objects (asteroidi vicino alla Terra)
  - Preferiti: database in memoria per salvare contenuti
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import httpx
from datetime import date, datetime, timedelta
import os

# ── Configurazione ──────────────────────────────────────────────────────────
NASA_KEY = "2vml7zI10bNIHZIawlwCXuRdNAdX6vCI4s1DaAzG"   # Chiave personale NASA
NASA_BASE = "https://api.nasa.gov"
IMG_BASE  = "https://images-api.nasa.gov"   # NASA Image Library (senza chiave)

app = FastAPI(
    title="Space Explorer API",
    description="Dashboard spaziale alimentata dalle API NASA",
    version="1.0.0"
)


# ── Modelli Pydantic ─────────────────────────────────────────────────────────

class APODItem(BaseModel):
    """Foto Astronomica del Giorno"""
    date: str
    title: str
    explanation: str
    url: str
    hdurl: Optional[str] = None
    media_type: str          # "image" oppure "video"
    copyright: Optional[str] = None



class NearEarthObject(BaseModel):
    """Asteroide o cometa che si avvicina alla Terra"""
    id: str
    name: str
    diameter_min_km: float
    diameter_max_km: float
    is_potentially_hazardous: bool
    close_approach_date: str
    velocity_km_h: float
    miss_distance_km: float


class GalleryItem(BaseModel):
    """Elemento della NASA Image & Video Library"""
    nasa_id: str
    title: str
    description: Optional[str] = None
    date_created: Optional[str] = None
    media_type: str
    thumb_url: Optional[str] = None






# ── Funzioni di supporto ─────────────────────────────────────────────────────

async def nasa_get(endpoint: str, params: dict = {}) -> dict:
    """Effettua una GET verso le API NASA aggiungendo automaticamente la api_key."""
    params["api_key"] = NASA_KEY
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{NASA_BASE}{endpoint}", params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Errore NASA API: {resp.text[:200]}")
    return resp.json()


async def img_get(endpoint: str, params: dict = {}) -> dict:
    """Effettua una GET verso la NASA Image Library (non richiede chiave)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{IMG_BASE}{endpoint}", params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Errore NASA Image API: {resp.text[:200]}")
    return resp.json()



# ── Traduzione automatica EN → IT ────────────────────────────────────────────

async def traduci(testo: str) -> str:
    # Traduce dall inglese all italiano usando MyMemory API.
    # Gratuita, nessuna chiave richiesta, fino a 5000 caratteri/giorno.
    # In caso di errore restituisce il testo originale.
    if not testo:
        return testo
    try:
        LIMIT = 500
        if len(testo) <= LIMIT:
            frammenti = [testo]
        else:
            # Divide in frasi mantenendo ogni pezzo sotto LIMIT caratteri
            frammenti = []
            corrente  = ""
            for frase in testo.replace(". ", ".|").split("|"):
                if len(corrente) + len(frase) < LIMIT:
                    corrente += frase + " "
                else:
                    if corrente:
                        frammenti.append(corrente.strip())
                    corrente = frase + " "
            if corrente:
                frammenti.append(corrente.strip())

        tradotto = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for frammento in frammenti:
                resp = await client.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": frammento, "langpair": "en|it"}
                )
                if resp.status_code == 200:
                    dati = resp.json()
                    trad = dati.get("responseData", {}).get("translatedText", "")
                    tradotto.append(trad if trad else frammento)
                else:
                    tradotto.append(frammento)

        return " ".join(tradotto)

    except Exception:
        return testo  # Fallback: testo originale inglese


# ── Endpoint: APOD ───────────────────────────────────────────────────────────

@app.get("/apod", response_model=APODItem, tags=["APOD"],
         summary="Foto astronomica del giorno")
async def get_apod(
    data: Optional[str] = Query(None, description="Data in formato YYYY-MM-DD (default: oggi)")
):
    """
    Restituisce la Astronomy Picture of the Day (APOD) della NASA.
    Se non si specifica una data, viene restituita quella di oggi.
    """
    params = {}
    if data:
        params["date"] = data
    raw = await nasa_get("/planetary/apod", params)

    # Traduce la spiegazione (e il titolo) in italiano
    spiegazione_it = await traduci(raw.get("explanation", ""))

    return APODItem(
        date=raw.get("date", ""),
        title=raw.get("title", ""),
        explanation=spiegazione_it,
        url=raw.get("url", ""),
        hdurl=raw.get("hdurl"),
        media_type=raw.get("media_type", "image"),
        copyright=raw.get("copyright")
    )


@app.get("/apod/range", response_model=list[APODItem], tags=["APOD"],
         summary="Foto astronomiche in un intervallo di date")
async def get_apod_range(
    start_date: str = Query(..., description="Data inizio YYYY-MM-DD"),
    end_date: str   = Query(..., description="Data fine YYYY-MM-DD")
):
    """Restituisce una lista di APOD tra due date."""
    raw_list = await nasa_get("/planetary/apod", {
        "start_date": start_date,
        "end_date": end_date
    })
    # L'API restituisce una lista quando si passa un intervallo
    if isinstance(raw_list, dict):
        raw_list = [raw_list]

    # Traduce la spiegazione di ogni elemento in italiano
    risultati = []
    for r in raw_list:
        spiegazione_it = await traduci(r.get("explanation", ""))
        risultati.append(APODItem(
            date=r.get("date", ""),
            title=r.get("title", ""),
            explanation=spiegazione_it,
            url=r.get("url", ""),
            hdurl=r.get("hdurl"),
            media_type=r.get("media_type", "image"),
            copyright=r.get("copyright")
        ))
    return risultati


# ── Endpoint: Near Earth Objects ─────────────────────────────────────────────

@app.get("/neo/feed", response_model=list[NearEarthObject], tags=["NEO"],
         summary="Asteroidi vicini alla Terra")
async def get_neo_feed(
    start_date: Optional[str] = Query(None, description="Data inizio YYYY-MM-DD (default: oggi)"),
    days:       int           = Query(3,    description="Giorni da analizzare (max 7)", ge=1, le=7)
):
    """
    Restituisce gli oggetti Near-Earth (NEO) rilevati dalla NASA
    nell'intervallo di date richiesto.
    """
    # Se non specificata, usa la data di oggi
    start = date.fromisoformat(start_date) if start_date else date.today()
    end   = start + timedelta(days=days - 1)

    raw = await nasa_get("/neo/rest/v1/feed", {
        "start_date": str(start),
        "end_date":   str(end)
    })

    risultati = []
    near_earth_objects = raw.get("near_earth_objects", {})

    # I NEO sono organizzati per data nel JSON della NASA
    for giorno, neo_list in near_earth_objects.items():
        for neo in neo_list:
            # Diametro stimato in km
            diam = neo["estimated_diameter"]["kilometers"]
            # Dati dell'avvicinamento più prossimo
            approach = neo["close_approach_data"][0] if neo["close_approach_data"] else {}

            risultati.append(NearEarthObject(
                id=neo["id"],
                name=neo["name"],
                diameter_min_km=round(diam["estimated_diameter_min"], 4),
                diameter_max_km=round(diam["estimated_diameter_max"], 4),
                is_potentially_hazardous=neo["is_potentially_hazardous_asteroid"],
                close_approach_date=approach.get("close_approach_date", giorno),
                velocity_km_h=round(float(approach.get("relative_velocity", {})
                                          .get("kilometers_per_hour", 0)), 2),
                miss_distance_km=round(float(approach.get("miss_distance", {})
                                             .get("kilometers", 0)), 2)
            ))

    # Ordina: prima quelli potenzialmente pericolosi
    risultati.sort(key=lambda x: (not x.is_potentially_hazardous, x.miss_distance_km))
    return risultati


# ── Endpoint: NASA Gallery ────────────────────────────────────────────────────

@app.get("/gallery/search", response_model=list[GalleryItem], tags=["Gallery"],
         summary="Cerca nella NASA Image & Video Library")
async def search_gallery(
    q:     str = Query(...,  description="Termine di ricerca (es. 'Apollo 11', 'nebula')"),
    limit: int = Query(12,   description="Numero massimo di risultati", ge=1, le=50),
    media: str = Query("image", description="Tipo media: image | video | audio")
):
    """
    Cerca immagini, video e audio nell'archivio storico della NASA.
    Non richiede chiave API.
    """
    raw = await img_get("/search", {
        "q": q,
        "media_type": media,
        "page_size": limit
    })

    items = raw.get("collection", {}).get("items", [])
    risultati = []

    for item in items[:limit]:
        data_item = item.get("data", [{}])[0]
        links      = item.get("links", [])

        # Trova la thumbnail
        thumb = next((l["href"] for l in links if l.get("rel") == "preview"), None)

        risultati.append(GalleryItem(
            nasa_id=data_item.get("nasa_id", ""),
            title=data_item.get("title", "Senza titolo"),
            description=data_item.get("description", "")[:300] if data_item.get("description") else None,
            date_created=data_item.get("date_created", "")[:10],
            media_type=data_item.get("media_type", "image"),
            thumb_url=thumb
        ))

    return risultati



# ── Serve il Frontend ─────────────────────────────────────────────────────────
# Monta la cartella corrente per servire index.html
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve il file index.html come pagina principale."""
    return FileResponse("index.html")


# ── Avvio ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)