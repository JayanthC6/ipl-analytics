from flask import Flask, render_template, request, jsonify
import pickle
import numpy as np
import pandas as pd

app = Flask(__name__)

# Load model and encoders
with open('../model/model.pkl', 'rb') as f:
    model = pickle.load(f)
with open('../model/encoders.pkl', 'rb') as f:
    encoders = pickle.load(f)

# Get known teams and venues
matches = pd.read_csv('../data/cleaned/matches_cleaned.csv')
teams = sorted(matches['team1'].unique().tolist())
venues = sorted(matches['venue'].unique().tolist())

@app.route('/')
def index():
    return render_template('index.html', teams=teams, venues=venues)

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