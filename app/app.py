from flask import Flask, render_template, request, jsonify
import pickle
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

app = Flask(__name__)

engine = create_engine('mysql+mysqlconnector://root:root123@localhost/ipl_analytics')

with open('../model/model.pkl', 'rb') as f:
    model = pickle.load(f)
with open('../model/encoders.pkl', 'rb') as f:
    encoders = pickle.load(f)

matches = pd.read_csv('../data/cleaned/matches_cleaned.csv')
teams = sorted(matches['team1'].unique().tolist())
venues = sorted(matches['venue'].unique().tolist())

def get_home_stats():
    with engine.connect() as conn:
        total_matches = conn.execute(text("SELECT COUNT(*) FROM matches")).scalar()
        total_teams = conn.execute(text("SELECT COUNT(DISTINCT team1) FROM matches")).scalar()
        most_wins = conn.execute(text("SELECT winner, COUNT(*) as wins FROM matches GROUP BY winner ORDER BY wins DESC LIMIT 1")).fetchone()
        seasons = conn.execute(text("SELECT season, COUNT(*) as total FROM matches GROUP BY season ORDER BY season")).fetchall()
        top_teams = conn.execute(text("SELECT winner, COUNT(*) as wins FROM matches GROUP BY winner ORDER BY wins DESC LIMIT 10")).fetchall()
        top_venues = conn.execute(text("SELECT venue, COUNT(*) as matches_hosted FROM matches GROUP BY venue ORDER BY matches_hosted DESC LIMIT 8")).fetchall()
    return {
        'total_matches': total_matches,
        'total_teams': total_teams,
        'most_wins_team': most_wins[0],
        'most_wins_count': most_wins[1],
        'seasons': [str(s[0]) for s in seasons],
        'season_counts': [s[1] for s in seasons],
        'top_teams': top_teams,
        'top_venues': top_venues
    }

@app.route('/')
def index():
    data = get_home_stats()
    return render_template('index.html',
        active='home',
        title='Home',
        stats={
            'total_matches': data['total_matches'],
            'total_teams': data['total_teams'],
            'most_wins_team': data['most_wins_team'],
            'most_wins_count': data['most_wins_count']
        },
        seasons=data['seasons'],
        season_counts=data['season_counts'],
        team_names=[t[0] for t in data['top_teams']],
        team_wins=[t[1] for t in data['top_teams']],
        venues=[{'venue': v[0], 'matches_hosted': v[1]} for v in data['top_venues']]
    )

@app.route('/teams')
def teams_page():
    with engine.connect() as conn:
        all_teams = conn.execute(text("SELECT DISTINCT team1 FROM matches ORDER BY team1")).fetchall()
    return render_template('teams.html', active='teams', title='Team Stats',
        teams=[t[0] for t in all_teams])

@app.route('/api/team-stats')
def team_stats():
    team = request.args.get('team')
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM matches WHERE team1=:t OR team2=:t"), {'t': team}).scalar()
        wins = conn.execute(text("SELECT COUNT(*) FROM matches WHERE winner=:t"), {'t': team}).scalar()
        toss_wins = conn.execute(text("SELECT COUNT(*) FROM matches WHERE toss_winner=:t"), {'t': team}).scalar()
        best_venue = conn.execute(text("""
            SELECT venue, COUNT(*) as wins FROM matches
            WHERE winner=:t GROUP BY venue ORDER BY wins DESC LIMIT 1"""), {'t': team}).fetchone()
        season_perf = conn.execute(text("""
            SELECT season,
                SUM(CASE WHEN team1=:t OR team2=:t THEN 1 ELSE 0 END) as played,
                SUM(CASE WHEN winner=:t THEN 1 ELSE 0 END) as won
            FROM matches GROUP BY season ORDER BY season"""), {'t': team}).fetchall()
    return jsonify({
        'total': total, 'wins': wins,
        'win_pct': round(wins/total*100, 1) if total else 0,
        'toss_wins': toss_wins,
        'best_venue': best_venue[0] if best_venue else 'N/A',
        'seasons': [str(s[0]) for s in season_perf],
        'played': [s[1] for s in season_perf],
        'won': [s[2] for s in season_perf]
    })

@app.route('/players')
def players_page():
    with engine.connect() as conn:
        batters = conn.execute(text("""
            SELECT batter, SUM(batsman_runs) as runs,
            COUNT(DISTINCT match_id) as matches
            FROM deliveries GROUP BY batter
            ORDER BY runs DESC LIMIT 15""")).fetchall()
        bowlers = conn.execute(text("""
            SELECT bowler, COUNT(*) as wickets,
            COUNT(DISTINCT match_id) as matches
            FROM deliveries WHERE is_wicket=1
            AND dismissal_kind NOT IN ('run out','retired hurt','obstructing the field')
            GROUP BY bowler ORDER BY wickets DESC LIMIT 15""")).fetchall()
    return render_template('players.html', active='players', title='Players',
        batters=[{'name': b[0], 'runs': int(b[1]), 'matches': b[2]} for b in batters],
        bowlers=[{'name': b[0], 'wickets': b[1], 'matches': b[2]} for b in bowlers])

@app.route('/h2h')
def h2h_page():
    with engine.connect() as conn:
        all_teams = conn.execute(text("SELECT DISTINCT team1 FROM matches ORDER BY team1")).fetchall()
    return render_template('h2h.html', active='h2h', title='Head-to-Head',
        teams=[t[0] for t in all_teams])

@app.route('/api/h2h')
def h2h_data():
    t1 = request.args.get('team1')
    t2 = request.args.get('team2')
    with engine.connect() as conn:
        matches_data = conn.execute(text("""
            SELECT winner, venue, date, result, result_margin
            FROM matches
            WHERE (team1=:t1 AND team2=:t2) OR (team1=:t2 AND team2=:t1)
            ORDER BY date DESC"""), {'t1': t1, 't2': t2}).fetchall()
    total = len(matches_data)
    t1_wins = sum(1 for m in matches_data if m[0] == t1)
    t2_wins = sum(1 for m in matches_data if m[0] == t2)
    return jsonify({
        'total': total, 't1_wins': t1_wins, 't2_wins': t2_wins,
        'matches': [{'winner': m[0], 'venue': m[1], 'date': str(m[3]),
                     'result': m[3], 'margin': m[4]} for m in matches_data[:10]]
    })

@app.route('/predictor')
def predictor_page():
    return render_template('predictor.html', active='predictor', title='Predictor',
        teams=teams, venues=venues)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    team1 = data['team1']
    team2 = data['team2']
    venue = data['venue']
    toss_winner = data['toss_winner']
    toss_decision = data['toss_decision']
    try:
        venue_enc = encoders['venue'].transform([venue])[0]
        team1_enc = encoders['team1'].transform([team1])[0]
        team2_enc = encoders['team2'].transform([team2])[0]
    except ValueError as e:
        return jsonify({'error': str(e)})
    toss_winner_is_team1 = 1 if toss_winner == team1 else 0
    batting_first = 1 if toss_decision == 'bat' else 0
    features = np.array([[venue_enc, team1_enc, team2_enc, toss_winner_is_team1, batting_first]])
    prediction = model.predict(features)[0]
    probability = model.predict_proba(features)[0]
    winner = team1 if prediction == 1 else team2
    confidence = round(max(probability) * 100, 2)
    return jsonify({'winner': winner, 'confidence': confidence})

if __name__ == '__main__':
    app.run(debug=True)