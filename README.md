# 🚀 Space Explorer — Dashboard NASA

Web app che consente di esplorare contenuti spaziali in tempo reale tramite le API pubbliche della NASA. Le descrizioni testuali vengono tradotte automaticamente dall'inglese all'italiano.

## Funzionalità

- **APOD** — Foto Astronomica del Giorno con descrizione tradotta in italiano
- **NEO** — Asteroidi vicini alla Terra, ordinati per pericolosità
- **Gallery** — Ricerca immagini e video nell'archivio storico NASA

## Requisiti

- Python 3.10+
- pip

## Installazione

```bash
# 1. Clona il repository
git clone https://github.com/alessandroaloe6-sketch/SPACE-EXPLORER.git
cd SPACE-EXPLORER

# 2. Crea e attiva un ambiente virtuale
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Installa le dipendenze
pip install -r requirements.txt
```

## Avvio

```bash
uvicorn main:app --reload
```

L'app sarà disponibile su: [http://localhost:8000](http://localhost:8000)

La documentazione automatica Swagger è disponibile su: [http://localhost:8000/docs](http://localhost:8000/docs)

## Struttura del Progetto

```
├── main.py          # Backend FastAPI (endpoint APOD, NEO, Gallery + traduzione)
├── index.html       # Frontend single-page (HTML5 / CSS / JavaScript)
├── requirements.txt # Dipendenze Python
└── README.md
```

## API utilizzate

| API | Descrizione | Chiave richiesta |
|-----|-------------|-----------------|
| [NASA APOD](https://api.nasa.gov/) | Foto Astronomica del Giorno | Sì |
| [NASA NEO](https://api.nasa.gov/) | Near Earth Objects | Sì |
| [NASA Image Library](https://images.nasa.gov/) | Archivio immagini e video | No |
| [MyMemory](https://mymemory.translated.net/) | Traduzione EN→IT | No |
