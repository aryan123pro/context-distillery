#!/usr/bin/env python3

import requests
import json
import sys
from datetime import datetime

def test_events_serialization():
    """Test that events endpoint returns proper JSON without ObjectId serialization issues"""
    
    base_url = "https://context-distillery.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print(f"🔍 Testing events endpoint JSON serialization...")
    print(f"   Base URL: {base_url}")
    
    try:
        # Step 1: Create a run
        print("\n1️⃣ Creating test run...")
        create_response = requests.post(f"{api_url}/runs", json={
            "objective": "Test events serialization",
            "scenario": "C",
            "config": {
                "use_llm": False,
                "stm_max_messages": 12,
                "compression_token_threshold": 2400,
                "compression_interval_steps": 3
            }
        }, timeout=30)
        
        if create_response.status_code != 200:
            print(f"❌ Failed to create run: {create_response.status_code}")
            return False
            
        run_data = create_response.json()
        run_id = run_data["run_id"]
        print(f"✅ Created run: {run_id}")
        
        # Step 2: Send a step to generate events
        print("\n2️⃣ Sending step to generate events...")
        step_response = requests.post(f"{api_url}/runs/{run_id}/step", json={
            "user_message": "Test message to generate events"
        }, timeout=30)
        
        if step_response.status_code != 200:
            print(f"❌ Failed to send step: {step_response.status_code}")
            return False
            
        print("✅ Step sent successfully")
        
        # Step 3: Test events endpoint
        print("\n3️⃣ Testing events endpoint...")
        events_response = requests.get(f"{api_url}/runs/{run_id}/events", timeout=30)
        
        if events_response.status_code != 200:
            print(f"❌ Events endpoint failed: {events_response.status_code}")
            print(f"   Response: {events_response.text}")
            return False
            
        print("✅ Events endpoint returned 200")
        
        # Step 4: Verify JSON serialization
        print("\n4️⃣ Verifying JSON serialization...")
        try:
            events_data = events_response.json()
            print("✅ Response is valid JSON")
        except json.JSONDecodeError as e:
            print(f"❌ Response is not valid JSON: {e}")
            return False
            
        # Step 5: Check response structure
        print("\n5️⃣ Checking response structure...")
        if "events" not in events_data:
            print("❌ Response missing 'events' field")
            return False
            
        events = events_data["events"]
        print(f"✅ Found {len(events)} events")
        
        # Step 6: Verify no ObjectId in events
        print("\n6️⃣ Verifying no ObjectId serialization issues...")
        events_json_str = json.dumps(events)
        
        if "ObjectId" in events_json_str:
            print("❌ Found ObjectId in events JSON - serialization issue!")
            return False
            
        print("✅ No ObjectId found in events JSON")
        
        # Step 7: Check event structure
        print("\n7️⃣ Checking event structure...")
        if len(events) > 0:
            first_event = events[0]
            required_fields = ["id", "run_id", "step_index", "ts", "type", "payload"]
            
            for field in required_fields:
                if field not in first_event:
                    print(f"❌ Missing required field '{field}' in event")
                    return False
                    
            print("✅ Event structure is correct")
            
            # Check payload is properly serialized
            payload = first_event.get("payload", {})
            payload_json_str = json.dumps(payload)
            
            if "ObjectId" in payload_json_str:
                print("❌ Found ObjectId in event payload - serialization issue!")
                return False
                
            print("✅ Event payload is properly serialized")
        
        print("\n🎉 Events serialization test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

def main():
    success = test_events_serialization()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())