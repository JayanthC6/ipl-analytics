import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import pickle

# Load cleaned data
matches = pd.read_csv('../data/cleaned/matches_cleaned.csv')

# Feature engineering
matches['toss_winner_is_team1'] = (matches['toss_winner'] == matches['team1']).astype(int)
matches['batting_first'] = (matches['toss_decision'] == 'bat').astype(int)

# Target: did team1 win?
matches['team1_won'] = (matches['winner'] == matches['team1']).astype(int)

# Encode categorical features
le_venue = LabelEncoder()
le_team1 = LabelEncoder()
le_team2 = LabelEncoder()

matches['venue_enc'] = le_venue.fit_transform(matches['venue'])
matches['team1_enc'] = le_team1.fit_transform(matches['team1'])
matches['team2_enc'] = le_team2.fit_transform(matches['team2'])

# Features and target
X = matches[['venue_enc', 'team1_enc', 'team2_enc', 'toss_winner_is_team1', 'batting_first']]
y = matches['team1_won']

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"Model Accuracy: {round(acc * 100, 2)}%")

# Save model and encoders
with open('model.pkl', 'wb') as f:
    pickle.dump(model, f)
with open('encoders.pkl', 'wb') as f:
    pickle.dump({'venue': le_venue, 'team1': le_team1, 'team2': le_team2}, f)

print("Model and encoders saved.")