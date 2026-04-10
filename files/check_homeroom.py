import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Check Section Laurel's assignments (homeroom subject)
print("=" * 70)
print("SECTION LAUREL - ASSIGNMENTS & SUBJECTS")
print("=" * 70)

laurel_section = conn.execute(
    "SELECT id FROM sections WHERE section_name='Laurel'"
).fetchone()

if laurel_section:
    # Get all subjects that could be assigned to this section
    laurel_id = laurel_section['id']
    
    # Check assignments
    assignments = conn.execute("""
        SELECT a.id, a.subject_id, a.teacher_id, 
               s.subject_name, s.subject_code,
               t.first_name || ' ' || t.last_name as teacher_name
        FROM assignments a
        JOIN subjects s ON a.subject_id = s.id
        JOIN teachers t ON a.teacher_id = t.id
        WHERE a.section_id = ?
        ORDER BY s.subject_name
    """, (laurel_id,)).fetchall()
    
    print(f"\nAssignments for Section Laurel: {len(assignments)} total\n")
    for a in assignments:
        print(f"  {a['subject_code']:12} {a['subject_name'][:40]:40} → {a['teacher_name']}")
    
    # Check if any are homeroom subjects
    homeroom_subjects = conn.execute("""
        SELECT DISTINCT s.id, s.subject_code, s.subject_name
        FROM subjects s
        WHERE LOWER(s.subject_name) LIKE '%homeroom%' 
           OR LOWER(s.subject_code) LIKE '%homeroom%'
        AND s.grade_level = 'Grade 10'
    """).fetchall()
    
    print(f"\nAvailable homeroom subjects for Grade 10: {len(homeroom_subjects)}")
    for hs in homeroom_subjects:
        print(f"  {hs['subject_code']:12} {hs['subject_name']}")
    
    # Check what JHS subjects exist
    jhs_subjects = conn.execute("""
        SELECT DISTINCT subject_code, subject_name, grade_level
        FROM subjects
        WHERE grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
        ORDER BY grade_level, subject_code
    """).fetchall()
    
    print(f"\nTotal JHS subjects available: {len(jhs_subjects)}")

# Check if Christine's conflict check would have caught it
print("\n" + "=" * 70)
print("CHRISTINE BETITO - WHY WASN'T CONFLICT DETECTED?")
print("=" * 70)

christine = conn.execute(
    "SELECT id FROM teachers WHERE first_name='Christine' AND last_name='Betito'"
).fetchone()

if christine:
    # Check what happens when we look for conflicts for 5th period on Monday
    # Simulating: adding her to teach AP 010 to Laurel on Monday 13:00-14:00
    
    print("\nSimulating conflict check for Christine Betito:")
    print("  Adding: AP 010 to Section Laurel on Monday 13:00-14:00\n")
    
    # What's already scheduled for her at that time?
    existing = conn.execute("""
        SELECT sc.id, sc.teacher_id, sc.subject_id, sec.section_name, sc.day, sc.time_start,
               sub.subject_code
        FROM schedules sc
        JOIN sections sec ON sc.section_id = sec.id
        JOIN subjects sub ON sc.subject_id = sub.id
        WHERE sc.teacher_id = ? AND sc.day='Monday' AND sc.time_start='13:00'
    """, (christine['id'],)).fetchall()
    
    print(f"  Existing schedules for Christine on Monday 13:00:")
    for ex in existing:
        print(f"    - {ex['subject_code']} in Section {ex['section_name']}")
    
    if len(existing) > 0:
        print(f"\n  ✗ CONFLICT DETECTED: She already teaches at this time!")
        print(f"    Cannot also teach Laurel at same time.")

conn.close()
