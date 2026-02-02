package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	demoinfocs "github.com/markus-wa/demoinfocs-golang/v4/pkg/demoinfocs"
	"github.com/markus-wa/demoinfocs-golang/v4/pkg/demoinfocs/common"
	"github.com/markus-wa/demoinfocs-golang/v4/pkg/demoinfocs/events"
)

// PlayerStats holds the aggregated stats for a player
type PlayerStats struct {
	Player        string         `json:"Player"`
	SteamID       uint64         `json:"SteamID"`
	TeamNum       int            `json:"TeamNum"`
	Kills         int            `json:"Kills"`
	Deaths        int            `json:"Deaths"`
	Assists       int            `json:"Assists"`
	KD            float64        `json:"K/D"`
	ADR           float64        `json:"ADR"`
	HSPercent     float64        `json:"HS%"`
	Score         int            `json:"Score"`
	Damage        int            `json:"Damage"`
	UtilityDamage int            `json:"UtilityDamage"`
	Flashed       int            `json:"Flashed"`     // Number of enemies flashed
	TeamFlashed   int            `json:"TeamFlashed"` // Number of teammates flashed
	FlashAssists  int            `json:"FlashAssists"`
	TotalSpent    int            `json:"TotalSpent"`
	EntryKills    int            `json:"EntryKills"`
	EntryDeaths   int            `json:"EntryDeaths"`
	ClutchWins    int            `json:"ClutchWins"`  // 1vX wins
	MultiKills    map[int]int    `json:"MultiKills"`  // 1k, 2k, 3k, 4k, 5k count
	WeaponKills   map[string]int `json:"WeaponKills"` // Kills per weapon
	BombPlants    int            `json:"BombPlants"`
	BombDefuses   int            `json:"BombDefuses"`
	Headshots     int            `json:"Headshots"` // Raw count
}

