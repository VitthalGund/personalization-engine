import os
import json
from fastapi import FastAPI, Depends, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import google.generativeai.client as genai
from google.generativeai.generative_models import GenerativeModel

from . import schemas, models, database, config
from report_generator.generate import generate_report_for_user

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = GenerativeModel("gemini-1.5-flash")

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Personalized Learning Engine",
    description="Provides real-time recommendations and AI-powered assessments.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(x_internal_api_key: str = Header(...)):
    """A dependency to protect endpoints from public access."""
    if x_internal_api_key != config.settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid Internal API Key")


# --- API Endpoints ---
@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Decision Engine is running!"}


@app.post("/quiz/generate", dependencies=[Depends(verify_api_key)])
def generate_quiz(request: schemas.QuizGenerationRequest):
    """
    Generates a quiz for a given piece of content using the Gemini API.
    """
    if not request.source_text or len(request.source_text) < 50:
        raise HTTPException(
            status_code=400,
            detail="Source text is too short to generate a meaningful quiz.",
        )

    prompt = f"""
    Based on the following text, generate a 5-question quiz to test understanding.
    The quiz must include 3 multiple-choice questions and 2 short-answer (open-ended) questions.
    For multiple-choice questions, provide 4 options and indicate the correct answer.
    For short-answer questions, provide an ideal answer for evaluation.
    Provide a relevant hint for every question.

    Respond ONLY with a valid JSON object following this structure, with no markdown formatting:
    {{
      "questions": [
        {{ "type": "multiple-choice", "question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "hint": "..." }},
        {{ "type": "short-answer", "question": "...", "answer": "...", "hint": "..." }}
      ]
    }}

    Source Text:
    ---
    {request.source_text}
    ---
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it is valid JSON before parsing
        cleaned_text = response.text.strip().lstrip("```json").rstrip("```")
        json_response = json.loads(cleaned_text)
        return json_response
    except Exception as e:
        print(f"Error generating quiz from Gemini: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate quiz from AI model."
        )


@app.post("/quiz/evaluate", dependencies=[Depends(verify_api_key)])
def evaluate_quiz_answers(request: schemas.QuizEvaluationRequest):
    """
    Evaluates a user's answers, especially open-ended ones, using the Gemini API.
    """
    total_questions = len(request.questions)
    correct_answers = 0
    results = []

    for i, question_data in enumerate(request.questions):
        user_answer = request.userAnswers[i]
        is_correct = False

        if question_data.type == "multiple-choice":
            is_correct = (
                user_answer.strip().lower() == question_data.answer.strip().lower()
            )
        elif question_data.type == "short-answer":
            prompt = f"""
            A user was asked the following question:
            '{question_data.question}'

            The ideal answer is:
            '{question_data.answer}'

            The user's answer was:
            '{user_answer}'

            Based on the ideal answer, is the user's answer correct? The user's answer should capture the main idea but does not need to be a word-for-word match.
            Respond ONLY with the single word "true" if the answer is correct or "false" if it is incorrect.
            """
            try:
                response = model.generate_content(prompt)
                is_correct = response.text.strip().lower() == "true"
            except Exception as e:
                print(f"Error evaluating answer with Gemini: {e}")
                is_correct = False

        if is_correct:
            correct_answers += 1

        results.append({"questionIndex": i, "isCorrect": is_correct})

    score = correct_answers / total_questions
    return {"score": score, "results": results}


# --- Existing Endpoints ---
@app.post(
    "/recommend",
    response_model=schemas.RecommendationResponse,
    dependencies=[Depends(verify_api_key)],
)
def get_recommendation(
    request: schemas.RecommendationRequest, db: Session = Depends(database.get_db)
):
    """
    Intelligent recommendation logic.
    Finds the concept with the lowest mastery and recommends content for it.
    """
    # 1. Fetch the user's learner profile.
    profile = (
        db.query(models.LearnerProfile)
        .filter(models.LearnerProfile.userId == request.userId)
        .first()
    )

    if not profile or not profile.competenceMap:
        raise HTTPException(
            status_code=404, detail="Learner profile not found or is empty."
        )

    # 2. Find the concept with the lowest competence score below a mastery threshold.
    competence_map = profile.competenceMap
    mastery_threshold = 0.90

    # Filter out mastered concepts and sort by score
    weakest_concepts = sorted(
        [item for item in competence_map.items() if item[1] < mastery_threshold],
        key=lambda item: item[1],
    )

    if not weakest_concepts:
        # User has mastered everything, maybe recommend a final exam or new topic.
        # For now, we'll indicate no specific content is needed.
        return {"contentNodeId": None}

    target_concept_id = weakest_concepts[0][0]

    # 3. Find a ContentNode that teaches this specific concept.
    # This assumes `contentJson` contains `{"conceptId": "..."}`.
    recommended_node = (
        db.query(models.ContentNode)
        .filter(models.ContentNode.contentJson["conceptId"].astext == target_concept_id)
        .first()
    )

    if not recommended_node:
        raise HTTPException(
            status_code=404, detail=f"No content found for concept: {target_concept_id}"
        )

    return {"contentNodeId": recommended_node.id}


@app.post(
    "/reports/generate",
    status_code=202,
    dependencies=[Depends(verify_api_key)],
)
async def trigger_report_generation(
    request: schemas.RecommendationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Triggers a report generation job for a specific user as a background task.
    """
    background_tasks.add_task(generate_report_for_user, request.userId)

    return {"message": "Report generation has been queued."}
