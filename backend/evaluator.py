import logging
import pathlib
from typing import List

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger(__name__)


# definimos la estructura que queremos que devuelva Claude
class ResumeEvaluation(BaseModel):
    # cada campo tiene una descripcion para que Claude entienda que poner
    candidate_name: str = Field(description="Full name of the candidate")
    overall_score: int = Field(description="ATS compatibility score from 0 to 100")
    approved: bool = Field(description="True if score is 80 or above")
    formatting_issues: List[str] = Field(
        description="List of formatting problems found"
    )
    keywords_found: List[str] = Field(description="List of relevant keywords found")
    keywords_missing: List[str] = Field(
        description="List of important keywords missing"
    )
    recommendations: List[str] = Field(
        description="List of recommendations to improve the resume"
    )
    summary: str = Field(description="Brief summary of the overall analysis")


# creamos el modelo de Claude con LangChain
model = ChatAnthropic(model="claude-haiku-4-5")

# forzamos estructura de ResumeEvaluation
structured_model = model.with_structured_output(ResumeEvaluation)

# leemos el skill como prompt (path absoluto para evitar problemas con el cwd en producción)
_prompt_path = pathlib.Path(__file__).parent / "prompts" / "ats_skill.md"
logger.info("[evaluator] Loading prompt from: %s", _prompt_path)
with open(_prompt_path, "r", encoding="utf-8") as f:
    ats_skill = f.read()

# armamos el template del prompt
# {ats_skill} y {cv_text} son variables que se reemplazan en cada llamada
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
ROLE
You are an expert ATS resume evaluator. Your job is to analyze resumes
and evaluate their compatibility with Applicant Tracking Systems.

EVALUATION CRITERIA
{ats_skill}

RESPONSE FORMAT
Return a structured evaluation with: candidate name, overall score (0-100),
approved (true if score >= 80), formatting issues, keywords found,
keywords missing, recommendations, and a brief summary.
""",
        ),
        ("human", "Please analyze this resume:\n\n{cv_text}"),
    ]
)

# conectamos el template con el modelo estructurado
chain = prompt_template | structured_model


def evaluate_cv(cv_text: str, job_context: str | None = None) -> dict:
    job_section = (
        f"\n\nTARGET JOB DESCRIPTION:\n{job_context}" if job_context else ""
    )
    try:
        logger.info(
            "[evaluator] Invoking Claude with %d chars of CV text", len(cv_text)
        )
        result = chain.invoke(
            {"ats_skill": ats_skill, "cv_text": cv_text + job_section}
        )
        logger.info("[evaluator] Claude response received")
        return result.model_dump()
    except Exception as e:
        logger.exception("[evaluator] Error calling Anthropic API: %s", e)
        raise
