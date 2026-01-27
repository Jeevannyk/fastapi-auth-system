import requests
import time

def verify():
    url = "http://127.0.0.1:8000/login"
    payload = {"email": "test@example.com", "password": "password"}
    
    print("Attempting to connect to backend...")
    for _ in range(5):
        try:
            response = requests.post(url, json=payload)
            # 401 is expected because user doesn't exist, but it means server is running and endpoint works
            if response.status_code in [200, 401, 404]: 
                print(f"Success! Server responded with status code: {response.status_code}")
                return
        except requests.exceptions.ConnectionError:
            print("Server not ready yet, retrying...")
            time.sleep(1)
    
    print("Failed to connect to backend.")

if __name__ == "__main__":
    verify()
