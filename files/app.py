from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'sis_secret_key_2024_secure'
DATABASE = 'school.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_level TEXT NOT NULL,
            section_name TEXT NOT NULL,
            adviser_id INTEGER,
            strand_id INTEGER,
            student_limit INTEGER DEFAULT 40,
            FOREIGN KEY (adviser_id) REFERENCES teachers(id) ON DELETE SET NULL,
            FOREIGN KEY (strand_id) REFERENCES strands(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            strand TEXT,
            semester TEXT
        );
        CREATE TABLE IF NOT EXISTS strands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strand_code TEXT UNIQUE NOT NULL,
            strand_name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS strand_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strand_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            UNIQUE(strand_id, subject_id),
            FOREIGN KEY (strand_id) REFERENCES strands(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            strand_id INTEGER,
            day TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            room TEXT,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            FOREIGN KEY (strand_id) REFERENCES strands(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            section_id INTEGER NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
            UNIQUE(teacher_id, subject_id, section_id)
        );
        CREATE TABLE IF NOT EXISTS students (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id       TEXT UNIQUE NOT NULL,
            first_name       TEXT NOT NULL,
            last_name        TEXT NOT NULL,
            middle_name      TEXT,
            gender           TEXT,
            birthdate        TEXT,
            address          TEXT,
            contact_no       TEXT,
            email            TEXT,
            guardian_name    TEXT,
            guardian_contact TEXT,
            section_id       INTEGER,
            strand_id        INTEGER,
            grade_level      TEXT,
            enrollment_status TEXT DEFAULT 'Enrolled',
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL,
            FOREIGN KEY (strand_id)  REFERENCES strands(id)  ON DELETE SET NULL
        );
    ''')
    # Migration: add student_limit column to existing databases
    try:
        conn.execute("ALTER TABLE sections ADD COLUMN student_limit INTEGER DEFAULT 40")
    except Exception:
        pass  # column already exists
    # Migration: add strand_id column to existing databases
    try:
        conn.execute("ALTER TABLE sections ADD COLUMN strand_id INTEGER REFERENCES strands(id) ON DELETE SET NULL")
    except Exception:
        pass  # column already exists
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO admins (username,password,full_name) VALUES (?,?,?)",
                    ('admin', hash_password('admin123'), 'System Administrator'))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── AUTH ──
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=? AND password=?",
                             (username, hash_password(password))).fetchone()
        conn.close()
        if admin:
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['full_name']
            return redirect(url_for('dashboard'))
        error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── DASHBOARD ──
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    stats = {
        'teachers':  conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0],
        'subjects':  conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
        'sections':  conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
        'strands':   conn.execute("SELECT COUNT(*) FROM strands").fetchone()[0],
        'schedules': conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0],
    }
    recent_teachers = conn.execute("SELECT first_name,last_name,email FROM teachers ORDER BY id DESC LIMIT 5").fetchall()
    recent_subjects = conn.execute("SELECT subject_name,subject_code,grade_level FROM subjects ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return render_template('dashboard.html', stats=stats, recent_teachers=recent_teachers, recent_subjects=recent_subjects)

# ── TEACHERS ──
@app.route('/teachers')
@login_required
def teachers():
    conn = get_db()
    tlist = conn.execute("SELECT * FROM teachers ORDER BY last_name").fetchall()
    conn.close()
    return render_template('teachers.html', teachers=tlist)

@app.route('/teachers/add', methods=['POST'])
@login_required
def add_teacher():
    d = request.form
    try:
        conn = get_db()
        conn.execute("INSERT INTO teachers (first_name,last_name,email,username,password) VALUES (?,?,?,?,?)",
                     (d['first_name'],d['last_name'],d['email'],d['username'],hash_password(d['password'])))
        conn.commit(); conn.close()
        flash('Teacher added successfully.', 'success')
    except sqlite3.IntegrityError as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('teachers'))

@app.route('/teachers/edit/<int:tid>', methods=['POST'])
@login_required
def edit_teacher(tid):
    d = request.form
    conn = get_db()
    if d.get('password'):
        conn.execute("UPDATE teachers SET first_name=?,last_name=?,email=?,username=?,password=? WHERE id=?",
                     (d['first_name'],d['last_name'],d['email'],d['username'],hash_password(d['password']),tid))
    else:
        conn.execute("UPDATE teachers SET first_name=?,last_name=?,email=?,username=? WHERE id=?",
                     (d['first_name'],d['last_name'],d['email'],d['username'],tid))
    conn.commit(); conn.close()
    flash('Teacher updated.', 'success')
    return redirect(url_for('teachers'))

@app.route('/teachers/delete/<int:tid>', methods=['POST'])
@login_required
def delete_teacher(tid):
    conn = get_db()
    conn.execute("DELETE FROM teachers WHERE id=?", (tid,))
    conn.commit(); conn.close()
    flash('Teacher deleted.', 'success')
    return redirect(url_for('teachers'))

@app.route('/teachers/get/<int:tid>')
@login_required
def get_teacher(tid):
    conn = get_db()
    t = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    conn.close()
    return jsonify(dict(t)) if t else (jsonify({}), 404)

@app.route('/teachers/<int:tid>/schedule')
@login_required
def teacher_schedule(tid):
    conn = get_db()
    teacher = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    if not teacher:
        flash('Teacher not found.', 'danger')
        return redirect(url_for('teachers'))

    schedules_list = conn.execute("""
        SELECT sc.id, sc.section_id, sc.subject_id, sc.teacher_id,
               sc.day, sc.time_start, sc.time_end, sc.room,
               sub.subject_name, sub.subject_code, sub.semester,
               sec.section_name, sec.grade_level,
               st.strand_code
        FROM schedules sc
        JOIN subjects  sub ON sc.subject_id  = sub.id
        JOIN sections  sec ON sc.section_id  = sec.id
        LEFT JOIN strands st ON sc.strand_id = st.id
        WHERE sc.teacher_id = ?
        ORDER BY
            CASE sc.day
                WHEN 'Monday'    THEN 1
                WHEN 'Tuesday'   THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday'  THEN 4
                WHEN 'Friday'    THEN 5
                WHEN 'Saturday'  THEN 6
                ELSE 7
            END,
            sc.time_start
    """, (tid,)).fetchall()

    days_active    = len(set(s['day']        for s in schedules_list))
    sections_count = len(set(s['section_id'] for s in schedules_list))

    semesters_present = sorted({s['semester'] for s in schedules_list if s['semester']})
    sem_stats = {}
    for sem in semesters_present:
        sem_rows = [s for s in schedules_list if s['semester'] == sem]
        sem_stats[sem] = {
            'classes':  len(sem_rows),
            'days':     len(set(s['day']        for s in sem_rows)),
            'sections': len(set(s['section_id'] for s in sem_rows)),
        }

    conn.close()
    return render_template('teacher_schedule.html',
                           teacher=teacher,
                           schedules=schedules_list,
                           days_active=days_active,
                           sections_count=sections_count,
                           semesters=semesters_present,
                           sem_stats=sem_stats)

# ── SUBJECTS (table view) ──
@app.route('/subjects')
@login_required
def subjects():
    conn = get_db()
    slist = conn.execute("SELECT * FROM subjects ORDER BY grade_level,subject_name").fetchall()
    conn.close()
    return render_template('subjects.html', subjects=slist)

@app.route('/subjects/add', methods=['POST'])
@login_required
def add_subject():
    d = request.form
    conn = get_db()
    conn.execute("INSERT INTO subjects (subject_code,subject_name,grade_level,strand,semester) VALUES (?,?,?,?,?)",
                 (d['subject_code'],d['subject_name'],d['grade_level'],d.get('strand',''),d.get('semester','')))
    conn.commit(); conn.close()
    flash('Subject added successfully.', 'success')
    return redirect(url_for('subjects'))

@app.route('/subjects/edit/<int:sid>', methods=['POST'])
@login_required
def edit_subject(sid):
    d = request.form
    conn = get_db()
    conn.execute("UPDATE subjects SET subject_code=?,subject_name=?,grade_level=?,strand=?,semester=? WHERE id=?",
                 (d['subject_code'],d['subject_name'],d['grade_level'],d.get('strand',''),d.get('semester',''),sid))
    conn.commit(); conn.close()
    flash('Subject updated.', 'success')
    return redirect(url_for('subjects'))

@app.route('/subjects/delete/<int:sid>', methods=['POST'])
@login_required
def delete_subject(sid):
    conn = get_db()
    conn.execute("DELETE FROM subjects WHERE id=?", (sid,))
    conn.commit(); conn.close()
    flash('Subject deleted.', 'success')
    return redirect(url_for('subjects'))

@app.route('/subjects/get/<int:sid>')
@login_required
def get_subject(sid):
    conn = get_db()
    s = conn.execute("SELECT * FROM subjects WHERE id=?", (sid,)).fetchone()
    conn.close()
    return jsonify(dict(s)) if s else (jsonify({}), 404)

# ── STRANDS ──
@app.route('/strands')
@login_required
def strands():
    conn = get_db()
    strands_list = conn.execute("SELECT * FROM strands ORDER BY strand_code").fetchall()
    all_subjects  = conn.execute("SELECT * FROM subjects ORDER BY subject_name").fetchall()
    strands_data  = []
    for st in strands_list:
        assigned = conn.execute("""
            SELECT sub.* FROM subjects sub
            JOIN strand_subjects ss ON ss.subject_id=sub.id
            WHERE ss.strand_id=? ORDER BY sub.subject_name
        """, (st['id'],)).fetchall()
        strands_data.append({'strand': st, 'subjects': assigned})
    conn.close()
    return render_template('strands.html', strands_data=strands_data, all_subjects=all_subjects)

@app.route('/strands/add', methods=['POST'])
@login_required
def add_strand():
    d = request.form
    try:
        conn = get_db()
        conn.execute("INSERT INTO strands (strand_code,strand_name,description) VALUES (?,?,?)",
                     (d['strand_code'].upper(), d['strand_name'], d.get('description','')))
        conn.commit(); conn.close()
        flash('Strand added.', 'success')
    except sqlite3.IntegrityError:
        flash('Strand code already exists.', 'danger')
    return redirect(url_for('strands'))

@app.route('/strands/edit/<int:stid>', methods=['POST'])
@login_required
def edit_strand(stid):
    d = request.form
    conn = get_db()
    conn.execute("UPDATE strands SET strand_code=?,strand_name=?,description=? WHERE id=?",
                 (d['strand_code'].upper(), d['strand_name'], d.get('description',''), stid))
    conn.commit(); conn.close()
    flash('Strand updated.', 'success')
    return redirect(url_for('strands'))

@app.route('/strands/delete/<int:stid>', methods=['POST'])
@login_required
def delete_strand(stid):
    conn = get_db()
    conn.execute("DELETE FROM strands WHERE id=?", (stid,))
    conn.commit(); conn.close()
    flash('Strand deleted.', 'success')
    return redirect(url_for('strands'))

@app.route('/strands/get/<int:stid>')
@login_required
def get_strand(stid):
    conn = get_db()
    st = conn.execute("SELECT * FROM strands WHERE id=?", (stid,)).fetchone()
    conn.close()
    return jsonify(dict(st)) if st else (jsonify({}), 404)

@app.route('/strands/<int:stid>/assign_subject', methods=['POST'])
@login_required
def assign_subject_to_strand(stid):
    subject_ids = request.form.getlist('subject_ids')
    conn = get_db()
    added = 0
    for sid in subject_ids:
        try:
            conn.execute("INSERT INTO strand_subjects (strand_id,subject_id) VALUES (?,?)", (stid, sid))
            added += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit(); conn.close()
    flash(f'{added} subject(s) assigned to strand.', 'success')
    return redirect(url_for('strands'))

@app.route('/strands/<int:stid>/remove_subject/<int:sid>', methods=['POST'])
@login_required
def remove_subject_from_strand(stid, sid):
    conn = get_db()
    conn.execute("DELETE FROM strand_subjects WHERE strand_id=? AND subject_id=?", (stid, sid))
    conn.commit(); conn.close()
    flash('Subject removed from strand.', 'success')
    return redirect(url_for('strands'))

@app.route('/api/all_subjects')
@login_required
def api_all_subjects():
    conn = get_db()
    subs = conn.execute(
        "SELECT id, subject_name, subject_code, grade_level FROM subjects ORDER BY subject_name"
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in subs])

@app.route('/api/strand/<int:stid>/subjects')
@login_required
def api_strand_subjects(stid):
    conn = get_db()
    subs = conn.execute("""
        SELECT sub.id, sub.subject_name, sub.subject_code, sub.grade_level
        FROM subjects sub
        JOIN strand_subjects ss ON ss.subject_id=sub.id
        WHERE ss.strand_id=?
        ORDER BY sub.subject_name
    """, (stid,)).fetchall()
    conn.close()
    return jsonify([dict(s) for s in subs])

# ── SECTIONS (card view) ──
@app.route('/sections')
@login_required
def sections():
    conn = get_db()
    sections_raw = conn.execute("""
        SELECT s.*, t.first_name, t.last_name,
               COALESCE(s.student_limit, 40) AS student_limit,
               (SELECT COUNT(*) FROM students st WHERE st.section_id = s.id) AS student_count,
               st.strand_code, st.strand_name
        FROM sections s
        LEFT JOIN teachers t ON s.adviser_id = t.id
        LEFT JOIN strands st ON s.strand_id = st.id
        ORDER BY s.grade_level, s.section_name
    """).fetchall()
    teachers_list = conn.execute("SELECT id,first_name,last_name FROM teachers ORDER BY last_name").fetchall()
    strands_list  = conn.execute("SELECT id,strand_code,strand_name FROM strands ORDER BY strand_code").fetchall()
    sections_data = []
    for sec in sections_raw:
        cnt = conn.execute("SELECT COUNT(*) FROM schedules WHERE section_id=?", (sec['id'],)).fetchone()[0]
        sections_data.append({
            'section':        sec,
            'schedule_count': cnt,
            'student_count':  sec['student_count'],
            'student_limit':  sec['student_limit'],
        })
    conn.close()
    return render_template('sections.html', sections_data=sections_data, teachers=teachers_list, strands=strands_list)

@app.route('/sections/add', methods=['POST'])
@login_required
def add_section():
    d = request.form
    conn = get_db()
    conn.execute(
        "INSERT INTO sections (grade_level,section_name,adviser_id,strand_id,student_limit) VALUES (?,?,?,?,?)",
        (d['grade_level'], d['section_name'],
         d.get('adviser_id') or None,
         d.get('strand_id') or None,
         int(d.get('student_limit') or 40))
    )
    conn.commit(); conn.close()
    flash('Section added.', 'success')
    return redirect(url_for('sections'))

@app.route('/sections/edit/<int:sec_id>', methods=['POST'])
@login_required
def edit_section(sec_id):
    d = request.form
    conn = get_db()
    conn.execute(
        "UPDATE sections SET grade_level=?,section_name=?,adviser_id=?,strand_id=?,student_limit=? WHERE id=?",
        (d['grade_level'], d['section_name'],
         d.get('adviser_id') or None,
         d.get('strand_id') or None,
         int(d.get('student_limit') or 40),
         sec_id)
    )
    conn.commit(); conn.close()
    flash('Section updated.', 'success')
    return redirect(url_for('sections'))

@app.route('/sections/delete/<int:sec_id>', methods=['POST'])
@login_required
def delete_section(sec_id):
    conn = get_db()
    conn.execute("DELETE FROM sections WHERE id=?", (sec_id,))
    conn.commit(); conn.close()
    flash('Section deleted.', 'success')
    return redirect(url_for('sections'))

@app.route('/sections/get/<int:sec_id>')
@login_required
def get_section(sec_id):
    conn = get_db()
    s = conn.execute("SELECT * FROM sections WHERE id=?", (sec_id,)).fetchone()
    conn.close()
    return jsonify(dict(s)) if s else (jsonify({}), 404)

# ── CONFLICT DETECTION ──────────────────────────────────────────

def times_overlap(s1, e1, s2, e2):
    """True if [s1,e1) overlaps [s2,e2). Strings compare correctly as HH:MM."""
    return s1 < e2 and s2 < e1

def fmt_time(t):
    """Convert HH:MM to readable 12-hour format."""
    try:
        h, m = map(int, t.split(':'))
        suffix = 'AM' if h < 12 else 'PM'
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"
    except Exception:
        return t

MAX_SECTIONS_PER_TEACHER = 8   # configurable workload cap

def find_conflicts(conn, section_id, teacher_id, day, time_start, time_end,
                   room='', exclude_id=None, subject_id=None):
    base_q = """
        SELECT sc.id, sc.section_id, sc.teacher_id, sc.time_start, sc.time_end,
               sc.room, sub.subject_name, sub.subject_code,
               sec.section_name, sec.grade_level,
               t.first_name || ' ' || t.last_name AS teacher_name
        FROM schedules sc
        JOIN subjects  sub ON sc.subject_id  = sub.id
        JOIN sections  sec ON sc.section_id  = sec.id
        JOIN teachers  t   ON sc.teacher_id  = t.id
        WHERE sc.day = ?
    """
    excl  = " AND sc.id != ?" if exclude_id else ""
    args  = [day] + ([exclude_id] if exclude_id else [])
    rows  = conn.execute(base_q + excl, args).fetchall()

    conflicts = []

    for r in rows:
        if not times_overlap(time_start, time_end, r['time_start'], r['time_end']):
            continue

        ts = fmt_time(r['time_start'])
        te = fmt_time(r['time_end'])

        if str(r['section_id']) == str(section_id):
            conflicts.append({
                'type':   'section',
                'label':  'Section Conflict',
                'detail': (f'This section already has "{r["subject_name"]}" '
                           f'scheduled from {ts} to {te}.')
            })

        if str(r['teacher_id']) == str(teacher_id):
            conflicts.append({
                'type':   'teacher',
                'label':  'Teacher Conflict',
                'detail': (f'{r["teacher_name"]} is already teaching '
                           f'"{r["subject_name"]}" in Grade {r["grade_level"]} '
                           f'– {r["section_name"]} from {ts} to {te}.')
            })

        if room and room.strip() and r['room']:
            if r['room'].strip().lower() == room.strip().lower():
                conflicts.append({
                    'type':   'room',
                    'label':  'Room Conflict',
                    'detail': (f'Room "{room}" is already occupied by '
                               f'"{r["subject_name"]}" ({r["section_name"]}) '
                               f'from {ts} to {te}.')
                })

    semester = None
    if subject_id:
        row = conn.execute(
            "SELECT semester FROM subjects WHERE id=?", (subject_id,)
        ).fetchone()
        if row:
            semester = row['semester']

    if semester:
        excl_w   = " AND sc.id != ?" if exclude_id else ""
        args_w   = [teacher_id, semester] + ([exclude_id] if exclude_id else [])
        sec_q    = """
            SELECT DISTINCT sc.section_id
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id = sub.id
            WHERE sc.teacher_id = ? AND sub.semester = ?
        """ + excl_w
        existing_sections = conn.execute(sec_q, args_w).fetchall()
        existing_sec_ids  = {str(r['section_id']) for r in existing_sections}

        if str(section_id) not in existing_sec_ids and \
                len(existing_sec_ids) >= MAX_SECTIONS_PER_TEACHER:
            teacher_row = conn.execute(
                "SELECT first_name || ' ' || last_name AS name FROM teachers WHERE id=?",
                (teacher_id,)
            ).fetchone()
            teacher_name = teacher_row['name'] if teacher_row else 'This teacher'
            conflicts.append({
                'type':   'workload',
                'label':  'Workload Limit Reached',
                'detail': (f'{teacher_name} already covers '
                           f'{len(existing_sec_ids)} section(s) in {semester} — '
                           f'the maximum is {MAX_SECTIONS_PER_TEACHER} per semester.')
            })

    seen, unique = set(), []
    for c in conflicts:
        key = c['type'] + c['detail']
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


@app.route('/api/schedule/check_conflict', methods=['POST'])
@login_required
def api_check_conflict():
    d          = request.get_json(force=True) or {}
    section_id = d.get('section_id')
    teacher_id = d.get('teacher_id')
    day        = d.get('day')
    time_start = d.get('time_start', '')
    time_end   = d.get('time_end', '')
    room       = d.get('room', '')
    subject_id = d.get('subject_id')
    exclude_id = d.get('exclude_id')

    def get_workload(conn, tid, sid, sec_id):
        if sid:
            row = conn.execute("SELECT semester FROM subjects WHERE id=?", (sid,)).fetchone()
            semester = row['semester'] if row else None
        else:
            semester = None

        if semester:
            cnt = conn.execute("""
                SELECT COUNT(DISTINCT sc.section_id)
                FROM schedules sc
                JOIN subjects sub ON sc.subject_id = sub.id
                WHERE sc.teacher_id = ? AND sub.semester = ?
            """, (tid, semester)).fetchone()[0]

            is_new = conn.execute("""
                SELECT COUNT(*) FROM schedules sc
                JOIN subjects sub ON sc.subject_id = sub.id
                WHERE sc.teacher_id = ? AND sc.section_id = ? AND sub.semester = ?
            """, (tid, sec_id, semester)).fetchone()[0] == 0

            projected = cnt + 1 if is_new else cnt
            return {
                'current':   cnt,
                'projected': projected,
                'max':       MAX_SECTIONS_PER_TEACHER,
                'semester':  semester,
            }
        else:
            rows = conn.execute("""
                SELECT sub.semester, COUNT(DISTINCT sc.section_id) AS cnt
                FROM schedules sc
                JOIN subjects sub ON sc.subject_id = sub.id
                WHERE sc.teacher_id = ?
                GROUP BY sub.semester
            """, (tid,)).fetchall()
            per_sem = {r['semester']: r['cnt'] for r in rows}
            busiest_sem = max(per_sem, key=per_sem.get) if per_sem else None
            busiest_cnt = per_sem[busiest_sem] if busiest_sem else 0
            return {
                'current':   busiest_cnt,
                'projected': busiest_cnt,
                'max':       MAX_SECTIONS_PER_TEACHER,
                'semester':  busiest_sem,
                'per_sem':   per_sem,
            }

    if not all([section_id, teacher_id, day, time_start, time_end]):
        workload = None
        if teacher_id:
            conn = get_db()
            workload = get_workload(conn, teacher_id, subject_id, section_id)
            workload['projected'] = workload['current']
            conn.close()
        return jsonify({'conflicts': [], 'ready': False,
                        'incomplete': True, 'workload': workload})

    if time_start >= time_end:
        return jsonify({
            'conflicts': [{
                'type':   'time',
                'label':  'Invalid Time Range',
                'detail': 'End time must be later than start time.'
            }],
            'ready': False, 'incomplete': False, 'workload': None
        })

    conn      = get_db()
    conflicts = find_conflicts(conn, section_id, teacher_id, day,
                               time_start, time_end, room, exclude_id,
                               subject_id=subject_id)
    workload  = get_workload(conn, teacher_id, subject_id, section_id)
    conn.close()

    return jsonify({
        'conflicts':  conflicts,
        'ready':      len(conflicts) == 0,
        'incomplete': False,
        'workload':   workload
    })


# ── SCHEDULE / TIMETABLE ──
@app.route('/schedule/<int:sec_id>')
@login_required
def schedule(sec_id):
    conn = get_db()
    section = conn.execute("""
        SELECT s.*, t.first_name, t.last_name
        FROM sections s LEFT JOIN teachers t ON s.adviser_id=t.id
        WHERE s.id=?
    """, (sec_id,)).fetchone()
    if not section:
        flash('Section not found.', 'danger')
        return redirect(url_for('sections'))
    schedules_list = conn.execute("""
        SELECT sc.*, sub.subject_name, sub.subject_code, sub.semester,
               t.first_name||' '||t.last_name AS teacher_name,
               st.strand_name, st.strand_code
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN teachers t ON sc.teacher_id=t.id
        LEFT JOIN strands st ON sc.strand_id=st.id
        WHERE sc.section_id=?
        ORDER BY CASE sc.day
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
            ELSE 7 END, sc.time_start
    """, (sec_id,)).fetchall()

    semesters_present = sorted({s['semester'] for s in schedules_list if s['semester']})
    strands_list  = conn.execute("SELECT * FROM strands ORDER BY strand_code").fetchall()
    teachers_list = conn.execute("SELECT id,first_name,last_name FROM teachers ORDER BY last_name").fetchall()
    conn.close()
    return render_template('schedule.html', section=section, schedules=schedules_list,
                           strands=strands_list, teachers=teachers_list,
                           semesters=semesters_present,
                           max_sections=MAX_SECTIONS_PER_TEACHER)

@app.route('/schedule/<int:sec_id>/add', methods=['POST'])
@login_required
def add_schedule(sec_id):
    d = request.form
    time_start = d['time_start']
    time_end   = d['time_end']
    teacher_id = d['teacher_id']
    day        = d['day']
    room       = d.get('room', '').strip()
    force      = d.get('force_save') == '1'

    if time_start >= time_end:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    conn = get_db()
    conflicts = find_conflicts(conn, sec_id, teacher_id, day, time_start, time_end, room)

    if conflicts and not force:
        for c in conflicts:
            flash(f'⚠️ {c["label"]}: {c["detail"]}', 'warning')
        flash('To save anyway, enable "Force save" in the form and resubmit.', 'warning')
        conn.close()
        return redirect(url_for('schedule', sec_id=sec_id))

    conn.execute("""
        INSERT INTO schedules (section_id,subject_id,teacher_id,strand_id,day,time_start,time_end,room)
        VALUES (?,?,?,?,?,?,?,?)
    """, (sec_id, d['subject_id'], teacher_id, d.get('strand_id') or None,
          day, time_start, time_end, room))
    conn.commit(); conn.close()

    if force and conflicts:
        flash('Schedule entry saved with known conflicts.', 'warning')
    else:
        flash('Schedule entry added successfully.', 'success')
    return redirect(url_for('schedule', sec_id=sec_id))

@app.route('/schedule/delete/<int:sch_id>/<int:sec_id>', methods=['POST'])
@login_required
def delete_schedule(sch_id, sec_id):
    conn = get_db()
    conn.execute("DELETE FROM schedules WHERE id=?", (sch_id,))
    conn.commit(); conn.close()
    flash('Schedule entry removed.', 'success')
    return redirect(url_for('schedule', sec_id=sec_id))

@app.route('/schedule/<int:sec_id>/flush', methods=['POST'])
@login_required
def flush_schedule(sec_id):
    conn = get_db()
    section = conn.execute("SELECT section_name FROM sections WHERE id=?", (sec_id,)).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'danger')
        return redirect(url_for('sections'))
    count = conn.execute("SELECT COUNT(*) FROM schedules WHERE section_id=?", (sec_id,)).fetchone()[0]
    conn.execute("DELETE FROM schedules WHERE section_id=?", (sec_id,))
    conn.commit(); conn.close()
    flash(f'All {count} schedule entr{"ies" if count != 1 else "y"} for {section["section_name"]} have been cleared.', 'success')
    return redirect(url_for('schedule', sec_id=sec_id))

# ── STUDENTS ─────────────────────────────────────────────────

@app.route('/students')
@login_required
def students():
    conn = get_db()
    students_list = conn.execute("""
        SELECT s.*, sec.section_name, sec.grade_level AS sec_grade,
               st.strand_code, st.strand_name
        FROM students s
        LEFT JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN strands  st  ON s.strand_id  = st.id
        ORDER BY s.last_name, s.first_name
    """).fetchall()
    sections_list = conn.execute("SELECT * FROM sections ORDER BY grade_level, section_name").fetchall()
    strands_list  = conn.execute("SELECT * FROM strands ORDER BY strand_code").fetchall()
    total      = len(students_list)
    enrolled   = sum(1 for s in students_list if s['enrollment_status'] == 'Enrolled')
    conn.close()
    return render_template('students.html',
                           students=students_list,
                           sections=sections_list,
                           strands=strands_list,
                           total=total,
                           enrolled=enrolled)

@app.route('/students/add', methods=['POST'])
@login_required
def add_student():
    d = request.form
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO students
              (student_id, first_name, last_name, middle_name, gender, birthdate,
               address, contact_no, email, guardian_name, guardian_contact,
               section_id, strand_id, grade_level, enrollment_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d['student_id'].strip(), d['first_name'].strip(), d['last_name'].strip(),
            d.get('middle_name','').strip() or None,
            d.get('gender') or None, d.get('birthdate') or None,
            d.get('address','').strip() or None,
            d.get('contact_no','').strip() or None,
            d.get('email','').strip() or None,
            d.get('guardian_name','').strip() or None,
            d.get('guardian_contact','').strip() or None,
            d.get('section_id') or None, d.get('strand_id') or None,
            d.get('grade_level','').strip() or None,
            d.get('enrollment_status','Enrolled')
        ))
        conn.commit()
        flash('Student added successfully.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('students'))

@app.route('/students/edit/<int:sid>', methods=['POST'])
@login_required
def edit_student(sid):
    d = request.form
    conn = get_db()
    try:
        conn.execute("""
            UPDATE students SET
              student_id=?, first_name=?, last_name=?, middle_name=?,
              gender=?, birthdate=?, address=?, contact_no=?, email=?,
              guardian_name=?, guardian_contact=?,
              section_id=?, strand_id=?, grade_level=?, enrollment_status=?
            WHERE id=?
        """, (
            d['student_id'].strip(), d['first_name'].strip(), d['last_name'].strip(),
            d.get('middle_name','').strip() or None,
            d.get('gender') or None, d.get('birthdate') or None,
            d.get('address','').strip() or None,
            d.get('contact_no','').strip() or None,
            d.get('email','').strip() or None,
            d.get('guardian_name','').strip() or None,
            d.get('guardian_contact','').strip() or None,
            d.get('section_id') or None, d.get('strand_id') or None,
            d.get('grade_level','').strip() or None,
            d.get('enrollment_status','Enrolled'),
            sid
        ))
        conn.commit()
        flash('Student updated.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('students'))

@app.route('/students/delete/<int:sid>', methods=['POST'])
@login_required
def delete_student(sid):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=?", (sid,))
    conn.commit(); conn.close()
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))

@app.route('/students/flush_by_strand', methods=['POST'])
@login_required
def flush_students_by_strand():
    strand_id  = request.form.get('strand_id') or None
    grade      = request.form.get('grade_level') or None
    status     = request.form.get('enrollment_status') or None

    if not strand_id and not grade and not status:
        flash('Please select at least one filter before flushing.', 'warning')
        return redirect(url_for('students'))

    conn = get_db()
    wheres, args = [], []
    if strand_id:
        wheres.append("strand_id = ?"); args.append(strand_id)
    if grade:
        wheres.append("grade_level = ?"); args.append(grade)
    if status:
        wheres.append("enrollment_status = ?"); args.append(status)

    where_sql = " AND ".join(wheres)
    count = conn.execute(f"SELECT COUNT(*) FROM students WHERE {where_sql}", args).fetchone()[0]
    conn.execute(f"DELETE FROM students WHERE {where_sql}", args)
    conn.commit(); conn.close()

    flash(f'{count} student(s) deleted successfully.', 'success')
    return redirect(url_for('students'))

@app.route('/students/section/<int:sec_id>')
@login_required
def section_student_list(sec_id):
    conn = get_db()
    section = conn.execute("""
        SELECT s.*, t.first_name, t.last_name,
               st.strand_code, st.strand_name,
               COALESCE(s.student_limit, 40) AS student_limit
        FROM sections s
        LEFT JOIN teachers t  ON s.adviser_id = t.id
        LEFT JOIN strands  st ON s.strand_id  = st.id
        WHERE s.id = ?
    """, (sec_id,)).fetchone()
    if not section:
        flash('Section not found.', 'danger')
        return redirect(url_for('students'))

    all_students = conn.execute("""
        SELECT s.*, st.strand_code
        FROM students s
        LEFT JOIN strands st ON s.strand_id = st.id
        WHERE s.section_id = ?
        ORDER BY s.last_name, s.first_name
    """, (sec_id,)).fetchall()
    conn.close()

    males   = [s for s in all_students if (s['gender'] or '').upper() == 'MALE']
    females = [s for s in all_students if (s['gender'] or '').upper() == 'FEMALE']
    others  = [s for s in all_students if (s['gender'] or '').upper() not in ('MALE', 'FEMALE')]

    return render_template('section_students.html',
                           section=section,
                           males=males, females=females, others=others,
                           total=len(all_students))
@app.route('/students/get/<int:sid>')
@login_required
def get_student(sid):
    conn = get_db()
    s = conn.execute("""
        SELECT s.*, sec.section_name, st.strand_code, st.strand_name
        FROM students s
        LEFT JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN strands  st  ON s.strand_id  = st.id
        WHERE s.id = ?
    """, (sid,)).fetchone()
    conn.close()
    return jsonify(dict(s)) if s else (jsonify({}), 404)

@app.route('/students/bulk_add', methods=['POST'])
@login_required
def bulk_add_students():
    import csv, io
    raw = request.form.get('csv_data', '').strip()
    if not raw:
        flash('No data provided.', 'danger')
        return redirect(url_for('students'))

    reader = csv.DictReader(io.StringIO(raw))
    conn   = get_db()
    added = skipped = 0
    errors = []

    # Build a strand_code -> id lookup so CSV can use text like STEM instead of an ID
    strand_lookup = {}
    for r in conn.execute("SELECT id, strand_code FROM strands").fetchall():
        strand_lookup[r['strand_code'].upper()] = r['id']

    for i, row in enumerate(reader, start=2):
        sid_val = (row.get('student_id') or '').strip()
        fname   = (row.get('first_name') or '').strip()
        lname   = (row.get('last_name')  or '').strip()
        if not sid_val or not fname or not lname:
            errors.append(f'Row {i}: student_id, first_name, last_name are required.')
            skipped += 1
            continue

        # Resolve strand — accept numeric ID or text code (e.g. STEM)
        strand_id_val = None
        raw_strand = (row.get('strand_id') or row.get('strand_code') or '').strip()
        if raw_strand:
            if raw_strand.isdigit():
                strand_id_val = int(raw_strand)
            else:
                strand_id_val = strand_lookup.get(raw_strand.upper())
                if strand_id_val is None:
                    errors.append(f'Row {i}: strand "{raw_strand}" not found — skipping strand.')

        try:
            conn.execute("""
                INSERT OR IGNORE INTO students
                  (student_id, first_name, last_name, middle_name, gender, birthdate,
                   address, contact_no, email, guardian_name, guardian_contact,
                   grade_level, enrollment_status, strand_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                sid_val, fname, lname,
                row.get('middle_name','').strip() or None,
                row.get('gender','').strip() or None,
                row.get('birthdate','').strip() or None,
                row.get('address','').strip() or None,
                row.get('contact_no','').strip() or None,
                row.get('email','').strip() or None,
                row.get('guardian_name','').strip() or None,
                row.get('guardian_contact','').strip() or None,
                row.get('grade_level','').strip() or None,
                row.get('enrollment_status','Enrolled').strip() or 'Enrolled',
                strand_id_val,
            ))
            if conn.execute("SELECT changes()").fetchone()[0]:
                added += 1
            else:
                skipped += 1
                errors.append(f'Row {i}: student_id "{sid_val}" already exists.')
        except Exception as e:
            skipped += 1
            errors.append(f'Row {i}: {e}')

    conn.commit(); conn.close()

    if added:
        flash(f'{added} student(s) imported successfully.{ " " + str(skipped) + " skipped." if skipped else ""}', 'success')
    else:
        flash(f'No students imported. {skipped} row(s) skipped.', 'warning')
    if errors:
        for err in errors[:5]:
            flash(err, 'warning')
    return redirect(url_for('students'))


# ── AUTO-ASSIGN SECTION API ──────────────────────────────────

@app.route('/api/sections/by_strand')
@login_required
def api_sections_by_strand():
    """Return sections with student count and available slots, filtered by strand/grade."""
    strand_id = request.args.get('strand_id')
    grade     = request.args.get('grade_level')

    conn = get_db()
    base = """
        SELECT s.id, s.grade_level, s.section_name,
               COALESCE(s.student_limit, 40) AS student_limit,
               (SELECT COUNT(*) FROM students st WHERE st.section_id = s.id) AS student_count,
               t.first_name, t.last_name,
               st.strand_code, st.strand_name
        FROM sections s
        LEFT JOIN teachers t ON s.adviser_id = t.id
        LEFT JOIN strands st ON s.strand_id = st.id
    """
    wheres, args = [], []

    if grade:
        wheres.append("s.grade_level = ?")
        args.append(grade)

    if strand_id:
        wheres.append("s.strand_id = ?")
        args.append(strand_id)

    if wheres:
        base += " WHERE " + " AND ".join(wheres)
    base += " ORDER BY s.grade_level, s.section_name"

    rows = conn.execute(base, args).fetchall()
    conn.close()

    result = []
    for r in rows:
        limit    = r['student_limit']
        enrolled = r['student_count']
        result.append({
            'id':            r['id'],
            'grade_level':   r['grade_level'],
            'section_name':  r['section_name'],
            'student_limit': limit,
            'student_count': enrolled,
            'available':     max(0, limit - enrolled),
            'adviser':       f"{r['first_name']} {r['last_name']}" if r['first_name'] else None,
            'strand_code':   r['strand_code'],
            'strand_name':   r['strand_name'],
        })
    return jsonify(result)


@app.route('/students/auto_assign', methods=['POST'])
@login_required
def auto_assign_students():
    """Greedy round-robin auto-assign unassigned enrolled students into sections."""
    data       = request.get_json(force=True) or {}
    strand_id  = data.get('strand_id')
    grade      = data.get('grade_level')
    manual_ids = data.get('student_ids')

    conn = get_db()

    # Fetch candidate students
    q_args = []
    q = """
        SELECT id, first_name, last_name, grade_level, strand_id
        FROM students
        WHERE section_id IS NULL AND enrollment_status = 'Enrolled'
    """
    if manual_ids:
        placeholders = ','.join('?' * len(manual_ids))
        q += f" AND id IN ({placeholders})"
        q_args.extend(manual_ids)
    if strand_id:
        q += " AND strand_id = ?"
        q_args.append(strand_id)
    if grade:
        q += " AND grade_level = ?"
        q_args.append(grade)

    students_to_assign = conn.execute(q, q_args).fetchall()

    if not students_to_assign:
        conn.close()
        return jsonify({'assigned': 0, 'skipped': 0,
                        'details': [], 'message': 'No eligible unassigned students found.'})

    # Shuffle students so assignment is random, not alphabetical
    import random
    students_to_assign = list(students_to_assign)
    random.shuffle(students_to_assign)

    # Load target sections with available slots
    sec_q_args = []
    sec_q = """
        SELECT s.id, s.grade_level, s.section_name,
               COALESCE(s.student_limit, 40) AS student_limit,
               (SELECT COUNT(*) FROM students st WHERE st.section_id = s.id) AS student_count
        FROM sections s
    """
    sec_wheres = []
    if grade:
        sec_wheres.append("s.grade_level = ?")
        sec_q_args.append(grade)
    if strand_id:
        sec_wheres.append("s.strand_id = ?")
        sec_q_args.append(strand_id)
    if sec_wheres:
        sec_q += " WHERE " + " AND ".join(sec_wheres)
    sec_q += " ORDER BY s.grade_level, s.section_name"

    sections_raw = conn.execute(sec_q, sec_q_args).fetchall()

    section_slots = []
    for sec in sections_raw:
        available = max(0, (sec['student_limit'] or 40) - sec['student_count'])
        if available > 0:
            section_slots.append({
                'id':        sec['id'],
                'name':      f"Grade {sec['grade_level']} – {sec['section_name']}",
                'available': available,
            })

    if not section_slots:
        conn.close()
        return jsonify({'assigned': 0, 'skipped': len(students_to_assign),
                        'details': [],
                        'message': 'No sections with available slots found.'})

    # Shuffle sections so the starting point is random each run
    random.shuffle(section_slots)

    # Round-robin across sections so students are spread randomly and evenly
    assigned_count = skipped_count = 0
    details = []

    for student in students_to_assign:
        # Find next section with an available slot (round-robin)
        placed = False
        for _ in range(len(section_slots)):
            sec = section_slots[0]
            section_slots.append(section_slots.pop(0))  # rotate
            if sec['available'] > 0:
                conn.execute("UPDATE students SET section_id = ? WHERE id = ?", (sec['id'], student['id']))
                sec['available'] -= 1
                assigned_count += 1
                details.append({
                    'student_id': student['id'],
                    'name':    f"{student['first_name']} {student['last_name']}",
                    'status':  'assigned',
                    'section': sec['name'],
                })
                placed = True
                break

        if not placed:
            skipped_count += 1
            details.append({
                'student_id': student['id'],
                'name':   f"{student['first_name']} {student['last_name']}",
                'status': 'skipped',
                'reason': 'No available section slots'
            })

    conn.commit()
    conn.close()

    return jsonify({
        'assigned': assigned_count,
        'skipped':  skipped_count,
        'details':  details,
        'message':  f'{assigned_count} student(s) assigned, {skipped_count} skipped.'
    })


# ── ASSIGNMENTS (timetable overview) ──
@app.route('/assignments')
@login_required
def assignments():
    conn = get_db()
    sections_raw = conn.execute("""
        SELECT s.*, t.first_name, t.last_name
        FROM sections s LEFT JOIN teachers t ON s.adviser_id=t.id
        ORDER BY s.grade_level, s.section_name
    """).fetchall()
    sections_data = []
    for sec in sections_raw:
        cnt = conn.execute("SELECT COUNT(*) FROM schedules WHERE section_id=?", (sec['id'],)).fetchone()[0]
        sections_data.append({'section': sec, 'schedule_count': cnt})
    conn.close()
    return render_template('assignments.html', sections_data=sections_data)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)