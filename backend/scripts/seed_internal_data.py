import asyncio
import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from services.recommendations import get_recommendation_store, Analyst, InternalView

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def deterministic_uuid(seed_string: str) -> str:
    """Generate a deterministic UUID from a string. Makes seeding idempotent."""
    hash_bytes = hashlib.md5(seed_string.encode()).digest()
    return str(uuid.UUID(bytes=hash_bytes))

# --- Mock Data ---

ANALYSTS = [
    {
        "name": "Sarah Chen",
        "team": "Global Technology",
        "coverage_sector": "Technology, AI, Semiconductors",
        "bio": "Senior Analyst with 12 years of experience covering US and Asian tech hardware. Ranked #1 for Semiconductor research in 2023. Known for early calls on AI infrastructure cycles.",
        "accuracy_score": 0.88
    },
    {
        "name": "Marcus Weber",
        "team": "Global Macro Strategy",
        "coverage_sector": "Fixed Income, FX, Rates",
        "bio": "Macro strategist focusing on central bank policy and inflation dynamics. Previously worked at the ECB. Takes a defensive, data-driven approach to duration management.",
        "accuracy_score": 0.76
    },
    {
        "name": "Elena Rossi",
        "team": "European Equities",
        "coverage_sector": "Consumer, Luxury, Retail",
        "bio": "Expert in European luxury and consumer trends. Takes high-conviction contrarian bets. Famous for predicting the 2022 luxury slowdown before the market consensus.",
        "accuracy_score": 0.82
    }
]

# History: We generate ~5 records per analyst (mix of active and historical)
def generate_recommendations(analysts_map):
    recos = []
    
    # Sarah Chen (Bullish Tech)
    recos.append({
        "analyst_id": analysts_map["Sarah Chen"],
        "asset_class": "equity",
        "sub_asset": "US Semiconductors",
        "stance": "Overweight",
        "rationale": "AI data center demand continues to outpace supply. Valuation premium is justified by 40% YoY earnings growth.",
        "horizon": "Strategic",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Sarah Chen"],
        "asset_class": "equity",
        "sub_asset": "Enterprise Software",
        "stance": "Neutral",
        "rationale": "Spending optimization in IT budgets limits upside near-term.",
        "horizon": "Tactical",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Sarah Chen"],
        "asset_class": "equity",
        "sub_asset": "Crypto-exposed Hardware",
        "stance": "Underweight",
        "rationale": "Mining profitability collapse will lead to inventory glut.",
        "horizon": "6-12m",
        "is_active": False,
        "outcome": "Correct (+22% Alpha)",
        "date": (datetime.utcnow() - timedelta(days=365)).isoformat()
    })

    # Marcus Weber (Defensive Macro)
    recos.append({
        "analyst_id": analysts_map["Marcus Weber"],
        "asset_class": "fixed_income",
        "sub_asset": "US Treasuries (10Y)",
        "stance": "Neutral",
        "rationale": "Yields at 4.2% fair value given sticky services inflation.",
        "horizon": "Tactical",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Marcus Weber"],
        "asset_class": "fixed_income",
        "sub_asset": "Eurozone Bonds",
        "stance": "Overweight",
        "rationale": "ECB cutting cycle will be faster than Fed due to weak German growth.",
        "horizon": "Strategic",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Marcus Weber"],
        "asset_class": "fx",
        "sub_asset": "USD/JPY",
        "stance": "Underweight",
        "rationale": "BoJ normalization will drive Yen appreciation despite carry costs.",
        "horizon": "6m",
        "is_active": False,
        "outcome": "Incorrect (-8% Loss)",
        "date": (datetime.utcnow() - timedelta(days=180)).isoformat()
    })

    # Elena Rossi (Consumer Contrarian)
    recos.append({
        "analyst_id": analysts_map["Elena Rossi"],
        "asset_class": "equity",
        "sub_asset": "European Luxury",
        "stance": "Underweight",
        "rationale": "China demand recovery is structurally impaired. Margins have peaked.",
        "horizon": "Strategic",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Elena Rossi"],
        "asset_class": "equity",
        "sub_asset": "Global Travel",
        "stance": "Overweight",
        "rationale": "Experience economy spending remains resilient among high-net-worth consumers.",
        "horizon": "Tactical",
        "is_active": True,
        "date": datetime.utcnow().isoformat()
    })
    recos.append({
        "analyst_id": analysts_map["Elena Rossi"],
        "asset_class": "equity",
        "sub_asset": "US Retail",
        "stance": "Overweight",
        "rationale": "Consumer savings buffer underappreciated by market.",
        "horizon": "3-6m",
        "is_active": False,
        "outcome": "Correct (+12% Alpha)",
        "date": (datetime.utcnow() - timedelta(days=200)).isoformat()
    })

    return recos

async def seed_data():
    store = get_recommendation_store()

    # 1. Seed Analysts (deterministic IDs for idempotency)
    analyst_objects = []
    analysts_map = {} # name -> id

    for a_data in ANALYSTS:
        # Deterministic ID based on name - running twice = same ID = no duplicates
        a_id = deterministic_uuid(f"analyst:{a_data['name']}")
        analysts_map[a_data["name"]] = a_id
        analyst_objects.append(
            Analyst(
                id=a_id,
                name=a_data["name"],
                team=a_data["team"],
                bio=a_data["bio"],
                coverage_sector=a_data["coverage_sector"],
                accuracy_score=a_data["accuracy_score"]
            )
        )

    await store.save_analysts(analyst_objects)
    print(f"Seeded {len(analyst_objects)} analysts.")
    
    # 2. Seed Recommendations (Views) - deterministic IDs for idempotency
    raw_recos = generate_recommendations(analysts_map)
    reco_objects = []

    for r in raw_recos:
        # Deterministic ID based on analyst + asset - running twice = same ID = no duplicates
        reco_id = deterministic_uuid(f"view:{r['analyst_id']}:{r['asset_class']}:{r['sub_asset']}:{r['is_active']}")
        reco_objects.append(
            InternalView(
                id=reco_id,
                doc_id=None,
                bank="AllianzGI",
                source_type="internal_view",
                asset_class=r["asset_class"],
                sub_asset=r["sub_asset"],
                stance=r["stance"],
                horizon=r["horizon"],
                rationale=r["rationale"],
                page=None,
                section=None,
                date=r["date"],
                # Internal fields
                analyst_id=r["analyst_id"],
                is_active=r["is_active"],
                outcome=r.get("outcome")
            )
        )
        
    await store.save_recommendations(reco_objects)
    print(f"Seeded {len(reco_objects)} internal views/history.")

if __name__ == "__main__":
    asyncio.run(seed_data())
