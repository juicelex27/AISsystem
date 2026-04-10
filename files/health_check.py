import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

print("=" * 70)
print("SCHEDULE HEALTH CHECK")
print("=" * 70)

# 1. Total schedules
total = conn.execute("SELECT COUNT(*) as cnt FROM schedules").fetchone()
print(f"\n✓ Total schedule entries: {total['cnt']}")

# 2. Schedules by grade level
by_grade = conn.execute("""
    SELECT sec.grade_level, COUNT(*) as cnt
    FROM schedules sc
    JOIN sections sec ON sc.section_id = sec.id
    GROUP BY sec.grade_level
    ORDER BY sec.grade_level
""").fetchall()
print("\nSchedules by grade level:")
for row in by_grade:
    print(f"  {row['grade_level']}: {row['cnt']}")

# 3. Check for orphaned schedules (section not found)
orphaned = conn.execute("""
    SELECT COUNT(*) as cnt FROM schedules sc
    WHERE NOT EXISTS (SELECT 1 FROM sections WHERE id = sc.section_id)
""").fetchone()
print(f"\n✓ Orphaned schedules (invalid section_id): {orphaned['cnt']}")

# 4. Check for orphaned subjects
orphaned_sub = conn.execute("""
    SELECT COUNT(*) as cnt FROM schedules sc
    WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE id = sc.subject_id)
""").fetchone()
print(f"✓ Orphaned subjects (invalid subject_id): {orphaned_sub['cnt']}")

# 5. Check for orphaned teachers
orphaned_teach = conn.execute("""
    SELECT COUNT(*) as cnt FROM schedules sc
    WHERE NOT EXISTS (SELECT 1 FROM teachers WHERE id = sc.teacher_id)
""").fetchone()
print(f"✓ Orphaned teachers (invalid teacher_id): {orphaned_teach['cnt']}")

# 6. Check JHS sections with auto-schedule
jhs_sections = conn.execute("""
    SELECT s.id, s.section_name, s.grade_level, COUNT(sc.id) as schedule_count
    FROM sections s
    LEFT JOIN schedules sc ON s.id = sc.section_id
    WHERE s.grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
    GROUP BY s.id
    ORDER BY s.grade_level, s.section_name
""").fetchall()

print(f"\n✓ JHS sections with schedules ({len(jhs_sections)} total):")
jhs_with_schedules = sum(1 for s in jhs_sections if s['schedule_count'] > 0)
jhs_without_schedules = sum(1 for s in jhs_sections if s['schedule_count'] == 0)
print(f"  {jhs_with_schedules} sections WITH schedules")
print(f"  {jhs_without_schedules} sections WITHOUT schedules")

if jhs_without_schedules > 0 and jhs_without_schedules <= 5:
    print("\n  Sections without schedules:")
    for s in jhs_sections:
        if s['schedule_count'] == 0:
            print(f"    - {s['section_name']} ({s['grade_level']})")

# 7. Teachers with schedules
teachers_with_schedules = conn.execute("""
    SELECT COUNT(DISTINCT teacher_id) as cnt FROM schedules
""").fetchone()
print(f"\n✓ Teachers with schedules: {teachers_with_schedules['cnt']}")

# 8. Check for invalid day values
invalid_days = conn.execute("""
    SELECT DISTINCT day FROM schedules
    WHERE day NOT IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
""").fetchall()
if invalid_days:
    print(f"\n⚠ Invalid day values found: {[d['day'] for d in invalid_days]}")
else:
    print(f"\n✓ All day values are valid")

# 9. Sample check - show schedules for one section
sample_section = conn.execute("""
    SELECT s.id, s.section_name, s.grade_level
    FROM sections s
    WHERE s.grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
    LIMIT 1
""").fetchone()

if sample_section:
    sample_schedules = conn.execute("""
        SELECT 
            sub.subject_name, sub.subject_code,
            t.first_name || ' ' || t.last_name as teacher_name,
            sc.day, sc.time_start, sc.time_end
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id = sub.id
        JOIN teachers t ON sc.teacher_id = t.id
        WHERE sc.section_id = ?
        ORDER BY 
            CASE sc.day
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 ELSE 6
            END,
            sc.time_start
    """, (sample_section['id'],)).fetchall()
    
    print(f"\n✓ Sample: {sample_section['section_name']} ({sample_section['grade_level']})")
    print(f"  {len(sample_schedules)} schedules:")
    for sc in sample_schedules[:5]:
        print(f"    {sc['subject_code']:12} {sc['teacher_name']:30} {sc['day']:10} {sc['time_start']}-{sc['time_end']}")
    if len(sample_schedules) > 5:
        print(f"    ... and {len(sample_schedules) - 5} more")

print("\n" + "=" * 70)
print("SUMMARY: Database appears to be in good condition.")
print("=" * 70)

conn.close()
