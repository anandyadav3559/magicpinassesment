import os
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple
import uvicorn

import bot
import conversation_handlers

app = FastAPI(title="Magicpin AI Challenge - Stateful Bot")
START = time.time()

# In-memory stores (per testing brief requirements)
# (scope, context_id) -> {"version": int, "payload": dict}
contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}
# conversation_id -> [{"from": str, "msg": str}]
conversations: Dict[str, List[Dict[str, str]]] = {}


@app.get("/v1/healthz")
async def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        counts[scope] = counts.get(scope, 0) + 1
    return {"status": "ok", "uptime_seconds": int(time.time() - START), "contexts_loaded": counts}


@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "TCC Innovators",
        "team_members": ["Magicpin Challenger"],
        "model": "groq-llama3-70b",
        "approach": "Triage-Critic-Composer (TCC) Pipeline via LangGraph",
        "contact_email": "team@example.com",
        "version": "1.0.0",
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }


class CtxBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str

@app.post("/v1/context")
async def push_context(body: CtxBody):
    key = (body.scope, body.context_id)
    cur = contexts.get(key)
    
    # Idempotent version check
    if cur and cur["version"] >= body.version:
        return {"accepted": False, "reason": "stale_version", "current_version": cur["version"]}
        
    contexts[key] = {"version": body.version, "payload": body.payload}
    return {
        "accepted": True, 
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }


class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = []

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []
    
    for trg_id in body.available_triggers:
        trg = contexts.get(("trigger", trg_id), {}).get("payload")
        if not trg: 
            continue
            
        merchant_id = trg.get("merchant_id")
        merchant = contexts.get(("merchant", merchant_id), {}).get("payload")
        
        category = None
        if merchant:
            category_slug = merchant.get("category_slug") or trg.get("payload", {}).get("category")
            category = contexts.get(("category", category_slug), {}).get("payload")
            
        if not (merchant and category): 
            continue
            
        customer_id = trg.get("customer_id")
        customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None

        # Call our TCC pipeline logic
        action = bot.process_tick(
            category=category,
            merchant=merchant,
            trigger=trg,
            customer=customer,
            trg_id=trg_id
        )
        
        if action:
            actions.append(action)
            
    return {"actions": actions}


class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    conversations.setdefault(body.conversation_id, []).append({
        "from": body.from_role, 
        "msg": body.message
    })
    
    state = conversations[body.conversation_id]
    
    merchant = contexts.get(("merchant", body.merchant_id), {}).get("payload") if body.merchant_id else None
    
    category = None
    if merchant:
        category_slug = merchant.get("category_slug")
        category = contexts.get(("category", category_slug), {}).get("payload")
        
    customer = contexts.get(("customer", body.customer_id), {}).get("payload") if body.customer_id else None
    
    trigger = None
    if body.merchant_id:
        # Find the first trigger for this merchant to provide context
        for (scope, ctx_id), ctx in contexts.items():
            if scope == "trigger" and ctx["payload"].get("merchant_id") == body.merchant_id:
                trigger = ctx["payload"]
                break
    
    # Call our conversational logic
    action = conversation_handlers.process_reply(state, body, merchant, category, customer, trigger)
    
    return action

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # reload=True is removed for production deployment (Railway)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
