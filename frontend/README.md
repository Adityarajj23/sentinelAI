# SentinelAI Frontend

This folder contains the React dashboard for SentinelAI.

## Local run

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Default local URL:

1. http://localhost:5173

## Environment variable

1. VITE_API_BASE_URL=http://localhost:5000

## Notes

1. Dashboard polls backend for stats, chart, alerts, and demo-control status.
2. Explain Anomaly requests are sent to backend; API keys are never stored in frontend.
3. For full project setup and deployment, see the root README.
