from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    userId: str


class RecommendationResponse(BaseModel):
    contentNodeId: str | None
