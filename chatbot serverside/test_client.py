"""
test_client.py
──────────────
Interactive CLI client to test streaming conversations with the Attendify Chatbot.
Run this in a separate terminal while your Uvicorn server is active.
"""
import asyncio
import json
import httpx
from app.core.security import create_access_token
from app.core.config import get_settings

settings = get_settings()
BASE_URL = "http://127.0.0.1:8050"

# ── MOCK TOKEN DEFINITION ────────────────────────────────────────────────────
# Toggle "role" between "student" and "lecturer" to test different agent paths!
MOCK_USER_PAYLOAD = {
    "sub": "56",
    "email": "ahmed6532256@gmail.com",
    "role": "student",  # ◄── Change to "lecturer" to test instructor tools
    "faculty_id": 1
}

token = create_access_token(MOCK_USER_PAYLOAD)
headers = {"Authorization": f"Bearer {token}"}


async def run_interactive_chat():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        print("\n🚀 Contacting backend gateway...")
        
        # 1. Initialize the session out-of-band
        try:
            init_resp = await client.post(f"{settings.api_v1_prefix}/chat/init", headers=headers)
            if init_resp.status_code != 200:
                print(f"❌ Initialization failed: {init_resp.text}")
                return
        except Exception as e:
            print(f"❌ Could not connect to server. Is Uvicorn running? Error: {e}")
            return

        init_data = init_resp.json()
        session_id = init_data["session_id"]
        
        print(f"✅ Session Active! Thread ID: {session_id}")
        print(f"👤 Simulated User Role: '{init_data['role']}'")
        print(f"🛡️ Active Guard Capabilities: {init_data['capabilities']}")
        print("=" * 60)
        print("Type your questions below. Type 'exit' or 'quit' to stop.")

        # 2. Real-time Stream Request Loop
        while True:
            try:
                user_message = input("\nYou: ").strip()
                if not user_message:
                    continue
                if user_message.lower() in ["exit", "quit"]:
                    print("👋 Closing test session.")
                    break

                payload = {
                    "session_id": session_id,
                    "message": user_message,
                    "course_context": "35"  # Static fallback string context
                }

                print("AI: ", end="", flush=True)

                async with client.stream(
                    "POST", 
                    f"{settings.api_v1_prefix}/chat/message", 
                    json=payload, 
                    headers=headers, 
                    timeout=30.0
                ) as response:
                    
                    if response.status_code == 422:
                        error_body = await response.aread()
                        print(f"\n❌ Validation Error Details:\n{error_body.decode()}")
                        continue
                    elif response.status_code != 200:
                        error_body = await response.aread()
                        print(f"\n❌ Server Error ({response.status_code}):\n{error_body.decode()}")
                        continue
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_content = line[6:].strip()
                            if not data_content or data_content == "{}":
                                continue
                                
                            try:
                                json_chunk = json.loads(data_content)
                                
                                # ✅ CRITICAL FIX: Ensure chunk is a dictionary before reading keys
                                if isinstance(json_chunk, dict):
                                    if "text" in json_chunk:
                                        raw_text = json_chunk["text"]
                                        
                                        # Clean up list-wrapped signed blocks if present
                                        if isinstance(raw_text, list) and len(raw_text) > 0:
                                            raw_text = raw_text[0].get("text", str(raw_text))
                                        elif isinstance(raw_text, str) and raw_text.startswith("[{'type':"):
                                            try:
                                                import ast
                                                parsed_list = ast.literal_eval(raw_text)
                                                if parsed_list and isinstance(parsed_list, list):
                                                    raw_text = parsed_list[0].get("text", raw_text)
                                            except Exception:
                                                pass
                                                
                                        print(raw_text, end="", flush=True)
                                        
                                    elif "detail" in json_chunk:
                                        print(f"\n⚠️ [Backend Tool Warning]: {json_chunk['detail']}")
                                    elif "error" in json_chunk:
                                        print(f"\n❌ [Backend Execution Error]: {json_chunk['error']}")
                                else:
                                    # Handle raw string data streams cleanly
                                    print(str(json_chunk), end="", flush=True)
                                    
                            except json.JSONDecodeError:
                                # Fallback for non-JSON content payloads
                                print(data_content, end="", flush=True)
                                
                        elif line.startswith("event: done"):
                            break
                print()

            except Exception as stream_err:
                import traceback
                print(f"\n❌ Client Connection Interrupted Details:")
                print(f"Exception Type: {type(stream_err).__name__}")
                print(f"Exception Message: {stream_err}")
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_interactive_chat())