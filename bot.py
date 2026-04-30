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

def triage_node(state: GraphState) -> GraphState:
    """Extracts a StrategyBrief based on contexts."""
    if not state.get("merchant") or not state.get("trigger") or not instructor_client:
        return state
        
    prompt = f"""
    You are an expert engagement strategist for magicpin. Create a StrategyBrief.
    
    Trigger: {state['trigger'].model_dump_json()}
    Merchant: {state['merchant'].model_dump_json()}
    """
    if state.get("category"):
        prompt += f"\nCategory Voice: {state['category'].voice.model_dump_json()}"
    if state.get("customer"):
        prompt += f"\nCustomer: {state['customer'].model_dump_json()}"
        
    strategy = instructor_client.chat.completions.create(
        model=MODEL_NAME,
        response_model=StrategyBrief,
        messages=[
            {"role": "system", "content": "Analyze the context and define the strategy."},
            {"role": "user", "content": prompt}
        ]
    )
    return {"strategy_brief": strategy, **state}

def composer_node(state: GraphState) -> GraphState:
    """Drafts the message based on the StrategyBrief."""
    if not state.get("strategy_brief") or not instructor_client:
        return state
        
    prompt = f"""
    Draft a WhatsApp message following this strategy strictly.
    Strategy: {state['strategy_brief'].model_dump_json()}
    """
    
    if state.get("critic_scorecard") and not state["critic_scorecard"].passed:
        prompt += f"\n\nCRITICAL FEEDBACK FROM PREVIOUS DRAFT: {state['critic_scorecard'].feedback}. YOU MUST FIX THIS."

    draft = instructor_client.chat.completions.create(
        model=MODEL_NAME,
        response_model=ComposedMessage,
        messages=[
            {"role": "system", "content": "You are Vera. Write WhatsApp messages strictly adhering to the grading dimensions and rationale-first prompting."},
            {"role": "user", "content": prompt}
        ]
    )
    return {"draft_message": draft, **state}

def critic_node(state: GraphState) -> GraphState:
    """Scores the draft. Returns feedback."""
    if not state.get("draft_message") or not instructor_client:
        return state
        
    prompt = f"""
    Evaluate the following draft message out of 10 for each dimension.
    Draft: {state['draft_message'].model_dump_json()}
    Original Strategy: {state['strategy_brief'].model_dump_json()}
    """
    
    scorecard = instructor_client.chat.completions.create(
        model=MODEL_NAME,
        response_model=CriticScorecard,
        messages=[
            {"role": "system", "content": "You are a strict Judge. Grade the message on Decision Quality, Specificity, Category Fit, Merchant Fit, and Engagement."},
            {"role": "user", "content": prompt}
        ]
    )
    
    # Check if passed
    all_passed = (scorecard.decision_quality_score >= 9 and 
                  scorecard.specificity_score >= 9 and 
                  scorecard.category_fit_score >= 9 and 
                  scorecard.merchant_fit_score >= 9 and 
                  scorecard.engagement_score >= 9)
    scorecard.passed = all_passed
                  
    return {"critic_scorecard": scorecard, "retries": state.get("retries", 0) + 1, **state}

def route_critic(state: GraphState) -> str:
    """Decides whether to retry or end."""
    if not state.get("critic_scorecard"):
        return END
        
    if state["critic_scorecard"].passed or state.get("retries", 0) >= 2:
        return END
        
    return "composer"

# Build the Graph
workflow = StateGraph(GraphState)
workflow.add_node("triage", triage_node)
workflow.add_node("composer", composer_node)
workflow.add_node("critic", critic_node)

workflow.set_entry_point("triage")
workflow.add_edge("triage", "composer")
workflow.add_edge("composer", "critic")
workflow.add_conditional_edges("critic", route_critic, {"composer": "composer", END: END})

tcc_app = workflow.compile()


def process_tick(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]],
    trg_id: str
) -> Optional[Dict[str, Any]]:
    """
    Called every time the judge says a trigger is active.
    Runs the TCC Pipeline.
    """
    if not merchant or not trigger:
        return None
        
    # Convert dicts to Pydantic models (graceful fallback if keys missing)
    try:
        cat_model = CategoryContext(**category) if category else None
        merch_model = MerchantContext(**merchant) if merchant else None
        trig_model = TriggerContext(**trigger) if trigger else None
        cust_model = CustomerContext(**customer) if customer else None
    except Exception as e:
        print(f"Pydantic Validation Error: {e}")
        return None # Graceful fail on bad context
        
    if not merch_model or not trig_model:
        return None

    # Run LangGraph
    initial_state = {
        "category": cat_model,
        "merchant": merch_model,
        "trigger": trig_model,
        "customer": cust_model,
        "strategy_brief": None,
        "draft_message": None,
        "critic_scorecard": None,
        "retries": 0
    }
    
    try:
        final_state = tcc_app.invoke(initial_state)
    except Exception as e:
        print(f"LLM/Graph Error: {e}")
        return None
        
    draft = final_state.get("draft_message")
    if not draft:
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
        "rationale": draft.rationale
    }
