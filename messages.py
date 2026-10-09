"""Fixed texts for the assistant's messages in Portuguese and English (no AI quota needed for these)."""
import ai_insight

TEXTS = {
    "pt": {
        "paired": "Pareado! 🎉 A partir de agora eu falo só com você. Pode me perguntar sobre o seu dia, marcar "
                  "hábitos, criar eventos, registrar estudos… Ou mande um áudio.",
        "help": "Exemplos: \"como está meu dia?\", \"marca academia como ok\", \"descanso no alongamento hoje\", "
                "\"cria dentista sexta 14h30\", \"estudei docker 40 minutos: volumes\", \"o que vence este mês?\". "
                "Também entendo áudios. Eu nunca apago nada.",
        "no_ai": "Para conversar eu preciso da chave do Gemini (no app: Study → ✨ ou Options).",
        "ai_error": "Não consegui pensar agora ({error}). Tente de novo em instantes.",
        "checkin_title": "🌙 Check-in: ainda falta marcar {n} hábito(s) de hoje. Toque para responder:",
        "checkin_done": "✅ Tudo marcado hoje! Nota do dia: {score}.",
        "checkin_done_noscore": "✅ Tudo marcado hoje!",
        "marked": "{habit}: {answer} ✓",
        "event_soon": "📅 {title} — {when}.",
        "event_today": "hoje às {time}",
        "event_tomorrow": "amanhã às {time}",
        "event_allday_today": "hoje (o dia todo)",
        "event_allday_tomorrow": "amanhã (o dia todo)",
        "doc_window": "📄 {title} vence em {date} — já dá para planejar a renovação.",
        "doc_week": "📄 {title} vence em {days} dias ({date}).",
        "doc_due": "📄 {title} venceu/vence hoje ({date}). Renove quando puder e marque \"Renewed\" no app.",
        "reviews": "📚 {n} revisão(ões) de estudo para hoje: {topics}. Leva poucos minutos!",
        "level_up": "⬆️ Subiu para o nível {level} — {rank}! Mandou bem.",
        "streak": "🔥 {n} dias seguidos! Continue no seu ritmo.",
        "quest_done": "🏆 Quest concluída: {title} (+{xp:g} XP)!",
        "mastered": "🎓 Capítulo dominado: {title}! As revisões começam amanhã.",
        "briefing_fallback": "☀️ Bom dia! Hoje: {events}. Revisões: {reviews}. Próximos passos: {steps}.",
        "nothing": "nada marcado",
        "private": "Este é um assistente privado.",
    },
    "en": {
        "paired": "Paired! 🎉 From now on I only talk to you. Ask about your day, mark habits, create events, "
                  "log studies… or send a voice message.",
        "help": "Examples: \"how's my day?\", \"mark gym as ok\", \"rest day for stretching today\", "
                "\"add dentist friday 2:30pm\", \"I studied docker 40 minutes: volumes\", \"what expires this month?\". "
                "I understand voice messages too. I never delete anything.",
        "no_ai": "To chat I need the Gemini key (in the app: Study → ✨ or Options).",
        "ai_error": "I couldn't think right now ({error}). Try again in a moment.",
        "checkin_title": "🌙 Check-in: {n} habit(s) still unmarked today. Tap to answer:",
        "checkin_done": "✅ All marked for today! Daily score: {score}.",
        "checkin_done_noscore": "✅ All marked for today!",
        "marked": "{habit}: {answer} ✓",
        "event_soon": "📅 {title} — {when}.",
        "event_today": "today at {time}",
        "event_tomorrow": "tomorrow at {time}",
        "event_allday_today": "today (all day)",
        "event_allday_tomorrow": "tomorrow (all day)",
        "doc_window": "📄 {title} expires on {date} — time to plan the renewal.",
        "doc_week": "📄 {title} expires in {days} days ({date}).",
        "doc_due": "📄 {title} expired / expires today ({date}). Renew it when you can and press \"Renewed\" in the app.",
        "reviews": "📚 {n} study review(s) due today: {topics}. Just a few minutes!",
        "level_up": "⬆️ Level {level} — {rank}! Nicely done.",
        "streak": "🔥 {n}-day streak! Keep your rhythm.",
        "quest_done": "🏆 Quest complete: {title} (+{xp:g} XP)!",
        "mastered": "🎓 Chapter mastered: {title}! Reviews start tomorrow.",
        "briefing_fallback": "☀️ Good morning! Today: {events}. Reviews: {reviews}. Next steps: {steps}.",
        "nothing": "nothing scheduled",
        "private": "This is a private assistant.",
    },
}


def lang() -> str:
    return "en" if ai_insight.language() == "English" else "pt"


def t(key: str, **kw) -> str:
    text = TEXTS[lang()].get(key) or TEXTS["en"][key]
    return text.format(**kw) if kw else text
