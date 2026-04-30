import argparse
import requests
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_URL = "http://0.0.0.0:8000"
DATASET_DIR = Path("../dataset")
LOG_FILE = "test_run.log"

def log(msg):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def test_healthz():
    log("Testing /v1/healthz...")
    try:
        r = requests.get(f"{BASE_URL}/v1/healthz")
        log(f"Response: {r.status_code} {r.text}")
    except Exception as e:
        log(f"Failed: {e}")

def test_metadata():
    log("Testing /v1/metadata...")
    try:
        r = requests.get(f"{BASE_URL}/v1/metadata")
        log(f"Response: {r.status_code} {r.text}")
    except Exception as e:
        log(f"Failed: {e}")

def push_context(scope, ctx_id, payload):
    body = {
        "scope": scope,
        "context_id": ctx_id,
        "version": 1,
        "payload": payload,
        "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    r = requests.post(f"{BASE_URL}/v1/context", json=body)
    if r.status_code != 200:
        log(f"Failed to push {scope}/{ctx_id}: {r.status_code} {r.text}")

def load_and_push_dataset():
    log("Loading and pushing dataset...")
    
    # 1. Categories
    cat_dir = DATASET_DIR / "categories"
    if cat_dir.exists():
        for f in cat_dir.glob("*.json"):
            data = json.loads(f.read_text())
            slug = data.get("slug", f.stem)
            push_context("category", slug, data)
            log(f"Pushed category: {slug}")

    # 2. Merchants
    merch_file = DATASET_DIR / "merchants_seed.json"
    if merch_file.exists():
        data = json.loads(merch_file.read_text())
        merchants = data.get("merchants", [])
        for m in merchants:
            m_id = m.get("merchant_id")
            push_context("merchant", m_id, m)
        log(f"Pushed {len(merchants)} merchants")

    # 3. Customers
    cust_file = DATASET_DIR / "customers_seed.json"
    if cust_file.exists():
        data = json.loads(cust_file.read_text())
        customers = data.get("customers", [])
        for c in customers:
            c_id = c.get("customer_id")
            push_context("customer", c_id, c)
        log(f"Pushed {len(customers)} customers")

    # 4. Triggers
    trig_file = DATASET_DIR / "triggers_seed.json"
    triggers_list = []
    if trig_file.exists():
        data = json.loads(trig_file.read_text())
        triggers = data.get("triggers", [])
        for t in triggers:
            t_id = t.get("id")
            triggers_list.append(t_id)
            push_context("trigger", t_id, t)
        log(f"Pushed {len(triggers)} triggers")
        
    return triggers_list

def test_tick(trigger_ids=None):
    log("Testing /v1/tick...")
    if not trigger_ids:
        trig_file = DATASET_DIR / "triggers_seed.json"
        if trig_file.exists():
            data = json.loads(trig_file.read_text())
            # Just send the first 3 by default
            trigger_ids = [t.get("id") for t in data.get("triggers", [])][:3]
        else:
            trigger_ids = []

    body = {
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "available_triggers": trigger_ids
    }
    r = requests.post(f"{BASE_URL}/v1/tick", json=body)
    log(f"Response: {r.status_code} {r.text}")
    
    try:
        data = r.json()
        return data.get("actions", [])
    except:
        return []

def test_reply(conversation_id, message):
    log(f"Testing /v1/reply for conv: {conversation_id} with msg: '{message}'...")
    body = {
        "conversation_id": conversation_id,
        "from_role": "merchant",
        "message": message,
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "turn_number": 1
    }
    r = requests.post(f"{BASE_URL}/v1/reply", json=body)
    log(f"Response: {r.status_code} {r.text}")

def run_all():
    with open(LOG_FILE, "w") as f:
        f.write("--- Starting Full Test Suite ---\n")
        
    test_healthz()
    test_metadata()
    
    triggers = load_and_push_dataset()
    
    log("Checking /v1/healthz after load...")
    test_healthz()
    
    actions = test_tick(triggers[:3] if triggers else None)
    
    if actions:
        # Test reply on the first conversation generated
        first_action = actions[0]
        conv_id = first_action.get("conversation_id")
        if conv_id:
            test_reply(conv_id, "Yes, please send me more information.")
            
    log("--- Test Run Complete ---")

def main():
    parser = argparse.ArgumentParser(description="Modular test harness for Magicpin bot.")
    subparsers = parser.add_subparsers(dest="command", help="Endpoint to test")

    subparsers.add_parser("healthz", help="Test /v1/healthz")
    subparsers.add_parser("metadata", help="Test /v1/metadata")
    subparsers.add_parser("context", help="Push dataset to /v1/context")
    subparsers.add_parser("tick", help="Simulate a /v1/tick (using top 3 dataset triggers)")
    
    reply_parser = subparsers.add_parser("reply", help="Send a /v1/reply message")
    reply_parser.add_argument("--conv-id", required=True, help="The conversation_id to reply to")
    reply_parser.add_argument("--message", default="Yes please!", help="The message from the merchant")

    subparsers.add_parser("all", help="Run the full sequence (health, context, tick, reply)")

    args = parser.parse_args()

    if args.command == "healthz":
        test_healthz()
    elif args.command == "metadata":
        test_metadata()
    elif args.command == "context":
        load_and_push_dataset()
    elif args.command == "tick":
        test_tick()
    elif args.command == "reply":
        test_reply(args.conv_id, args.message)
    elif args.command == "all" or args.command is None:
        run_all()

if __name__ == "__main__":
    main()
