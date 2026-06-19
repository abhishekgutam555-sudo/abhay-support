"""
agent.py
--------
Groq AI brain — intent detection, system prompt builder,
escalation logic, rate-limit retry.
"""

import time
from groq import Groq


# ── Intent keywords ────────────────────────────────────────────────────────────

INTENT_MAP = {
    "order_status":   ["order", "kahan hai", "deliver", "track",
                       "status", "late", "nahi aaya", "kitni der"],
    "refund":         ["refund", "paisa wapas", "return", "cancel",
                       "money back", "payment wapas", "charge galat"],
    "complaint":      ["complaint", "problem", "issue", "galat", "kharab",
                       "wrong item", "missing", "quality", "ganda", "bura"],
    "booking":        ["book", "reserve", "table", "party", "event",
                       "birthday", "anniversary", "appointment"],
    "menu_pricing":   ["menu", "kya milta", "price", "cost", "kitne ka",
                       "rate", "charges", "offer", "discount"],
    "hours_location": ["timing", "open", "close", "band", "location",
                       "address", "kahan ho", "direction"],
    "lead_capture":   ["contact", "call me", "callback", "reach",
                       "mujhe call", "number do"],
}

ESCALATION_TRIGGERS = [
    "manager", "owner", "legal", "police", "consumer court",
    "cheating", "fraud", "social media", "review", "bahut gussa",
    "worst", "disgusting", "bakwaas",
]

INTENT_TIPS = {
    "order_status":   "Order ID ya phone number maango. Delay ke liye empathy dikhao.",
    "refund":         "Order details lo pehle. Refund timeline batao (3-5 business days).",
    "complaint":      "Pehle genuinely maafi maango, phir solution do. Compensation offer karo agar zarurat ho.",
    "booking":        "Date, time, party size aur contact collect karo.",
    "menu_pricing":   "Menu, prices aur current offers batao. Bestsellers suggest karo.",
    "hours_location": "Business hours aur location clearly batao.",
    "lead_capture":   "Name aur phone number collect karo for callback.",
    "general":        "Helpful raho. Sahi department redirect karo agar zarurat ho.",
}


def detect_intent(message: str) -> str:
    msg = message.lower()
    for intent, keywords in INTENT_MAP.items():
        if any(k in msg for k in keywords):
            return intent
    return "general"


def is_escalation(message: str) -> bool:
    msg = message.lower()
    return any(t in msg for t in ESCALATION_TRIGGERS)


# ── Main Agent class ───────────────────────────────────────────────────────────

class CustomerAgent:

    def __init__(self, config: dict):
        self.cfg = config
        import os
        api_key = config.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "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").strip()
        self.client = Groq(api_key=api_key)

    def _system_prompt(self, intent: str) -> str:
        cfg = self.cfg
        return f"""You are {cfg['agent_name']}, a professional AI customer support agent for {cfg['business_name']}, a {cfg['business_type']} in {cfg['business_city']}, India.

PERSONALITY:
- Warm, polite, patient, solution-focused
- Reply in natural Hinglish (mix of Hindi + English)
- Keep replies short: 3-5 lines max unless detail needed
- Never say "I don't know" — always give a next step
- Max 1 emoji per reply

BUSINESS INFO:
- Hours: {cfg['business_hours']}
- Phone: {cfg['support_phone']}

CURRENT INTENT: {intent}
HANDLING TIP: {INTENT_TIPS.get(intent, INTENT_TIPS['general'])}

STRICT RULES:
1. Never invent order numbers, prices, or policies you don't know
2. If unresolvable → "Main yeh apni team ko forward kar raha hoon"
3. End every reply with "Kuch aur help chahiye?" (except escalations)
4. Never argue with customer — even if they are wrong
5. Always collect missing info before making any promise"""

    def _escalation_reply(self) -> str:
        cfg = self.cfg
        return (
            f"Aapki baat sun ke mujhe bahut afsos hua. Dil se maafi chahta hoon. 🙏\n"
            f"Main yeh matter abhi apni senior team ko escalate kar raha hoon.\n"
            f"Direct baat ke liye call karein: {cfg['support_phone']}\n"
            f"Hum {cfg['business_hours']} available hain. Aapka issue zaroor resolve hoga."
        )

    def reply(self, session_id: str, user_message: str, history: list) -> dict:
        """
        Main method — call karo har customer message pe.

        Returns:
            {
              "text":      str,   ← Agent ka reply
              "intent":    str,   ← Detected intent
              "escalated": bool   ← Escalation hua?
            }
        """
        intent = detect_intent(user_message)

        # Escalation check
        if is_escalation(user_message):
            return {
                "text":      self._escalation_reply(),
                "intent":    "escalated",
                "escalated": True
            }

        # Build messages for Groq
        messages = [{"role": "system", "content": self._system_prompt(intent)}]
        messages += history
        messages.append({"role": "user", "content": user_message})

        # Groq call with retry
        reply_text = self._call_groq(messages)

        return {
            "text":      reply_text,
            "intent":    intent,
            "escalated": False
        }

    def _call_groq(self, messages: list) -> str:
        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.cfg.get("groq_model", "llama3-8b-8192"),
                    messages=messages,
                    temperature=0.5,
                    max_tokens=600,
                )
                return resp.choices[0].message.content.strip()

            except Exception as e:
                err = str(e)
                if "429" in err or "rate_limit" in err.lower():
                    wait = 2.5 * (attempt + 1)
                    time.sleep(wait)
                    continue
                elif "401" in err:
                    return "❌ API key galat hai. config.json check karo."
                else:
                    return "Abhi technical issue aa raha hai. Thodi der baad try karo. 🙏"

        return "Server busy hai. 1-2 minute baad try karo. 🙏"
