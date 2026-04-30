# Magicpin AI Challenge: Stateful TCC Pipeline

This project implements a stateful **Triage-Critic-Composer (TCC)** architecture to solve the magicpin AI Challenge. It uses **Groq** for high-speed LLM inference, **Instructor** for enforcing strict Pydantic JSON schemas, and **LangGraph** for orchestrating the Critic-Loop.

## Project Setup

1.  Make sure you have `uv` installed.
2.  Set your Groq API Key in the `.env` file:
    ```
    GROQ_API_KEY=your_key_here
    ```
3.  Run the server:
    ```bash
    uv run main.py
    ```

## Exposed APIs (Testing Harness Contract)

The application exposes the 5 endpoints explicitly required by `challenge-testing-brief.md`. The judge acts as the orchestrator, pushing data to the bot and ticking time forward.

### 1. `POST /v1/context`
Receives context data pushed by the judge and stores it in-memory. Idempotent by version.
- **Request:** `{ "scope": "...", "context_id": "...", "version": 1, "payload": {...} }`
- **Response:** `{ "accepted": true, "ack_id": "...", "stored_at": "..." }`

### 2. `POST /v1/tick`
Called every simulated 5 minutes. Gives the bot a chance to initiate an outbound message.
- **Request:** `{ "now": "...", "available_triggers": ["..."] }`
- **Response:** `{ "actions": [ { "conversation_id": "...", "body": "...", "cta": "..." } ] }`

### 3. `POST /v1/reply`
Called when the merchant/customer responds to a message.
- **Request:** `{ "conversation_id": "...", "message": "...", "turn_number": 2, ... }`
- **Response:** `{ "action": "send" | "wait" | "end", "body": "...", "rationale": "..." }`

### 4. `GET /v1/healthz`
Liveness probe. Checks uptime and how many contexts are stored.
- **Response:** `{ "status": "ok", "uptime_seconds": ..., "contexts_loaded": {...} }`

### 5. `GET /v1/metadata`
Returns identity and bot version information.
- **Response:** `{ "team_name": "TCC Innovators", "model": "groq-llama3-70b", ... }`

## Testing with Postman

Since the testing harness is stateful, testing with Postman requires a specific sequence:

1. **Start the Server:** `uv run main.py`
2. **Push Context (POST `/v1/context`)**
   - URL: `http://localhost:8000/v1/context`
   - Body (JSON): 
     ```json
     {
       "scope": "merchant",
       "context_id": "m_001_drmeera",
       "version": 1,
       "payload": { "merchant_id": "m_001_drmeera", "identity": {"name": "Dr. Meera"} },
       "delivered_at": "2026-04-30T10:00:00Z"
     }
     ```
3. **Trigger a Message (POST `/v1/tick`)**
   - URL: `http://localhost:8000/v1/tick`
   - Body (JSON):
     ```json
     {
       "now": "2026-04-30T10:05:00Z",
       "available_triggers": ["trg_001"]
     }
     ```
   - **Important:** The response will contain a `conversation_id`. Copy this!
4. **Reply to the Bot (POST `/v1/reply`)**
   - URL: `http://localhost:8000/v1/reply`
   - Body (JSON):
     ```json
     {
       "conversation_id": "PASTE_CONVERSATION_ID_HERE",
       "from_role": "merchant",
       "message": "Yes, let's do it.",
       "received_at": "2026-04-30T10:10:00Z",
       "turn_number": 1
     }
     ```