// MatchResult holds the final output structure
type MatchResult struct {
	ScoreStr string        `json:"score_str"`
	Stats    []PlayerStats `json:"stats"`
	MapName  string        `json:"map_name"`
	ScoreT   int           `json:"score_t"`
	ScoreCT  int           `json:"score_ct"`
	Error    string        `json:"error,omitempty"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go_parser <demo_file>")
		os.Exit(1)
	}

	demoPath := os.Args[1]
	f, err := os.Open(demoPath)
	if err != nil {
		outputError(fmt.Sprintf("Error opening file: %v", err))
		return
	}
	defer f.Close()

	p := demoinfocs.NewParser(f)
	defer p.Close()

	// Stats accumulation
	stats := make(map[uint64]*PlayerStats) // Keyed by SteamID64

	// Helper to get or create stats
	getStats := func(p *common.Player) *PlayerStats {
		if p == nil {
			return nil
		}
		if _, ok := stats[p.SteamID64]; !ok {
			stats[p.SteamID64] = &PlayerStats{
				Player:      p.Name,
				SteamID:     p.SteamID64,
				TeamNum:     int(p.Team),
				MultiKills:  make(map[int]int),
				WeaponKills: make(map[string]int),
			}
		}
		// Update name/team just in case
		s := stats[p.SteamID64]
		if p.Name != "" {
			s.Player = p.Name
		}
		if p.Team > 0 {
			s.TeamNum = int(p.Team)
		}
		return s
	}

	// Variables for round tracking
	// var currentRoundDamage map[uint64]int // Unused
	var totalRounds int
	var scoreT, scoreCT int

	// Round-specific temp data
	var roundKills map[uint64]int
	var firstKillOccurred bool

	// Init round data
	p.RegisterEventHandler(func(e events.RoundStart) {
		roundKills = make(map[uint64]int)
		firstKillOccurred = false
	})

	// Init for first round
	roundKills = make(map[uint64]int)

	// Basic Handlers
	p.RegisterEventHandler(func(e events.Kill) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		kStats := getStats(e.Killer)
		vStats := getStats(e.Victim)
		aStats := getStats(e.Assister)

		if kStats != nil {
			kStats.Kills++
			roundKills[e.Killer.SteamID64]++

			if e.IsHeadshot {
				kStats.Headshots++
			}

			// Weapon Stats
			if e.Weapon != nil {
				wName := e.Weapon.String()
				kStats.WeaponKills[wName]++
			}

			// Entry Kill Logic
			if !firstKillOccurred {
				kStats.EntryKills++
				if vStats != nil {
					vStats.EntryDeaths++
				}
				firstKillOccurred = true
			}
		}
		if vStats != nil {
			vStats.Deaths++
		}
		if aStats != nil {
			aStats.Assists++
			if e.AssistedFlash {
				aStats.FlashAssists++
			}
		}
	})

	p.RegisterEventHandler(func(e events.PlayerHurt) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		if e.Attacker != nil {
			s := getStats(e.Attacker)
			if s != nil {
				s.Damage += e.HealthDamage

				// Utility Damage
				if e.Weapon != nil && (e.Weapon.Type == common.EqMolotov || e.Weapon.Type == common.EqIncendiary || e.Weapon.Type == common.EqHE) {
					s.UtilityDamage += e.HealthDamage
				}
			}
		}
	})

	p.RegisterEventHandler(func(e events.PlayerFlashed) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		// PlayerFlashed: e.Player (victim), e.Attacker (thrower)
		if e.Attacker != nil && e.Player != nil && e.Attacker.Team != e.Player.Team {
			s := getStats(e.Attacker)
			if s != nil {
				s.Flashed++
			}
		} else if e.Attacker != nil && e.Player != nil && e.Attacker.Team == e.Player.Team {
			// Team flash
			s := getStats(e.Attacker)
			if s != nil {
				s.TeamFlashed++
			}
		}
	})

	p.RegisterEventHandler(func(e events.BombPlanted) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		s := getStats(e.Player)
		if s != nil {
			s.BombPlants++
		}
	})

	p.RegisterEventHandler(func(e events.BombDefused) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		s := getStats(e.Player)
		if s != nil {
			s.BombDefuses++
		}
	})

	// Match Start / Round tracking for ADR
	p.RegisterEventHandler(func(e events.RoundEnd) {
		if !p.GameState().IsMatchStarted() {
			return
		}
		totalRounds++

		// Process Multi-Kills
		for steamID, kills := range roundKills {
			if kills > 0 {
				s := stats[steamID]
				if s != nil {
					s.MultiKills[kills]++
				}
			}
		}

		// Logic to determine Clutches would go here, requires tracking alive players per tick or snapshotting at death
		// Simplified Clutch Logic: Winner survives alone against X enemies
		// This is complex to do accurately without tick-state, skipping precise clutch for now or infer at end of round
	})

	// Parse to end
	err = p.ParseToEnd()
	if err != nil {
		outputError(fmt.Sprintf("Error parsing demo: %v", err))
		return
	}

	// Finalizing Data
	gameState := p.GameState()
	tTeam := gameState.Team(common.TeamTerrorists)
	ctTeam := gameState.Team(common.TeamCounterTerrorists)

	if tTeam != nil {
		scoreT = tTeam.Score()
	}
	if ctTeam != nil {
		scoreCT = ctTeam.Score()
	}

	scoreStr := fmt.Sprintf("T %d - %d CT", scoreT, scoreCT)

	// Check header for map
	header := p.Header()
	mapName := header.MapName
	if strings.HasPrefix(mapName, "de_") {
		mapName = strings.Title(mapName[3:])
	}

	// Process stats map into slice
	var statsList []PlayerStats
	for _, s := range stats {
		// Calculate derived stats
		if s.Kills > 0 {
			s.HSPercent = (float64(s.Headshots) / float64(s.Kills)) * 100
		}
		if s.Deaths == 0 {
			s.KD = float64(s.Kills)
		} else {
			s.KD = float64(s.Kills) / float64(s.Deaths)
		}
		if totalRounds > 0 {
			s.ADR = float64(s.Damage) / float64(totalRounds)
		}
		// Rounding
		s.KD = float64(int(s.KD*100)) / 100
		s.HSPercent = float64(int(s.HSPercent*10)) / 10
		s.ADR = float64(int(s.ADR*10)) / 10

		statsList = append(statsList, *s)
	}

	// Sort by Kills or Score (Naive Score: K*2 + A*1 + D*-1? Or just damage. User had Score from game)
	// We didn't track "Score" explicitly from GameState, but we could have read it from p.GameState().Participants()
	// Let's do a pass using Participants() for final Score/Money if possible,
	// BUT Participants() refers to current state at end of demo.
	// Best to rely on accumulated stats or capture Score from Participants at end.

	for _, participant := range gameState.Participants().All() {
		s := getStats(participant)
		if s != nil {
			s.Score = participant.Score()
			// s.TotalSpent is tricky, might need to track ItemPickup or similar event, or MoneySpent event if available
		}
	}

	// Sort
	sort.Slice(statsList, func(i, j int) bool {
		return statsList[i].Score > statsList[j].Score // Descending
	})

	result := MatchResult{
		ScoreStr: scoreStr,
		Stats:    statsList,
		MapName:  mapName,
		ScoreT:   scoreT,
		ScoreCT:  scoreCT,
	}

	encoder := json.NewEncoder(os.Stdout)
	encoder.Encode(result)
}

func outputError(msg string) {
	json.NewEncoder(os.Stdout).Encode(MatchResult{
		Error: msg,
	})
}
