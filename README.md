# Ceramics Portfolio

An open-source studio management app for clay artists and ceramic studios. Built on [Wagtail CMS](https://wagtail.org/) with a Claude AI integration for automatic firing-stage detection and glaze analysis.

## Features

- **Membership & profiles** — studio members get their own portfolio, avatar, bio, and join date
- **Artwork tracking & cataloging** — organize pieces into named collections, track each piece through greenware → bisque → glaze with photo documentation at every stage
- **Claude AI integration** — upload a photo and Claude detects the firing stage, writes a description, and identifies glazes in a potter's notebook style
- **Calendar timeline** — monthly calendar view of when each piece was started; click any piece to jump to its detail page
- **Real-time kiln monitoring** — live status strip in the navbar showing temperature, cone fire, heat bar, and last-updated time for every kiln in the studio; push updates from any IoT device via a simple JSON API
- **Wagtail CMS** — full content management backend at `/cms/` for admins
- **Docker-ready** — single `docker compose up` to run anywhere

---

## Tech Stack

| Layer | Technology |
|---|---|
| CMS / Framework | Wagtail 7.3.1 + Django 4.x |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Database | SQLite (dev) · PostgreSQL (production) |
| Storage | Local filesystem (dev) · swappable for S3/Cloudinary |
| Static files | WhiteNoise |
| IoT | Raspberry Pi Pico 2, ESP32, or any HTTP-capable device |
| Deployment | Docker + Docker Compose |

---

## Installation

### Prerequisites

- Python 3.11+
- Git
- An [Anthropic API key](https://console.anthropic.com/) (optional — AI features degrade gracefully without one)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/ceramics-portfolio.git
cd ceramics-portfolio
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env .env.local   # or create .env from scratch
```

Edit `.env`:

```ini
SECRET_KEY=your-django-secret-key
DEBUG=True

# Claude AI (optional — app works without it)
ANTHROPIC_API_KEY=sk-ant-...

# Kiln IoT API key (leave blank to disable auth in dev)
KILN_API_KEY=

# Production database (optional — defaults to SQLite in dev)
DATABASE_URL=postgres://user:password@localhost:5432/ceramics_db
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Load demo kiln data (optional)

```bash
python manage.py seed_kilns
```

This creates three fictitious kilns with realistic status data so the kiln strip in the navbar is populated immediately.

### 8. Start the development server

```bash
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000) — you'll be redirected to the dashboard.

| URL | Description |
|---|---|
| `/my-collections/` | Studio dashboard |
| `/cms/` | Wagtail admin |
| `/django-admin/` | Django admin |
| `/accounts/login/` | Login page |

---

## Docker

### Development

```bash
docker compose up
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

A sample `Dockerfile` and `docker-compose.yml` are included. The production compose file expects `DATABASE_URL`, `SECRET_KEY`, and `ANTHROPIC_API_KEY` to be set as environment variables or in a `.env` file.

---

## Kiln IoT Integration

The kiln status strip in the navbar updates in real time when your IoT device POSTs to the API.

### API endpoint

```
POST /my-collections/api/kilns/<number>/
Content-Type: application/json
Authorization: Bearer <KILN_API_KEY>
```

### Request body

All keys are optional — only the keys you send are updated.

```json
{
  "temp": 2287,
  "cone_fire": "Cone 10",
  "status": "firing",
  "notes": "Stoneware reduction load — 42 pieces."
}
```

| Field | Type | Values |
|---|---|---|
| `temp` | float | Temperature in °F |
| `cone_fire` | string | e.g. `"Cone 06"`, `"Cone 10"` |
| `status` | string | `idle` · `firing` · `cooling` · `done` |
| `notes` | string | Free text — shown on hover |

### Response

```json
{
  "ok": true,
  "kiln": 1,
  "temp": 2287.0,
  "cone_fire": "Cone 10",
  "status": "firing",
  "last_updated": "2026-04-05T22:14:03.421Z"
}
```

### Raspberry Pi Pico 2 (MicroPython)

```python
import urequests, ujson

KILN_NUMBER = 1
API_URL = "https://your-studio.com/my-collections/api/kilns/{}/".format(KILN_NUMBER)
API_KEY  = "your-kiln-api-key"

def push_temp(temp_f, status="firing"):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
    }
    data = ujson.dumps({"temp": temp_f, "status": status})
    r = urequests.post(API_URL, data=data, headers=headers)
    r.close()
```

### ESP32 (Arduino / C++)

```cpp
#include <HTTPClient.h>
#include <ArduinoJson.h>

void pushKilnTemp(float tempF, const char* status) {
    HTTPClient http;
    http.begin("https://your-studio.com/my-collections/api/kilns/1/");
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer your-kiln-api-key");

    StaticJsonDocument<128> doc;
    doc["temp"]   = tempF;
    doc["status"] = status;
    String body;
    serializeJson(doc, body);

    http.POST(body);
    http.end();
}
```

---

## Project Structure

```
ceramics_portfolio/
├── ceramics/                   # Main app
│   ├── models.py               # Wagtail page models + Kiln, PieceUpdate, UserProfile
│   ├── views.py                # All views including IoT API
│   ├── forms.py                # Collection, Piece, Profile, PieceUpdate forms
│   ├── ai_service.py           # Claude integration
│   ├── context_processors.py   # Injects kilns into every template
│   ├── urls.py
│   ├── templates/ceramics/
│   ├── management/commands/
│   │   └── seed_kilns.py
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_forms.py
│       └── test_ai_service.py
├── ceramics_portfolio/         # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── production.py
│   └── urls.py
├── static/
│   └── ceramics/js/ai_upload.js
├── requirements.txt
├── manage.py
└── .env
```

---

## Running Tests

```bash
python manage.py test ceramics
```

The test suite covers model logic, form validation, all HTTP views, and the AI service (Anthropic API is fully mocked — no API key required to run tests).

---

## Contributing

Pull requests are welcome. For major changes please open an issue first.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

---

## License

MIT
