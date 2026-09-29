import requests
import json
import time
import subprocess

BASE_URL = "http://localhost:8000/api/v1"
PARTICIPANT_EMAIL = "test.user3@example.com"
PARTICIPANT_PASS = "TestPassword123!"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "AdminPassword123!"

def print_res(name, res):
    print(f"--- {name} ---")
    print(f"Status: {res.status_code}")
    print(f"Body: {res.text[:200]}")
    print()

def main():
    print("3.8 Testing Health")
    res = requests.get(f"{BASE_URL}/health")
    print_res("Health", res)
    res = requests.get(f"{BASE_URL}/health/db")
    print_res("Health DB", res)

    print("Registering Participant")
    requests.post(f"{BASE_URL}/auth/register", json={
        "email": PARTICIPANT_EMAIL,
        "display_name": "Test User 2",
        "password": PARTICIPANT_PASS
    })

    print("Registering Admin")
    requests.post(f"{BASE_URL}/auth/register", json={
        "email": ADMIN_EMAIL,
        "display_name": "Admin User",
        "password": ADMIN_PASS
    })

    print("Promoting admin in DB manually...")
    subprocess.run([
        "docker", "exec", "judgeguard-postgres", "psql", "-U", "judgeguard", "-d", "judgeguard",
        "-c", f"UPDATE users SET role = 'ADMIN' WHERE email = '{ADMIN_EMAIL}';"
    ])
    
    print("3.10 Login as Participant")
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": PARTICIPANT_EMAIL,
        "password": PARTICIPANT_PASS
    })
    print_res("Participant Login", res)
    p_token = res.json().get("token")
    p_id = res.json().get("user", {}).get("id")

    print("3.11 Try to create an event as participant")
    res = requests.post(f"{BASE_URL}/events", json={
        "name": "Hackerthon",
        "slug": "hackerthon-2028",
        "voting_access": "AUTHENTICATED"
    }, headers={"Authorization": f"Bearer {p_token}"})
    print_res("Participant Create Event", res)

    print("3.15 Try to promote self as participant")
    res = requests.patch(f"{BASE_URL}/users/{p_id}/role", json={
        "role": "ORGANIZER"
    }, headers={"Authorization": f"Bearer {p_token}"})
    print_res("Participant Self-Promote", res)

    print("3.12 Login as Admin")
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    print_res("Admin Login", res)
    a_token = res.json().get("token")

    print("3.12 Admin List Users")
    res = requests.get(f"{BASE_URL}/users", headers={"Authorization": f"Bearer {a_token}"})
    print_res("Admin List Users", res)

    print("3.13 Admin Promote Participant to Organizer")
    res = requests.patch(f"{BASE_URL}/users/{p_id}/role", json={
        "role": "ORGANIZER"
    }, headers={"Authorization": f"Bearer {a_token}"})
    print_res("Admin Promote", res)

    print("3.14 Try creating event as Organizer")
    res = requests.post(f"{BASE_URL}/events", json={
        "name": "Hackerthon",
        "slug": "hackerthon-2028",
        "voting_access": "AUTHENTICATED"
    }, headers={"Authorization": f"Bearer {p_token}"})
    print_res("Organizer Create Event", res)

if __name__ == "__main__":
    main()
