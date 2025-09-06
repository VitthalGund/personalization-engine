from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import Base
import datetime


class ContentNode(Base):
    __tablename__ = "ContentNode"
    id = Column(String, primary_key=True, index=True)
    createdAt = Column(DateTime, default=datetime.datetime.utcnow)
    contentJson = Column(JSON)


class UserInteraction(Base):
    __tablename__ = "UserInteraction"
    id = Column(String, primary_key=True, index=True)
    userId = Column(String, index=True)
    contentNodeId = Column(String, ForeignKey("ContentNode.id"))
    createdAt = Column(DateTime, default=datetime.datetime.utcnow)
    contentNode = relationship("ContentNode")


class LearnerProfile(Base):
    __tablename__ = "LearnerProfile"
    id = Column(String, primary_key=True, index=True)
    userId = Column(String, unique=True, index=True)
    engagementScore = Column(Float, default=0.5)
    competenceMap = Column(JSON, nullable=False)
