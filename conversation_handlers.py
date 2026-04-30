import os
import json
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import groq
import instructor

load_dotenv()

try:
    client = groq.Groq()
    instructor_client = instructor.from_groq(client, mode=instructor.Mode.TOOLS)
except Exception as e:
    instructor_client = None

MODEL_NAME = "llama-3.3-70b-versatile"

class ReplyIntent(BaseModel):
    action: Literal["send", "wait", "end"] = Field(..., description="Action to take. 'send' for replying, 'wait' if they asked for time, 'end' if they said no or it's an auto-reply loop.")
    body: str = Field(..., description="The message body to send if action is 'send'. Output an empty string if action is 'wait' or 'end'.")
    cta: str = Field(..., description="The CTA to send if action is 'send'. Output an empty string if action is 'wait' or 'end'.")
    rationale: str = Field(..., description="Why this action was chosen.")

merchant_history: Dict[str, List[str]] = {}

def detect_auto_reply_loop(merchant_id: str, current_msg: str) -> bool:
    """Detects if the merchant is sending the exact same message 3+ times across any conversation."""
    if not merchant_id:
        return False
    history = merchant_history.setdefault(merchant_id, [])
    history.append(current_msg)
    if len(history) >= 3:
        last_three = history[-3:]
        if last_three[0] == last_three[1] == last_three[2]:
            return True
    return False

def process_reply(state: List[Dict[str, str]], request_body: Any, merchant: Optional[Dict[str, Any]] = None, category: Optional[Dict[str, Any]] = None, customer: Optional[Dict[str, Any]] = None, trigger: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Given the conversation state so far, produce the reply using the LLM.
    Handles edge cases gracefully.
    """
    if not instructor_client:
        return {
            "action": "end",
            "rationale": "Gracefully failed: LLM client not initialized."
        }
        
    merchant_id = getattr(request_body, "merchant_id", None)
    latest_msg = state[-1]["msg"] if state else ""
        
    if merchant_id and detect_auto_reply_loop(merchant_id, latest_msg):
        return {
            "action": "end",
            "rationale": "Auto-reply loop detected. Gracefully exiting conversation."
        }

    # Format state for LLM
    transcript = ""
    for msg in state:
        transcript += f"{msg['from'].upper()}: {msg['msg']}\n"
        
    merchant_info = ""
    if merchant:
        offers = [o.get("title") for o in merchant.get("offers", []) if o.get("status") == "active"]
        merchant_info = f"\nYou are acting on behalf of {merchant.get('identity', {}).get('name', 'this merchant')}.\nActive Offers you can quote: {offers}"
    
    customer_info = ""
    if customer:
        customer_info = f"\nYou are talking to {customer.get('identity', {}).get('name', 'a customer')}."
        
    category_info = ""
    if category:
        tone = category.get("voice", {}).get("tone", "")
        patient_content = category.get("patient_content_library", [])
        category_info = f"\nUse this tone: {tone}.\nPatient Content Snippets you can use: {[c.get('title') for c in patient_content]}"
        
    trigger_info = ""
    if trigger:
        trigger_info = f"\nThe original context for this conversation was: {json.dumps(trigger.get('payload', {}))}."
        
    role_instruction = "merchant assistant"
    if getattr(request_body, "from_role", "") == "customer":
        role_instruction = "Vera, a helpful assistant acting on behalf of the merchant, talking to a customer."
    else:
        role_instruction = "Vera, an AI engagement strategist acting for magicpin, talking to the merchant."

    prompt = f"""
    Analyze this conversation transcript and decide the next action.
    Transcript:
    {transcript}
    
    Role: You are {role_instruction}. {merchant_info} {customer_info} {category_info} {trigger_info}
    
    CRITICAL GRADING RULES:
    1. INTENT TRANSITION: If the user says 'yes', 'let's do it', 'go ahead', or asks for the next step, you MUST switch to ACTION mode immediately. Do NOT ask more qualifying questions. Write the action outcome in the 'body' and choose 'send'.
    2. HOSTILITY HANDLING: If the user is hostile, abusive, or says "stop messaging me", you MUST choose 'end' action, and leave 'body' blank or write a very brief polite apology.
    3. SPECIFICITY: If you are sending a message, you MUST include concrete numbers, dates, or prices from the Active Offers or Context. Never hallucinate fake prices.
    4. AUTO-REPLIES: If the user's message looks like an automated generic response (e.g., 'Thank you for contacting us', 'Our team will respond shortly'), you MUST choose 'wait' or 'end'. Do not engage with auto-replies.
    """
    
    try:
        intent = instructor_client.chat.completions.create(
            model=MODEL_NAME,
            response_model=ReplyIntent,
            messages=[
                {"role": "system", "content": "You are a smart merchant assistant. Decide if you need to 'send' a reply, 'wait', or 'end' the conversation."},
                {"role": "user", "content": prompt}
            ]
        )
        
        response = {
            "action": intent.action,
            "rationale": intent.rationale
        }
        
        if intent.action == "send":
            response["body"] = intent.body
            response["cta"] = intent.cta
            
        return response
        
    except Exception as e:
        print(f"Reply LLM Error: {e}")
        return {
            "action": "end",
            "rationale": "Gracefully failed due to LLM error."
        }
