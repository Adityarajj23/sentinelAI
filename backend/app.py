import datetime
import os
import time
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from bson.objectid import ObjectId
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentinel_db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_ADMIN_TOKEN = os.getenv("DEMO_ADMIN_TOKEN", "")
SIM_CONTROL_ID = os.getenv("SIM_CONTROL_ID", "default")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": [FRONTEND_ORIGIN]}})

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
logs_collection = db["api_logs"]
alerts_collection = db["api_alerts"]
sim_control_collection = db["simulator_control"]


def _control_projection(doc):
    if not doc:
        return {
            "control_id": SIM_CONTROL_ID,
            "running": False,
            "attack_enabled": False,
            "normal_workers": 3,
            "normal_min_delay": 1.0,
            "normal_max_delay": 3.0,
            "attack_interval": 0.1,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }

    doc.pop("_id", None)
    return {
        "control_id": doc.get("control_id", SIM_CONTROL_ID),
        "running": bool(doc.get("running", False)),
        "attack_enabled": bool(doc.get("attack_enabled", False)),
        "normal_workers": int(doc.get("normal_workers", 3)),
        "normal_min_delay": float(doc.get("normal_min_delay", 1.0)),
        "normal_max_delay": float(doc.get("normal_max_delay", 3.0)),
        "attack_interval": float(doc.get("attack_interval", 0.1)),
        "updated_at": doc.get("updated_at"),
    }


def get_or_create_control_state():
    doc = sim_control_collection.find_one({"control_id": SIM_CONTROL_ID})
    if doc:
        return _control_projection(doc)

    initial = _control_projection(None)
    sim_control_collection.update_one(
        {"control_id": SIM_CONTROL_ID},
        {"$setOnInsert": initial},
        upsert=True,
    )
    return get_or_create_control_state()


def require_demo_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not DEMO_MODE:
            return jsonify({"error": "Demo controls are disabled."}), 403
        if not DEMO_ADMIN_TOKEN:
            return jsonify({"error": "Demo admin token is not configured on server."}), 503

        provided = request.headers.get("X-Admin-Token", "")
        if provided != DEMO_ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized demo control access."}), 401
        return fn(*args, **kwargs)

    return wrapper

@app.before_request
def log_request():
    # Skip logging for CORS preflight
    if request.method == 'OPTIONS':
        return

    # Skip self-referential dashboard/control traffic so the graph only tracks simulated API activity.
    if request.path.startswith('/api/dashboard') or request.path.startswith('/api/explain') or request.path.startswith('/api/demo/'):
        return
        
    log_entry = {
        "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
        "endpoint": request.path,
        "method": request.method,
        "payload": request.get_json(silent=True) or {},
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "user_agent": request.headers.get("User-Agent"),
    }
    # Fire and forget logging
    try:
        logs_collection.insert_one(log_entry)
    except Exception as e:
        print(f"Failed to log request: {e}")

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    # Simulate processing time
    time.sleep(0.1)
    if username == "admin":
        return jsonify({"status": "success", "message": "Logged in successfully"})
    return jsonify({"status": "failure", "message": "Invalid credentials"}), 401

@app.route('/api/payment', methods=['POST'])
def payment():
    data = request.get_json(silent=True) or {}
    amount = data.get('amount', 0)
    time.sleep(0.2)
    if amount > 10000:
        return jsonify({"status": "flagged", "message": "Transaction requires manual review"}), 202
    return jsonify({"status": "success", "message": "Payment processed"}), 200

@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    time.sleep(0.05)
    return jsonify({"status": "success", "message": "Item added to cart"}), 200

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    window = (request.args.get('window') or '1h').strip().lower()
    window_hours_map = {
        '1h': 1,
        '5h': 5,
        '24h': 24,
    }
    bucket_minutes_map = {
        '1h': 1,
        '5h': 5,
        '24h': 15,
    }

    hours = window_hours_map.get(window, 1)
    bucket_minutes = bucket_minutes_map.get(window, 1)

    alerts = list(alerts_collection.find().sort("timestamp", -1).limit(20))
    for a in alerts:
        a['_id'] = str(a['_id'])
    
    since_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    logs = list(logs_collection.find({"timestamp": {"$gte": since_time}}))
    
    anomalies_count = alerts_collection.count_documents({"timestamp": {"$gte": since_time}})
    ips = set()
    reqs_by_bucket = {}
    
    for log in logs:
        ips.add(log.get('ip_address'))
        t = log.get('timestamp')
        if t:
            if t.tzinfo is None:
                t = t.replace(tzinfo=datetime.timezone.utc)
            local_t = t.astimezone()
            floored_minute = local_t.minute - (local_t.minute % bucket_minutes)
            bucket_time = local_t.replace(minute=floored_minute, second=0, microsecond=0)
            reqs_by_bucket[bucket_time] = reqs_by_bucket.get(bucket_time, 0) + 1
            
    label_format = '%H:%M' if hours <= 5 else '%d %b %H:%M'
    chart_data = [
        {"time": bucket.strftime(label_format), "reqs": count}
        for bucket, count in sorted(reqs_by_bucket.items())
    ]
    
    return jsonify({
        "stats": {
            "requests": len(logs),
            "anomalies": anomalies_count,
            "activeIps": len(ips)
        },
        "alerts": alerts,
        "chart": chart_data[-60:],
        "window": window,
    })

