import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"


with open("backend/prompts/ats_skill.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


TOOLS = [
    {
        "name": "evaluate_resume",
        "description": "Evaluates a resume for ATS compatibility and returns a structured analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "overall_score": {
                    "type": "integer",
                    "description": "Overall ATS compatibility score from 0 to 100"
                },
                "approved": {
                    "type": "boolean",
                    "description": "True if score is 80 or above, False otherwise"
                },
                "candidate_name": {
                    "type": "string",
                    "description": "Full name of the candidate extracted from the resume"
                },
                "formatting_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of formatting problems found in the resume"
                },
                "keywords_found": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relevant keywords found in the resume"
                },
                "keywords_missing": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of important keywords missing from the resume"
                },
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific recommendations to improve the resume"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the overall resume analysis"
                }
            },
            "required": [
                "overall_score",
                "approved",
                "candidate_name",
                "formatting_issues",
                "keywords_found",
                "keywords_missing",
                "recommendations",
                "summary"
            ]
        }
    }
]

def evaluate_cv(cv_text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[
            {
                "role": "user",
                "content": f"Please analyze this resume:\n\n{cv_text}"
            }
        ]
    )

    
    for block in response.content:
        if block.type == "tool_use" and block.name == "evaluate_resume":
            return block.input

   
    return {"error": "Claude did not use the tool correctly"}