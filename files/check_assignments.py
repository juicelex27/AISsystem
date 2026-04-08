import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Check which sections have assignments
sections_with_assignments = conn.execute("""
    SELECT s.id, s.section_name, s.grade_level, COUNT(a.id) as assignment_count
    FROM sections s
    JOIN assignments a ON s.id = a.section_id
    WHERE s.grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
    GROUP BY s.id, s.section_name, s.grade_level
    ORDER BY assignment_count DESC
""").fetchall()

print("=" * 70)
print("JHS SECTIONS WITH ASSIGNMENTS")
print("=" * 70)

if sections_with_assignments:
    for s in sections_with_assignments:
        print(f"{s['section_name']:15} ({s['grade_level']:8}) - {s['assignment_count']:2} assignments")
else:
    print("No JHS sections have assignments!")

# Check total assignments
total_assignments = conn.execute("SELECT COUNT(*) as cnt FROM assignments").fetchone()
print(f"\nTotal assignments in database: {total_assignments['cnt']}")

conn.close()
