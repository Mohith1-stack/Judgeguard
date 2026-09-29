import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "AdminPassword123!"

def print_res(name, res):
    print(f"--- {name} ---")
    print(f"Status: {res.status_code}")
    try:
        print(f"Body: {json.dumps(res.json(), indent=2)[:500]}")
    except:
        print(f"Body: {res.text[:200]}")
    print()

def main():
    print("Health Checks")
    print_res("Health", requests.get(f"{BASE_URL}/health"))
    print_res("Health DB", requests.get(f"{BASE_URL}/health/db"))

    print("Login as Admin")
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    token = res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    unique_slug = f"my-hackathon-{uuid.uuid4().hex[:8]}"

    print("Create Event")
    res_create = requests.post(f"{BASE_URL}/events", json={
        "name": "My Hackathon",
        "slug": unique_slug,
        "description": "Test event"
    }, headers=headers)
    print_res("Create Event", res_create)
    
    if res_create.status_code != 201:
        print("Failed to create event. Exiting.")
        return

    event_id = res_create.json().get("id")

    print("Test Date Validation (Impossible Dates)")
    res_invalid = requests.post(f"{BASE_URL}/events", json={
        "name": "Invalid Event",
        "slug": f"invalid-{uuid.uuid4().hex[:8]}",
        "registration_opens_at": "2026-09-28T12:00:00Z",
        "registration_closes_at": "2026-09-28T10:00:00Z"
    }, headers=headers)
    print_res("Invalid Dates Event", res_invalid)

    print("Test Duplicate Slug")
    res_duplicate = requests.post(f"{BASE_URL}/events", json={
        "name": "My Hackathon Duplicate",
        "slug": unique_slug,
        "description": "Test event duplicate"
    }, headers=headers)
    print_res("Duplicate Slug Event", res_duplicate)

    print("Test Event Detail")
    res_detail = requests.get(f"{BASE_URL}/events/{event_id}", headers=headers)
    print_res("Event Detail", res_detail)

    print("Add a Track")
    res_track = requests.post(f"{BASE_URL}/events/{event_id}/tracks", json={
        "name": "Cybersecurity",
        "slug": "cybersecurity",
        "description": "Security-focused projects"
    }, headers=headers)
    print_res("Add Track", res_track)

    print("Add a Prize")
    res_prize = requests.post(f"{BASE_URL}/events/{event_id}/prizes", json={
        "name": "First Place",
        "description": "Grand prize",
        "amount": 800,
        "rank": 1
    }, headers=headers)
    print_res("Add Prize", res_prize)

    print("Test Lifecycle Transition: DRAFT -> JUDGING (Invalid)")
    res_invalid_transition = requests.post(f"{BASE_URL}/events/{event_id}/status", json={
        "status": "JUDGING"
    }, headers=headers)
    print_res("Invalid Transition (DRAFT -> JUDGING)", res_invalid_transition)

    print("Configure Registration Window (Update Event)")
    res_update = requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": "2026-09-28T10:00:00Z",
        "registration_closes_at": "2026-09-29T10:00:00Z"
    }, headers=headers)
    print_res("Configure Registration Window", res_update)

    print("Test Lifecycle Transition: DRAFT -> REGISTRATION_OPEN (Valid)")
    res_valid_transition = requests.post(f"{BASE_URL}/events/{event_id}/status", json={
        "status": "REGISTRATION_OPEN"
    }, headers=headers)
    print_res("Valid Transition", res_valid_transition)

if __name__ == "__main__":
    main()
