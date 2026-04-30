from pydantic import BaseModel, Field
from typing import List, Optional, TypedDict
from .input_models import CategoryContext, MerchantContext, TriggerContext, CustomerContext
from .output_models import ComposedMessage

class StrategyBrief(BaseModel):
    core_objective: str = Field(..., description="The main goal of this message based strictly on the trigger context.")
    key_facts: List[str] = Field(..., description="Specific numbers, dates, or prices from the context to include to ensure 10/10 Specificity.")
    tone_guidance: str = Field(..., description="Instructions on the tone (e.g., clinical vs casual) based on the Category voice profile.")
    target_audience: str = Field(..., description="Who this is aimed at (merchant vs customer).")

class CriticScorecard(BaseModel):
    decision_quality_score: int = Field(..., ge=1, le=10, description="Does the message explicitly anchor on the trigger event? 10=Explicit, 1=Generic.")
    specificity_score: int = Field(..., ge=1, le=10, description="Are exact numbers, dates, or prices used from context? 10=Exact, 1=Generic placeholders.")
    category_fit_score: int = Field(..., ge=1, le=10, description="Does the tone match the category voice profile? 10=Perfect match, 1=Tone violation.")
    merchant_fit_score: int = Field(..., ge=1, le=10, description="Is the message highly personalized to this specific merchant's data? 10=Highly personalized, 1=Generic.")
    engagement_score: int = Field(..., ge=1, le=10, description="Does it give a strong reason to reply now with a single clear CTA? 10=Compelling, 1=Weak or multiple CTAs.")
    feedback: str = Field(..., description="Constructive feedback for the Composer if any score is < 9. Otherwise, 'Passed'.")
    passed: bool = Field(..., description="True if ALL scores are 9 or 10. False otherwise.")

class GraphState(TypedDict):
    category: Optional[CategoryContext]
    merchant: Optional[MerchantContext]
    trigger: Optional[TriggerContext]
    customer: Optional[CustomerContext]
    strategy_brief: Optional[StrategyBrief]
    draft_message: Optional[ComposedMessage]
    critic_scorecard: Optional[CriticScorecard]
    retries: int
