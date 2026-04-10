import argparse
import os
import random
import threading
import time

import requests
from pymongo import MongoClient


class Simulator:
    def __init__(
        self,
        base_url,
        normal_workers,
        min_delay,
        max_delay,
        attack_interval,
        mongo_uri=None,
        mongo_db="sentinel_db",
        control_id="default",
    ):
        self.base_url = base_url.rstrip("/")
        self.normal_workers = normal_workers
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.attack_interval = attack_interval
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.control_id = control_id

        self.normal_ips = ["192.168.1.10", "10.0.0.5", "172.16.0.2"]
        self.attacker_ip = "99.99.99.99"
        self.endpoints = [
            ("/login", lambda: {"username": random.choice(["admin", "user1", "user2"])}),
            ("/payment", lambda: {"amount": random.randint(10, 500)}),
            ("/add-to-cart", lambda: {"item_id": random.randint(1, 100)}),
        ]

        self.stop_event = threading.Event()
        self.running_event = threading.Event()
        self.attack_active_event = threading.Event()
        self.lock = threading.Lock()

        self.normal_count = 0
        self.attack_count = 0
        self.start_time = time.time()
        self.mongo_collection = None

    def _ensure_control_doc(self):
        if self.mongo_collection is None:
            return

        self.mongo_collection.update_one(
            {"control_id": self.control_id},
            {
                "$setOnInsert": {
                    "control_id": self.control_id,
                    "running": False,
                    "attack_enabled": False,
                    "normal_workers": self.normal_workers,
                    "normal_min_delay": self.min_delay,
                    "normal_max_delay": self.max_delay,
                    "attack_interval": self.attack_interval,
                    "updated_at": time.time(),
                }
            },
            upsert=True,
        )

    def _update_control_doc(self, values):
        if self.mongo_collection is None:
            return

        values = dict(values)
        values["updated_at"] = time.time()
        self.mongo_collection.update_one(
            {"control_id": self.control_id},
            {
                "$set": values,
                "$setOnInsert": {"control_id": self.control_id},
            },
            upsert=True,
        )

    def _sync_control_loop(self):
        while not self.stop_event.is_set():
            try:
                doc = self.mongo_collection.find_one({"control_id": self.control_id}) or {}
                if doc.get("running"):
                    self.running_event.set()
                else:
                    self.running_event.clear()

                if doc.get("attack_enabled"):
                    self.attack_active_event.set()
                else:
                    self.attack_active_event.clear()

                # Allow remote runtime tuning.
                self.min_delay = float(doc.get("normal_min_delay", self.min_delay))
                self.max_delay = float(doc.get("normal_max_delay", self.max_delay))
                self.attack_interval = float(doc.get("attack_interval", self.attack_interval))
            except Exception:
                pass

            time.sleep(1)

    def _normal_traffic(self):
        while not self.stop_event.is_set():
            if not self.running_event.is_set():
                time.sleep(0.2)
                continue

            ip = random.choice(self.normal_ips)
            endpoint, payload_gen = random.choice(self.endpoints)
            try:
                requests.post(
                    f"{self.base_url}{endpoint}",
                    json=payload_gen(),
                    headers={"X-Forwarded-For": ip},
                    timeout=2,
                )
                with self.lock:
                    self.normal_count += 1
            except Exception:
                pass
            time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _attacker_traffic(self):
        while not self.stop_event.is_set():
            if not self.running_event.is_set() or not self.attack_active_event.is_set():
                time.sleep(0.2)
                continue

            try:
                requests.post(
                    f"{self.base_url}/login",
                    json={"username": "admin"},
                    headers={"X-Forwarded-For": self.attacker_ip},
                    timeout=2,
                )
                with self.lock:
                    self.attack_count += 1
            except Exception:
                pass
            time.sleep(self.attack_interval)

    def _delayed_attack_start(self, delay_seconds):
        deadline = time.time() + delay_seconds
        while not self.stop_event.is_set() and time.time() < deadline:
            time.sleep(0.2)

        if not self.stop_event.is_set():
            self.attack_active_event.set()
            print("[sim] Attack traffic is now ON.")

    def print_status(self):
        elapsed = int(time.time() - self.start_time)
        with self.lock:
            total = self.normal_count + self.attack_count
            normal = self.normal_count
            attack = self.attack_count

        print(
            f"[sim] status | elapsed={elapsed}s total={total} normal={normal} "
            f"attack={attack} attack_on={self.attack_active_event.is_set()}"
        )

    def _command_loop(self):
        while not self.stop_event.is_set():
            try:
                cmd = input().strip().lower()
            except EOFError:
                return
            except Exception:
                continue

            if cmd == "status":
                self.print_status()
            elif cmd == "start":
                self.running_event.set()
                self._update_control_doc({"running": True})
                print("[sim] Traffic generation enabled.")
            elif cmd == "pause":
                self.running_event.clear()
                self.attack_active_event.clear()
                self._update_control_doc({"running": False, "attack_enabled": False})
                print("[sim] Traffic generation paused.")
            elif cmd == "attack on":
                self.attack_active_event.set()
                self._update_control_doc({"attack_enabled": True})
                print("[sim] Attack traffic enabled.")
            elif cmd == "attack off":
                self.attack_active_event.clear()
                self._update_control_doc({"attack_enabled": False})
                print("[sim] Attack traffic disabled.")
            elif cmd == "stop":
                self.stop_event.set()
            elif cmd == "help":
                print("[sim] Commands: status | start | pause | attack on | attack off | stop | help")
            elif cmd:
                print(f"[sim] Unknown command: {cmd}. Type 'help'.")

    def run(self, attack_delay, enable_attack, auto_stop_seconds):
        print(f"[sim] Starting simulator against {self.base_url}")
        print("[sim] Commands: status | start | pause | attack on | attack off | stop | help")

        if self.mongo_uri:
            mongo_client = MongoClient(self.mongo_uri)
            self.mongo_collection = mongo_client[self.mongo_db]["simulator_control"]
            self._ensure_control_doc()
            threading.Thread(target=self._sync_control_loop, daemon=True).start()
            print(f"[sim] Remote control mode enabled (mongo control_id={self.control_id}).")
        else:
            # Standalone mode keeps the simulator idle until traffic is started manually.
            print("[sim] Standalone mode enabled (traffic stays idle until 'start' is issued).")

        for _ in range(self.normal_workers):
            threading.Thread(target=self._normal_traffic, daemon=True).start()

        threading.Thread(target=self._attacker_traffic, daemon=True).start()

        if enable_attack and not self.mongo_uri:
            print(f"[sim] Attack traffic scheduled in {attack_delay} seconds.")
            threading.Thread(target=self._delayed_attack_start, args=(attack_delay,), daemon=True).start()
        elif enable_attack:
            print("[sim] Attack traffic is controlled remotely and will stay off until enabled from the dashboard.")
        else:
            print("[sim] Attack traffic is disabled at startup.")

        threading.Thread(target=self._command_loop, daemon=True).start()

        try:
            while not self.stop_event.is_set():
                if auto_stop_seconds > 0 and (time.time() - self.start_time) >= auto_stop_seconds:
                    print(f"[sim] Auto-stop reached ({auto_stop_seconds}s). Stopping simulator.")
                    self.stop_event.set()
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[sim] Keyboard interrupt received. Stopping simulator.")
            self.stop_event.set()

        self.print_status()
        print("[sim] Simulator stopped.")


