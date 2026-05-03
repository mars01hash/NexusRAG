
import requests
import json

def test_api():
    base_url = "http://127.0.0.1:8001"
    
    # Login
    login_url = f"{base_url}/auth/login"
    login_data = {"username": "admin", "password": "admin123"}
    resp = requests.post(login_url, json=login_data)
    token = resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Ask
    ask_url = f"{base_url}/ask"
    ask_data = {"question": "What is the Pink Palace?"}
    resp = requests.post(ask_url, json=ask_data, headers=headers)
    
    print("Response JSON:")
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    test_api()
