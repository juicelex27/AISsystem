import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Check Section Laurel
print("=" * 70)
print("SECTION LAUREL SCHEDULE")
print("=" * 70)

laurel_section = conn.execute(
    "SELECT id, section_name, grade_level FROM sections WHERE section_name='Laurel'"
).fetchone()

if laurel_section:
    print(f"Section: {laurel_section['section_name']} ({laurel_section['grade_level']})\n")
    
    schedules = conn.execute("""
        SELECT 
            sc.id, sc.subject_id, sc.section_id,
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
    """, (laurel_section['id'],)).fetchall()
    
    if schedules:
        # Group by day
        current_day = None
        for sc in schedules:
            if current_day != sc['day']:
                current_day = sc['day']
                print(f"\n{current_day}:")
            
            # Determine if this is homeroom
            is_homeroom = 'homeroom' in sc['subject_name'].lower()
            period = "1st Period (HOMEROOM)" if sc['time_start'] == '07:30' and 'homeroom' in sc['subject_name'].lower() else f"{sc['time_start']}-{sc['time_end']}"
            
            print(f"  {period:25} {sc['subject_code']:12} {sc['teacher_name']:30} → {sc['subject_name'][:30]}")
    else:
        print("No schedules found for this section")
else:
    print("Section Laurel not found")

# Check Christine Betito's schedule
print("\n" + "=" * 70)
print("CHRISTINE BETITO'S SCHEDULE - Period Conflicts")
print("=" * 70)

christine = conn.execute(
    "SELECT id, first_name, last_name FROM teachers WHERE first_name='Christine' AND last_name='Betito'"
).fetchone()

if christine:
    print(f"Teacher: {christine['first_name']} {christine['last_name']}\n")
    
    # Find periods where she teaches multiple sections with SAME subject
    conflicts = conn.execute("""
        SELECT 
            sc1.day, sc1.time_start, sc1.time_end,
            sub.subject_code, sub.subject_name,
            sec1.section_name as section1,
            sec2.section_name as section2,
            COUNT(*) as count
        FROM schedules sc1
        JOIN schedules sc2 ON sc1.day = sc2.day 
            AND sc1.time_start = sc2.time_start 
            AND sc1.subject_id = sc2.subject_id
            AND sc1.teacher_id = sc2.teacher_id
            AND sc1.section_id != sc2.section_id
            AND sc1.id < sc2.id
        JOIN subjects sub ON sc1.subject_id = sub.id
        JOIN sections sec1 ON sc1.section_id = sec1.id
        JOIN sections sec2 ON sc2.section_id = sec2.id
        WHERE sc1.teacher_id = ?
        GROUP BY sc1.day, sc1.time_start, sc1.subject_id
        ORDER BY sc1.time_start
    """, (christine['id'],)).fetchall()
    
    if conflicts:
        print(f"Found {len(conflicts)} time conflicts:\n")
        for conf in conflicts:
            period_map = {
                '07:30': '1st Period',
                '08:30': '2nd Period',
                '10:00': '3rd Period',
                '11:00': '4th Period',
                '13:00': '5th Period',
                '14:00': '6th Period',
                '15:00': '7th Period',
                '16:00': 'Last Period'
            }
            period = period_map.get(conf['time_start'], f"{conf['time_start']}-{conf['time_end']}")
            print(f"{conf['day']} {period} ({conf['time_start']}-{conf['time_end']})")
            print(f"  Subject: {conf['subject_code']} - {conf['subject_name']}")
            print(f"  Section 1: {conf['section1']}")
            print(f"  Section 2: {conf['section2']}")
            print()
    else:
        print("No conflicts found")
        
        # Show all her schedules
        all_schedules = conn.execute("""
            SELECT 
                sc.day, sc.time_start,
                sub.subject_code, sub.subject_name,
                sec.section_name
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id = sub.id
            JOIN sections sec ON sc.section_id = sec.id
            WHERE sc.teacher_id = ?
            ORDER BY 
                CASE sc.day
                    WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 ELSE 6
                END,
                sc.time_start
        """, (christine['id'],)).fetchall()
        
        print("All her schedules:\n")
        for sch in all_schedules:
            print(f"{sch['day']:10} {sch['time_start']:6} {sch['subject_code']:12} {sch['section_name']}")
else:
    print("Christine Betito not found")

conn.close()
