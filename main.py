from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .decision_engine import schemas
from .decision_engine import models, database, config

# Create all database tables defined in models.py if they don't exist.
# In a full production setup, a tool like Alembic would handle migrations.
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Personalized Learning Engine",
    description="Provides real-time, personalized content recommendations.",
    version="1.0.0",
)

# --- Security & CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(x_internal_api_key: str = Header(...)):
    """Dependency to verify the internal API key."""
    if x_internal_api_key != config.settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid Internal API Key")


# --- API Endpoints ---
@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Decision Engine is running!"}


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
