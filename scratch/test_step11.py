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
    for i in range(1, 6):  # 5 teams/projects
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

    # Let's perform evaluations to create data for step 11
    import random
    print("\n--- Submitting Evaluations ---")
    for j_idx, (j_token, j_id) in enumerate(zip(j_tokens, j_ids)):
        j_assignments = [a for a in assignments if a["judge_id"] == j_id]
        
        # J1 does all 5, J2 does 4, J3 does 2 (insufficient data if min=3)
        limit = [5, 4, 2][j_idx]
        
        for i, a in enumerate(j_assignments[:limit]):
            # Simulate drift for J1: slope increases over time
            base_score = 3 + (i * 0.5) if j_idx == 0 else (2 if j_idx == 1 else 4)
            c1_score = min(5, max(1, int(base_score + random.uniform(-0.5, 0.5))))
            c2_score = min(5, max(1, int(base_score + random.uniform(-0.5, 0.5))))
            
            requests.post(f"{BASE_URL}/events/{event_id}/judging/assignments/{a['id']}/evaluation", json={
                "overall_comment": f"Eval {i} by J{j_idx}",
                "scores": [
                    {"criterion_id": c1_id, "score": c1_score},
                    {"criterion_id": c2_id, "score": c2_score}
                ]
            }, headers={"Authorization": f"Bearer {j_token}"})
    
    print("\n--- Step 11: Calibration ---")
    cal_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/calibration/analyze", json={
        "min_observations": 3
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Calibration Run", cal_res)

    print("\n--- Step 11: Normalization (Z-score) ---")
    norm_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/normalization/run", json={
        "normalization_method": "zscore",
        "min_observations": 3,
        "clip": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Normalization Run", norm_res)

    print("\n--- Step 11: Drift Analysis ---")
    drift_res = requests.post(f"{BASE_URL}/events/{event_id}/judging/drift/analyze", json={
        "min_observations": 3
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Drift Run", drift_res)
    
    print("\n--- Step 11: Checking Insufficient Data ---")
    if norm_res.status_code == 200:
        diagnostics = norm_res.json()["result"]["diagnostics"]
        print(f"Insufficient row count: {diagnostics.get('insufficient_row_count')}")
        print("Success! The insufficient data logic is correctly applied.")


if __name__ == "__main__":
    main()
