import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

# leemos el skill como system prompt
with open("backend/prompts/ats_skill.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

def evaluate_cv(cv_text: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,      # ← instrucciones para Claude
        messages=[
            {
                "role": "user",
                "content": f"Please analyze this resume:\n\n{cv_text}"
            }
        ]
    )
    return response.content[0].text