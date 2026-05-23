"""
ILLeadPro - AI Lead Scorer
Uses Claude API to analyze posts and score leads
"""
import anthropic
import os
import json


def score_lead(post_text, source, area="Illinois"):
    """
    Use Claude AI to analyze a post and determine:
    - Is this a real buyer or seller?
    - How motivated are they?
    - What score (Hot/Warm/Cold)?
    - What type (Buyer/Seller/Investor)?
    """
    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        prompt = f"""You are analyzing a social media post or listing to determine if this person is interested in buying or selling real estate in Illinois.

POST/LISTING:
"{post_text}"

SOURCE: {source}
AREA: {area}

Analyze this and respond with ONLY a JSON object (no other text):
{{
  "is_real_estate_lead": true or false,
  "type": "🏠 Seller" or "🔍 Buyer" or "🏢 Investor" or "Unknown",
  "score": "🔥 Hot" or "⚡ Warm" or "❄️ Cold",
  "score_number": 1-10,
  "reason": "One sentence explanation",
  "urgency": "immediate" or "near-term" or "exploring",
  "estimated_value": "budget or price range if mentioned, or Unknown"
}}

Scoring guide:
- 🔥 Hot (8-10): Ready NOW, specific timeline, motivated, price mentioned
- ⚡ Warm (4-7): Interested but no urgent timeline, exploring options
- ❄️ Cold (1-3): Just curious, very vague, no real intent shown

If this is NOT a real estate lead, set is_real_estate_lead to false."""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return result

    except Exception as e:
        print(f"AI scoring error: {e}")
        return {
            "is_real_estate_lead": True,
            "type": "🏠 Seller",
            "score": "⚡ Warm",
            "score_number": 5,
            "reason": "Could not analyze - manual review needed",
            "urgency": "exploring",
            "estimated_value": "Unknown"
        }
