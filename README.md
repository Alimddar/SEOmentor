<p align="center">
  <img src="frontend/public/seomentor-favicon.svg" width="80" height="80" alt="SEOmentor logo" />
</p>

<h1 align="center">SEOmentor</h1>

<p align="center">
  <strong>AI-powered SEO analysis and roadmap generator</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React 19" />
  <img src="https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white" alt="Vite 7" />
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Claude_AI-Sonnet_4-D97706?logo=anthropic&logoColor=white" alt="Claude AI" />
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License" />
  <img src="https://img.shields.io/github/last-commit/Alimddar/SEOmentor" alt="Last commit" />
</p>

---

SEOmentor analyzes any website's SEO health, identifies competitors, discovers keyword gaps, and generates a personalized day-by-day execution roadmap — all powered by Claude AI.

## Features

- **SEO Health Score** — Weighted analysis across technical, content, on-page, and authority signals (0-100)
- **Issue Detection** — Categorized issues with evidence from crawled data, impact analysis, and step-by-step fixes
- **Competitor Discovery** — Identifies 5 real competitors in your market with competitive advantage analysis and verified URLs
- **Keyword Gap Analysis** — 12-15 keyword opportunities with search intent classification and ranking potential
- **Day-by-Day Roadmap** — 7-30 day execution plan with specific deliverables, target pages, and KPIs per task
- **Task Deep-Dive** — Click any roadmap day to get a 6-step execution checklist with tool recommendations
- **Email Reports** — Generate and send branded PDF reports with the full analysis
- **Analysis History** — Browse and revisit past analyses

## Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| React 19 | UI framework |
| TypeScript 5.9 | Type safety |
| Vite 7 | Build tooling |
| Tailwind CSS 4 | Styling |
| Axios | HTTP client |

### Backend
| Technology | Purpose |
|---|---|
| FastAPI | API framework |
| Claude Sonnet 4 | Main SEO analysis |
| Claude 3.5 Sonnet | Task detail generation |
| BeautifulSoup4 | Web scraping |
| SQLite | Data persistence |
| DuckDuckGo Search | Competitor URL enrichment |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Anthropic API key](https://console.anthropic.com/)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
ANTHROPIC_API_KEY=sk-ant-...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your@gmail.com
SMTP_FROM_NAME=SEOmentor
```

Start the server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will open at `http://localhost:5173`.

To point the frontend to a different backend URL:

```bash
VITE_API_BASE_URL=https://your-backend.up.railway.app npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analyze` | Submit a website for SEO analysis |
| `GET` | `/project/{id}` | Retrieve full analysis results |
| `GET` | `/projects` | List recent analyses |
| `GET` | `/project/{id}/day/{day}/detail` | Get detailed execution steps for a roadmap day |
| `POST` | `/project/{id}/email` | Send the analysis report via email |
| `GET` | `/health` | Health check |

## Project Structure

```
SEOmentor/
├── backend/
│   ├── main.py                 # FastAPI routes
│   ├── ai_service.py           # Claude AI integration & prompts
│   ├── day_detail_service.py   # Task detail generation
│   ├── scraper.py              # SEO metrics extraction (15+ signals)
│   ├── database.py             # SQLite operations
│   ├── mailer.py               # PDF generation & email delivery
│   ├── models.py               # Data types
│   ├── schemas.py              # Request/response schemas
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.tsx              # Main application
    │   ├── index.css            # Global styles
    │   └── main.tsx             # Entry point
    ├── package.json
    └── vite.config.ts
```

## Deployment

The recommended setup is **frontend on Vercel** + **backend on Railway**:

| Component | Platform | Config |
|---|---|---|
| Frontend | Vercel | Root directory: `frontend/` — Add env var: `VITE_API_BASE_URL` |
| Backend | Railway | Root directory: `backend/` — Add all env vars from `.env` |

See the included `backend/Procfile` and `backend/runtime.txt` for Railway configuration.

## How It Works

```
User submits URL → Scraper extracts 20+ SEO signals → Claude Sonnet 4 analyzes
→ Score + Issues + Competitors + Keyword Gaps + Roadmap → Stored in SQLite
→ Competitor URLs enriched via DuckDuckGo → Results displayed in dashboard
→ Click any day → Claude generates 6-step execution guide → PDF emailable
```

## License

MIT
