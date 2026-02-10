
import logging
from local_processor import process_match_local

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

LOBBY_IDS = [
    5430489, 5460860, 5463408, 5466612, 5468509, 5469691, 5469867, 5495232, 5496705,
    5546449, 5547225, 5603097, 5604926, 5605357, 5606293, 5672573, 5674707, 5676869,
    5678354, 5709937, 5710685, 5711438, 5711582, 5763728, 5764904, 5824753, 5825725,
    5919858, 5921892
]

def batch_process():
    print(f"Starting batch processing for {len(LOBBY_IDS)} lobbies...")
    
    success_count = 0
    fail_count = 0
    skipped_count = 0
    
    for match_id in LOBBY_IDS:
        print(f"\nProcessing Lobby {match_id}...")
        try:
            # We don't want to auto-upload right now, just generate the JSONs locally
            # User said "generate the json file so that i can upload"
            result = process_match_local(str(match_id), admin_name="Skeez", upload_url=None)
            
            if result:
                success_count += 1
                print(f"✅ Successfully processed {match_id}")
            else:
                fail_count += 1
                print(f"❌ Failed to process {match_id}")
                
        except Exception as e:
            fail_count += 1
            print(f"❌ Exception processing {match_id}: {e}")
            
    print("\n--- Batch Processing Complete ---")
    print(f"Total: {len(LOBBY_IDS)}")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    batch_process()
