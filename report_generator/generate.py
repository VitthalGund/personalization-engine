import json
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from decision_engine.database import SessionLocal
from decision_engine.models import LearnerProfile, UserInteraction

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from decision_engine.database import Base


class LearnerReport(Base):
    __tablename__ = "LearnerReport"
    id = Column(String, primary_key=True)
    userId = Column(String, index=True)
    generatedAt = Column(DateTime, default=datetime.utcnow)
    reportData = Column(JSON)


def generate_reports_for_all_users():
    """
    Simulates a weekly job to generate performance reports for all users.
    """
    db = SessionLocal()
    try:
        print("Starting weekly report generation job...")

        # Get all user profiles
        profiles = db.query(LearnerProfile).all()

        for profile in profiles:
            print(f"Generating report for user: {profile.userId}")

            # 1. Analyze competence map for strengths and weaknesses
            competence_map = profile.competenceMap
            if not competence_map:
                continue

            strengths = [
                concept for concept, score in competence_map.items() if score >= 0.90
            ]
            weaknesses = [
                concept for concept, score in competence_map.items() if score < 0.60
            ]

            # 2. Calculate activity in the last 7 days
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            recent_activity_count = (
                db.query(UserInteraction)
                .filter(
                    UserInteraction.userId == profile.userId,
                    UserInteraction.createdAt >= one_week_ago,
                )
                .count()
            )

            # 3. Construct the report data
            report_data = {
                "summary": f"You completed {recent_activity_count} activities this week. Great job!",
                "strengths": strengths,
                "weaknesses": weaknesses,
                "engagementScore": profile.engagementScore,
                "generatedOn": datetime.utcnow().isoformat(),
            }

            # 4. Save the new report to the database
            new_report = LearnerReport(
                id=f"rep_{profile.userId}_{datetime.utcnow().timestamp()}",
                userId=profile.userId,
                reportData=report_data,
            )
            db.add(new_report)

        db.commit()
        print(f"Successfully generated reports for {len(profiles)} users.")

    finally:
        db.close()


if __name__ == "__main__":
    # To run this job: python -m report_generator.generate
    generate_reports_for_all_users()
