import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('mysql+mysqlconnector://root:root123@localhost/ipl_analytics')

# Top batters with mock auction prices
batters = pd.read_sql("""
    SELECT batter as player_name, 
           SUM(batsman_runs) as total_runs,
           COUNT(DISTINCT match_id) as matches,
           ROUND(SUM(batsman_runs)/COUNT(DISTINCT match_id), 2) as avg_runs_per_match,
           'Batter' as role
    FROM deliveries 
    GROUP BY batter 
    ORDER BY total_runs DESC 
    LIMIT 50
""", engine)

# Top bowlers with mock auction prices
bowlers = pd.read_sql("""
    SELECT bowler as player_name,
           COUNT(*) as total_wickets,
           COUNT(DISTINCT match_id) as matches,
           ROUND(COUNT(*)/COUNT(DISTINCT match_id), 2) as avg_wickets_per_match,
           'Bowler' as role
    FROM deliveries
    WHERE is_wicket=1
    AND dismissal_kind NOT IN ('run out','retired hurt','obstructing the field')
    GROUP BY bowler
    ORDER BY total_wickets DESC
    LIMIT 50
""", engine)

# Add mock auction prices based on performance
import numpy as np

def assign_price_batter(row):
    if row['total_runs'] > 6000: return round(np.random.uniform(14, 18), 1)
    elif row['total_runs'] > 4000: return round(np.random.uniform(10, 14), 1)
    elif row['total_runs'] > 2000: return round(np.random.uniform(6, 10), 1)
    elif row['total_runs'] > 1000: return round(np.random.uniform(3, 6), 1)
    else: return round(np.random.uniform(0.5, 3), 1)

def assign_price_bowler(row):
    if row['total_wickets'] > 150: return round(np.random.uniform(12, 18), 1)
    elif row['total_wickets'] > 100: return round(np.random.uniform(8, 12), 1)
    elif row['total_wickets'] > 50: return round(np.random.uniform(4, 8), 1)
    elif row['total_wickets'] > 20: return round(np.random.uniform(2, 4), 1)
    else: return round(np.random.uniform(0.5, 2), 1)

batters['auction_price_cr'] = batters.apply(assign_price_batter, axis=1)
batters['total_wickets'] = 0
batters['avg_wickets_per_match'] = 0

bowlers['auction_price_cr'] = bowlers.apply(assign_price_bowler, axis=1)
bowlers['total_runs'] = 0
bowlers['avg_runs_per_match'] = 0

# Combine
players = pd.concat([batters, bowlers], ignore_index=True)
players.drop_duplicates(subset=['player_name'], keep='first', inplace=True)

# Push to MySQL
players.to_sql('player_auction', con=engine, if_exists='replace', index=False)
print(f"Created player_auction table with {len(players)} players")
print(players.head())