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


async def generate_message(job_title: str, company: str, job_description: str) -> str:
    """
    Generate a personalized French cover message using Claude.
    Implements retry logic with exponential backoff (3 attempts).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

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
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            message_text = response.content[0].text.strip()
            logger.info(f"Message generated successfully for '{job_title}' at '{company}'")
            return message_text

        except anthropic.RateLimitError as exc:
            wait = 2 ** attempt
            logger.warning(f"Rate limit hit (attempt {attempt}/3), waiting {wait}s: {exc}")
            last_exception = exc
            await asyncio.sleep(wait)

        except anthropic.APIStatusError as exc:
            wait = 2 ** attempt
            logger.warning(f"API error (attempt {attempt}/3), waiting {wait}s: {exc}")
            last_exception = exc
            await asyncio.sleep(wait)

        except Exception as exc:
            wait = 2 ** attempt
            logger.error(f"Unexpected error generating message (attempt {attempt}/3): {exc}")
            last_exception = exc
            await asyncio.sleep(wait)

    logger.error(f"Failed to generate message after 3 attempts: {last_exception}")
    raise RuntimeError(f"Failed to generate cover message after 3 attempts: {last_exception}")
