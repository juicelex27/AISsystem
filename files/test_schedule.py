import sqlite3
import random

conn = sqlite3.connect('school.db')
conn.row_factory = sqlite3.Row

# Get a JHS section
section = conn.execute(
    "SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.grade_level IN ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10') LIMIT 1"
).fetchone()

if section:
    print(f"Section: {section['section_name']} ({section['grade_level']})")
    
    # Simulate form data
    form_subjects = ['1', '2', '3', '4']  # Subject IDs
    form_teachers = ['10', '11', '12', '13']  # Teacher IDs
    form_homerooms = ['0', '1', '0', '0']  # Mark subject 2 as homeroom
    
    # Parse as backend does
    subjects = [
        {
            'subject_id': int(sid),
            'teacher_id': int(tid),
            'is_homeroom': form_homerooms[idx] == '1' if idx < len(form_homerooms) else False
        }
        for idx, (sid, tid) in enumerate(zip(form_subjects, form_teachers))
    ]
    
    print("\nParsed subjects:")
    for s in subjects:
        print(f"  Subject {s['subject_id']}: teacher_id={s['teacher_id']}, is_homeroom={s['is_homeroom']}")
    
    # Build assignments as backend does
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
    
    slots = period_times.copy()
    assignments = []
    
    homeroom = next((item for item in subjects if item['is_homeroom']), None)
    others = [item for item in subjects if item != homeroom]
    
    print(f"\nHomeroom: {homeroom}")
    print(f"Others: {others}")
    
    if homeroom:
        assignments.append((homeroom, slots[0]))
        slots = slots[1:]
    
    others_ordered = others.copy()
    random.shuffle(others_ordered)
    
    print(f"\nShuffled others: {others_ordered}")
    
    for idx, item in enumerate(others_ordered):
        assignments.append((item, slots[idx]))
    
    print(f"\nAssignments (subject_id, period, times):")
    for item, slot in assignments:
        print(f"  Subject {item['subject_id']}: {slot[0]} ({slot[1]}-{slot[2]})")
    
    # Simulate insertion loop
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    print(f"\nInsertion simulation for day 'Monday':")
    for item, slot in assignments:
        subject_id = item['subject_id']
        is_homeroom = item.get('is_homeroom', False)
        
        if is_homeroom:
            _, time_start, time_end = period_times[0]
            print(f"  Subject {subject_id} (HOMEROOM): 1st Period {time_start}-{time_end}")
        else:
            _, time_start, time_end = slot
            print(f"  Subject {subject_id}: {slot[0]} {time_start}-{time_end}")

conn.close()
