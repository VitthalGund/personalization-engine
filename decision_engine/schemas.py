from pydantic import BaseModel
from typing import List


class RecommendationRequest(BaseModel):
    userId: str


class RecommendationResponse(BaseModel):
    contentNodeId: str | None


class QuizGenerationRequest(BaseModel):
    """Schema for requesting a new quiz to be generated."""

    source_text: str


class Question(BaseModel):
    """Represents a single question within a quiz."""

    type: str
    question: str
    options: List[str] | None = None
    answer: str
    hint: str


class QuizEvaluationRequest(BaseModel):
    """Schema for submitting user answers for evaluation."""

    questions: List[Question]
    userAnswers: List[str]
