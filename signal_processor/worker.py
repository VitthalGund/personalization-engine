import json
import time
from sqlalchemy.orm import Session

# Note: In a real microservices project, these would be in a shared library
from decision_engine.database import SessionLocal, Base, engine
from decision_engine.models import LearnerProfile

# --- Mock Message Queue ---
# In a real system, this would be replaced with a Kafka or RabbitMQ consumer.
# For this demo, we'll use a simple file as a queue.
MESSAGE_QUEUE_FILE = "message_queue.json"


def get_messages_from_queue():
    """Reads and clears messages from the mock queue file."""
    try:
        with open(MESSAGE_QUEUE_FILE, "r+") as f:
            messages = json.load(f)
            f.seek(0)
            f.truncate()
            json.dump([], f)
            return messages
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def process_interaction_event(db: Session, event: dict):
    """
    Updates the learner's competence map based on a quiz attempt.
    This is a simplified Bayesian Knowledge Tracing (BKT) update.
    """
    if event.get("interactionType") != "QUIZ_ATTEMPT":
        return  # We only care about quiz attempts for now

    user_id = event.get("userId")
    data = event.get("data", {})
    concept_id = data.get("conceptId")
    is_correct = data.get("isCorrect")

    if not all([user_id, concept_id, is_correct is not None]):
        print(f"Skipping invalid event: {event}")
        return

    # Fetch user profile
    profile = db.query(LearnerProfile).filter(LearnerProfile.userId == user_id).first()
    if not profile:
        print(f"Profile not found for user {user_id}")
        return

    # BKT Parameters (simplified)
    prob_learn = 0.10  # Chance of learning from this attempt
    prob_slip = 0.15  # Chance of making a mistake when knowing the material
    prob_guess = 0.25  # Chance of guessing correctly when not knowing

    # Get current probability of knowing the concept
    current_prob_know = profile.competenceMap.get(
        concept_id, 0.1
    )  # Start with a small prior

    # Update probability based on the answer
    if is_correct:
        prob_know_if_correct = (current_prob_know * (1 - prob_slip)) / (
            (current_prob_know * (1 - prob_slip)) + (1 - current_prob_know) * prob_guess
        )
        updated_prob_know = (
            prob_know_if_correct + (1 - prob_know_if_correct) * prob_learn
        )
    else:  # Incorrect
        prob_know_if_incorrect = (current_prob_know * prob_slip) / (
            (current_prob_know * prob_slip) + (1 - current_prob_know) * (1 - prob_guess)
        )
        updated_prob_know = (
            prob_know_if_incorrect + (1 - prob_know_if_incorrect) * prob_learn
        )

    # Update the competence map and commit to DB
    profile.competenceMap[concept_id] = round(updated_prob_know, 4)
    db.commit()
    print(
        f"Updated competence for user {user_id}, concept {concept_id}: {updated_prob_know:.4f}"
    )


def main():
    """Main worker loop to process messages from the queue."""
    print("Starting Signal Processor Worker...")
    while True:
        db = SessionLocal()
        try:
            messages = get_messages_from_queue()
            if messages:
                print(f"Found {len(messages)} events in queue.")
                for message in messages:
                    process_interaction_event(db, message)
            else:
                time.sleep(5)  # Wait for 5 seconds if queue is empty
        finally:
            db.close()


if __name__ == "__main__":
    # To run this worker: python -m signal_processor.worker
    main()
