import requests
import json
import uuid
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
J1_EMAIL = "j1_s8@example.com"
J2_EMAIL = "j2_s8@example.com"
P1_EMAIL = "p1_s8@example.com"
P2_EMAIL = "p2_s8@example.com"
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
    
    register(J1_EMAIL, "Judge 1")
    register(J2_EMAIL, "Judge 2")
    register(P1_EMAIL, "Participant 1")
    register(P2_EMAIL, "Participant 2")

    admin_token = login(ADMIN_EMAIL, "AdminPassword123!")
    j1_token = login(J1_EMAIL)
    j2_token = login(J2_EMAIL)
    p1_token = login(P1_EMAIL)
    p2_token = login(P2_EMAIL)

    # User IDs for judges
    users_req = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {j1_token}"})
    print("User ME:", users_req.json())
    j1_user_id = users_req.json().get("id")
    
    users_req2 = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {j2_token}"})
    j2_user_id = users_req2.json().get("id")

    event_slug = f"s8-ev-{uuid.uuid4().hex[:8]}"
    res_event = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 8 Event",
        "slug": event_slug,
        "description": "Event for step 8 testing"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    if res_event.status_code != 201:
        print("Failed to create event")
        return
    event_id = res_event.json().get("id")

    # Create Teams
    t1 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"T1 {uuid.uuid4().hex[:4]}"}, headers={"Authorization": f"Bearer {p1_token}"})
    t1_id = t1.json()['id']
    t2 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"T2 {uuid.uuid4().hex[:4]}"}, headers={"Authorization": f"Bearer {p2_token}"})
    t2_id = t2.json()['id']

    print("\n--- 6. Create a rubric ---")
    rubric1_res = requests.post(f"{BASE_URL}/events/{event_id}/rubrics", json={"name": "Tech Eval v1"}, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Create Rubric 1", rubric1_res)
    rubric1_id = rubric1_res.json()["id"]

    print("\n--- 9. Test Invalid Weighting ---")
    requests.post(f"{BASE_URL}/rubrics/{rubric1_id}/criteria", json={"name": "C1", "weight": 0.50, "min_score": 1, "max_score": 5}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/rubrics/{rubric1_id}/criteria", json={"name": "C2", "weight": 0.30, "min_score": 1, "max_score": 5}, headers={"Authorization": f"Bearer {admin_token}"})
    
    val_res1 = requests.get(f"{BASE_URL}/rubrics/{rubric1_id}/validate", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Validate (Invalid)", val_res1)
    
    act_res1 = requests.post(f"{BASE_URL}/rubrics/{rubric1_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Activate (Invalid -> 422)", act_res1)

    print("\n--- 7 & 10. Fix Weights & Activate ---")
    requests.post(f"{BASE_URL}/rubrics/{rubric1_id}/criteria", json={"name": "C3", "weight": 0.20, "min_score": 1, "max_score": 5}, headers={"Authorization": f"Bearer {admin_token}"})
    
    val_res2 = requests.get(f"{BASE_URL}/rubrics/{rubric1_id}/validate", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Validate (Valid)", val_res2)

    act_res2 = requests.post(f"{BASE_URL}/rubrics/{rubric1_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Activate (Valid)", act_res2)

    print("\n--- 11. Immutability ---")
    patch_rubric = requests.patch(f"{BASE_URL}/rubrics/{rubric1_id}", json={"name": "Changed"}, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Patch Active Rubric (-> 409)", patch_rubric)

    print("\n--- 12. Create Rubric Version 2 ---")
    rubric2_res = requests.post(f"{BASE_URL}/events/{event_id}/rubrics", json={"name": "Tech Eval v2"}, headers={"Authorization": f"Bearer {admin_token}"})
    rubric2_id = rubric2_res.json()["id"]
    requests.post(f"{BASE_URL}/rubrics/{rubric2_id}/criteria", json={"name": "C1", "weight": 1.0, "min_score": 1, "max_score": 5}, headers={"Authorization": f"Bearer {admin_token}"})
    act_res3 = requests.post(f"{BASE_URL}/rubrics/{rubric2_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Activate v2", act_res3)

    print("\n--- 13 & 14. Judge Profile ---")
    judge_res = requests.post(f"{BASE_URL}/events/{event_id}/judges", json={
        "user_id": j1_user_id,
        "capacity": 10,
        "expertise": ["cybersecurity"]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Create Judge Profile", judge_res)
    
    list_judges = requests.get(f"{BASE_URL}/events/{event_id}/judges", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("List Judges", list_judges)

    print("\n--- 15 & 16. Judge Invitations ---")
    inv_res = requests.post(f"{BASE_URL}/events/{event_id}/judge-invites", json={
        "invited_email": J2_EMAIL,
        "expires_hours": 72,
        "capacity": 12,
        "expertise": ["ai"]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Create Invite", inv_res)
    if inv_res.status_code == 201:
        token = inv_res.json()["token"]
        acc_res = requests.post(f"{BASE_URL}/judge-invites/{token}/accept", headers={"Authorization": f"Bearer {j2_token}"})
        print_res("Accept Invite", acc_res)

    print("\n--- 17 & 18. Judge Conflicts ---")
    list_judges2 = requests.get(f"{BASE_URL}/events/{event_id}/judges", headers={"Authorization": f"Bearer {admin_token}"})
    print_res("List Judges After Invite", list_judges2)
    j2_valid_user_id = list_judges2.json()[0]["user_id"]

    conf_res = requests.post(f"{BASE_URL}/events/{event_id}/judge-conflicts", json={
        "judge_id": j2_valid_user_id,
        "team_id": t1_id,
        "reason": "Mentor"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Create Conflict", conf_res)
    
    # Event B for cross-event test
    res_event_b = requests.post(f"{BASE_URL}/events", json={
        "name": "Event B", "slug": f"ev-b-{uuid.uuid4().hex[:8]}"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    t_b = requests.post(f"{BASE_URL}/events/{res_event_b.json()['id']}/teams", json={"name": "TB"}, headers={"Authorization": f"Bearer {p1_token}"})
    
    conf_b_res = requests.post(f"{BASE_URL}/events/{event_id}/judge-conflicts", json={
        "judge_id": j2_valid_user_id,
        "team_id": t_b.json()['id'],
        "reason": "Invalid"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Create Conflict (Cross-Event -> Error)", conf_b_res)

    print("\n--- 21. Event Transition to JUDGING ---")
    # Need to move through states
    now = datetime.utcnow()
    requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": (now - timedelta(hours=3)).isoformat() + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat() + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat() + "Z",
        "submission_deadline": (now - timedelta(minutes=1)).isoformat() + "Z",
        "judging_opens_at": (now).isoformat() + "Z",
        "judging_deadline": (now + timedelta(hours=1)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "REGISTRATION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "SUBMISSION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    
    judging_res = requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "JUDGING"}, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Transition to JUDGING", judging_res)
    
    # Let's test the error if rubric is missing by trying it on Event B
    requests.patch(f"{BASE_URL}/events/{res_event_b.json()['id']}", json={
        "registration_opens_at": (now - timedelta(hours=3)).isoformat() + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat() + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat() + "Z",
        "submission_deadline": (now - timedelta(minutes=1)).isoformat() + "Z",
        "judging_opens_at": (now).isoformat() + "Z",
        "judging_deadline": (now + timedelta(hours=1)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{res_event_b.json()['id']}/status", json={"status": "REGISTRATION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{res_event_b.json()['id']}/status", json={"status": "SUBMISSION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    
    judging_b_res = requests.post(f"{BASE_URL}/events/{res_event_b.json()['id']}/status", json={"status": "JUDGING"}, headers={"Authorization": f"Bearer {admin_token}"})
    print_res("Transition to JUDGING (No Rubric -> 409)", judging_b_res)

if __name__ == "__main__":
    main()
