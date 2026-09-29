import requests
import json
import uuid
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@example.com"
P1_EMAIL = "p1_s7@example.com"
P2_EMAIL = "p2_s7@example.com"
P3_EMAIL = "p3_s7@example.com"
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
    
    register(P1_EMAIL, "Participant 1 S7")
    register(P2_EMAIL, "Participant 2 S7")
    register(P3_EMAIL, "Participant 3 S7")

    admin_token = login(ADMIN_EMAIL, "AdminPassword123!")
    p1_token = login(P1_EMAIL)
    p2_token = login(P2_EMAIL)
    p3_token = login(P3_EMAIL)

    event_slug = f"s7-event-{uuid.uuid4().hex[:8]}"
    res_event = requests.post(f"{BASE_URL}/events", json={
        "name": "Step 7 Event",
        "slug": event_slug,
        "description": "Event for step 7 testing"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    if res_event.status_code != 201:
        print("Failed to create event")
        return
    event_id = res_event.json().get("id")

    # Create Track
    res_track = requests.post(f"{BASE_URL}/events/{event_id}/tracks", json={
        "name": "Cybersecurity",
        "slug": f"cyber-{uuid.uuid4().hex[:8]}",
        "description": "Security-focused projects"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    track_id = res_track.json().get("id")

    # Make event SUBMISSION_OPEN
    now = datetime.utcnow()
    requests.patch(f"{BASE_URL}/events/{event_id}", json={
        "registration_opens_at": (now - timedelta(hours=3)).isoformat() + "Z",
        "registration_closes_at": (now - timedelta(hours=2)).isoformat() + "Z",
        "submission_opens_at": (now - timedelta(hours=1)).isoformat() + "Z",
        "submission_deadline": (now + timedelta(hours=1)).isoformat() + "Z"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "REGISTRATION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})
    requests.post(f"{BASE_URL}/events/{event_id}/status", json={"status": "SUBMISSION_OPEN"}, headers={"Authorization": f"Bearer {admin_token}"})

    # P1 Creates Team and Draft Submission
    t1 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"T1 {uuid.uuid4().hex[:4]}"}, headers={"Authorization": f"Bearer {p1_token}"})
    s1 = requests.post(f"{BASE_URL}/teams/{t1.json()['id']}/submissions", json={
      "name": "Draft Project",
      "tagline": "Hidden from gallery",
      "description": "Draft",
      "tech_tags": ["Python"]
    }, headers={"Authorization": f"Bearer {p1_token}"})
    draft_id = s1.json()['id']

    # P2 Creates Team, Submission, and Submits
    t2 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"T2 {uuid.uuid4().hex[:4]}"}, headers={"Authorization": f"Bearer {p2_token}"})
    s2 = requests.post(f"{BASE_URL}/teams/{t2.json()['id']}/submissions", json={
      "name": "Alpha Security",
      "tagline": "Secure your web apps",
      "description": "Uses AI to secure web apps.",
      "tech_tags": ["Python", "FastAPI"],
      "track_id": track_id
    }, headers={"Authorization": f"Bearer {p2_token}"})
    sub2_id = s2.json()['id']
    requests.post(f"{BASE_URL}/submissions/{sub2_id}/submit", headers={"Authorization": f"Bearer {p2_token}"})

    # P3 Creates Team, Submission, and Submits
    t3 = requests.post(f"{BASE_URL}/events/{event_id}/teams", json={"name": f"T3 {uuid.uuid4().hex[:4]}"}, headers={"Authorization": f"Bearer {p3_token}"})
    s3 = requests.post(f"{BASE_URL}/teams/{t3.json()['id']}/submissions", json={
      "name": "Beta Tools",
      "tagline": "Developer tools made easy",
      "description": "Build things fast.",
      "tech_tags": ["TypeScript", "React"]
    }, headers={"Authorization": f"Bearer {p3_token}"})
    sub3_id = s3.json()['id']
    requests.post(f"{BASE_URL}/submissions/{sub3_id}/submit", headers={"Authorization": f"Bearer {p3_token}"})

    print("\n--- Gallery Test: Base ---")
    g_base = requests.get(f"{BASE_URL}/events/{event_id}/gallery")
    print_res("Gallery Base", g_base)

    print("\n--- Gallery Test: Search ---")
    g_search = requests.get(f"{BASE_URL}/events/{event_id}/gallery?q=security")
    print_res("Gallery Search", g_search)

    print("\n--- Gallery Test: Track ---")
    g_track = requests.get(f"{BASE_URL}/events/{event_id}/gallery?track_id={track_id}")
    print_res("Gallery Track", g_track)

    print("\n--- Gallery Test: Tag ---")
    g_tag = requests.get(f"{BASE_URL}/events/{event_id}/gallery?tag=fastapi")
    print_res("Gallery Tag", g_tag)

    print("\n--- Gallery Test: Sorting ---")
    g_sort_newest = requests.get(f"{BASE_URL}/events/{event_id}/gallery?sort=NEWEST")
    print_res("Sort NEWEST", g_sort_newest)
    
    g_sort_random = requests.get(f"{BASE_URL}/events/{event_id}/gallery?sort=RANDOM")
    print_res("Sort RANDOM", g_sort_random)

    print("\n--- Gallery Test: Details ---")
    g_detail = requests.get(f"{BASE_URL}/events/{event_id}/gallery/{sub2_id}")
    print_res("Gallery Detail (Valid)", g_detail)

    g_detail_draft = requests.get(f"{BASE_URL}/events/{event_id}/gallery/{draft_id}")
    print_res("Gallery Detail (Draft - Should be 404)", g_detail_draft)

if __name__ == "__main__":
    main()
