import asyncio
import os
from loguru import logger
import anthropic
from dotenv import load_dotenv

load_dotenv()

PROFILE = """
Name: El Mahdi ALOUI
Formation: Cycle Ingénieur Informatique – EILCO (Calais)
Skills: Python, Java, JavaScript, PHP, React Native, Laravel, Angular, Docker, Git, MySQL, PostgreSQL, MongoDB, Agile/Scrum
Key experiences:
- Internship CGI (Rabat): Java/Angular development for banking client, Agile/Scrum methodology
- Internship Maroc Telecom: Python scripting, Cisco network configuration, level 1 diagnostics
- Club Infobots: Python IoT training workshops for students
Key projects:
- M&O CRM: Full CRM adopted by 7 Moroccan companies (Laravel/Kotlin)
- MonParking: Real-time mobile booking app with geolocation (React Native/Laravel)
- BankApp: Secure banking simulation (Java Spring Boot/Angular)
- SmartIoT: Real-time sensor dashboard (Python/MQTT/Grafana)
Certifications: Google IT Automation Python, CCNA 1, Scrum Foundation, React Native (Udemy), ALX AICE
Languages: Arabic (native), French C1, English C2, Spanish B1
Looking for: 2-year alternance starting September 2026, national mobility, Permis B
"""

SYSTEM_PROMPT = f"""Tu es un assistant expert en rédaction de lettres de motivation professionnelles en français.

Voici le profil du candidat :
{PROFILE}

Ta tâche est de générer un message de candidature court et personnalisé (3-4 phrases maximum) en français pour une offre d'emploi donnée.

Règles STRICTES à respecter :
1. Le message commence OBLIGATOIREMENT par "Bonjour,"
2. Mentionne EXPLICITEMENT le nom de l'entreprise et le poste visé
3. Mets en avant UNIQUEMENT les compétences et expériences présentes dans le profil ci-dessus — ne mentionne jamais des compétences non listées
4. Le message doit être naturel, professionnel et adapté aux exigences spécifiques de l'offre
5. Maximum 3-4 phrases, concis et percutant
6. Ne génère QUE le message, sans introduction ni explication
"""

# Keyword → most relevant experience/project mapping for template fallback
_SKILL_MAP = {
    "python":     "mon expérience en scripting Python (stage Maroc Telecom) et ma certification Google IT Automation Python",
    "java":       "mon expérience Java/Angular développée lors de mon stage chez CGI pour un client bancaire",
    "angular":    "mon expérience Angular acquise lors de mon stage chez CGI (développement bancaire en Agile/Scrum)",
    "react":      "mon projet MonParking (application mobile React Native/Laravel) et ma certification React Native",
    "docker":     "ma maîtrise de Docker utilisée dans plusieurs projets dont SmartIoT et BankApp",
    "data":       "mon projet SmartIoT (dashboard temps réel Python/MQTT/Grafana) et ma certification Google IT Automation",
    "sql":        "ma pratique quotidienne de MySQL et PostgreSQL dans mes projets CRM et bancaires",
    "laravel":    "mon projet M&O CRM (adopté par 7 entreprises marocaines) développé avec Laravel",
    "mobile":     "mon projet MonParking (application mobile de réservation temps réel React Native/Laravel)",
    "agile":      "ma certification Scrum Foundation et mon expérience Agile/Scrum chez CGI",
    "réseau":     "ma certification CCNA 1 et mon stage chez Maroc Telecom (configuration Cisco)",
    "iot":        "mon projet SmartIoT et mes ateliers IoT Python animés au club Infobots",
    "banking":    "mon projet BankApp (simulation bancaire Java Spring Boot/Angular) et mon stage CGI",
    "banque":     "mon projet BankApp (simulation bancaire Java Spring Boot/Angular) et mon stage CGI",
}


def _fallback_message(job_title: str, company: str, job_description: str) -> str:
    """Generate a template-based cover message when the AI API is unavailable."""
    desc_lower = (job_description + " " + job_title).lower()

    # Find best matching skill
    best_match = "mon profil polyvalent (Python, Java, Angular, Docker, Agile/Scrum)"
    for keyword, description in _SKILL_MAP.items():
        if keyword in desc_lower:
            best_match = description
            break

    return (
        f"Bonjour, je suis El Mahdi ALOUI, étudiant en Cycle Ingénieur Informatique à l'EILCO (Calais), "
        f"à la recherche d'une alternance de 2 ans à partir de septembre 2026. "
        f"Votre offre de {job_title} chez {company} m'intéresse particulièrement car elle correspond à "
        f"{best_match}. "
        f"Je serais ravi d'échanger avec vous sur la façon dont je pourrais contribuer à vos projets."
    )


async def generate_message(job_title: str, company: str, job_description: str) -> str:
    """
    Generate a personalized French cover message using Claude.
    Falls back to a template-based message if the API is unavailable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        logger.warning("ANTHROPIC_API_KEY not set or invalid — using template fallback")
        return _fallback_message(job_title, company, job_description)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    user_message = f"""Génère un message de candidature personnalisé pour cette offre :

Poste : {job_title}
Entreprise : {company}
Description de l'offre :
{job_description[:3000]}

Rappel : commence par "Bonjour,", mentionne l'entreprise et le poste, reste en 3-4 phrases maximum."""

    last_exception = None
    for attempt in range(1, 4):
        try:
            logger.debug(f"Generating message for '{job_title}' at '{company}' (attempt {attempt}/3)")
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            message_text = response.content[0].text.strip()
            logger.info(f"AI message generated for '{job_title}' at '{company}'")
            return message_text

        except anthropic.AuthenticationError as exc:
            logger.error(f"Anthropic authentication failed — check ANTHROPIC_API_KEY: {exc}")
            logger.info("Falling back to template message")
            return _fallback_message(job_title, company, job_description)

        except anthropic.RateLimitError as exc:
            wait = 2 ** attempt
            logger.warning(f"Rate limit hit (attempt {attempt}/3), waiting {wait}s")
            last_exception = exc
            await asyncio.sleep(wait)

        except anthropic.APIStatusError as exc:
            wait = 2 ** attempt
            logger.warning(f"API error (attempt {attempt}/3), waiting {wait}s: {exc}")
            last_exception = exc
            await asyncio.sleep(wait)

        except Exception as exc:
            wait = 2 ** attempt
            logger.error(f"Unexpected error (attempt {attempt}/3): {exc}")
            last_exception = exc
            await asyncio.sleep(wait)

    logger.warning(f"All AI attempts failed — using template fallback")
    return _fallback_message(job_title, company, job_description)

