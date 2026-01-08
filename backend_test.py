#!/usr/bin/env python3

import requests
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

class ContextDistilleryTester:
    def __init__(self, base_url="https://context-distillery.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.current_run_id = None

    def log(self, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, data: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {"raw_response": response.text}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self) -> bool:
        """Test GET /api/ returns Context Distillery API"""
        success, response = self.run_test(
            "Root API endpoint",
            "GET", 
            "",
            200
        )
        if success and response.get("message") == "Context Distillery API":
            self.log("✅ Root endpoint returns correct message")
            return True
        else:
            self.log(f"❌ Root endpoint message mismatch: {response}")
            return False

    def test_create_run_llm_off(self) -> Optional[str]:
        """Test POST /api/runs creates run with LLM off (deterministic mode)"""
        success, response = self.run_test(
            "Create run (LLM off)",
            "POST",
            "runs",
            200,
            data={
                "objective": "Test objective for deterministic mode",
                "scenario": "C",
                "config": {
                    "use_llm": False,
                    "stm_max_messages": 12,
                    "compression_token_threshold": 2400,
                    "compression_interval_steps": 3
                }
            }
        )
        if success and "run_id" in response:
            run_id = response["run_id"]
            self.current_run_id = run_id
            self.log(f"✅ Created run with ID: {run_id}")
            return run_id
        return None

    def test_get_run(self, run_id: str) -> bool:
        """Test GET /api/runs/{run_id}"""
        success, response = self.run_test(
            f"Get run {run_id}",
            "GET",
            f"runs/{run_id}",
            200
        )
        if success and response.get("run_id") == run_id:
            self.log(f"✅ Retrieved run details for {run_id}")
            return True
        return False

    def test_step_endpoint(self, run_id: str) -> bool:
        """Test POST /api/runs/{run_id}/step"""
        success, response = self.run_test(
            f"Send step to run {run_id}",
            "POST",
            f"runs/{run_id}/step",
            200,
            data={"user_message": "This is a test message for the compression engine"}
        )
        if success and "step_index" in response:
            self.log(f"✅ Step completed, step_index: {response.get('step_index')}")
            return True
        return False

    def test_memory_endpoint(self, run_id: str) -> bool:
        """Test GET /api/runs/{run_id}/memory"""
        success, response = self.run_test(
            f"Get memory for run {run_id}",
            "GET",
            f"runs/{run_id}/memory",
            200
        )
        if success and "stm" in response and "cwm" in response:
            self.log(f"✅ Memory retrieved - STM: {len(response.get('stm', []))} messages")
            return True
        return False

    def test_events_endpoint(self, run_id: str) -> bool:
        """Test GET /api/runs/{run_id}/events"""
        success, response = self.run_test(
            f"Get events for run {run_id}",
            "GET",
            f"runs/{run_id}/events",
            200
        )
        if success and "events" in response:
            events = response.get("events", [])
            self.log(f"✅ Events retrieved - Count: {len(events)}")
            # Check for expected event types
            event_types = [e.get("type") for e in events]
            self.log(f"   Event types: {set(event_types)}")
            return True
        return False

    def test_force_compress(self, run_id: str) -> bool:
        """Test POST /api/runs/{run_id}/compress"""
        success, response = self.run_test(
            f"Force compress run {run_id}",
            "POST",
            f"runs/{run_id}/compress",
            200
        )
        if success and "cwm" in response:
            self.log(f"✅ Compression forced successfully")
            return True
        return False

    def test_demo_run_llm_off(self) -> bool:
        """Test POST /api/demo/run with LLM off"""
        success, response = self.run_test(
            "Demo run (LLM off)",
            "POST",
            "demo/run",
            200,
            data={
                "objective": "Demo objective for testing compression engine",
                "scenario": "C",
                "config": {
                    "use_llm": False,
                    "stm_max_messages": 12,
                    "compression_token_threshold": 1800,
                    "compression_interval_steps": 2
                }
            }
        )
        if success and "run_id" in response:
            demo_run_id = response["run_id"]
            self.log(f"✅ Demo run completed with ID: {demo_run_id}")
            return True
        return False

    def test_overwrite_behavior(self, run_id: str) -> bool:
        """Test overwrite behavior by sending conflicting messages"""
        # Send first constraint
        success1, _ = self.run_test(
            f"Send initial constraint to {run_id}",
            "POST",
            f"runs/{run_id}/step",
            200,
            data={"user_message": "Set compression threshold to 2000 tokens"}
        )
        
        time.sleep(1)  # Brief pause
        
        # Send conflicting constraint
        success2, _ = self.run_test(
            f"Send conflicting constraint to {run_id}",
            "POST",
            f"runs/{run_id}/step", 
            200,
            data={"user_message": "Actually, change compression threshold to 1500 tokens instead"}
        )
        
        if success1 and success2:
            # Check memory to see if overwrite behavior is reflected
            success3, memory_response = self.run_test(
                f"Check memory after overwrite for {run_id}",
                "GET",
                f"runs/{run_id}/memory",
                200
            )
            
            if success3:
                cwm = memory_response.get("cwm", {})
                constraints = cwm.get("constraints", [])
                self.log(f"✅ Overwrite test completed - CWM has {len(constraints)} constraints")
                return True
        
        return False

    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        self.log("🚀 Starting Context Distillery API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
        # Test 1: Root endpoint
        if not self.test_root_endpoint():
            self.log("❌ Root endpoint failed - stopping tests")
            return False
            
        # Test 2: Create run (LLM off for reliability)
        run_id = self.test_create_run_llm_off()
        if not run_id:
            self.log("❌ Run creation failed - stopping tests")
            return False
            
        # Test 3: Get run details
        if not self.test_get_run(run_id):
            self.log("❌ Get run failed")
            
        # Test 4: Send step
        if not self.test_step_endpoint(run_id):
            self.log("❌ Step endpoint failed")
            
        # Test 5: Get memory
        if not self.test_memory_endpoint(run_id):
            self.log("❌ Memory endpoint failed")
            
        # Test 6: Get events  
        if not self.test_events_endpoint(run_id):
            self.log("❌ Events endpoint failed")
            
        # Test 7: Force compression
        if not self.test_force_compress(run_id):
            self.log("❌ Force compress failed")
            
        # Test 8: Demo run
        if not self.test_demo_run_llm_off():
            self.log("❌ Demo run failed")
            
        # Test 9: Overwrite behavior
        if not self.test_overwrite_behavior(run_id):
            self.log("❌ Overwrite behavior test failed")
        
        return True

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*50)
        self.log(f"📊 Test Summary:")
        self.log(f"   Tests run: {self.tests_run}")
        self.log(f"   Tests passed: {self.tests_passed}")
        self.log(f"   Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 All tests passed!")
            return 0
        else:
            self.log("⚠️  Some tests failed")
            return 1

def main():
    tester = ContextDistilleryTester()
    tester.run_comprehensive_test()
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())