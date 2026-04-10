# SentinelAI

SentinelAI is a full-stack API monitoring and anomaly detection demo built for software and security-focused internship applications. It simulates normal and suspicious API traffic, stores request metadata in MongoDB, detects anomalous IP behavior with rule-based logic plus Isolation Forest, and visualizes alerts in a React dashboard.

## Why this project is useful

- Shows full-stack ownership across backend, data, ML logic, and frontend visualization.
- Demonstrates practical security ideas like request logging, traffic baselining, anomaly triage, and attack simulation.
- Gives you a concrete system to discuss in interviews instead of only algorithm questions.

## Architecture

1. Flask API receives requests and logs metadata such as IP, endpoint, payload, timestamp, and user agent.
2. MongoDB stores raw request logs in `api_logs` and generated alerts in `api_alerts`.
3. A detector worker scans the last hour of traffic, applies threshold-based rules, and runs Isolation Forest over aggregated IP features.
4. A traffic simulator creates normal users and a bursty attacker to trigger realistic alerts.
5. A React dashboard polls the backend and displays metrics, alerts, and optional AI-generated explanations.

## Tech stack

- Frontend: React, Vite, Recharts, Lucide React
- Backend: Flask, Flask-CORS, PyMongo, python-dotenv
- Data/ML: MongoDB, pandas, scikit-learn Isolation Forest
- Optional AI: Google Gemini for natural-language alert explanations

## Project structure

```text
backend/
  app.py
  detector.py
  simulator.py
  requirements.txt
frontend/
  src/App.jsx
  src/index.css
```

## Setup

### 1. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

### 2. Detector worker

```powershell
cd backend
.\venv\Scripts\activate
python detector.py
```

### 3. Traffic simulator

```powershell
cd backend
.\venv\Scripts\activate
python simulator.py
```

### 4. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

## Environment variables

### Backend

- `MONGO_URI`: MongoDB connection string
- `MONGO_DB_NAME`: database name for SentinelAI data
- `FRONTEND_ORIGIN`: allowed frontend origin for CORS
- `BACKEND_PORT`: Flask server port
- `FLASK_DEBUG`: set `true` only for local debugging
- `DETECTION_INTERVAL_SECONDS`: detector polling interval
- `REQUEST_RATE_THRESHOLD`: rule-based alert threshold
- `SENTINEL_API_BASE_URL`: base URL used by the simulator
- `GEMINI_API_KEY`: optional key for AI anomaly explanations

### Frontend

- `VITE_API_BASE_URL`: backend base URL, defaults to `http://localhost:5000`

## Demo flow

1. Start the Flask API.
2. Start the detector worker.
3. Start the simulator.
4. Open the frontend dashboard.
5. Watch request counts rise and alerts appear after the attacker begins sending rapid `/login` traffic.

## What this project currently demonstrates

- Middleware-based request logging
- Hybrid anomaly detection using rules and unsupervised ML
- Real-time dashboard polling with offline cache fallback
- Simple security event explanation workflow

## Good next improvements

- Add tests for backend routes and detector behavior
- Add endpoint-level analytics and alert severity
- Add Docker Compose for one-command startup
- Add indexes for `timestamp` and `ip_address`
- Replace polling with WebSockets or server-sent events
- Add alert resolution workflow and audit trail

## Interview talking points

- Why hybrid detection is often more practical than ML-only detection
- False positives vs false negatives in security monitoring
- Why environment-based config matters for deployment and safety
- How polling trades simplicity for freshness and scalability
- How you would harden this for production with auth, rate limiting, indexes, and tests
