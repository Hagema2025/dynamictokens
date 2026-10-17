import time
import os
import json
import base64
import requests
from DrissionPage import ChromiumOptions, ChromiumPage

# GitHub Configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO_SHOWS = os.getenv("GITHUB_REPO_SHOWS")
GITHUB_TOKEN_SHOWS = os.getenv("GITHUB_TOKEN_SHOWS")
GITHUB_SDYNAMICTOKENS_PATH = os.getenv("GITHUB_SDYNAMICTOKENS_PATH")
GITHUB_BRANCH_SHOWS = os.getenv("GITHUB_BRANCH_SHOWS", "main") # Assuming main branch as default

def _github_headers(isWatch=False):
    # Helper to return appropriate auth headers
    token = GITHUB_TOKEN_SHOWS # Adapt if you use a different token for isWatch
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def _github_get_file(path, isWatch):
    repo = GITHUB_REPO_SHOWS # Defaulting to shows repo based on your context
    r = requests.get(f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}", headers=_github_headers(isWatch), timeout=20)
    if r.status_code == 404: 
        return None, None
    r.raise_for_status()
    payload = r.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(raw), payload.get("sha")

def _github_put_file(path, data, message, isWatch):
    repo = GITHUB_REPO_SHOWS 
    branch = GITHUB_BRANCH_SHOWS 
    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}"
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    
    for attempt in range(3):
        _, sha = _github_get_file(path, isWatch)
        body = {
            "message": message, 
            "content": base64.b64encode(content.encode()).decode(), 
            "branch": branch
        }
        if sha: 
            body["sha"] = sha
        r = requests.put(url, headers=_github_headers(isWatch), json=body, timeout=20)
        if r.status_code in (200, 201): 
            return
        if r.status_code == 409 and attempt < 2: 
            continue
        r.raise_for_status()
    raise RuntimeError(f"Could not update GitHub file: {path}")

def extract_tokens():
    co = ChromiumOptions()
    co.headless(False) 
    page = ChromiumPage(co)
    
    page.listen.start('in.bookmyshow.com/api/') 
    
    print("🌍 Navigating to region context (Chennai)...")
    page.get("https://in.bookmyshow.com/explore/home/chennai")
    
    # Wait longer in a datacenter environment
    print("⏳ Waiting 15 seconds for Cloudflare...")
    time.sleep(15) 
    
    # Take a picture of what the browser is actually seeing
    page.get_screenshot(path="cloudflare_debug.png")
    print("📸 Saved debug screenshot.")
    
    tokens = {"x-token": None, "bmsId": None, "cf_clearance": None}
    
    # 1. EXTRACT COOKIES
    for cookie in page.cookies():
        if cookie.get("name") == "cf_clearance":
            tokens["cf_clearance"] = cookie.get("value")
        elif cookie.get("name") == "bmsId":
            tokens["bmsId"] = cookie.get("value")
            
    # 2. NAVIGATE TO TRIGGER THE TOKEN
    print("🎬 Navigating to a movie page to trigger API requests...")
    page.get("https://in.bookmyshow.com/chennai/movies")
    
    # 3. INTERCEPT THE X-TOKEN
    try:
        packet = page.listen.wait(timeout=5)
        if packet:
            req_headers = packet.request.headers
            tokens["x-token"] = req_headers.get("x-token") or req_headers.get("X-Token")
            print("✅ Successfully intercepted x-token from network traffic!")
    except Exception as e:
        print(f"⚠️ Could not intercept token: {e}")
        
    page.listen.stop()
    page.quit()
    
    # 4. DEBUG AND STORE IN GITHUB
    print("\n--- 📊 TOKEN EXTRACTION RESULTS ---")
    print(f"bmsId: {'✅ FOUND' if tokens['bmsId'] else '❌ MISSING'}")
    print(f"cf_clearance: {'✅ FOUND' if tokens['cf_clearance'] else '❌ MISSING'}")
    print(f"x-token: {'✅ FOUND' if tokens['x-token'] else '❌ MISSING'}")
    print("-----------------------------------\n")

    if all([tokens["x-token"], tokens["bmsId"], tokens["cf_clearance"]]):
        print("💾 All tokens acquired successfully. Saving to GitHub...")
        try:
            _github_put_file(
                path=GITHUB_SDYNAMICTOKENS_PATH, 
                data=tokens, 
                message="Automated token update", 
                isWatch=False
            )
            print("✅ Successfully pushed dynamictokens.json to GitHub!")
        except Exception as e:
            print(f"❌ Failed to push to GitHub: {e}")
    else:
        print("⚠️ Missing one or more tokens. Skipping GitHub update.")
        
    return tokens
if __name__ == "__main__":
    extract_tokens()
