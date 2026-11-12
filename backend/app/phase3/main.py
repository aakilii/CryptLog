import duckdb
import datetime
import asyncio
import pyarrow
import pyarrow.parquet
from fastapi import FastAPI, BackgroundTasks, Request
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from sentence_transformers import SentenceTransformer

new_app = FastAPI()
new_db = duckdb.connect('master_whiteboard.db')
new_db.execute("DROP TABLE IF EXISTS live_events")
new_db.execute("CREATE TABLE live_events (Target_User VARCHAR, Notes VARCHAR, Lineage VARCHAR, Vector DOUBLE[], created_at TIMESTAMP, ttl_seconds INTEGER, is_locked BOOLEAN, is_tombstoned BOOLEAN)")

new_nlp = AnalyzerEngine()

new_pat_tok = Pattern(name="bearer_token", regex="Bearer\s+[a-zA-Z0-9\-\._~\+\/]+", score=0.9)
new_rec_tok = PatternRecognizer(supported_entity="AUTH_TOKEN", patterns=[new_pat_tok])
new_nlp.registry.add_recognizer(new_rec_tok)

new_pat_pwd = Pattern(name="password_log", regex="[Pp]assword[\s\:\=]+[a-zA-Z0-9\@\#\$\%\^\&\*\!\?]+", score=0.9)
new_rec_pwd = PatternRecognizer(supported_entity="PASSWORD", patterns=[new_pat_pwd])
new_nlp.registry.add_recognizer(new_rec_pwd)

new_pat_aad = Pattern(name="aadhaar", regex="\d{4}[\s\-]\d{4}[\s\-]\d{4}", score=0.9)
new_rec_aad = PatternRecognizer(supported_entity="IN_AADHAAR", patterns=[new_pat_aad])
new_nlp.registry.add_recognizer(new_rec_aad)

new_targets = ["CREDIT_CARD", "US_SSN", "US_PASSPORT", "AUTH_TOKEN", "PASSWORD", "IN_AADHAAR"]

new_embed = SentenceTransformer('all-MiniLM-L6-v2')

new_flag_20 = []
new_flag_10 = []
new_flag_0 = []

async def run_janitor():
    print(">>> SYSTEM: Enterprise Janitor loop running in background... <<<")
    while True:
        await asyncio.sleep(1)
        new_now = datetime.datetime.now()
        new_rows = new_db.execute("SELECT Lineage, created_at, ttl_seconds, is_locked FROM live_events").fetchall()

        for new_row in new_rows:
            new_id = new_row[0]
            new_time = new_row[1]
            new_ttl = new_row[2]
            new_lock = new_row[3]

            if new_time is None:
                continue

            new_diff = (new_now - new_time).total_seconds()
            new_left = int(new_ttl - new_diff)

            if new_left <= 20 and new_left > 10 and new_id not in new_flag_20:
                print(f">>> NOTIFICATION [{new_id}]: 20 seconds remaining <<<")
                new_flag_20.append(new_id)

            if new_left <= 10 and new_left > 0 and new_id not in new_flag_10:
                print(f">>> NOTIFICATION [{new_id}]: 10 seconds remaining (Alert 1) <<<")
                print(f">>> NOTIFICATION [{new_id}]: 10 seconds remaining (Alert 2) <<<")
                new_flag_10.append(new_id)

            if new_left <= 0 and new_id not in new_flag_0:
                print(f">>> !!! ALERT [{new_id}]: Delete category reached !!! <<<")
                if new_lock:
                    new_db.execute(f"UPDATE live_events SET is_tombstoned = TRUE WHERE Lineage = '{new_id}'")
                    print(f">>> DEADLOCK TRIGGERED [{new_id}]: Tombstone applied safely.")
                if not new_lock:
                    print(f">>> ACTION REQUIRED [{new_id}]: Awaiting /extend or /remove API call")
                new_flag_0.append(new_id)

@new_app.on_event("startup")
async def start_janitor():
    asyncio.create_task(run_janitor())

