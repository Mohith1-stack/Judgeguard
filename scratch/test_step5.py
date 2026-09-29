import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "AdminPassword123!"

P1_EMAIL = "test.p1@example.com"
P2_EMAIL = "friend@example.com"
P3_EMAIL = "another@example.com"
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

def login(email, password):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    return res.json().get("token")

def main():
    print("Health Checks")
    requests.get(f"{BASE_URL}/health")

    # Register users
    register(P1_EMAIL, "Participant 1")
    register(P2_EMAIL, "Participant 2")
    register(P3_EMAIL, "Participant 3")

    admin_token = login(ADMIN_EMAIL, ADMIN_PASS)
    p1_token = login(P1_EMAIL, PASS)
    p2_token = login(P2_EMAIL, PASS)
    p3_token = login(P3_EMAIL, PASS)

    if not admin_token:
        print("Admin login failed, please ensure admin exists.")
        return

    # Create Event as Admin
    unique_slug = f"hackathon-{uuid.uuid4().hex[:8]}"
    res_event = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 5 Event",
        "slug": unique_slug,
        "description": "Event for step 5 testing"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    if res_event.status_code != 201:
        print("Failed to create event!")
        print_res("Create Event", res_event)
        return
    
    event_id = res_event.json().get("id")

    # Update event to allow teams (REGISTRATION_OPEN)
    requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": "2026-09-28T10:00:00Z",
        "registration_closes_at": "2026-09-29T10:00:00Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={
        "status": "REGISTRATION_OPEN"
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Test 1 - Create Team as P1
    print("\nTest 1 - Create Team as P1")
    res_team = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={
        "name": "Cyber Crew"
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Create Cyber Crew", res_team)
    team_id = res_team.json().get("id")

    # Test 2 - Check ownership
    print("\nTest 2 - Check Ownership")
    res_team_get = requests.get(f"{BASE_URL}/teams/{team_id}", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Get Team", res_team_get)

    # Test 3 - Duplicate team name
    print("\nTest 3 - Duplicate Team Name")
    res_dup = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={
        "name": "cyber crew"
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Duplicate Team", res_dup)

    # Test 4 - One team per participant
    print("\nTest 4 - One team per participant")
    res_one = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={
        "name": "Another Team"
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Another Team", res_one)

    # Test 5 - Create invitation
    print("\nTest 5 - Create Invitation")
    res_invite = requests.post(f"{BASE_URL}/teams/{team_id}/invites", json={
        "invited_email": P2_EMAIL,
        "expires_hours": 48
    }, headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Create Invite", res_invite)
    token = res_invite.json().get("token")

    # Test 6 - Join using the invitation
    print("\nTest 6 - Join using invitation")
    res_join = requests.post(f"{BASE_URL}/teams/join/{token}", headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Join Team", res_join)

    # Test 7 - Reuse the invitation
    print("\nTest 7 - Reuse invitation")
    res_reuse = requests.post(f"{BASE_URL}/teams/join/{token}", headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Reuse Invite", res_reuse)

    # Test 8 - Wrong email
    print("\nTest 8 - Wrong Email")
    res_invite_p3 = requests.post(f"{BASE_URL}/teams/{team_id}/invites", json={
        "invited_email": "someone@example.com",
        "expires_hours": 48
    }, headers={"Authorization": f"Bearer {p1_token}"})
    token_p3 = res_invite_p3.json().get("token")
    res_join_wrong = requests.post(f"{BASE_URL}/teams/join/{token_p3}", headers={"Authorization": f"Bearer {p3_token}"})
    print_res("Wrong Email", res_join_wrong)

    # Test 9 - One participant cannot join two teams
    print("\nTest 9 - One participant cannot join two teams")
    # P1 creates another event so P3 can create a team there?
    # No, let P3 create a team in the SAME event.
    res_team2 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={
        "name": "Cyber Squad"
    }, headers={"Authorization": f"Bearer {p3_token}"})
    team2_id = res_team2.json().get("id")
    # P3 invites P2
    res_invite_t2 = requests.post(f"{BASE_URL}/teams/{team2_id}/invites", json={
        "invited_email": P2_EMAIL,
        "expires_hours": 48
    }, headers={"Authorization": f"Bearer {p3_token}"})
    token_t2 = res_invite_t2.json().get("token")
    # P2 tries to join
    res_join_t2 = requests.post(f"{BASE_URL}/teams/join/{token_t2}", headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Join Second Team", res_join_t2)

    # Test 10 - Owner protection
    print("\nTest 10 - Owner Protection")
    res_leave = requests.post(f"{BASE_URL}/teams/{team_id}/leave", headers={"Authorization": f"Bearer {p1_token}"})
    print_res("Owner Leave", res_leave)

    # Test 11 - Backend Authorization
    print("\nTest 11 - Backend Authorization")
    res_auth1 = requests.patch(f"{BASE_URL}/teams/{team_id}", json={
        "name": "Hacked Team"
    }, headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Non-Owner Patch", res_auth1)
    
    res_auth2 = requests.post(f"{BASE_URL}/teams/{team_id}/invites", json={
        "invited_email": "test@test.com",
        "expires_hours": 48
    }, headers={"Authorization": f"Bearer {p2_token}"})
    print_res("Non-Owner Invite", res_auth2)

if __name__ == "__main__":
    main()
