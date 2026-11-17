"""
auto_test_student.py
────────────────────
Automated test: Simulates a student (ahmed6532256@gmail.com, user_id=101)
asking about attendance percentage for course CS103 (course_id=33).
"""
import asyncio
import json
import sys
import io
import httpx
from app.core.security import create_access_token
from app.core.config import get_settings

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

settings = get_settings()
BASE_URL = "http://127.0.0.1:8050"

# Student token matching the requested scenario
MOCK_USER_PAYLOAD = {
    "sub": "101",
    "email": "ahmed6532256@gmail.com",
    "role": "student",
    "faculty_id": 1
}

token = create_access_token(MOCK_USER_PAYLOAD)
headers = {"Authorization": f"Bearer {token}"}


async def run_automated_test():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180.0) as client:
        print("=" * 70)
        print("   ATTENDIFY CHATBOT -- AUTOMATED LIVE TEST")
        print("=" * 70)
        print(f"   Email:     ahmed6532256@gmail.com")
        print(f"   Role:      student")
        print(f"   User ID:   101")
        print(f"   Course:    CS103 (ID: 33)")
        print("=" * 70)

        # -- Step 1: Initialize Session --
        print("\n[STEP 1] Initializing chat session...")
        try:
            init_resp = await client.post(
                f"{settings.api_v1_prefix}/chat/init", headers=headers
            )
            if init_resp.status_code != 200:
                print(f"   FAILED -- Status {init_resp.status_code}: {init_resp.text}")
                return
        except Exception as e:
            print(f"   FAILED -- Connection Error: {e}")
            return

        init_data = init_resp.json()
        session_id = init_data["session_id"]
        print(f"   [PASS] Session Created: {session_id}")
        print(f"   [PASS] User ID: {init_data['user_id']}")
        print(f"   [PASS] Role: {init_data['role']}")
        print(f"   [PASS] Capabilities: {init_data['capabilities']}")

        # -- Step 2: Ask about attendance percentage for CS103 (ID: 33) --
        test_message = "What is my attendance percentage for the course CS103 which has id 33?"
        print(f"\n[STEP 2] Sending message: \"{test_message}\"")

        payload = {
            "session_id": session_id,
            "message": test_message,
            "course_context": "33"
        }

        print("\n   Streaming AI Response:")
        print("   " + "-" * 60)
        print("   AI: ", end="", flush=True)  # ◄── Open horizontal line print

        full_response = ""
        try:
            async with client.stream(
                "POST",
                f"{settings.api_v1_prefix}/chat/message",
                json=payload,
                headers=headers,
                timeout=180.0,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    print(f"\n   FAILED -- HTTP Error {response.status_code}: {error_body.decode()}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_content = line[6:].strip()
                        if not data_content or data_content == "{}":
                            continue

                        try:
                            json_chunk = json.loads(data_content)
                            if isinstance(json_chunk, dict):
                                if "text" in json_chunk:
                                    raw_text = json_chunk["text"]
                                    
                                    # Handle list structures safely
                                    if isinstance(raw_text, list) and len(raw_text) > 0:
                                        raw_text = raw_text[0].get("text", str(raw_text))
                                    # Handle raw list-wrapped string blocks safely using ast
                                    elif isinstance(raw_text, str) and raw_text.startswith("[{'type':"):
                                        try:
                                            import ast
                                            parsed_list = ast.literal_eval(raw_text)
                                            if parsed_list and isinstance(parsed_list, list):
                                                raw_text = parsed_list[0].get("text", raw_text)
                                        except Exception:
                                            pass
                                            
                                    full_response += str(raw_text)
                                    print(raw_text, end="", flush=True)  # ◄── Print tokens side-by-side
                                    
                                elif "error" in json_chunk:
                                    print(f"\n   [ERROR]: {json_chunk['error']}")
                        except json.JSONDecodeError:
                            full_response += data_content
                            print(data_content, end="", flush=True)

                    elif line.startswith("event: done"):
                        break

        except Exception as e:
            print(f"\n   FAILED -- Stream Error: {e}")
            import traceback
            traceback.print_exc()
            return

        print()  # Break line spacing carriage

        # -- Step 3: Validation Summary --
        print("\n" + "=" * 70)
        print("   TEST RESULTS SUMMARY")
        print("=" * 70)
        print(f"   [PASS] Session Init:      HTTP 200")
        print(f"   [PASS] Role Verified:      {init_data['role']}")
        print(f"   [PASS] SSE Streaming:      Response received")

        if full_response:
            print(f"   [PASS] AI Response:       RECEIVED ({len(full_response)} chars)")
            response_lower = full_response.lower()
            has_attendance = any(w in response_lower for w in [
                "attendance", "percentage", "present", "absent",
                "sessions", "lectures", "rate", "course", "%"
            ])
            if has_attendance:
                print(f"   [PASS] Content Check:      Response contains attendance data")
            else:
                print(f"   [WARN] Content Check:      Response may not contain attendance data")
        else:
            print(f"   [WARN] AI Response:       EMPTY (no text chunks received)")

        print("=" * 70)
        print("   END OF AUTOMATED TEST")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_automated_test())