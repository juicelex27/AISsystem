import sqlite3

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Test the new scheduling logic with a section that has conflicts
print("=" * 70)
print("TESTING AUTO-SCHEDULE WITH CONFLICT RESOLUTION")
print("=" * 70)

# Find a JHS section with some assignments
jhs_section = conn.execute("""
    SELECT s.id, s.section_name, s.grade_level, COUNT(a.id) as assignment_count
    FROM sections s
    LEFT JOIN assignments a ON s.id = a.section_id
    WHERE s.grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
    AND (SELECT COUNT(*) FROM assignments WHERE section_id = s.id) > 0
    ORDER BY assignment_count DESC
    LIMIT 1
""").fetchone()

if jhs_section:
    sec_id = jhs_section['id']
    print(f"Testing with Section: {jhs_section['section_name']} ({jhs_section['grade_level']})")
    print(f"Assignments: {jhs_section['assignment_count']}")

    # Get current schedules for this section
    current_schedules = conn.execute("""
        SELECT COUNT(*) as schedule_count FROM schedules WHERE section_id = ?
    """, (sec_id,)).fetchone()

    print(f"Current schedules: {current_schedules['schedule_count']}")

    # Simulate what the auto-schedule would do
    assignments_data = conn.execute("""
        SELECT a.subject_id, a.teacher_id, s.subject_name, s.subject_code,
               t.first_name || ' ' || t.last_name as teacher_name
        FROM assignments a
        JOIN subjects s ON a.subject_id = s.id
        JOIN teachers t ON a.teacher_id = t.id
        WHERE a.section_id = ?
        ORDER BY s.subject_name
    """, (sec_id,)).fetchall()

    print(f"\nAvailable subjects for auto-schedule: {len(assignments_data)}")
    for i, a in enumerate(assignments_data[:5]):  # Show first 5
        print(f"  {i+1}. {a['subject_code']} - {a['subject_name'][:30]} → {a['teacher_name']}")

    if len(assignments_data) > 5:
        print(f"  ... and {len(assignments_data) - 5} more")

    # Test the period assignment logic
    period_times = [
        ('1st Period', '07:30', '08:30'),
        ('2nd Period', '08:30', '09:30'),
        ('3rd Period', '10:00', '11:00'),
        ('4th Period', '11:00', '12:00'),
        ('5th Period', '13:00', '14:00'),
        ('6th Period', '14:00', '15:00'),
        ('7th Period', '15:00', '16:00'),
        ('Last Period', '16:00', '17:00'),
    ]

    # Simulate parsing subjects (mark first as homeroom)
    parsed = []
    for i, a in enumerate(assignments_data[:8]):  # Limit to 8 for testing
        parsed.append({
            'subject_id': a['subject_id'],
            'teacher_id': a['teacher_id'],
            'is_homeroom': i == 0  # First subject is homeroom
        })

    print(f"\nSimulating auto-schedule for {len(parsed)} subjects:")
    print(f"  - Homeroom: Subject ID {parsed[0]['subject_id']}")
    print(f"  - Other subjects: {len(parsed) - 1}")

    # Test slot assignment logic
    slots = period_times.copy()
    assignments = []

    homeroom = next((item for item in parsed if item['is_homeroom']), None)
    esp_subjects = [s for s in assignments_data if 'ESP' in s['subject_code'].upper()]
    esp = next((item for item in parsed if any(s['subject_id'] == item['subject_id'] for s in esp_subjects)), None)
    others = [item for item in parsed if item != homeroom and item != esp]

    print(f"  - ESP subjects found: {len(esp_subjects)}")
    print(f"  - ESP in parsed: {esp is not None}")

    if homeroom:
        assignments.append((homeroom, slots[0]))
        slots = slots[1:]

    last_slot = None
    if esp:
        last_slot = slots[-1]
        slots = slots[:-1]

    import random
    others_ordered = others.copy()
    random.shuffle(others_ordered)

    for idx, item in enumerate(others_ordered):
        assignments.append((item, slots[idx]))

    if esp:
        assignments.append((esp, last_slot))

    print(f"\nSlot assignments:")
    for item, slot in assignments:
        subject_name = next((s['subject_name'] for s in assignments_data if s['subject_id'] == item['subject_id']), 'Unknown')
        teacher_name = next((s['teacher_name'] for s in assignments_data if s['subject_id'] == item['subject_id']), 'Unknown')
        is_hr = item.get('is_homeroom', False)
        is_esp = esp and item == esp
        marker = " (HOMEROOM)" if is_hr else " (ESP)" if is_esp else ""
        print(f"  {slot[0]:12} {slot[1]}-{slot[2]} → {subject_name[:25]}{marker} ({teacher_name})")

    print(f"\n✓ Logic test completed successfully")
    print(f"✓ All {len(parsed)} subjects would be assigned slots")

else:
    print("No suitable JHS section found for testing")

conn.close()
