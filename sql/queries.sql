USE ipl_analytics;

-- Q1: Total matches played per season
SELECT season, COUNT(*) AS total_matches
FROM matches
GROUP BY season
ORDER BY season;

-- Q2: Top 10 teams by win count
SELECT winner, COUNT(*) AS total_wins
FROM matches
WHERE winner != ''
GROUP BY winner
ORDER BY total_wins DESC
LIMIT 10;

-- Q3: Toss impact - does winning toss help win the match?
SELECT toss_decision,
       COUNT(*) AS total_matches,
       SUM(CASE WHEN toss_winner = winner THEN 1 ELSE 0 END) AS toss_winner_won,
       ROUND(SUM(CASE WHEN toss_winner = winner THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS win_percentage
FROM matches
GROUP BY toss_decision;

-- Q4: Top 10 venues by number of matches hosted
SELECT venue, COUNT(*) AS matches_hosted
FROM matches
GROUP BY venue
ORDER BY matches_hosted DESC
LIMIT 10;

-- Q5: Win percentage by batting first vs second per season
SELECT season,
       SUM(CASE WHEN result = 'runs' THEN 1 ELSE 0 END) AS batting_first_wins,
       SUM(CASE WHEN result = 'wickets' THEN 1 ELSE 0 END) AS chasing_wins,
       COUNT(*) AS total_matches,
       ROUND(SUM(CASE WHEN result = 'runs' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS bat_first_win_pct
FROM matches
GROUP BY season
ORDER BY season;

-- Q6: Top 10 batters by total runs
SELECT batter, SUM(batsman_runs) AS total_runs
FROM deliveries
GROUP BY batter
ORDER BY total_runs DESC
LIMIT 10;

-- Q7: Top 10 bowlers by total wickets (excluding run outs)
SELECT bowler, COUNT(*) AS total_wickets
FROM deliveries
WHERE is_wicket = 1
AND dismissal_kind NOT IN ('run out', 'retired hurt', 'obstructing the field')
GROUP BY bowler
ORDER BY total_wickets DESC
LIMIT 10;

-- Q8: Average first innings score per venue (min 10 matches)
SELECT batting_team, venue, ROUND(AVG(total_score), 2) AS avg_first_innings_score
FROM (
    SELECT d.match_id, d.batting_team, m.venue, SUM(d.total_runs) AS total_score
    FROM deliveries d
    JOIN matches m ON d.match_id = m.id
    WHERE d.inning = 1
    GROUP BY d.match_id, d.batting_team, m.venue
) AS first_innings
GROUP BY batting_team, venue
HAVING COUNT(*) >= 3
ORDER BY avg_first_innings_score DESC
LIMIT 10;