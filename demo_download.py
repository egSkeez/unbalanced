
import requests
import os
import zipfile
from cybershoke import get_headers

DEMO_DIR = "demos"

def download_demo(match_id, admin_name="Skeez", direct_url=None):
    """
    Downloads the match demo from Cybershoke.
    Tries multiple endpoints if direct_url is not provided.
    Automatically extracts .zip files.
    """
    if not os.path.exists(DEMO_DIR):
        os.makedirs(DEMO_DIR)

    headers = get_headers(admin_name)
    headers["Referer"] = f"https://cybershoke.net/match/{match_id}"
    
    urls_to_try = []
    if direct_url:
        urls_to_try.append(direct_url)
    else:
        urls_to_try = [
             f"https://cdn-de-1.cybershoke.net/demos/{match_id}",
             f"https://api.cybershoke.net/api/v1/custom-matches/lobbys/{match_id}/demo",
             f"https://cybershoke.net/api/match/{match_id}/demo",
             f"https://api.cybershoke.net/api/v1/match/{match_id}/demo",
             f"https://api.cybershoke.net/api/v1/matches/{match_id}/demo"
        ]
    
    last_error = ""

    for url in urls_to_try:
        print(f"Attempting download from: {url}")
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=15)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'html' in content_type:
                    last_error = f"Endpoint {url} returned HTML page, not file."
                    continue
                
                # Determine filename
                filename = f"match_{match_id}.dem"
                cd = response.headers.get('content-disposition', '')
                if 'filename=' in cd:
                    filename = cd.split('filename=')[1].strip('"')
                elif 'bz2' in content_type:
                    filename = f"match_{match_id}.dem.bz2"
                elif 'zip' in content_type:
                    filename = f"match_{match_id}.zip"
                
                filepath = os.path.join(DEMO_DIR, filename)
                
                # Download file
                bytes_downloaded = 0
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                
                msg = f"Downloaded {filename} ({bytes_downloaded/1024/1024:.2f} MB)"
                
                # Extract if it's a zip
                if filename.endswith('.zip'):
                    print(f"Extracting {filename}...")
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zip_ref:
                            # Extract all files
                            zip_ref.extractall(DEMO_DIR)
                        
                        # Find the .dem file
                        dem_files = [f for f in os.listdir(DEMO_DIR) if f.endswith('.dem') and match_id in f]
                        if not dem_files:
                            # Try any .dem file
                            dem_files = [f for f in os.listdir(DEMO_DIR) if f.endswith('.dem')]
                        
                        if dem_files:
                            # Rename to standard format
                            extracted_dem = os.path.join(DEMO_DIR, dem_files[0])
                            target_dem = os.path.join(DEMO_DIR, f"match_{match_id}.dem")
                            
                            # Only rename if different
                            if os.path.abspath(extracted_dem) != os.path.abspath(target_dem):
                                # Remove old file if exists
                                if os.path.exists(target_dem):
                                    os.remove(target_dem)
                                # Rename extracted file
                                os.rename(extracted_dem, target_dem)
                            
                            msg += f" → Extracted to match_{match_id}.dem"
                        else:
                            return False, "Downloaded zip but no .dem file found inside"
                        
                        # Clean up zip
                        os.remove(filepath)
                    except Exception as e:
                        return False, f"Downloaded but extraction failed: {e}"
                
                return True, msg
            
            elif response.status_code == 403:
                last_error = f"403 Forbidden at {url}. Check Cookies or Headers."
            elif response.status_code == 404:
                last_error = f"404 Not Found at {url}."
            else:
                last_error = f"Status {response.status_code} at {url}."

        except Exception as e:
            last_error = f"Error connecting to {url}: {e}"
    
    return False, f"Failed to download demo. Last error: {last_error}"
