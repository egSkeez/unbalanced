
import pandas as pd
import json
import subprocess
import os
import sys
import platform
import shutil
import tarfile
import urllib.request
import re

def install_go_if_needed(target_version="1.22.0"):
    """
    Checks if 'go' is available and is a sufficient version.
    If not, downloads and installs a local copy of Go.
    Returns the path to the go executable.
    """
    system = platform.system()
    # Define current directory for installation
    base_dir = os.path.dirname(os.path.abspath(__file__))
    go_root = os.path.join(base_dir, "go_dist")
    
    # Executable naming
    exe_name = "go.exe" if system == "Windows" else "go"
    
    # 1. Check system Go
    system_go = shutil.which("go")
    if system_go:
        try:
            res = subprocess.run([system_go, "version"], capture_output=True, text=True)
            # Output example: "go version go1.21.3 linux/amd64"
            match = re.search(r"go(\d+)\.(\d+)", res.stdout)
            if match:
                major, minor = int(match.group(1)), int(match.group(2))
                # We need at least 1.21 for unsafe.StringData (technically 1.20 but lets be safe)
                if major > 1 or (major == 1 and minor >= 21):
                    # print(f"System Go version {major}.{minor} is sufficient.")
                    return system_go
        except Exception:
            pass
            
    # 2. Check local Go
    local_go_bin = os.path.join(go_root, "go", "bin", exe_name)
    if os.path.exists(local_go_bin):
        # We assume if it exists, it's the one we downloaded
        return local_go_bin
        
    # 3. Download and Install
    print(f"Installing Go {target_version} locally...")
    
    if system == "Linux":
        url = f"https://go.dev/dl/go{target_version}.linux-amd64.tar.gz"
        filename = "go_tar.tar.gz"
    elif system == "Windows":
        # Windows typically relies on user install, but we can try zip
        url = f"https://go.dev/dl/go{target_version}.windows-amd64.zip"
        filename = "go_zip.zip"
        # If user is on windows they probably have go, but this handles edge cases
    else:
        # Darwin/MacOS not primarily supported for this cloud patch but good to have
        return "go" 

    try:
        if not os.path.exists(go_root):
            os.makedirs(go_root)
            
        archive_path = os.path.join(go_root, filename)
        print(f"Downloading {url}...")
        urllib.request.urlretrieve(url, archive_path)
        
        print("Extracting...")
        if filename.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(go_root)
        else:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=go_root)
                
        # Cleanup
        os.remove(archive_path)
        
        if os.path.exists(local_go_bin):
            print("Go installed successfully.")
            return local_go_bin
            
    except Exception as e:
        print(f"Failed to install Go: {e}")
        
    return "go" # Fallback to system go command even if it fails later
    
def analyze_demo_file(demo_path):


    """
    Analyzes a .dem file using the external Go parser.
    Returns:
    - score_str: String describing match result
    - stats_df: DataFrame with player stats
    - map_name: Map name
    - score_t: T side score
    - score_ct: CT side score
    """
    # Determine current OS and binary name
    import platform
    system = platform.system()
    binary_name = "parser.exe" if system == "Windows" else "parser"
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    go_dir = os.path.join(current_dir, "go_parser")
    go_binary = os.path.join(go_dir, binary_name)
    go_source = os.path.join(go_dir, "main.go")
    
    # Ensure Go is installed
    go_exe_path = install_go_if_needed()
    
    # Check if binary exists, if not, try to build it
    if not os.path.exists(go_binary):
        print(f"Parser binary not found at {go_binary}. Attempting to build from source...")
        if os.path.exists(go_source):
            try:
                # Build command: go build -o parser.exe main.go
                # Important: Use the specific go executable we found/installed
                build_cmd = [go_exe_path, "build", "-o", binary_name, "main.go"]
                print(f"Running build: {' '.join(build_cmd)}")
                
                # Setup environment variables to include the new go bin in path if needed
                env = os.environ.copy()
                if "go_dist" in go_exe_path:
                   # Attempt to set GOROOT/PATH if we are using local go
                   # Assuming go_exe_path is .../go/bin/go
                   go_bin_dir = os.path.dirname(go_exe_path)
                   go_home_dir = os.path.dirname(go_bin_dir) # .../go
                   env["GOROOT"] = go_home_dir
                   env["PATH"] = go_bin_dir + os.pathsep + env.get("PATH", "")
                
                build_res = subprocess.run(build_cmd, cwd=go_dir, capture_output=True, text=True, env=env)
                
                if build_res.returncode == 0:
                    print("Build successful.")
                else:
                    print(f"Build failed: {build_res.stderr}")
                    return f"Build Error: {build_res.stderr}", None, "Unknown", 0, 0
            except Exception as e:
                print(f"Could not build Go parser: {e}")
                return "Build Failed (Go installed?)", None, "Unknown", 0, 0
        else:
            print(f"Go source not found at {go_source}")
            return "Parser Source Not Found", None, "Unknown", 0, 0
            
    if not os.path.exists(go_binary):
        return "Parser not found and build failed", None, "Unknown", 0, 0

    try:
        # Run Go parser
        print(f"Running Go parser on: {demo_path}")
        result = subprocess.run([go_binary, demo_path], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            print(f"Go parser error: {result.stderr}")
            return f"Parser Error: {result.stderr}", None, "Unknown", 0, 0
            
        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON: {result.stdout}")
            return "JSON Error", None, "Unknown", 0, 0
            
        if data.get("error"):
            print(f"Parser reported error: {data['error']}")
            return f"Error: {data['error']}", None, "Unknown", 0, 0

        # Extract basic info
        score_str = data.get("score_str", "Unknown")
        map_name = data.get("map_name", "Unknown")
        score_t = data.get("score_t", 0)
        score_ct = data.get("score_ct", 0)
        
        stats_list = data.get("stats", [])
        
        if not stats_list:
            print("No stats found in parser output")
            return score_str, None, map_name, score_t, score_ct
            
        # Convert to DataFrame
        stats_df = pd.DataFrame(stats_list)
        
        # Ensure columns exist and order them
        expected_cols = ['Player', 'SteamID', 'TeamNum', 'Kills', 'Deaths', 'Assists', 'K/D', 'ADR', 'HS%', 'Score', 
                         'Damage', 'UtilityDamage', 'Flashed', 'TeamFlashed', 'FlashAssists', 
                         'TotalSpent', 'EntryKills', 'EntryDeaths', 'ClutchWins', 
                         'BombPlants', 'BombDefuses', 'Headshots', 'MultiKills', 'WeaponKills']
        
        for col in expected_cols:
            if col not in stats_df.columns:
                # specific handling for object/map columns
                if col in ['MultiKills', 'WeaponKills']:
                     stats_df[col] = [{} for _ in range(len(stats_df))]
                else:
                     stats_df[col] = 0
                
        # Sort by Score or Kills
        stats_df = stats_df.sort_values("Score", ascending=False)
        
        print(f"Successfully parsed stats for {len(stats_df)} players")
        return score_str, stats_df, map_name, score_t, score_ct

    except Exception as e:
        print(f"Error executing Go parser: {e}")
        return f"Execution Error: {str(e)}", None, "Unknown", 0, 0
