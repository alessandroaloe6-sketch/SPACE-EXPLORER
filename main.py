"""
╔══════════════════════════════════════════════════════════════════╗
║              Space Explorer — Backend FastAPI                    ║
║  Consuma le API pubbliche della NASA per esplorare lo spazio.    ║
║                                                                  ║
║  Moduli esposti:                                                 ║
║    - APOD    : Astronomy Picture of the Day                      ║
║    - NEO     : Near Earth Objects (asteroidi vicini alla Terra)  ║
║    - Gallery : NASA Image & Video Library                        ║
║                                                                  ║
║  Funzionalità trasversale:                                       ║
║    - Traduzione automatica EN → IT via MyMemory API              ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Import delle librerie ────────────────────────────────────────────────────
# FastAPI: framework web per costruire API REST veloci e con documentazione automatica
from fastapi import FastAPI, HTTPException, Query
# StaticFiles: permette di servire file statici (HTML, CSS, JS) tramite FastAPI
from fastapi.staticfiles import StaticFiles
# FileResponse: restituisce un file come risposta HTTP (usato per servire index.html)
from fastapi.responses import FileResponse
# BaseModel: classe base di Pydantic per definire modelli dati con validazione automatica
from pydantic import BaseModel
# Optional: indica che un campo può essere None (non obbligatorio)
from typing import Optional
# httpx: libreria HTTP asincrona per chiamare API esterne (NASA, MyMemory)
import httpx
# Moduli per la gestione delle date (usati nel calcolo degli intervalli NEO)
from datetime import date, datetime, timedelta
import os


# ── Configurazione ───────────────────────────────────────────────────────────
# Chiave personale ottenuta registrandosi su https://api.nasa.gov
NASA_KEY  = "2vml7zI10bNIHZIawlwCXuRdNAdX6vCI4s1DaAzG"
# URL base delle API NASA (APOD, NEO, ecc.)
NASA_BASE = "https://api.nasa.gov"
# URL base della NASA Image & Video Library (non richiede chiave API)
IMG_BASE  = "https://images-api.nasa.gov"

# Creazione dell'istanza FastAPI: il titolo e la descrizione appaiono in Swagger (/docs)
app = FastAPI(
    title="Space Explorer API",
    description="Dashboard spaziale alimentata dalle API NASA",
    version="1.0.0"
)


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 1 — MODELLI PYDANTIC
#  Pydantic valida automaticamente i dati in entrata e in uscita dagli endpoint.
#  Ogni classe definisce la struttura esatta del JSON che l'API restituisce.
# ════════════════════════════════════════════════════════════════════════════

class APODItem(BaseModel):
    """
    Rappresenta la Foto Astronomica del Giorno (Astronomy Picture of the Day).
    Corrisponde al formato restituito dall'endpoint /apod e /apod/range.
    """
    date: str                       # Data nel formato YYYY-MM-DD
    title: str                      # Titolo della foto (in inglese, non tradotto)
    explanation: str                # Descrizione (tradotta in italiano dal backend)
    url: str                        # URL dell'immagine o del video
    hdurl: Optional[str] = None     # URL alta definizione (non sempre presente)
    media_type: str                 # "image" oppure "video"
    copyright: Optional[str] = None # Autore/copyright (assente per immagini NASA)


class NearEarthObject(BaseModel):
    """
    Rappresenta un oggetto Near-Earth (asteroide o cometa) rilevato dalla NASA.
    Corrisponde al formato restituito dall'endpoint /neo/feed.
    """
    id: str                          # ID univoco NASA dell'oggetto
    name: str                        # Nome dell'asteroide (es. "(2023 BU)")
    diameter_min_km: float           # Diametro minimo stimato in km
    diameter_max_km: float           # Diametro massimo stimato in km
    is_potentially_hazardous: bool   # True se classificato come pericoloso dalla NASA
    close_approach_date: str         # Data del passaggio più vicino alla Terra
    velocity_km_h: float             # Velocità relativa in km/h
    miss_distance_km: float          # Distanza minima dalla Terra in km


class GalleryItem(BaseModel):
    """
    Rappresenta un elemento dell'archivio NASA Image & Video Library.
    Corrisponde al formato restituito dall'endpoint /gallery/search.
    """
    nasa_id: str                        # ID univoco nell'archivio NASA
    title: str                          # Titolo del contenuto
    description: Optional[str] = None  # Descrizione breve (max 300 caratteri)
    date_created: Optional[str] = None # Data di creazione (formato YYYY-MM-DD)
    media_type: str                     # "image", "video" o "audio"
    thumb_url: Optional[str] = None    # URL dell'anteprima (thumbnail)


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 2 — FUNZIONI HELPER (chiamate HTTP verso API esterne)
#  Centralizzano la logica di comunicazione con NASA e MyMemory,
#  evitando duplicazioni negli endpoint.
# ════════════════════════════════════════════════════════════════════════════

async def nasa_get(endpoint: str, params: dict = None) -> dict:
    """
    Esegue una richiesta GET verso le API NASA.
    Aggiunge automaticamente la api_key a ogni chiamata.

    NOTA: params usa None come default (non {}) per evitare il classico
    bug Python del 'mutable default argument': usando {} come default,
    il dizionario verrebbe condiviso tra tutte le chiamate, causando
    effetti collaterali imprevedibili.
    """
    if params is None:
        params = {}  # Crea un nuovo dizionario ad ogni chiamata
    params["api_key"] = NASA_KEY
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{NASA_BASE}{endpoint}", params=params)
    # Se la NASA risponde con un errore, lo propaghiamo al client come HTTP exception
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Errore NASA API: {resp.text[:200]}")
    return resp.json()


async def img_get(endpoint: str, params: dict = None) -> dict:
    """
    Esegue una richiesta GET verso la NASA Image & Video Library.
    Questa API è pubblica e non richiede chiave di autenticazione.
    Stessa precauzione sul mutable default argument applicata qui.
    """
    if params is None:
        params = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{IMG_BASE}{endpoint}", params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Errore NASA Image API: {resp.text[:200]}")
    return resp.json()


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 3 — TRADUZIONE AUTOMATICA EN → IT
#  Il testo delle spiegazioni NASA è in inglese. Questa funzione lo traduce
#  in italiano usando MyMemory API, gratuita e senza necessità di chiave.
#
#  Sfida tecnica risolta: MyMemory accetta al massimo 500 caratteri per
#  richiesta. Per testi lunghi (le spiegazioni APOD superano spesso i 1000
#  caratteri), il testo viene suddiviso in frammenti, tradotto pezzo per
#  pezzo e poi riassemblato.
# ════════════════════════════════════════════════════════════════════════════

async def traduci(testo: str) -> str:
    """
    Traduce un testo dall'inglese all'italiano tramite MyMemory API.
    Gestisce automaticamente testi lunghi suddividendoli in frammenti.
    In caso di errore (rete, limiti API) restituisce il testo originale inglese.
    """
    if not testo:
        return testo
    try:
        LIMIT = 500  # Limite di caratteri per singola richiesta MyMemory

        # Se il testo è corto, non serve suddividerlo
        if len(testo) <= LIMIT:
            frammenti = [testo]
        else:
            # Suddivisione intelligente: si tenta di spezzare alle frasi (". ")
            # per non troncare le parole a metà
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

        # Traduce ogni frammento separatamente e raccoglie i risultati
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
                    # Se la traduzione è vuota, mantieni il testo originale del frammento
                    tradotto.append(trad if trad else frammento)
                else:
                    tradotto.append(frammento)  # Fallback: frammento in inglese

        # Riassembla i frammenti tradotti in un unico testo
        return " ".join(tradotto)

    except Exception:
        # Qualsiasi errore imprevisto → restituisce il testo originale inglese
        return testo


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 4 — ENDPOINT: APOD (Astronomy Picture of the Day)
#  Permette di recuperare la foto astronomica del giorno o di un intervallo
#  di date. Le descrizioni vengono tradotte automaticamente in italiano.
# ════════════════════════════════════════════════════════════════════════════

@app.get(
    "/apod",
    response_model=APODItem,
    tags=["APOD"],
    summary="Foto astronomica del giorno"
)
async def get_apod(
    data: Optional[str] = Query(None, description="Data in formato YYYY-MM-DD (default: oggi)")
):
    """
    Restituisce la Astronomy Picture of the Day (APOD) della NASA.

    - Senza parametri → restituisce la foto di oggi
    - Con il parametro 'data' → restituisce la foto della data specificata
    - La spiegazione è tradotta automaticamente in italiano
    """
    params = {}
    if data:
        params["date"] = data  # Passa la data alla NASA solo se specificata

    # Chiamata all'API NASA APOD
    raw = await nasa_get("/planetary/apod", params)

    # Traduzione della spiegazione in italiano prima di restituirla al client
    spiegazione_it = await traduci(raw.get("explanation", ""))

    # Costruisce e restituisce l'oggetto validato da Pydantic
    return APODItem(
        date=raw.get("date", ""),
        title=raw.get("title", ""),
        explanation=spiegazione_it,
        url=raw.get("url", ""),
        hdurl=raw.get("hdurl"),
        media_type=raw.get("media_type", "image"),
        copyright=raw.get("copyright")
    )


@app.get(
    "/apod/range",
    response_model=list[APODItem],
    tags=["APOD"],
    summary="Foto astronomiche in un intervallo di date"
)
async def get_apod_range(
    start_date: str = Query(..., description="Data inizio YYYY-MM-DD"),
    end_date: str   = Query(..., description="Data fine YYYY-MM-DD")
):
    """
    Restituisce una lista di APOD compresi tra due date.

    NOTA: quando si passa un intervallo, la NASA API restituisce una lista JSON.
    Ma se l'intervallo copre un solo giorno, restituisce un dizionario singolo.
    Il codice gestisce entrambi i casi con il controllo isinstance().
    """
    raw_list = await nasa_get("/planetary/apod", {
        "start_date": start_date,
        "end_date": end_date
    })

    # Gestione del caso in cui NASA restituisce un dict invece di una lista
    if isinstance(raw_list, dict):
        raw_list = [raw_list]

    # Traduce la spiegazione di ciascuna foto e costruisce la lista di risposta
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


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 5 — ENDPOINT: NEO (Near Earth Objects)
#  Recupera gli asteroidi e le comete che si avvicinano alla Terra
#  in un dato intervallo di date. I risultati vengono ordinati per pericolosità.
# ════════════════════════════════════════════════════════════════════════════

@app.get(
    "/neo/feed",
    response_model=list[NearEarthObject],
    tags=["NEO"],
    summary="Asteroidi vicini alla Terra"
)
async def get_neo_feed(
    start_date: Optional[str] = Query(None, description="Data inizio YYYY-MM-DD (default: oggi)"),
    days:       int           = Query(3,    description="Giorni da analizzare (max 7)", ge=1, le=7)
):
    """
    Restituisce gli oggetti Near-Earth rilevati dalla NASA nell'intervallo specificato.

    - start_date: data di partenza (default: oggi)
    - days: numero di giorni da analizzare (1-7, come da limite NASA)
    - I risultati sono ordinati: prima gli asteroidi potenzialmente pericolosi,
      poi gli altri in ordine crescente di distanza dalla Terra
    """
    # Calcolo delle date di inizio e fine
    start = date.fromisoformat(start_date) if start_date else date.today()
    end   = start + timedelta(days=days - 1)

    raw = await nasa_get("/neo/rest/v1/feed", {
        "start_date": str(start),
        "end_date":   str(end)
    })

    risultati = []
    # La NASA organizza i NEO in un dizionario con le date come chiavi
    near_earth_objects = raw.get("near_earth_objects", {})

    for giorno, neo_list in near_earth_objects.items():
        for neo in neo_list:
            # Estrae i dati sul diametro stimato (in chilometri)
            diam = neo["estimated_diameter"]["kilometers"]
            # Prende il primo (e più vicino) evento di avvicinamento
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

    # Ordinamento: i potenzialmente pericolosi vengono messi in cima,
    # poi si ordina per distanza crescente dalla Terra
    risultati.sort(key=lambda x: (not x.is_potentially_hazardous, x.miss_distance_km))
    return risultati


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 6 — ENDPOINT: GALLERY (NASA Image & Video Library)
#  Permette di cercare immagini, video e audio nell'archivio storico NASA.
#  Non richiede chiave API.
# ════════════════════════════════════════════════════════════════════════════

@app.get(
    "/gallery/search",
    response_model=list[GalleryItem],
    tags=["Gallery"],
    summary="Cerca nella NASA Image & Video Library"
)
async def search_gallery(
    q:     str = Query(...,      description="Termine di ricerca (es. 'Apollo 11', 'nebula')"),
    limit: int = Query(12,       description="Numero massimo di risultati", ge=1, le=50),
    media: str = Query("image",  description="Tipo media: image | video | audio")
):
    """
    Cerca contenuti nell'archivio storico NASA (immagini, video, audio).
    Non richiede chiave API: usa l'endpoint pubblico images-api.nasa.gov.
    """
    raw = await img_get("/search", {
        "q": q,
        "media_type": media,
        "page_size": limit
    })

    items = raw.get("collection", {}).get("items", [])
    risultati = []

    for item in items[:limit]:
        # Ogni elemento ha un array "data" con i metadati e un array "links" con le URL
        data_item = item.get("data", [{}])[0]
        links      = item.get("links", [])

        # Cerca il link con rel="preview" per ottenere la thumbnail
        thumb = next((l["href"] for l in links if l.get("rel") == "preview"), None)

        risultati.append(GalleryItem(
            nasa_id=data_item.get("nasa_id", ""),
            title=data_item.get("title", "Senza titolo"),
            # Tronca la descrizione a 300 caratteri per non appesantire la risposta
            description=data_item.get("description", "")[:300] if data_item.get("description") else None,
            date_created=data_item.get("date_created", "")[:10],  # Solo la data, senza ora
            media_type=data_item.get("media_type", "image"),
            thumb_url=thumb
        ))

    return risultati


# ════════════════════════════════════════════════════════════════════════════
#  SEZIONE 7 — SERVE IL FRONTEND
#  FastAPI non è solo un backend: può anche servire file statici.
#  L'endpoint "/" restituisce direttamente index.html, rendendo l'app
#  accessibile come una normale pagina web.
# ════════════════════════════════════════════════════════════════════════════

# Rende disponibili i file statici al percorso /static
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/", include_in_schema=False)  # include_in_schema=False: nasconde da Swagger
async def serve_frontend():
    """Serve il file index.html come pagina principale dell'applicazione."""
    return FileResponse("index.html")


# ════════════════════════════════════════════════════════════════════════════
#  AVVIO DIRETTO
#  Permette di avviare il server con: python main.py
#  In alternativa: uvicorn main:app --reload
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
