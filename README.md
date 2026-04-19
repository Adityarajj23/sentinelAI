# SentinelAI — Real-Time API Anomaly Detection

A full-stack security monitoring system that detects anomalous API traffic patterns using hybrid rule-based and machine learning techniques, with real-time visualization and natural language incident analysis.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Detection Engine](#detection-engine)
- [Project Structure](#project-structure)
- [Local Development](#local-development)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Future Improvements](#future-improvements)

---

## Overview

SentinelAI monitors API traffic in real-time and surfaces suspicious behavior through:

1. **Hybrid Anomaly Detection**: Combines rule-based thresholds with unsupervised machine learning (Isolation Forest)
2. **Distributed Architecture**: Separate services for API ingestion, detection, traffic simulation, and visualization
3. **MongoDB-Backed State**: Persistent logs, alerts, and remote control state
4. **AI-Powered Explanations**: Generates human-readable incident summaries via Gemini API with graceful degradation
5. **Remote Control**: Manage traffic generation and attack simulation directly from the dashboard UI

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                │
│  - Real-time dashboard with Recharts visualization      │
│  - Admin-controlled traffic generation                  │
│  - Alert drill-down and incident explanation            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP Polling (5s)
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Flask API Server (Web Service)             │
│  - Request logging middleware                           │
│  - Dashboard aggregation endpoint (/api/dashboard)      │
│  - AI explanation endpoint (/api/explain/:id)           │
│  - Demo control endpoints (/api/demo/*)                │
└──────────────────────┬──────────────────────────────────┘
          │            │            │
          │ Write       │ Read       │ Write control state
          ▼            ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                    MongoDB Atlas                         │
│  Collections: api_logs, api_alerts, simulator_control   │
└────────────────┬─────────────────────────────────────────┘
         ▲       │       ▲
         │       │       │
(polls   │       │       │ (reads)
 logs)   │       │       │
         │       ▼       │
    ┌────────────────────────┐
    │ Detector Worker        │
    │ (background process)   │
    │                        │
    │ - Reads logs (1h window)
    │ - Runs rule engine     │
    │ - Runs ML (IF)         │
    │ - Writes alerts        │
    └────────────────────────┘

    ┌────────────────────────┐
    │ Simulator Worker       │
    │ (background process)   │
    │                        │
    │ - Polls control state  │
    │ - Generates normal IP  │
    │   traffic              │
    │ - Generates attacker   │
    │   traffic (toggle)     │
    └────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19, Vite, Recharts, Lucide React | Dashboard & visualization |
| **Backend** | Flask 3.0, Flask-CORS, python-dotenv | API server, middleware, secrets |
| **Data** | MongoDB 4.5, PyMongo | Logs, alerts, control state storage |
| **ML** | pandas 2.1, scikit-learn (Isolation Forest) | Anomaly detection |
| **AI** | Google Gemini API | Natural language explanations (optional) |
| **Deployment** | Render(Main server) + Railway(Background Workers), Vercel | Cloud hosting |

---

## Detection Engine

### Rule-Based Detection

- **Threshold**: IPs exceeding 50 requests/hour are flagged as high-rate abuse
- **Window**: Last 1-hour sliding window
- **Dedup**: Same IP + reason suppressed for 5 minutes to reduce noise

### Machine Learning Detection

- **Algorithm**: Isolation Forest (unsupervised outlier detection)
- **Features**:
  - `request_count`: requests per IP in the window
  - `unique_endpoints`: number of distinct endpoints accessed by that IP
- **Activation**: Requires ≥3 unique IPs in the dataset
- **Contamination**: 0.1 (expects up to ~10% anomalies)
- **Rationale**: Captures IPs with unusual combinations of volume + endpoint diversity not caught by rules alone

### Alert Augmentation

When an alert is clicked, the backend:

1. Tries to call Gemini API with alert context (IP + reason)
2. If Gemini is overloaded (503), retries up to 3 times with exponential backoff
3. Falls back to a templated explanation if all attempts fail
4. Returns insight text to the UI

---

## Project Structure

```
.
├── backend/
│   ├── app.py                 # Flask API, logging middleware, endpoints
│   ├── detector.py            # Anomaly detection loop
│   ├── simulator.py           # Traffic generator with remote control
│   ├── requirements.txt        # Python dependencies
│   └── .env.example           # Template env file
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main dashboard component
│   │   ├── App.css            # (legacy, unused)
│   │   ├── index.css          # Glassmorphic styling
│   │   └── main.jsx           # Entry point
│   ├── vite.config.js         # Vite bundler config
│   ├── eslint.config.js       # Linting rules
│   ├── package.json           # Node dependencies
│   └── .env.example           # Template env file
├── .gitignore                 # Git ignore patterns
└── README.md                  # This file
```

---

## Local Development

### Prerequisites

- Python 3.10+ (with venv support)
- Node.js 18+ (with npm)
- MongoDB running locally on `mongodb://localhost:27017/` (or configure MONGO_URI)

### Setup

#### 1. Clone and navigate

```bash
git clone <repo-url>
cd sentinelAI
```

#### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with local values if needed
```

#### 3. Frontend

```powershell
cd ..\frontend
npm install
Copy-Item .env.example .env
# Edit .env with VITE_API_BASE_URL=http://localhost:5000
```

### Running All Services

Open 4 terminals in the workspace root:

**Terminal 1: Flask API**

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

**Terminal 2: Detector**

```powershell
cd backend
.\venv\Scripts\activate
python detector.py
```

**Terminal 3: Simulator (with remote control)**

```powershell
cd backend
.\venv\Scripts\activate
python simulator.py --base-url http://localhost:5000/api --mongo-uri mongodb://localhost:27017/ --mongo-db sentinel_db --control-id default --disable-attack
```

**Terminal 4: Frontend**

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

---

## API Endpoints

### Traffic Simulation

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/login` | Simulated login attempt |
| POST | `/api/payment` | Simulated payment transaction |
| POST | `/api/add-to-cart` | Simulated cart addition |

### Monitoring

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/dashboard` | Aggregated stats, chart, and recent alerts |
| GET | `/api/explain/<alert_id>` | Gemini-generated or fallback explanation |

### Admin Demo Control

*Requires header: `X-Admin-Token: <DEMO_ADMIN_TOKEN>`*

| Method | Endpoint | Body | Purpose |
|--------|----------|------|---------|
| GET | `/api/demo/status` | — | Current simulator state |
| POST | `/api/demo/start` | — | Enable traffic generation |
| POST | `/api/demo/stop` | — | Stop all traffic |
| POST | `/api/demo/attack` | `{"enabled": true/false}` | Toggle attack stream |

---

## Configuration

### Backend (.env)

```env
# Database
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=sentinel_db

# CORS
FRONTEND_ORIGIN=http://localhost:5173

# Flask
BACKEND_PORT=5000
FLASK_DEBUG=false

# Demo Control
DEMO_MODE=true
DEMO_ADMIN_TOKEN=your-strong-secret-token
SIM_CONTROL_ID=default

# Detection
DETECTION_INTERVAL_SECONDS=10
REQUEST_RATE_THRESHOLD=50

# Optional AI
GEMINI_API_KEY=your-gemini-api-key
```

### Frontend (.env)

```env
VITE_API_BASE_URL=http://localhost:5000
```

---

## Deployment

### Cloud Stack

- **Database**: MongoDB Atlas (free tier available)
- **Backend**: Render Web Service
- **Workers**: Render Background Workers (2x)
- **Frontend**: Vercel

### Render Setup

#### Web Service (API)

```
Root: backend
Build: pip install -r requirements.txt
Start: python -m flask --app app run --host 0.0.0.0 --port $PORT
```

Env vars:
- MONGO_URI
- MONGO_DB_NAME
- FRONTEND_ORIGIN (your Vercel URL)
- DEMO_MODE=true
- DEMO_ADMIN_TOKEN=strong-token
- SIM_CONTROL_ID=default
- GEMINI_API_KEY (optional)

#### Background Worker 1 (Detector)

```
Root: backend
Build: pip install -r requirements.txt
Start: python detector.py
```

Env vars:
- MONGO_URI
- MONGO_DB_NAME

#### Background Worker 2 (Simulator)

```
Root: backend
Build: pip install -r requirements.txt
Start: python simulator.py --base-url https://YOUR_API.onrender.com/api --mongo-uri "$MONGO_URI" --mongo-db sentinel_db --control-id default --disable-attack
```

Env vars:
- MONGO_URI
- MONGO_DB_NAME

### Vercel Frontend

```
Build: npm run build
Output: dist
```

Env: 
- VITE_API_BASE_URL=https://YOUR_API.onrender.com

---

## Future Improvements

### Short-Term

1. **Testing**: Add pytest for backend routes and detector logic
2. **Indexing**: Add MongoDB indexes on `timestamp`, `ip_address`, and `control_id` for query performance
3. **Caching**: Redis layer for high-frequency dashboard refreshes
4. **Metrics**: Prometheus + Grafana for system-level observability

### Medium-Term

1. **Auth**: JWT + role-based access control (admin, analyst, viewer)
2. **Alert Workflows**: Incident lifecycle (triage, investigate, resolve)
3. **Response Actions**: Auto-block IPs, revoke tokens, send notifications
4. **Webhook Support**: Integrations with Slack, PagerDuty, Jira
5. **Real-Time Events**: Replace polling with WebSockets or Server-Sent Events

### Long-Term

1. **Multi-Tenancy**: Tenant isolation for SaaS deployment
2. **Behavioral Baseline**: Per-user/IP profiles to reduce false positives
3. **Advanced Models**: Time-series anomaly detection (LSTM, Prophet)
4. **Compliance**: SOC 2 audit controls, data retention policies
5. **Performance**: Distributed detector workers, message queues

---

