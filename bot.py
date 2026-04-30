import os
import uuid
from typing import Dict, Any, Optional
from dotenv import load_dotenv

import groq
import instructor
from langgraph.graph import StateGraph, END

from models.input_models import CategoryContext, MerchantContext, TriggerContext, CustomerContext
from models.internal_models import GraphState, StrategyBrief, CriticScorecard
from models.output_models import ComposedMessage

load_dotenv()

# Initialize Groq client with Instructor
# groq automatically picks up GROQ_API_KEY from environment
try:
    client = groq.Groq()
    instructor_client = instructor.from_groq(client, mode=instructor.Mode.TOOLS)
except Exception as e:
    print(f"Warning: Groq client failed to initialize (check GROQ_API_KEY). {e}")
    instructor_client = None

MODEL_NAME = "llama-3.3-70b-versatile"

# Remove LangGraph logic and replace with direct CoT call
def process_tick(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]],
    trg_id: str
) -> Optional[Dict[str, Any]]:
    """
    Called every time the judge says a trigger is active.
    Runs a single Chain-of-Thought LLM call to draft the optimal message.
    """
    if not merchant or not trigger or not instructor_client:
        return None
        
    try:
        cat_model = CategoryContext(**category) if category else None
        merch_model = MerchantContext(**merchant) if merchant else None
        trig_model = TriggerContext(**trigger) if trigger else None
        cust_model = CustomerContext(**customer) if customer else None
    except Exception as e:
        print(f"Pydantic Validation Error: {e}")
        return None
        
    if not merch_model or not trig_model:
        return None

    # Construct the supercharged prompt
    from models.internal_models import CoTDraftMessage

    prompt = f"""
    You are an expert engagement strategist for magicpin. Compose a WhatsApp message based on this trigger.
    
    ### CONTEXT ###
    Trigger Event (Why we are messaging NOW):
    {trig_model.model_dump_json()}
    
    Merchant (Who we are messaging or acting on behalf of):
    {merch_model.model_dump_json()}
    """
    
    if cat_model:
        prompt += f"""
    Category Voice & Taboos (STRICTLY ADHERE TO THIS):
    Tone: {cat_model.voice.tone}
    Allowed Vocabulary: {cat_model.voice.vocab_allowed}
    TABOO WORDS (DO NOT USE): {cat_model.voice.vocab_taboo}
    """
    
    if cust_model:
        prompt += f"\nCustomer (Who we are messaging on behalf of the merchant):\n{cust_model.model_dump_json()}"

    prompt += """
    ### GRADING RULES FOR 10/10 SCORE ###
    1. SPECIFICITY: You MUST include concrete numbers, dates, or prices from the context. Do not use generic placeholders like 'XX% off' if a specific price like '₹299' is available.
    2. CATEGORY FIT: You MUST adhere to the Category Voice. Do not use Taboo words.
    3. MERCHANT FIT: Personalize the message to the merchant. Use their actual performance numbers or offer names. Adhere to their language preference.
    4. TRIGGER RELEVANCE: Explicitly anchor the message on the trigger payload. State why you are messaging them today.
    5. ENGAGEMENT COMPULSION: End with a single, clear, low-friction CTA (e.g., 'Reply YES to proceed' or a simple question).
    """

    try:
        draft = instructor_client.chat.completions.create(
            model=MODEL_NAME,
            response_model=CoTDraftMessage,
            messages=[
                {"role": "system", "content": "You are Vera, magicpin's elite AI assistant. Think step-by-step to maximize your score across the 5 grading dimensions before drafting the exact WhatsApp message."},
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        print(f"LLM Error in process_tick: {e}")
        return None
        
    return {
        "conversation_id": f"conv_{merch_model.merchant_id}_{trg_id}_{uuid.uuid4().hex[:8]}",
        "merchant_id": merch_model.merchant_id, 
        "customer_id": cust_model.customer_id if cust_model else None,
        "send_as": draft.send_as, 
        "trigger_id": trg_id,
        "template_name": "tcc_dynamic",
        "template_params": [],
        "body": draft.body, 
        "cta": draft.cta,
        "suppression_key": draft.suppression_key,
        "rationale": f"CoT Strategy: {draft.reasoning_and_strategy[:200]}... | Rationale: {draft.rationale}"
    }
