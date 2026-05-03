
import requests
import time

def trigger_rebuild():
    base_url = "http://localhost:8000"
    
    # Login
    print("Logging in...")
    login_res = requests.post(f"{base_url}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if not login_res.ok:
        print(f"Login failed: {login_res.text}")
        return
    
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Trigger reindex
    print("Triggering reindex...")
    reindex_res = requests.post(f"{base_url}/reindex", headers=headers)
    if not reindex_res.ok:
        print(f"Reindex trigger failed: {reindex_res.text}")
        return
    
    print("Reindex started. Polling status...")
    
    # Poll status
    for _ in range(30):
        status_res = requests.get(f"{base_url}/reindex/status", headers=headers)
        status = status_res.json()
        print(f"Status: {status['status']} - {status['message']}")
        
        if status["status"] == "done":
            print("Reindex successful!")
            return
        if status["status"] == "error":
            print(f"Reindex failed: {status['message']}")
            return
        
        time.sleep(2)
    
    print("Timed out waiting for reindex")

if __name__ == "__main__":
    trigger_rebuild()
