from match_registry import init_match_registry, add_match_to_registry, get_match_status, get_pending_matches
from match_processor import process_match_queue
import logging

# Setup basic logging to see output
logging.basicConfig(level=logging.INFO)

print("--- 1. Initializing Registry ---")
init_match_registry()
print("Registry initialized.")

print("\n--- 2. Adding Test Match ---")
test_id = "test_match_12345"
if add_match_to_registry(test_id):
    print(f"Added {test_id} successfully.")
else:
    print(f"{test_id} already exists. Checking status...")
    print(f"Status: {get_match_status(test_id)}")

print(f"Pending matches: {get_pending_matches()}")

print("\n--- 3. Running Processor (Dry Run / Error Check) ---")
# This will likely fail the download since it's a fake ID, but should handle the error gracefully and mark as failed.
summary, logs = process_match_queue()
print(f"Summary: {summary}")
print("Logs:")
for log in logs:
    print(log)

print("\n--- 4. Checking Final Status ---")
final_status = get_match_status(test_id)
print(f"Final Status of {test_id}: {final_status}")

if final_status == 'failed':
    print("SUCCESS: System correctly handled a fake match ID and marked it as failed.")
else:
    print(f"WARNING: Unexpected status {final_status}")
