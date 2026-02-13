import os, requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("MIXEDBREAD_API_KEY")
sid = os.getenv("MIXEDBREAD_STORE_ID")

if not key or not sid:
    print("❌ Missing Mixedbread key or store id")
    exit()

url = f"https://api.mixedbread.ai/v1/stores/{sid}"

resp = requests.get(url, headers={"Authorization": f"Bearer {key}"})
print("Status:", resp.status_code)
print("Response:", resp.text)
