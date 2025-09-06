import json
import time
import redis
from sqlalchemy.orm import Session
from decision_engine.database import SessionLocal
from decision_engine.models import LearnerProfile
from decision_engine.config import settings

redis_client = redis.from_url(settings.DATABASE_URL)
INTERACTION_QUEUE_KEY = "interaction-queue"


def process_interaction_event(db: Session, event: dict):
    # This logic remains the same
    if event.get("interactionType") != "QUIZ_ATTEMPT":
        return

    user_id = event.get("userId")
    data = event.get("data", {})
    concept_id = data.get("conceptId")
    is_correct = data.get("isCorrect")

    if not all([user_id, concept_id, is_correct is not None]):
        print(f"Skipping invalid event: {event}")
        return

    profile = db.query(LearnerProfile).filter(LearnerProfile.userId == user_id).first()
    if not profile:
        print(f"Profile not found for user {user_id}")
        return

    prob_learn, prob_slip, prob_guess = 0.10, 0.15, 0.25
    current_prob_know = profile.competenceMap.get(concept_id, 0.1)

    if is_correct:
        prob_know_if_correct = (current_prob_know * (1 - prob_slip)) / (
            (current_prob_know * (1 - prob_slip)) + (1 - current_prob_know) * prob_guess
        )
        updated_prob_know = (
            prob_know_if_correct + (1 - prob_know_if_correct) * prob_learn
        )
    else:
        prob_know_if_incorrect = (current_prob_know * prob_slip) / (
            (current_prob_know * prob_slip) + (1 - current_prob_know) * (1 - prob_guess)
        )
        updated_prob_know = (
            prob_know_if_incorrect + (1 - prob_know_if_incorrect) * prob_learn
        )

    profile.competenceMap[concept_id] = round(updated_prob_know, 4)
    db.commit()
    print(
        f"Updated competence for user {user_id}, concept {concept_id}: {updated_prob_know:.4f}"
    )


def main():
    """Main worker loop to process messages from the Redis queue."""
    print("Starting Signal Processor Worker...")
    while True:
        db = SessionLocal()
        try:
            # --- CHANGE: Use blocking pop from Redis ---
            # BRPOP efficiently waits for an item to appear on the right of the list
            # The '0' means it will wait indefinitely.
            message_tuple = redis_client.brpop([INTERACTION_QUEUE_KEY], 0)

            # message_tuple is (b'queue_name', b'message_body')
            event_data = json.loads(message_tuple[1])
            print(f"Processing event for user {event_data.get('userId')}")
            process_interaction_event(db, event_data)
            # --- END CHANGE ---
        except Exception as e:
            print(f"An error occurred: {e}")
            # In production, you'd have more robust error handling/re-queuing
            time.sleep(5)
        finally:
            db.close()


if __name__ == "__main__":
    main()
