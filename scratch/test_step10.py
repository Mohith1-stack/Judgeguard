import os
import requests
import uuid
import time
from datetime import datetime, timedelta, timezone

BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

def print_res(step, res):
    print(f"\n--- {step} ---")
    print(f"Status: {res.status_code}")
    try:
        print(f"Body: {res.json()}")
    except:
        print(f"Body: {res.text}")
    if res.status_code >= 400:
        print("FAILED!")

def login(email):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": "password123"
    })
    if res.status_code != 200:
        requests.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "display_name": "Test User",
            "password": "password123"
        })
        res = requests.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": "password123"
        })
    return res.json()["token"]

def login_admin():
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@example.com",
        "password": "AdminPassword123!"
    })
    return res.json()["token"]

def main():
    rand_id = str(uuid.uuid4())[:8]
    admin_token = login_admin()
    
    # 1. Create Event
    now = datetime.now(timezone.utc)
    ev_res = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 10 Event",
        "slug": f"s10-ev-{rand_id}",
        "description": "Event for step 10 testing",
        "registration_opens_at": (now - timedelta(hours=3)).isoformat().replace("+00:00", "") + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat().replace("+00:00", "") + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat().replace("+00:00", "") + "Z",
        "submission_deadline": (now + timedelta(hours=1)).isoformat().replace("+00:00", "") + "Z",
        "judging_opens_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "") + "Z",
        "judging_deadline": (now + timedelta(hours=3)).isoformat().replace("+00:00", "") + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print("Event Create Response:", ev_res.status_code, ev_res.text)
    event_id = ev_res.json()["id"]

    # Open Registration & Submission
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "REGISTRATION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "SUBMISSION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})

    # 2. Setup Rubric
    rubric_res = requests.post(f"{BASE_URL}/events/{event_id}/rubrics", json={"name": "Step 10 Rubric"}, headers={"Authorization": f"Bearer {admin_token}"})
    if rubric_res.status_code != 201:
        print("Rubric Create Failed:", rubric_res.status_code, rubric_res.text)
    rubric_id = rubric_res.json()["id"]

    c1_res = requests.post(f"{BASE_URL}/rubrics/{rubric_id}/criteria", json={
        "name": "Innovation",
        "description": "Is it novel?",
        "weight": 0.4,
        "min_score": 1,
        "max_score": 5
    }, headers={"Authorization": f"Bearer {admin_token}"})
    c1_id = c1_res.json()["id"]

    c2_res = requests.post(f"{BASE_URL}/rubrics/{rubric_id}/criteria", json={
        "name": "Execution",
        "description": "Does it work?",
        "weight": 0.6,
        "min_score": 1,
        "max_score": 5
    }, headers={"Authorization": f"Bearer {admin_token}"})
    c2_id = c2_res.json()["id"]

    requests.post(f"{BASE_URL}/rubrics/{rubric_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})

    # 3. Create Teams & Submissions
    t_ids, sub_ids = [], []
    for i in range(1, 4):
        p_token = login(f"p{i}_{rand_id}@example.com")
        t_res = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"Team {i}"}, headers={"Authorization": f"Bearer {p_token}"})
        if t_res.status_code != 201:
            print(f"Team {i} Create Failed:", t_res.status_code, t_res.text)
        t_id = t_res.json()['id']
        t_ids.append(t_id)

        s_res = requests.post(f"{BASE_URL}/teams/{t_id}/submissions", json={
            "name": f"Project {i}",
            "tagline": "Test",
            "description": "Desc"
        }, headers={"Authorization": f"Bearer {p_token}"})
        if s_res.status_code != 201:
            print(f"Project {i} Create Failed:", s_res.status_code, s_res.text)
        sub_id = s_res.json()['id']
        sub_ids.append(sub_id)
        requests.post(f"{BASE_URL}/submissions/{sub_id}/submit", headers={"Authorization": f"Bearer {p_token}"})

    # 4. Create Judges
    j_tokens, j_ids = [], []
    for i in range(1, 4):
        j_email = f"j{i}_{rand_id}@example.com"
        j_token = login(j_email)
        
        # Admin creates judge profile
        me_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {j_token}"})
        user_id = me_res.json()["id"]
        
        requests.post(f"{BASE_URL}/events/{event_id}/judges", json={
            "user_id": user_id,
            "capacity": 5,
            "expertise": []
        }, headers={"Authorization": f"Bearer {admin_token}"})
        
        j_tokens.append(j_token)
        j_ids.append(user_id)

    # 5. Fast-forward to Judging
    now = datetime.now(timezone.utc)
    requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": (now - timedelta(hours=4)).isoformat().replace("+00:00", "") + "Z",
        "registration_closes_at": (now - timedelta(hours=3)).isoformat().replace("+00:00", "") + "Z",
        "submission_opens_at": (now - timedelta(hours=3)).isoformat().replace("+00:00", "") + "Z",
        "submission_deadline": (now - timedelta(hours=2)).isoformat().replace("+00:00", "") + "Z",
        "judging_opens_at": (now - timedelta(hours=1)).isoformat().replace("+00:00", "") + "Z",
        "judging_deadline": (now + timedelta(hours=1)).isoformat().replace("+00:00", "") + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "JUDGING"}, headers={"Authorization": f"Bearer {admin_token}"})

    # 6. Run Assignment Engine
    preview_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign/preview", json={
        "optimization_restarts": 1,
        "seed": 42
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    commit_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assign", json={
        "optimization_restarts": 1,
        "seed": 42
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Assignment Commit", commit_res)

    assignments = commit_res.json()
    if not isinstance(assignments, list):
        print("Error: assignments not a list!")
        return

    # Let's find assignments for Judge 1
    j1_assignments = [a for a in assignments if a["judge_id"] == j_ids[0]]
    j2_assignments = [a for a in assignments if a["judge_id"] == j_ids[1]]

    print("\n--- Test 1: Judge Isolation (me) ---")
    my_res = requests.get(f"{BASE_URL}/events/{event_id}/judging/me", headers={"Authorization": f"Bearer {j_tokens[0]}"})
    my_assigned = my_res.json()
    print(f"J1 assignments: {len(my_assigned)}")
    if len(my_assigned) > 0 and len(my_assigned) == len(j1_assignments):
        print("Judge Isolation OK: Saw only own assignments.")
    else:
        print(f"Judge Isolation FAILED! Expected {len(j1_assignments)}, got {len(my_assigned)}")
        print(my_assigned)

    print("\n--- Test 2: Judge accessing another judge's assignment ---")
    # Try to access a project not assigned to J1 (assuming J2 has one that J1 doesn't)
    j1_sub_ids = {a["submission_id"] for a in j1_assignments}
    j2_only_subs = [a["submission_id"] for a in j2_assignments if a["submission_id"] not in j1_sub_ids]
    
    if j2_only_subs:
        forbidden_sub = j2_only_subs[0]
        forbidden_res = requests.get(f"{BASE_URL}/events/{event_id}/judging/submission/{forbidden_sub}", headers={"Authorization": f"Bearer {j_tokens[0]}"})
        print_res("Forbidden Submission Access", forbidden_res)
    else:
        print("Could not test forbidden access: no mutually exclusive assignments.")

    print("\n--- Test 3: Judge submitting evaluation ---")
    if j1_assignments:
        a_id = j1_assignments[0]["id"]
        eval_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/assignments/{a_id}/evaluation", json={
            "overall_comment": "Great work!",
            "scores": [
                {"criterion_id": c1_id, "score": 4},
                {"criterion_id": c2_id, "score": 5}
            ]
        }, headers={"Authorization": f"Bearer {j_tokens[0]}"})
        print_res("Submit Evaluation", eval_res)
    
    print("\n--- Test 4: Judge viewing results (Forbidden) ---")
    res_j1 = requests.get(f"{BASE_URL}/events/{event_id}/results", headers={"Authorization": f"Bearer {j_tokens[0]}"})
    print_res("Judge Results Access", res_j1)

    print("\n--- Test 5: Admin viewing results (Allowed) ---")
    res_admin = requests.get(f"{BASE_URL}/events/{event_id}/results", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Admin Results Access", res_admin)


if __name__ == "__main__":
    main()
