"""Test login via API endpoint"""
import requests
import json

url_login = "http://127.0.0.1:8000/login"

data = {
    "username": "testuser",
    "password": "password123"
}

print("🚀 Testing login endpoint...")
print(f"URL: {url_login}")
print(f"Credentials: username={data['username']}, password={data['password']}")

try:
    response = requests.post(url_login, json=data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        result = response.json()
        if 'access_token' in result:
            print("\n✅ Login successful!")
            print(f"Access Token: {result['access_token'][:50]}...")
        elif 'mfa_required' in result:
            print("\n✅ MFA required!")
            print(f"User ID: {result['user_id']}")
    else:
        print(f"\n❌ Login failed: {response.json()}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
