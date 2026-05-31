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
- total_wickets (int), avg_wickets_per_match (float), is_active (int)

IMPORTANT RULES:
1. Always return ONLY a valid MySQL SELECT query, nothing else
2. No markdown, no explanation, no backticks
3. Use table aliases for clarity
4. LIMIT results to 10 unless specified otherwise
5. For price queries, use auction_price_cr from player_auction table
6. ALWAYS filter WHERE pa.is_active = 1 when querying player_auction table
7. For wicket queries ALWAYS use: WHERE d.is_wicket = 1 AND d.dismissal_kind NOT IN ('run out','retired hurt','obstructing the field')
8. For phase-wise bowling:
   - Powerplay = overs 1-6: SUM(CASE WHEN d.over BETWEEN 1 AND 6 AND d.is_wicket = 1 THEN 1 ELSE 0 END)
   - Middle overs = overs 7-15: SUM(CASE WHEN d.over BETWEEN 7 AND 15 AND d.is_wicket = 1 THEN 1 ELSE 0 END)
   - Death overs = overs 16-20: SUM(CASE WHEN d.over > 15 AND d.is_wicket = 1 THEN 1 ELSE 0 END)
9. STRICT MySQL GROUP BY RULE: Every column in SELECT must either be in GROUP BY or wrapped in an aggregate function (SUM, COUNT, MAX, MIN, AVG)
10. Never select pa.total_runs, pa.total_wickets, pa.avg_runs_per_match directly when using GROUP BY — use MAX(pa.total_runs), MAX(pa.total_wickets) instead
11. For retention queries use this exact pattern:
    SELECT pa.player_name, MAX(pa.total_runs) as total_runs, MAX(pa.total_wickets) as total_wickets, MAX(pa.auction_price_cr) as price
    FROM player_auction pa
    JOIN deliveries d ON pa.player_name = d.batter OR pa.player_name = d.bowler
    WHERE (d.batting_team = 'TEAM' OR d.bowling_team = 'TEAM')
    AND pa.is_active = 1
    GROUP BY pa.player_name
    ORDER BY total_runs DESC
    LIMIT 5
12. For value queries (best player under X crore), always include performance stats alongside price
13. Never count deliveries as wickets — only count rows where is_wicket = 1
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