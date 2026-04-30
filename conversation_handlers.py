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

def process_reply(state: List[Dict[str, str]], request_body: Any) -> Dict[str, Any]:
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
        
    prompt = f"""
    Analyze this conversation transcript and decide the next action.
    Transcript:
    {transcript}
    
    CRITICAL RULE 1: If the merchant agrees, says 'let's do it', or asks for the next step, you MUST choose 'send'. 
    In the body, use action words like 'done', 'sending', 'draft', 'here', 'confirm', or 'proceed'. Do NOT ask qualifying questions if they already agreed.
    
    CRITICAL RULE 2: If the merchant's message looks like an automated generic response (e.g., 'Thank you for contacting us', 'Our team will respond shortly', 'out of office'), you MUST choose 'wait'. Do not reply to automated messages.
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
