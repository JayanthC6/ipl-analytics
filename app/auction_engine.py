from groq import Groq
from sqlalchemy import create_engine, text
import pandas as pd
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
engine = create_engine('mysql+mysqlconnector://root:root123@localhost/ipl_analytics')

SCHEMA = """
You are an IPL Auction Intelligence assistant. You have access to a MySQL database called ipl_analytics with these tables:

TABLE: matches
- id (int), season (text), city (text), date (date), match_type (text)
- player_of_match (text), venue (text), team1 (text), team2 (text)
- toss_winner (text), toss_decision (text), winner (text)
- result (text), result_margin (float), target_runs (float)
- super_over (text), umpire1 (text), umpire2 (text)

TABLE: deliveries
- match_id (int), inning (int), batting_team (text), bowling_team (text)
- over (int), ball (int), batter (text), bowler (text), non_striker (text)
- batsman_runs (int), extra_runs (int), total_runs (int)
- extras_type (text), is_wicket (int), player_dismissed (text)
- dismissal_kind (text), fielder (text)

TABLE: player_auction
- player_name (text), total_runs (float), matches (int)
- avg_runs_per_match (float), role (text), auction_price_cr (float)
- total_wickets (int), avg_wickets_per_match (float)

IMPORTANT RULES:
1. Always return ONLY a valid MySQL SELECT query, nothing else
2. No markdown, no explanation, no backticks
3. Use table aliases for clarity
4. LIMIT results to 10 unless specified otherwise
5. For price queries, use auction_price_cr from player_auction table
6. For performance queries, use deliveries table
7. Always use proper JOIN when combining tables
8. CRITICAL: When counting wickets, ALWAYS filter with is_wicket = 1
9. CRITICAL: Powerplay = overs 1-6, Middle overs = overs 7-15, Death overs = overs 16-20
10. CRITICAL: For wickets by phase use:
    SUM(CASE WHEN d.over BETWEEN 1 AND 6 AND d.is_wicket = 1 THEN 1 ELSE 0 END) AS powerplay_wickets
    SUM(CASE WHEN d.over BETWEEN 7 AND 15 AND d.is_wicket = 1 THEN 1 ELSE 0 END) AS middle_overs_wickets
    SUM(CASE WHEN d.over > 15 AND d.is_wicket = 1 THEN 1 ELSE 0 END) AS death_overs_wickets
11. Never count runs as wickets or wickets as runs
12. Always double check filters before returning query
"""

def generate_sql(question: str) -> str:
    prompt = f"""
{SCHEMA}

User question: {question}

Return only the MySQL SELECT query to answer this question. No explanation, no markdown, just the raw SQL query.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    sql = response.choices[0].message.content.strip()
    # Clean any accidental markdown
    sql = re.sub(r'```sql|```', '', sql).strip()
    return sql

def execute_sql(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        result = pd.read_sql(text(sql), conn)
    return result

def generate_insight(question: str, sql: str, data: str) -> str:
    prompt = f"""
You are an IPL Auction Intelligence assistant helping franchise managers make smart decisions.

User asked: {question}

SQL query used: {sql}

Data returned: {data}

Give a concise, actionable insight in 2-3 sentences. Be specific with numbers. 
Frame it as advice to an IPL franchise manager.
Do not mention SQL or technical details.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def ask(question: str) -> dict:
    try:
        sql = generate_sql(question)
        df = execute_sql(sql)
        data_str = df.to_string(index=False) if not df.empty else "No results found"
        insight = generate_insight(question, sql, data_str)
        return {
            'success': True,
            'sql': sql,
            'data': df.to_dict(orient='records'),
            'columns': df.columns.tolist(),
            'insight': insight
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'sql': '',
            'data': [],
            'columns': [],
            'insight': ''
        }