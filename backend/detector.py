import datetime
import os
import time
import uuid

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from sklearn.ensemble import IsolationForest

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentinel_db")
DETECTION_INTERVAL_SECONDS = int(os.getenv("DETECTION_INTERVAL_SECONDS", "10"))
REQUEST_RATE_THRESHOLD = int(os.getenv("REQUEST_RATE_THRESHOLD", "50"))

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
logs_collection = db["api_logs"]
alerts_collection = db["api_alerts"]


def run_detection():
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Running anomaly detection...")
    one_hour_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    logs = list(logs_collection.find({"timestamp": {"$gte": one_hour_ago}}))

    if not logs:
        return

    df = pd.DataFrame(logs)

    ip_stats = df.groupby("ip_address").agg(
        request_count=("timestamp", "count"),
        unique_endpoints=("endpoint", "nunique"),
    ).reset_index()

    suspicious_ips = ip_stats[ip_stats["request_count"] > REQUEST_RATE_THRESHOLD]["ip_address"].tolist()
    for ip in suspicious_ips:
        create_alert(
            ip,
            "Rule-based",
            f"High request rate detected (>{REQUEST_RATE_THRESHOLD} req/hr).",
            severity="high",
            confidence=95,
        )

    if len(ip_stats) >= 3:
        features = ip_stats[["request_count", "unique_endpoints"]]
        model = IsolationForest(contamination=0.1, random_state=42)
        ip_stats["anomaly"] = model.fit_predict(features)

        ml_anomalies = ip_stats[ip_stats["anomaly"] == -1]["ip_address"].tolist()
        for ip in ml_anomalies:
            create_alert(
                ip,
                "ML-based",
                "Isolation Forest detected unusual traffic pattern.",
                severity="medium",
                confidence=72,
            )


def create_alert(ip, alert_type, reason, severity="medium", confidence=70):
    five_mins_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    recent_alert = alerts_collection.find_one({
        "ip_address": ip,
        "reason": reason,
        "timestamp": {"$gte": five_mins_ago},
    })
    if not recent_alert:
        print(f"ALERT: {ip} - {reason}")
        alerts_collection.insert_one({
            "id": str(uuid.uuid4()),
            "ip_address": ip,
            "type": alert_type,
            "reason": reason,
            "severity": severity,
            "confidence": confidence,
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "status": "new",
            "ai_insight": "",
        })


if __name__ == "__main__":
    while True:
        run_detection()
        time.sleep(DETECTION_INTERVAL_SECONDS)
