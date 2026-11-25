from dental_agent.config import settings

MSG = {
    "English": {
        "handoff": "I'm connecting you with a member of our team. Please hold for a moment.",
        "limit": "I need to hand you to a colleague to help further. Please hold.",
        "closed": "This conversation has ended.",
        "scripted": "Sorry, I'm having technical trouble. I'm connecting you with our team.",
        "greeting": "Hello, welcome to the dental clinic. How can I help?",
    },
    "Urdu": {
        "handoff": "آپ کی بات ہمارے عملے کے رکن سے کروائی جا رہی ہے، براہ کرم ایک لمحہ انتظار کریں۔",
        "limit": "آپ کی بات ہمارے عملے کے رکن سے کروائی جا رہی ہے، براہ کرم ایک لمحہ انتظار کریں۔",
        "closed": "یہ گفتگو ختم ہو چکی ہے۔",
        "scripted": "معذرت، اس وقت تکنیکی مسئلہ ہے۔ آپ کی بات ہمارے عملے کے رکن سے کروائی جا رہی ہے۔",
        "greeting": "السلام علیکم، ڈینٹل کلینک میں خوش آمدید۔ آپ کی کیا مدد کی جا سکتی ہے؟",
    },
}


def msg(key: str) -> str:
    return MSG.get(settings.agent_language, MSG["English"])[key]