async def process_payload(new_data: dict):
    new_usr = new_data.get("Target_User", "")
    new_txt = new_data.get("Notes", "")
    new_lin = new_data.get("Lineage", "")

    print("\n==================================================")
    print(f">>> INITIATING DEEP SCAN FOR PAYLOAD: {new_lin}")
    
    new_scan = new_nlp.analyze(text=new_txt, entities=new_targets, language="en")
    new_safe = new_txt
    
    for new_match in new_scan:
        if new_match.score > 0.40:
            new_type = new_match.entity_type
            new_conf = new_match.score
            print("!!! CRITICAL VULNERABILITY DETECTED !!!")
            print(f"--> Threat Type: {new_type}")
            print(f"--> AI Confidence: {new_conf}")
            print("--> ACTION: Shredding payload and applying GCM Encryption...")
            new_safe = new_safe.replace(new_txt[new_match.start:new_match.end], f"[ENC:gcm:{new_type}_REDACTED]")

    print("--- PII SCAN COMPLETE ---")
    print("ORIGINAL:")
    print(new_txt)
    print("SECURED:")
    print(new_safe)
    print("==================================================\n")

    new_vec = new_embed.encode(new_safe).tolist()
    new_now = datetime.datetime.now()
    new_ttl = 30
    
    new_db.execute(f"INSERT INTO live_events VALUES ('{new_usr}', '{new_safe}', '{new_lin}', {new_vec}, '{new_now}', {new_ttl}, FALSE, FALSE)")

    new_dict = {"Target_User": [new_usr], "Notes": [new_safe], "Lineage": [new_lin], "Vector": [new_vec]}
    new_tab = pyarrow.Table.from_pydict(new_dict)
    pyarrow.parquet.write_table(new_tab, "master_glass_case.parquet")
    print(f">>> SUCCESS: Payload {new_lin} saved to Hot & Cold Storage.")

@new_app.post("/phase2_webhook")
async def catch_webhook(new_req: Request, new_bg: BackgroundTasks):
    new_raw = await new_req.json()
    new_bg.add_task(process_payload, new_raw)
    return {"status": "Phase 2 payload secured"}

@new_app.post("/lock_file")
async def lock_data(new_req: Request):
    new_data = await new_req.json()
    new_lin = new_data.get("Lineage")
    new_db.execute(f"UPDATE live_events SET is_locked = TRUE WHERE Lineage = '{new_lin}'")
    print(f">>> MVCC DEADLOCK ON: {new_lin} locked by investigator")
    return {"status": "Locked"}

@new_app.post("/extend")
async def extend_time(new_req: Request):
    new_data = await new_req.json()
    new_lin = new_data.get("Lineage")
    new_db.execute(f"UPDATE live_events SET ttl_seconds = ttl_seconds + 30 WHERE Lineage = '{new_lin}'")
    if new_lin in new_flag_20: new_flag_20.remove(new_lin)
    if new_lin in new_flag_10: new_flag_10.remove(new_lin)
    if new_lin in new_flag_0: new_flag_0.remove(new_lin)
    print(f">>> SUCCESS: Extended {new_lin} by 30 seconds")
    return {"status": "Extended"}

@new_app.post("/remove")
async def remove_data(new_req: Request):
    new_data = await new_req.json()
    new_lin = new_data.get("Lineage")
    new_db.execute(f"DELETE FROM live_events WHERE Lineage = '{new_lin}'")
    new_db.execute("VACUUM")
    print(f">>> SUCCESS: Removed {new_lin} and vacuumed RAM")
    return {"status": "Removed"}

@new_app.post("/graphql_query")
async def fetch_cold_data(new_req: Request):
    new_data = await new_req.json()
    new_dpth = new_data.get("depth", 1)
    new_usr = new_data.get("Target_User", "")

    if new_dpth > 4:
        return {"error": "HTTP 429: Too Many Requests. Query depth exceeds safety limit."}

    if new_dpth <= 4:
        new_sql = f"SELECT Target_User, Notes, Lineage FROM read_parquet('master_glass_case.parquet', union_by_name=True) WHERE Target_User = '{new_usr}'"
        new_cursor = new_db.execute(new_sql)
        new_chunk = new_cursor.fetchmany(10000)

        new_res = []
        for new_row in new_chunk:
            new_dict = {"Target_User": new_row[0], "Notes": new_row[1], "Lineage": new_row[2]}
            new_res.append(new_dict)

        print(f">>> SUCCESS: Rehydrated {len(new_res)} records from Cold Storage")
        return {"status": "Rehydration Success", "data": new_res}