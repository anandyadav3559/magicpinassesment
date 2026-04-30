from pydantic import BaseModel, Field
from typing import Literal

class ComposedMessage(BaseModel):
    rationale: str = Field(..., description="Explain why this message explicitly meets the 5 grading dimensions.")
    body: str = Field(..., description="The exact WhatsApp message text. Must be highly specific and match the voice.")
    cta: str = Field(..., description="The exact single call to action, e.g., 'Reply YES' or 'Reply STOP'. Must not have multiple choices.")
    send_as: Literal["vera", "merchant_on_behalf"] = Field(..., description="Whether Vera is sending to the merchant, or on behalf of the merchant to a customer.")
    suppression_key: str = Field(..., description="The suppression key from the trigger to prevent duplicate sends.")
