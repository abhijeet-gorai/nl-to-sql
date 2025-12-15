import requests
import os

BASE_URL = "http://localhost:8000"

def test_health():
    try:
        r = requests.get(f"{BASE_URL}/health")
        if r.status_code == 200:
            print("âœ… Health check passed")
        else:
            print(f"âŒ Health check failed: {r.status_code}")
    except:
        print("âŒ Backend not running")

def create_dummy_csv():
    content = "name,age,city\nAlice,30,New York\nBob,25,Los Angeles\nCharlie,35,Chicago"
    with open("test.csv", "w") as f:
        f.write(content)
    print("âœ… Created test.csv")

def test_upload():
    try:
        files = {'file': open('test.csv', 'rb')}
        r = requests.post(f"{BASE_URL}/upload", files=files)
        if r.status_code == 200:
            print("âœ… Upload passed")
            print("   Schema:", r.json()['schema'])
        else:
            print(f"âŒ Upload failed: {r.text}")
    except Exception as e:
        print(f"âŒ Upload error: {e}")

if __name__ == "__main__":
    test_health()
    create_dummy_csv()
    test_upload()
    # Clean up
    if os.path.exists("test.csv"):
        os.remove("test.csv")
