# AI Agent Constraints & Strategy (TCC Pipeline)

This document contains all the crucial constraints, anti-patterns, and the grading rubric from the Magicpin documentation (`challenge-brief.md`, `challenge-testing-brief.md`, `engagement-design.md`, `engagement-research.md`). This is the "bible" for our TCC Pipeline implementation.

## 1. The Core Architecture: LangGraph + Instructor
To guarantee performance, we use a deterministic **LangGraph** orchestration loop combined with **Instructor** (for structured Pydantic outputs).

1.  **Triage Engine (Decision Quality):** Evaluates the Trigger + Merchant State to create a strict "Strategy Brief" before the LLM writes anything.
2.  **Composer (Drafting):** Uses a *Rationale-First* prompting strategy. The LLM must explicitly prove it is following the dimensions before outputting the message body.
3.  **Critic Loop (LangGraph State Machine):** A separate Judge LLM grades the draft out of 10. If any dimension scores < 9, LangGraph routes it back to the Composer with fix instructions.
4.  **Grounding Filter (Instructor + Python):** A final deterministic check ensures exact numbers/dates from the JSON appear in the text, preventing hallucination penalties.

## 2. Testing Harness Constraints (Stateful & Time-Bound)
- **Stateful Memory:** We do not query MongoDB, Redis, or `aryan_client`. The testing harness pushes all data to `/v1/context`. We must rely **only** on our in-memory `contexts` dictionary.
- **Strict 30-Second Timeout:** The `/v1/tick` and `/v1/reply` endpoints must return within 30 seconds. If our LangGraph Critic loop takes too long, we will be penalized. (Set a `max_retries` limit on the graph).
- **Idempotency & Versioning:** We must honor the `version` field when context is pushed. Stale context versions should be rejected.

## 3. The 5 Grading Dimensions (Target: 10/10)
1.  **Decision Quality:** The bot must explicitly understand *why* it is messaging right now (the `TriggerContext`). Don't just send a generic reminder; tie it to the specific event (e.g., a drop in performance, a new DCI regulation, a weather event).
2.  **Specificity:** Anchor on concrete, verifiable facts from the provided JSON. Use exact numbers (e.g., `ctr: 0.021`), dates, and headlines. **Never use generic placeholders or "10% off" if a real catalog price exists.**
3.  **Category Fit:** Match the voice of the business. Clinical categories (Dentists) require a technical, peer-like tone and prohibit "hype" words ("guaranteed", "cure"). Non-clinical categories (Salons) can be more visual and casual.
4.  **Merchant Fit:** Personalize the message using the exact metrics, offer catalog prices (e.g., "Dental Cleaning @ ₹299"), and prior conversation behavior of that specific merchant.
5.  **Engagement Compulsion:** Give one strong reason to reply now. Use levers: Proof, Urgency, Curiosity. Include a **low-effort next action**.

## 4. Hard Constraints & Anti-Patterns
- **Single CTA:** Every message must contain exactly ONE call-to-action (e.g., a binary YES/STOP). Never offer multiple choices like "Reply YES for X, NO for Y".
- **No Hallucinations:** You must ONLY use the data provided in the contexts. Never fabricate external research or competitor names. The harness tests this heavily during the "Adaptive context injection" phase.
- **Voice Match:** Hindi-English code-mix (Hinglish) is highly preferred for Indian merchants.
- **Politeness / Preambles:** Keep messages concise. Avoid long preambles ("I hope this message finds you well...").
- **Auto-Reply Detection:** If the merchant replies with the exact same canned text multiple times, LangGraph must detect the loop and gracefully end the conversation (`action: end`).
- **Intent Handoff:** If a merchant says "I want to join" or "Let's do it," immediately switch from pitch mode to action mode. Do not ask another qualification question.