def parse_args():
    parser = argparse.ArgumentParser(description="SentinelAI controllable traffic simulator")
    parser.add_argument("--base-url", default="http://localhost:5000/api", help="Backend API base URL")
    parser.add_argument("--normal-workers", type=int, default=3, help="Number of normal traffic threads")
    parser.add_argument("--normal-min-delay", type=float, default=1.0, help="Min delay between normal requests")
    parser.add_argument("--normal-max-delay", type=float, default=3.0, help="Max delay between normal requests")
    parser.add_argument("--attack-interval", type=float, default=0.1, help="Delay between attack requests")
    parser.add_argument("--attack-delay", type=int, default=15, help="Seconds before attack auto-start")
    parser.add_argument("--disable-attack", action="store_true", help="Start simulator with attack disabled")
    parser.add_argument("--auto-stop", type=int, default=0, help="Auto-stop after N seconds (0 means never)")
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
        help="Enable remote control by reading simulator state from MongoDB",
    )
    parser.add_argument("--mongo-db", default="sentinel_db", help="MongoDB database name for simulator control")
    parser.add_argument("--control-id", default="default", help="Control document ID")
    parser.add_argument("--standalone", action="store_true", help="Do not use remote MongoDB control")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sim = Simulator(
        base_url=args.base_url,
        normal_workers=args.normal_workers,
        min_delay=args.normal_min_delay,
        max_delay=args.normal_max_delay,
        attack_interval=args.attack_interval,
        mongo_uri=None if args.standalone else args.mongo_uri,
        mongo_db=args.mongo_db,
        control_id=args.control_id,
    )
    sim.run(
        attack_delay=args.attack_delay,
        enable_attack=not args.disable_attack,
        auto_stop_seconds=args.auto_stop,
    )