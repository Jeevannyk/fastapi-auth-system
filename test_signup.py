"""Test signup via API endpoint"""
import requests
import json

url = "http://127.0.0.1:8000/register"

data = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
}

print("🚀 Testing signup endpoint...")
print(f"URL: {url}")
print(f"Data: {data}")

try:
    response = requests.post(url, json=data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("\n✅ User created successfully via API!")
        print("\nLogin credentials:")
        print("  Username: testuser")
        print("  Password: password123")
    else:
        print(f"\n⚠️  Failed: {response.json()}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
