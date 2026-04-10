import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Find all duplicate schedules (same subject, day, time, teacher, section)
# Keep the first one, delete the rest
duplicates_query = """
    SELECT sc.id, sc.subject_id, sc.day, sc.time_start, sc.section_id, sc.teacher_id,
           ROW_NUMBER() OVER (PARTITION BY sc.teacher_id, sc.subject_id, sc.day, sc.time_start, sc.section_id ORDER BY sc.id) as row_num
    FROM schedules sc
"""

cursor = conn.execute(duplicates_query)
schedules_with_row_num = cursor.fetchall()

# Find IDs of duplicate records (row_num > 1 means it's a duplicate)
duplicate_ids = [s['id'] for s in schedules_with_row_num if s['row_num'] > 1]

if duplicate_ids:
    print(f"Found {len(duplicate_ids)} duplicate schedule IDs to delete")
    
    for dup_id in duplicate_ids:
        conn.execute("DELETE FROM schedules WHERE id = ?", (dup_id,))
        print(f"  Deleted schedule ID {dup_id}")
    
    conn.commit()
    print(f"\nSuccessfully deleted {len(duplicate_ids)} duplicate entries.")
else:
    print("No duplicates found to delete.")

# Verify cleanup
remaining = conn.execute("""
    SELECT COUNT(*) as dup_count
    FROM (
        SELECT subject_id, day, time_start, section_id, teacher_id, COUNT(*) as cnt
        FROM schedules
        GROUP BY subject_id, day, time_start, section_id, teacher_id
        HAVING COUNT(*) > 1
    )
""").fetchone()

print(f"\nRemaining duplicates: {remaining['dup_count']}")

conn.close()
