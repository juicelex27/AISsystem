import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Find Christine Betito's duplicate entries (those with Laurel)
christine = conn.execute(
    "SELECT id FROM teachers WHERE first_name='Christine' AND last_name='Betito'"
).fetchone()

laurel = conn.execute(
    "SELECT id FROM sections WHERE section_name='Laurel'"
).fetchone()

if christine and laurel:
    # Find schedules for Christine teaching in Laurel at 5th period (13:00-14:00)
    conflicting_schedules = conn.execute("""
        SELECT sc.id, sc.subject_id, sc.day, 
               sub.subject_code, sub.subject_name,
               sec.section_name
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id = sub.id
        JOIN sections sec ON sc.section_id = sec.id
        WHERE sc.teacher_id = ? AND sc.section_id = ? 
        AND sc.time_start = '13:00'
    """, (christine['id'], laurel['id'])).fetchall()
    
    print(f"Found {len(conflicting_schedules)} conflicting schedules for deletion:\n")
    
    for sch in conflicting_schedules:
        print(f"  {sch['day']:10} {sch['subject_code']:12} in Section {sch['section_name']}")
        conn.execute("DELETE FROM schedules WHERE id = ?", (sch['id'],))
    
    conn.commit()
    print(f"\nDeleted {len(conflicting_schedules)} conflicting schedules from database.")
else:
    print("Christine Betito or Section Laurel not found")

conn.close()
