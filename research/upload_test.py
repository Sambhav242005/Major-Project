import httpx
import time

headers = {"Authorization": "Bearer dev-token-123"}

with open(r"C:\Users\NPC\Desktop\MajorProject\research\test_small.txt", "rb") as f:
    files = {"file": ("test_small.txt", f, "text/plain")}
    response = httpx.post("http://localhost:8000/documents", files=files, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")

if response.status_code == 202:
    doc_id = response.json()["id"]
    print(f"Doc ID: {doc_id}")

    for i in range(30):
        time.sleep(3)
        status = httpx.get(f"http://localhost:8000/documents/{doc_id}/status", headers=headers, timeout=10)
        data = status.json()
        print(f"Attempt {i+1}: {data['status']}")
        if data["status"] in ("processed", "failed"):
            print(f"Final: {data}")
            break
