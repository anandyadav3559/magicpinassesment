from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# --- Category Context ---
class VoiceProfile(BaseModel):
    tone: str
    vocab_allowed: List[str]
    taboos: List[str]

class PeerStats(BaseModel):
    avg_rating: float
    avg_reviews: int
    avg_ctr: float
    scope: str

class CategoryContext(BaseModel):
    slug: str
    offer_catalog: List[Dict[str, Any]]
    voice: VoiceProfile
    peer_stats: PeerStats
    digest: List[Dict[str, Any]]
    patient_content_library: Optional[List[Dict[str, Any]]] = []
    seasonal_beats: Optional[List[Dict[str, Any]]] = []
    trend_signals: Optional[List[Dict[str, Any]]] = []

# --- Merchant Context ---
class Identity(BaseModel):
    name: str
    city: str
    locality: str
    place_id: str
    verified: bool
    languages: List[str]

class Subscription(BaseModel):
    status: str
    plan: str
    days_remaining: int

class PerformanceSnapshot(BaseModel):
    window_days: int
    views: int
    calls: int
    directions: int
    ctr: float
    delta_7d: Dict[str, float]

class CustomerAggregate(BaseModel):
    total_unique_ytd: int
    lapsed_180d_plus: int
    retention_6mo_pct: float

class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Subscription
    performance: PerformanceSnapshot
    offers: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    customer_aggregate: CustomerAggregate
    signals: List[str]

# --- Customer Context ---
class CustomerIdentity(BaseModel):
    name: str
    phone_redacted: str
    language_pref: str

class Relationship(BaseModel):
    first_visit: str
    last_visit: str
    visits_total: int
    services_received: List[str]

class Preferences(BaseModel):
    preferred_slots: Optional[str] = None
    channel: str

class Consent(BaseModel):
    opted_in_at: str
    scope: List[str]

class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship
    state: str
    preferences: Preferences
    consent: Consent

# --- Trigger Context ---
class TriggerContext(BaseModel):
    id: str
    scope: str
    kind: str
    source: str
    merchant_id: str
    customer_id: Optional[str] = None
    payload: Dict[str, Any]
    urgency: int
    suppression_key: str
    expires_at: str
