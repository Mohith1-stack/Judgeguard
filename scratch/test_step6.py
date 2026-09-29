import requests
import json
import uuid
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
P1_EMAIL = "p1_s6@example.com"
P2_EMAIL = "p2_s6@example.com"
PASS = "TestPass123!"

def print_res(name, res):
    print(f"--- {name} ---")
    print(f"Status: {res.status_code}")
    try:
        print(f"Body: {json.dumps(res.json(), indent=2)[:500]}")
    except:
        print(f"Body: {res.text[:200]}")
    print()

def register(email, display_name):
    requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "display_name": display_name,
        "password": PASS
    })

def login(email):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": PASS
    })
    return res.json().get("token")

def main():
    print("Health Checks")
    requests.get(f"{BASE_URL}/health")
    
    # register(ADMIN_EMAIL, "Admin S6") # Skip admin register since they exist
    register(P1_EMAIL, "Participant 1 S6")
    register(P2_EMAIL, "Participant 2 S6")

    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": "AdminPassword123!"
    })
    admin_token = res.json().get("token")
    p1_token = login(P1_EMAIL)
    p2_token = login(P2_EMAIL)

    # Make admin an actual admin (if needed, but organizer works)
    # Actually, the user who creates the event is the organizer.
    
    event_slug = f"s6-event-{uuid.uuid4().hex[:8]}"
    res_event = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 6 Event",
        "slug": event_slug,
        "description": "Event for step 6 testing"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    if res_event.status_code != 201:
        print("Failed to create event")
        print_res("Event", res_event)
        return
    event_id = res_event.json().get("id")

    # Organizer Questions
    print("\n--- 7. Create Custom Questions ---")
    q1 = requests.post(f"{BASE_URL}/events/{event_id}/submission-questions", json={
      "key": "project_goal",
      "label": "What problem does your project solve?",
      "description": "Explain the problem in a few sentences.",
      "question_type": "LONG_TEXT",
      "required": True,
      "options": [],
      "sort_order": 0
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Q1", q1)

    q2 = requests.post(f"{BASE_URL}/events/{event_id}/submission-questions", json={
      "key": "primary_category",
      "label": "Primary category",
      "description": "Select the category that best describes the project.",
      "question_type": "SINGLE_SELECT",
      "required": True,
      "options": [
        "Cybersecurity",
        "AI",
        "Web",
        "Developer Tools"
      ],
      "sort_order": 1
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Q2", q2)

    print("\n--- 8. Test Question Restrictions ---")
    q_inv1 = requests.post(f"{BASE_URL}/events/{event_id}/submission-questions", json={
      "key": "invalid_1",
      "label": "Invalid",
      "question_type": "SINGLE_SELECT",
      "required": True,
      "options": []
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Invalid 1 (No options for Select)", q_inv1)

    q_inv2 = requests.post(f"{BASE_URL}/events/{event_id}/submission-questions", json={
      "key": "invalid_2",
      "label": "Text",
      "question_type": "TEXT",
      "options": ["A", "B"]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Invalid 2 (Options for Text)", q_inv2)

    # Make event SUBMISSION_OPEN
    now = datetime.utcnow()
    ev_update = requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": (now - timedelta(hours=3)).isoformat() + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat() + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat() + "Z",
        "submission_deadline": (now + timedelta(hours=1)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Event Time Update", ev_update)

    st1 = requests.post(f"{BASE_URL}/events/{event_id}/status", json={
        "status": "REGISTRATION_OPEN"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Status REGISTRATION_OPEN", st1)

    st2 = requests.post(f"{BASE_URL}/events/{event_id}/status", json={
        "status": "SUBMISSION_OPEN"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Status SUBMISSION_OPEN", st2)

    # P1 Creates Team
    res_team = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={
        "name": f"S6 Team {uuid.uuid4().hex[:8]}"
    }, headers={"Authorization": f"Bearer {p1_token}"})
    team_id = res_team.json().get("id")

    print("\n--- 9. Create Submission Draft ---")
    valid_sub_payload = {
      "name": "My Project",
      "tagline": "A useful project",
      "description": "A real project description.",
      "thumbnail_url": "https://example.com/image.png",
      "demo_video_url": "https://example.com/demo",
      "repository_url": "https://github.com/example/project",
      "live_url": "https://example.com",
      "tech_tags": [
        "Python",
        "FastAPI",
        "PostgreSQL"
      ],
      "custom_answers": {
        "project_goal": "Help organizers obtain more reliable judging results.",
        "primary_category": "AI"
      }
    }
    sub_res = requests.post(f"{BASE_URL}/teams/{team_id}/submissions", json=valid_sub_payload, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Submission Draft", sub_res)
    submission_id = sub_res.json().get("id")

    print("\n--- 10. Custom Answers Enforced ---")
    sub_inv1 = requests.post(f"{BASE_URL}/teams/{team_id}/submissions", json={
      "name": "My Project 2",
      "custom_answers": {
        "primary_category": "Blockchain"
      }
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Invalid Category Option", sub_inv1)

    sub_inv2 = requests.post(f"{BASE_URL}/teams/{team_id}/submissions", json={
      "name": "My Project 3",
      "custom_answers": {
        "primary_category": "AI"
      } # Missing project_goal
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Missing Required Question", sub_inv2)

    print("\n--- 11. Test Versioning ---")
    valid_sub_payload["name"] = "My Improved Project"
    patch1 = requests.patch(f"{BASE_URL}/submissions/{submission_id}", json=valid_sub_payload, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Patch 1 (Version 2)", patch1)
    
    valid_sub_payload["name"] = "My More Improved Project"
    patch2 = requests.patch(f"{BASE_URL}/submissions/{submission_id}", json=valid_sub_payload, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Patch 2 (Version 3)", patch2)

    versions_res = requests.get(f"{BASE_URL}/submissions/{submission_id}/versions", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Versions List", versions_res)

    print("\n--- 17. Add Media ---")
    media_res = requests.post(f"{BASE_URL}/submissions/{submission_id}/media", json={
      "url": "https://example.com/screenshot.png",
      "caption": "Dashboard screenshot",
      "sort_order": 0
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Add Media", media_res)
    
    sub_detail = requests.get(f"{BASE_URL}/submissions/{submission_id}/private", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Submission Detail with Media", sub_detail)

    print("\n--- 12. Finalize Submission ---")
    submit_res = requests.post(f"{BASE_URL}/submissions/{submission_id}/submit", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Finalize Submission", submit_res)

    print("\n--- 13. Edit after finalize but before deadline ---")
    valid_sub_payload["name"] = "Final Improved Project"
    patch3 = requests.patch(f"{BASE_URL}/submissions/{submission_id}", json=valid_sub_payload, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Patch 3 (Version 4)", patch3)

    print("\n--- 14. Deadline Enforcement ---")
    # Set deadline in the past
    requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "submission_deadline": (now - timedelta(minutes=5)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})

    patch4 = requests.patch(f"{BASE_URL}/submissions/{submission_id}", json=valid_sub_payload, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Patch after deadline", patch4)

    media_late = requests.post(f"{BASE_URL}/submissions/{submission_id}/media", json={
      "url": "https://example.com/late.png"
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Media after deadline", media_late)
    
    submit_late = requests.post(f"{BASE_URL}/submissions/{submission_id}/submit", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Submit after deadline", submit_late)

    print("\n--- 16. Private Draft Protection ---")
    # P2 (not in team) tries to view private
    private_res = requests.get(f"{BASE_URL}/submissions/{submission_id}/private", headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Non-member private view", private_res)
    
    # Public view works because it's SUBMITTED
    public_res = requests.get(f"{BASE_URL}/submissions/{submission_id}")
    print_res("Public view (should work)", public_res)

    print("\n--- 18. Manual Organizer Lock ---")
    # Organizer locks it
    lock_res = requests.post(f"{BASE_URL}/submissions/{submission_id}/lock", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Organizer Lock", lock_res)

if __name__ == "__main__":
    main()
