import requests
import json

def main():
    # Log in
    login_url = "http://localhost:3001/api/v1/auth/login"
    login_payload = {
        "username": "admin",
        "password": "Admin@123456"
    }
    r = requests.post(login_url, json=login_payload)
    print(f"Login Response: {r.status_code}")
    res = r.json()
    token = res.get("data", {}).get("accessToken") or res.get("accessToken")
    if not token:
        print("Failed to get token!")
        return
        
    # Fetch document content
    doc_id = "69f5c2d5-a117-4f21-8661-170e1ff5c77d"
    content_url = f"http://localhost:3001/api/v1/documents/{doc_id}/content"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    r2 = requests.get(content_url, headers=headers)
    print(f"Content API Response: {r2.status_code}")
    text = r2.text
    print(f"Text Length: {len(text)}")
    idx = text.lower().find("hear what")
    if idx != -1:
        print(repr(text[idx:idx+200]))
    else:
        print("No 'hear what' found in API response!")

if __name__ == "__main__":
    main()
