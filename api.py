import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from match_stats_db import save_match_stats

app = FastAPI()

class MatchData(BaseModel):
    match_id: str
    map_name: str
    score_str: str
    score_t: int
    score_ct: int
    player_stats: List[Dict[str, Any]]

@app.post("/upload_match")
async def upload_match(data: MatchData):
    try:
        print(f"Received upload for match {data.match_id}")
        
        # Convert player_stats list back to DataFrame
        if not data.player_stats:
             raise HTTPException(status_code=400, detail="No player stats provided")
             
        df = pd.DataFrame(data.player_stats)
        
        # Save to DB using existing logic
        # Note: Since we are running outside Streamlit here, ensure valid database access
        save_match_stats(
            match_id=data.match_id,
            cybershoke_id=data.match_id, # using match_id as cybershoke_id for now
            score_str=data.score_str,
            stats_df=df,
            map_name=data.map_name,
            score_t=data.score_t,
            score_ct=data.score_ct
        )
        
        return {"status": "success", "message": f"Match {data.match_id} saved successfully"}
        
    except Exception as e:
        print(f"Error saving match: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