@app.route('/api/explain/<alert_id>', methods=['GET'])
def explain_anomaly(alert_id):
    try:
        alert = alerts_collection.find_one({"_id": ObjectId(alert_id)})
    except Exception:
        alert = alerts_collection.find_one({"id": alert_id})
        
    if not alert:
        return jsonify({"insight": "Alert not found or already dismissed."}), 404
        
    ip = alert.get("ip_address", "Unknown IP")
    reason = alert.get("reason", "")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"insight": f"Sentinel detected an attack from {ip} because of {reason}. To see real AI analysis, you must set GEMINI_API_KEY environment variable running the backend."})
        
    prompt = (
        f"You are a cybersecurity expert analyzing API traffic. We flagged an IP '{ip}' for '{reason}'. "
        "Explain why this exact behavior is dangerous and what type of attack it signifies in 2 short actionable sentences."
    )

    insight = None
    last_error = None
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            insight = (response.text or "").strip()
            if insight:
                break
            last_error = "Empty AI response"
        except Exception as e:
            last_error = str(e)
            # Retry transient model saturation errors.
            if "503" in last_error or "UNAVAILABLE" in last_error.upper():
                if attempt < max_attempts - 1:
                    time.sleep(1 + attempt)
                    continue
            break

    if not insight:
        if last_error and ("503" in last_error or "UNAVAILABLE" in last_error.upper()):
            insight = (
                f"Model temporarily unavailable due to high demand. Based on current signal '{reason}', "
                f"traffic from {ip} likely indicates automated abuse; keep monitoring and apply temporary rate-limits or IP blocking."
            )
        else:
            insight = f"Failed to generate insight via AI: {last_error or 'Unknown error'}"
              
    return jsonify({"insight": insight})


def find_alert_by_id(alert_id):
    try:
        alert = alerts_collection.find_one({"_id": ObjectId(alert_id)})
        if alert:
            return alert
    except Exception:
        pass

    return alerts_collection.find_one({"id": alert_id})


@app.route('/api/alerts/<alert_id>/status', methods=['PATCH'])
def update_alert_status(alert_id):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get('status', '')).strip().lower()
    allowed_statuses = {'new', 'investigating', 'resolved'}

    if status not in allowed_statuses:
        return jsonify({'error': 'Invalid alert status.'}), 400

    alert = find_alert_by_id(alert_id)
    if not alert:
        return jsonify({'error': 'Alert not found.'}), 404

    alerts_collection.update_one(
        {'_id': alert['_id']},
        {
            '$set': {
                'status': status,
                'updated_at': datetime.datetime.now(datetime.timezone.utc),
            }
        },
    )

    updated_alert = alerts_collection.find_one({'_id': alert['_id']})
    if updated_alert and '_id' in updated_alert:
        updated_alert['_id'] = str(updated_alert['_id'])

    return jsonify({
        'status': 'updated',
        'alert': updated_alert,
    })


@app.route('/api/demo/status', methods=['GET'])
def demo_status():
    state = get_or_create_control_state()
    updated_at = state.get("updated_at")
    if hasattr(updated_at, "isoformat"):
        state["updated_at"] = updated_at.isoformat()

    return jsonify({
        "demo_mode": DEMO_MODE,
        "state": state,
    })


@app.route('/api/demo/start', methods=['POST'])
@require_demo_admin
def demo_start():
    sim_control_collection.update_one(
        {"control_id": SIM_CONTROL_ID},
        {
            "$set": {
                "running": True,
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            },
            "$setOnInsert": {"control_id": SIM_CONTROL_ID},
        },
        upsert=True,
    )
    return jsonify({"status": "started", "message": "Simulator marked as running."})


@app.route('/api/demo/stop', methods=['POST'])
@require_demo_admin
def demo_stop():
    sim_control_collection.update_one(
        {"control_id": SIM_CONTROL_ID},
        {
            "$set": {
                "running": False,
                "attack_enabled": False,
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            },
            "$setOnInsert": {"control_id": SIM_CONTROL_ID},
        },
        upsert=True,
    )
    return jsonify({"status": "stopped", "message": "Simulator marked as stopped."})


@app.route('/api/demo/attack', methods=['POST'])
@require_demo_admin
def demo_attack_toggle():
    payload = request.get_json(silent=True) or {}
    enabled = bool(payload.get("enabled", False))

    sim_control_collection.update_one(
        {"control_id": SIM_CONTROL_ID},
        {
            "$set": {
                "attack_enabled": enabled,
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
            },
            "$setOnInsert": {
                "control_id": SIM_CONTROL_ID,
                "running": False,
            },
        },
        upsert=True,
    )
    return jsonify({
        "status": "updated",
        "message": "Attack traffic enabled." if enabled else "Attack traffic disabled.",
    })

if __name__ == '__main__':
    app.run(port=BACKEND_PORT, debug=FLASK_DEBUG)
