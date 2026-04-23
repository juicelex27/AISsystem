import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), 'school.db')

conn = sqlite3.connect(DATABASE)
try:
    conn.execute('ALTER TABLE subject_section_offerings ADD COLUMN semester TEXT DEFAULT ""')
    conn.commit()
    print('✓ Migration complete: Added semester column to subject_section_offerings')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e):
        print('✓ Column already exists')
    else:
        print(f'Error: {e}')
finally:
    conn.close()