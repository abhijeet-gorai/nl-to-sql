import requests
import json

def test_stream_chat():
    url = "http://localhost:8000/chat"
    payload = {"message": "Show me the first 3 rows"}
    
    print(f"Connecting to {url}...")
    with requests.post(url, json=payload, stream=True) as r:
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text}")
            return
            
        print("--- Stream Start ---")
        for line in r.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    print(f"Received: {data}")
                except json.JSONDecodeError:
                    print(f"Raw line: {line}")
        print("--- Stream End ---")

if __name__ == "__main__":
    test_stream_chat()
