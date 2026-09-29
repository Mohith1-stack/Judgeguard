import requests
import json
import uuid
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
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

def login(email, password=PASS):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    return res.json().get("token")

def main():
    print("Health Checks")
    requests.get(f"{BASE_URL}/health")
    
    admin_token = login(ADMIN_EMAIL, "AdminPassword123!")

    rand_id = uuid.uuid4().hex[:4]
    
    # Register Participants & Judges
    for i in range(1, 6):
        register(f"j{i}_{rand_id}@example.com", f"Judge {i} S9")
        register(f"p{i}_{rand_id}@example.com", f"Participant {i} S9")

    # Create Event
    event_slug = f"s9-ev-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()
    res_event = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 9 Event",
        "slug": event_slug,
        "description": "Event for step 9 testing"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    event_id = res_event.json().get("id")

    patch_res = requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": (now - timedelta(hours=3)).isoformat() + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat() + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat() + "Z",
        "submission_deadline": (now + timedelta(hours=1)).isoformat() + "Z",
        "judging_opens_at": (now + timedelta(hours=2)).isoformat() + "Z",
        "judging_deadline": (now + timedelta(hours=3)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print("PATCH RES:", patch_res.status_code, patch_res.text)

    # Activate a Rubric
    rubric_res = requests.post(f"{BASE_URL}/events/{event_id}/rubrics", json={"name": "Eval v1"}, headers={"Authorization": f"Bearer {admin_token}"})
    rubric_id = rubric_res.json()["id"]
    requests.post(f"{BASE_URL}/rubrics/{rubric_id}/criteria", json={"name": "C1", "weight": 1.0, "min_score": 1, "max_score": 5}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/rubrics/{rubric_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})

    # Add 4 Judges with capacity 10
    j_ids = []
    for i in range(1, 5):
        j_token = login(f"j{i}_{rand_id}@example.com")
        j_user_id = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {j_token}"}).json().get("id")
        judge_res = requests.post(f"{BASE_URL}/events/{event_id}/judges", json={
            "user_id": j_user_id,
            "capacity": 10,
            "expertise": ["ai"]
        }, headers={"Authorization": f"Bearer {admin_token}"})
        j_ids.append(j_user_id)

    # Transition to REGISTRATION_OPEN then SUBMISSION_OPEN
    reg_open_res = requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "REGISTRATION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    print("REG OPEN RES:", reg_open_res.json())
    sub_open_res = requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "SUBMISSION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    print("SUB OPEN RES:", sub_open_res.json())

    # Add 4 Teams & Submissions
    t_ids = []
    sub_ids = []
    for i in range(1, 5):
        p_token = login(f"p{i}_{rand_id}@example.com")
        t_res = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"Team {i}"}, headers={"Authorization": f"Bearer {p_token}"})
        t_id = t_res.json()['id']
        t_ids.append(t_id)
        s_res = requests.post(f"{BASE_URL}/teams/{t_id}/submissions", json={
            "name": f"Project {i}",
            "tagline": "Test",
            "description": "Desc"
        }, headers={"Authorization": f"Bearer {p_token}"})
        print(f"Sub creation response for Team {i}:", s_res.json())
        sub_id = s_res.json()['id']
        sub_ids.append(sub_id)
        requests.post(f"{BASE_URL}/submissions/{sub_id}/submit", headers={"Authorization": f"Bearer {p_token}"})

    print("\n--- Test Conflict Avoidance (Creation) ---")
    # Add Conflict: J1 -> T1
    conf_res = requests.post(f"{BASE_URL}/events/{event_id}/judge-conflicts", json={
        "judge_id": j_ids[0],
        "team_id": t_ids[0],
        "reason": "Testing conflict"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print("Conflict Creation Response:", conf_res.status_code, conf_res.text)

    # Transition to JUDGING
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "JUDGING"}, headers={"Authorization": f"Bearer {admin_token}"})

    print("\n--- Test Preview ---")
    preview_payload = {
        "reviews_per_submission": 3,
        "optimization_restarts": 1,
        "seed": 123
    }
    preview_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign/preview", json=preview_payload, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Preview Output", preview_res)

    print("\n--- Test Insufficient Capacity ---")
    # Submissions = 4, needed = 4*3 = 12.
    # Change judges capacity to 2 each. Total = 8.
    for j_id in j_ids:
        requests.patch(f"{BASE_URL}/events/{event_id}/judges/{j_id}", json={"capacity": 2}, headers={"Authorization": f"Bearer {admin_token}"})
    
    preview_fail_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign/preview", json=preview_payload, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Preview Fail (Capacity)", preview_fail_res)

    # Restore capacity
    for j_id in j_ids:
        requests.patch(f"{BASE_URL}/events/{event_id}/judges/{j_id}", json={"capacity": 10}, headers={"Authorization": f"Bearer {admin_token}"})

    print("\n--- Test Conflict Avoidance (Evaluation) ---")
    
    preview_conf = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign/preview", json=preview_payload, headers={"Authorization": f"Bearer {admin_token}"})
    # We won't print the whole thing, just verify manually or if it succeeds.
    print(f"Preview Conflict Status: {preview_conf.status_code}")

    print("\n--- Test Commit ---")
    commit_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign", json=preview_payload, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Commit Plan", commit_res)

    assignments = commit_res.json()
    if isinstance(assignments, list):
        has_conflict = any(a["judge_id"] == j_ids[0] and a["submission_id"] == sub_ids[0] for a in assignments)
        print(f"Conflict Respected: {not has_conflict}")
    else:
        print(f"Conflict Respected: Error in commit! {assignments}")

    print("\n--- Test Latest Plan Retrieval ---")
    latest_res = requests.get(f"{BASE_URL}/events/{event_id}/judging/assignment-plan/latest", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Latest Plan", latest_res)

if __name__ == "__main__":
    main()
