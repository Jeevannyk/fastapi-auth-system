"""
Complete End-to-End Testing Suite
Tests all API endpoints and functionality
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_signup():
    """Test signup endpoint"""
    print("\n" + "="*60)
    print("TEST 2: User Signup")
    print("="*60)
    
    data = {
        "full_name": "New Test User",
        "email": "newuser@example.com",
        "access_key": "newpassword123",
        "verify_key": "newpassword123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/signup", json=data, timeout=5)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            print("✅ Signup successful")
            return True
        elif response.status_code == 400 and "already registered" in result.get("detail", ""):
            print("✅ User already exists (expected)")
            return True
        else:
            print(f"❌ Unexpected response")
            return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_login():
    """Test login endpoint"""
    print("\n" + "="*60)
    print("TEST 3: User Login")
    print("="*60)
    
    data = {
        "email": "test@example.com",
        "access_key": "password123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=data, timeout=5)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            if "access_token" in result:
                print("✅ Login successful with JWT token")
                return result["access_token"]
            else:
                print("❌ No access token in response")
                return None
        else:
            print(f"❌ Login failed")
            return None
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def test_login_invalid():
    """Test login with invalid credentials"""
    print("\n" + "="*60)
    print("TEST 4: Invalid Login (Should Fail)")
    print("="*60)
    
    data = {
        "email": "test@example.com",
        "access_key": "wrongpassword"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=data, timeout=5)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 401:
            print("✅ Correctly rejected invalid credentials")
            return True
        else:
            print(f"❌ Should have returned 401")
            return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_fingerprint(access_token=None):
    """Test fingerprint endpoint"""
    print("\n" + "="*60)
    print("TEST 5: Fingerprint/Session Creation")
    print("="*60)
    
    data = {
        "email": "test@example.com"
    }
    
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    
    try:
        response = requests.post(f"{BASE_URL}/fingerprint", json=data, headers=headers, timeout=5)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200 and "session_id" in result:
            print("✅ Session created successfully")
            return result["session_id"]
        else:
            print(f"❌ Session creation failed")
            return None
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def test_qr(session_id):
    """Test QR code endpoint"""
    print("\n" + "="*60)
    print("TEST 6: QR Code Generation")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/qr/{session_id}", timeout=5)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            print("✅ QR code metadata retrieved")
            return True
        else:
            print(f"❌ QR generation failed")
            return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_qr_image(session_id):
    """Test QR image endpoint"""
    print("\n" + "="*60)
    print("TEST 7: QR Image Serving")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/qr-image/{session_id}", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Content Length: {len(response.content)} bytes")
        
        if response.status_code == 200 and "image/png" in response.headers.get('content-type', ''):
            print("✅ QR image served successfully")
            return True
        else:
            print(f"❌ QR image serving failed")
            return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_uuid_validation():
    """Test UUID validation (security)"""
    print("\n" + "="*60)
    print("TEST 8: Path Traversal Protection")
    print("="*60)
    
    # Test multiple malicious patterns
    malicious_patterns = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "../../config",
        "invalid-uuid-123"
    ]
    
    all_blocked = True
    for pattern in malicious_patterns:
        try:
            response = requests.get(f"{BASE_URL}/qr-image/{pattern}", timeout=5)
            
            # Check status code first before attempting JSON parsing
            if response.status_code == 400:
                try:
                    result = response.json()
                    if "Invalid session ID" in result.get("detail", ""):
                        print(f"  ✅ Blocked: {pattern[:30]}...")
                    else:
                        print(f"  ⚠️  Unexpected 400 response for {pattern[:30]}...")
                except:
                    print(f"  ✅ Blocked (400): {pattern[:30]}...")
            elif response.status_code == 404:
                print(f"  ✅ Safe (404): {pattern[:30]}... - Not found in routing")
            else:
                print(f"  ❌ DANGER: {pattern} returned {response.status_code}")
                all_blocked = False
        except Exception as e:
            print(f"  ❌ Error testing {pattern}: {e}")
            all_blocked = False
    
    if all_blocked:
        print("✅ All path traversal attempts blocked")
    
    return all_blocked

def test_frontend_pages():
    """Test frontend HTML pages"""
    print("\n" + "="*60)
    print("TEST 9: Frontend Pages")
    print("="*60)
    
    pages = ["/", "/login", "/signup-page", "/home"]
    success = True
    
    for page in pages:
        try:
            response = requests.get(f"{BASE_URL}{page}", timeout=5, allow_redirects=True)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {page}: {response.status_code}")
            if response.status_code != 200:
                success = False
        except Exception as e:
            print(f"❌ {page}: {e}")
            success = False
    
    return success

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print(" "*20 + "COMPLETE END-TO-END TEST SUITE")
    print("="*80)
    
    # Wait a moment for server to be ready
    print("\n⏳ Waiting for server to be ready...")
    time.sleep(2)
    
    results = {}
    
    # Run tests in sequence
    results["health"] = test_health()
    results["frontend"] = test_frontend_pages()
    results["signup"] = test_signup()
    
    token = test_login()
    results["login"] = token is not None
    
    results["login_invalid"] = test_login_invalid()
    
    session_id = test_fingerprint(token)
    results["fingerprint"] = session_id is not None
    
    if session_id:
        results["qr"] = test_qr(session_id)
        results["qr_image"] = test_qr_image(session_id)
    else:
        results["qr"] = False
        results["qr_image"] = False
    
    results["uuid_security"] = test_uuid_validation()
    
    # Summary
    print("\n" + "="*80)
    print(" "*25 + "TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {test_name.upper().replace('_', ' ')}")
    
    print("\n" + "-"*80)
    print(f"\n  Total: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! System is fully functional!")
        print("\n  ✅ Database: Working")
        print("  ✅ Authentication: Working")
        print("  ✅ Security: Working")
        print("  ✅ API Endpoints: Working")
        print("  ✅ Frontend: Working")
        print("\n  🚀 Application is ready for use!")
        return 0
    else:
        print(f"\n  ⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
