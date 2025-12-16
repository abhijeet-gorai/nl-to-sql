import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_revamp_flow():
    # 0. Health
    print("Testing /health...")
    r = requests.get(f"{BASE_URL}/health")
    print(r.json())

    # 1. Analyze Upload
    print("\nTesting /analyze...")
    files = {'file': ('test.csv', 'name,age\nAlice,30\nBob,25', 'text/csv')}
    r = requests.post(f"{BASE_URL}/analyze", files=files)
    if r.status_code != 200:
        print(f"Analyze failed: {r.text}")
        return
    data = r.json()
    print(f"Analyze success. Suggested name: {data['suggested_table_name']}")
    
    # 2. Register Table
    print("\nTesting /register...")
    metadata = {
        "table_name": data['suggested_table_name'],
        "original_filename": "test.csv",
        "description": "Test dataset",
        "columns": data['columns']
    }
    payload = {
        "file_path": data['file_path'],
        "metadata": metadata
    }
    r = requests.post(f"{BASE_URL}/register", json=payload)
    if r.status_code != 200:
        print(f"Register failed: {r.text}")
        return
    print("Register success.")
    
    # 3. List Tables
    print("\nTesting /tables...")
    r = requests.get(f"{BASE_URL}/tables")
    tables = r.json()
    print(f"Found {len(tables)} tables.")
    print(tables)
    
    # 4. Chat with context
    print("\nTesting /chat with context...")
    chat_payload = {
        "message": "Show me the first row",
        "selected_tables": [data['suggested_table_name']]
    }
    # Just check if it connects, streaming response is hard to parse in simple script
    with requests.post(f"{BASE_URL}/chat", json=chat_payload, stream=True) as r:
        if r.status_code == 200:
           print("Chat connected successfully.")
        else:
           print(f"Chat failed: {r.text}")

if __name__ == "__main__":
    test_revamp_flow()
