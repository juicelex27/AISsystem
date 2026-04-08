import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Find teachers with duplicate schedules (same subject, day, time)
duplicates = conn.execute("""
    SELECT 
        sc.teacher_id,
        t.first_name || ' ' || t.last_name AS teacher_name,
        sub.subject_name,
        sub.subject_code,
        sc.day,
        sc.time_start,
        sc.time_end,
        sec.section_name,
        COUNT(*) as count
    FROM schedules sc
    JOIN teachers t ON sc.teacher_id = t.id
    JOIN subjects sub ON sc.subject_id = sub.id
    JOIN sections sec ON sc.section_id = sec.id
    GROUP BY sc.teacher_id, sc.subject_id, sc.day, sc.time_start, sc.time_end, sc.section_id
    HAVING COUNT(*) > 1
    ORDER BY sc.teacher_id, sc.day, sc.time_start
""").fetchall()

if duplicates:
    print(f"Found {len(duplicates)} duplicate schedule entries:\n")
    for dup in duplicates:
        print(f"Teacher: {dup['teacher_name']} (ID: {dup['teacher_id']})")
        print(f"  Subject: {dup['subject_name']} ({dup['subject_code']})")
        print(f"  Section: {dup['section_name']}")
        print(f"  Day/Time: {dup['day']} {dup['time_start']}-{dup['time_end']}")
        print(f"  Count: {dup['count']} entries in database\n")
else:
    print("No duplicate schedules found in database.")

conn.close()
