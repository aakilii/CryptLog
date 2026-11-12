import duckdb

new_db = duckdb.connect('master_whiteboard.db')

new_data = new_db.execute("SELECT Target_User, Lineage, is_locked, is_tombstoned FROM live_events").fetchall()

print("--------------------------------------------------")
print("LIVE DATABASE STATE:")

new_count = 0
for new_row in new_data:
    print(new_row)
    new_count = new_count + 1

if new_count == 0:
    print("DATABASE IS COMPLETELY EMPTY (Vacuumed)")

print("--------------------------------------------------")