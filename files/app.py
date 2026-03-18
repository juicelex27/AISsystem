from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, make_response
import sqlite3
import hashlib
import csv
import io
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
            password         TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL,
            FOREIGN KEY (strand_id)  REFERENCES strands(id)  ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS grades (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id          INTEGER NOT NULL,
            subject_id          INTEGER NOT NULL,
            section_id          INTEGER NOT NULL,
            quarter             TEXT NOT NULL CHECK(quarter IN ('Prelim','Midterm','Semi-Final','Final')),
            written_works       REAL,
            performance_tasks   REAL,
            quarterly_assessment REAL,
            midterm             REAL,
            finals              REAL,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now')),
            UNIQUE(student_id, subject_id, section_id, quarter),
            FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE,
            FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
            FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS grade_submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id  INTEGER,
            subject_id  INTEGER NOT NULL,
            section_id  INTEGER NOT NULL,
            quarter     TEXT NOT NULL CHECK(quarter IN ('Prelim','Midterm','Semi-Final','Final')),
            status      TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Submitted','Approved','Locked')),
            submitted_at TEXT,
            approved_at TEXT,
            approved_by TEXT,
            locked_at   TEXT,
            unlock_reason TEXT,
            updated_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(subject_id, section_id, quarter),
            FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
            FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS grade_edit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL,
            subject_id  INTEGER NOT NULL,
            section_id  INTEGER NOT NULL,
            quarter     TEXT NOT NULL,
            component   TEXT NOT NULL,
            old_value   REAL,
            new_value   REAL,
            reason      TEXT NOT NULL,
            edited_by   TEXT NOT NULL,
            edited_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS grading_period_settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            period      TEXT NOT NULL UNIQUE,
            is_open     INTEGER NOT NULL DEFAULT 0,
            opened_at   TEXT,
            opened_by   TEXT
        );
    ''')
    # Migrations for existing databases
    try:
        conn.execute("ALTER TABLE sections ADD COLUMN student_limit INTEGER DEFAULT 40")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE sections ADD COLUMN strand_id INTEGER REFERENCES strands(id) ON DELETE SET NULL")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE schedules ADD COLUMN semester TEXT")
    except Exception:
        pass  # Column already exists
    try:
        conn.execute("ALTER TABLE students ADD COLUMN password TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE grade_submissions ADD COLUMN submitted_at TEXT")
    except Exception:
        pass
    # Fix grade_submissions CHECK constraint to include 'Submitted' status
    try:
        has_submitted = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='grade_submissions'"
        ).fetchone()
        if has_submitted and 'Submitted' not in has_submitted['sql']:
            conn.executescript(
                "ALTER TABLE grade_submissions RENAME TO gs_backup;"
                "CREATE TABLE grade_submissions ("
                "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "    teacher_id INTEGER,"
                "    subject_id INTEGER NOT NULL,"
                "    section_id INTEGER NOT NULL,"
                "    quarter TEXT NOT NULL,"
                "    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Submitted','Approved','Locked')),"
                "    submitted_at TEXT,"
                "    approved_at TEXT,"
                "    approved_by TEXT,"
                "    locked_at TEXT,"
                "    unlock_reason TEXT,"
                "    updated_at TEXT DEFAULT (datetime('now')),"
                "    UNIQUE(subject_id, section_id, quarter),"
                "    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,"
                "    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE"
                ");"
                "INSERT OR IGNORE INTO grade_submissions"
                "    SELECT id, teacher_id, subject_id, section_id, quarter,"
                "           CASE WHEN status IN ('Draft','Submitted','Approved','Locked') THEN status ELSE 'Draft' END,"
                "           NULL, approved_at, approved_by, locked_at, unlock_reason, updated_at"
                "    FROM gs_backup;"
                "DROP TABLE gs_backup;"
            )
    except Exception:
        pass
    # Rename Q1-Q4 to grading period names
    # SQLite CHECK constraint blocks direct UPDATE, so we recreate the tables
    try:
        # Check if old Q1-style quarters exist
        has_old = conn.execute("SELECT COUNT(*) FROM grades WHERE quarter IN ('Q1','Q2','Q3','Q4')").fetchone()[0]
        if has_old:
            # Temporarily drop CHECK by recreating grades table
            conn.executescript("""
                ALTER TABLE grades RENAME TO grades_old;
                CREATE TABLE grades (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          INTEGER NOT NULL,
                    subject_id          INTEGER NOT NULL,
                    section_id          INTEGER NOT NULL,
                    quarter             TEXT NOT NULL,
                    written_works       REAL,
                    performance_tasks   REAL,
                    quarterly_assessment REAL,
                    midterm             REAL,
                    finals              REAL,
                    created_at          TEXT DEFAULT (datetime('now')),
                    updated_at          TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE,
                    FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
                    FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
                );
                INSERT INTO grades SELECT * FROM grades_old;
                DROP TABLE grades_old;
            """)
            for _old, _new in [('Q1','Prelim'),('Q2','Midterm'),('Q3','Semi-Final'),('Q4','Final')]:
                conn.execute("UPDATE grades SET quarter=? WHERE quarter=?", (_new, _old))
        # Now add CHECK constraint back via recreation if needed
    except Exception as _e:
        pass  # already migrated or no old data

    try:
        has_old_sub = conn.execute("SELECT COUNT(*) FROM grade_submissions WHERE quarter IN ('Q1','Q2','Q3','Q4')").fetchone()[0]
        if has_old_sub:
            conn.executescript("""
                ALTER TABLE grade_submissions RENAME TO gs_old;
                CREATE TABLE grade_submissions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id  INTEGER,
                    subject_id  INTEGER NOT NULL,
                    section_id  INTEGER NOT NULL,
                    quarter     TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'Draft',
                    submitted_at TEXT,
                    approved_at TEXT,
                    approved_by TEXT,
                    locked_at   TEXT,
                    unlock_reason TEXT,
                    updated_at  TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
                    FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
                );
                INSERT INTO grade_submissions SELECT * FROM gs_old;
                DROP TABLE gs_old;
            """)
            for _old, _new in [('Q1','Prelim'),('Q2','Midterm'),('Q3','Semi-Final'),('Q4','Final')]:
                conn.execute("UPDATE grade_submissions SET quarter=? WHERE quarter=?", (_new, _old))
    except Exception as _e:
        pass

    try:
        for _old, _new in [('Q1','Prelim'),('Q2','Midterm'),('Q3','Semi-Final'),('Q4','Final')]:
            conn.execute("UPDATE grade_edit_log SET quarter=? WHERE quarter=?", (_new, _old))
    except Exception as _e:
        pass

    # Add semester column to grading_period_settings if missing
    try:
        conn.execute("ALTER TABLE grading_period_settings ADD COLUMN semester TEXT DEFAULT '1st Semester'")
    except Exception:
        pass
    # Seed grading period settings with semester separation
    # 1st Semester: Prelim, Midterm  |  2nd Semester: Semi-Final, Final
    # Always ensure grading_period_settings has UNIQUE(period, semester)
    # Check by trying to insert a duplicate — if it fails with old constraint, recreate
    try:
        has_old = conn.execute(
            "SELECT COUNT(*) FROM grading_period_settings WHERE period='Prelim'"
        ).fetchone()[0] > 1
    except Exception:
        has_old = False
    # Detect old single-column unique constraint by checking table SQL
    try:
        tbl_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='grading_period_settings'"
        ).fetchone()
        old_constraint = tbl_sql and 'UNIQUE(period, semester)' not in (tbl_sql['sql'] or '')
    except Exception:
        old_constraint = False
    if old_constraint:
        conn.executescript(
            "DROP TABLE IF EXISTS grading_period_settings_new;"
            "CREATE TABLE grading_period_settings_new ("
            "    id         INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    period     TEXT NOT NULL,"
            "    semester   TEXT NOT NULL DEFAULT '1st Semester',"
            "    is_open    INTEGER NOT NULL DEFAULT 0,"
            "    opened_at  TEXT,"
            "    opened_by  TEXT,"
            "    UNIQUE(period, semester)"
            ");"
            "DROP TABLE grading_period_settings;"
            "ALTER TABLE grading_period_settings_new RENAME TO grading_period_settings;"
        )

    # Each semester has its own 4 periods
    period_semesters = [
        ('Prelim',     '1st Semester', 1),
        ('Midterm',    '1st Semester', 0),
        ('Semi-Final', '1st Semester', 0),
        ('Final',      '1st Semester', 0),
        ('Prelim',     '2nd Semester', 0),
        ('Midterm',    '2nd Semester', 0),
        ('Semi-Final', '2nd Semester', 0),
        ('Final',      '2nd Semester', 0),
    ]
    for period, sem, default_open in period_semesters:
        existing = conn.execute(
            "SELECT id FROM grading_period_settings WHERE period=? AND semester=?", (period, sem)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO grading_period_settings (period, semester, is_open, opened_at, opened_by) VALUES (?,?,?,?,?)",
                (period, sem, default_open,
                 __import__('datetime').datetime.utcnow().isoformat() if default_open else None,
                 'System' if default_open else None)
            )
    # Backfill default student passwords = hashed student_id
    students_no_pw = conn.execute(
        "SELECT id, student_id FROM students WHERE password IS NULL"
    ).fetchall()
    for s in students_no_pw:
        conn.execute("UPDATE students SET password=? WHERE id=?",
                     (hash_password(s['student_id']), s['id']))
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

# ── ROLE-BASED DECORATORS ──
def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'teacher_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_session_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── AUTH ──
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    if 'teacher_id' in session:
        return redirect(url_for('teacher_dashboard'))
    if 'student_session_id' in session:
        return redirect(url_for('student_dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()

        # Try admin
        admin = conn.execute(
            "SELECT * FROM admins WHERE username=? AND password=?",
            (username, hash_password(password))
        ).fetchone()
        if admin:
            conn.close()
            session['admin_id']   = admin['id']
            session['admin_name'] = admin['full_name']
            session['role']       = 'admin'
            return redirect(url_for('dashboard'))

        # Try teacher (username field)
        teacher = conn.execute(
            "SELECT * FROM teachers WHERE username=? AND password=?",
            (username, hash_password(password))
        ).fetchone()
        if teacher:
            conn.close()
            session['teacher_id']   = teacher['id']
            session['teacher_name'] = teacher['first_name'] + ' ' + teacher['last_name']
            session['role']         = 'teacher'
            return redirect(url_for('teacher_dashboard'))

        # Try student (student_id field as username)
        student = conn.execute(
            "SELECT * FROM students WHERE student_id=? AND password=?",
            (username, hash_password(password))
        ).fetchone()
        if student:
            conn.close()
            session['student_session_id'] = student['id']
            session['student_name']       = student['first_name'] + ' ' + student['last_name']
            session['role']               = 'student'
            return redirect(url_for('student_dashboard'))

        conn.close()
        error = 'Invalid credentials. Please check your username and password.'
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

    # Per-teacher workload: count distinct sections per semester (using sc.semester with fallback)
    workload_rows = conn.execute("""
        SELECT sc.teacher_id,
               COALESCE(sc.semester, sub.semester) AS sem,
               COUNT(DISTINCT sc.section_id) AS cnt
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id = sub.id
        WHERE COALESCE(sc.semester, sub.semester) IN ('1st Semester','2nd Semester')
        GROUP BY sc.teacher_id, COALESCE(sc.semester, sub.semester)
    """).fetchall()

    # Build dict: {teacher_id: {'1st Semester': n, '2nd Semester': n}}
    workload_map = {}
    for r in workload_rows:
        workload_map.setdefault(r['teacher_id'], {})[r['sem']] = r['cnt']

    conn.close()
    return render_template('teachers.html', teachers=tlist,
                           workload_map=workload_map,
                           max_sections=MAX_SECTIONS_PER_TEACHER)

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
               sc.day, sc.time_start, sc.time_end, sc.room, sc.semester,
               sub.subject_name, sub.subject_code, sub.semester AS subject_semester,
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

    # Build semester tabs — fall back to subject_semester for legacy NULL sc.semester rows
    raw_sems = set()
    for s in schedules_list:
        sem = s['semester'] or s['subject_semester'] or None
        if not sem:
            continue
        if sem == 'Whole Year':
            raw_sems.add('1st Semester')
            raw_sems.add('2nd Semester')
        else:
            raw_sems.add(sem)
    semesters_present = sorted(raw_sems)
    sem_stats = {}
    for sem in semesters_present:
        sem_rows = [s for s in schedules_list
                    if (s['semester'] or s['subject_semester'] or '') in (sem, 'Whole Year')]
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

# ── SUBJECTS ──
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
        "SELECT id, subject_name, subject_code, grade_level, semester FROM subjects ORDER BY subject_name"
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

# ── SECTIONS ──
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

MAX_SECTIONS_PER_TEACHER = 8

def find_conflicts(conn, section_id, teacher_id, day, time_start, time_end,
                   room='', exclude_id=None, subject_id=None, semester=None):
    """
    Detect scheduling conflicts for a new/edited entry.
    semester-aware: section, teacher, and room conflicts are only flagged when
    the existing entry's semester overlaps with the new entry's semester.
    Overlap rules:
      - '1st Semester' only overlaps with '1st Semester' and 'Whole Year'
      - '2nd Semester' only overlaps with '2nd Semester' and 'Whole Year'
      - 'Whole Year' overlaps with everything
      - blank/None overlaps with everything (conservative)
    """
    # Resolve semester of the new entry from subject if not provided directly
    if semester is None and subject_id:
        row = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if row:
            semester = row['semester'] or None

    def semesters_overlap(sem_a, sem_b):
        """True if two semester strings can conflict with each other."""
        WHOLE = 'Whole Year'
        if not sem_a or not sem_b:
            return True   # unknown semester = conservative, treat as overlap
        if sem_a == WHOLE or sem_b == WHOLE:
            return True   # whole-year blocks everything
        return sem_a == sem_b

    base_q = """
        SELECT sc.id, sc.section_id, sc.subject_id, sc.teacher_id, sc.time_start, sc.time_end,
               sc.room, sc.semester AS row_semester,
               sub.subject_name, sub.subject_code, sub.semester AS sub_semester,
               sec.section_name, sec.grade_level,
               t.first_name || ' ' || t.last_name AS teacher_name
        FROM schedules sc
        JOIN subjects  sub ON sc.subject_id  = sub.id
        JOIN sections  sec ON sc.section_id  = sec.id
        JOIN teachers  t   ON sc.teacher_id  = t.id
        WHERE sc.day = ?
    """
    excl = " AND sc.id != ?" if exclude_id else ""
    args = [day] + ([exclude_id] if exclude_id else [])
    rows = conn.execute(base_q + excl, args).fetchall()

    conflicts = []

    for r in rows:
        if not times_overlap(time_start, time_end, r['time_start'], r['time_end']):
            continue

        existing_sem = r['row_semester'] or r['sub_semester'] or None
        sem_clash    = semesters_overlap(semester, existing_sem)

        # Skip: this is the paired semester entry for the same Whole Year subject
        # (same subject, same section, different semester — not a real conflict)
        is_paired_wy = (
            subject_id and str(r['subject_id']) == str(subject_id) and
            str(r['section_id']) == str(section_id) and
            existing_sem != semester and
            r['sub_semester'] == 'Whole Year'
        )
        if is_paired_wy:
            continue

        ts = fmt_time(r['time_start'])
        te = fmt_time(r['time_end'])
        sem_note = f' ({existing_sem})' if existing_sem and existing_sem != semester else ''

        # Section conflict: same section can't have two subjects at the same time
        # (same semester only — different semesters share the same room/teacher but not the section slot)
        if str(r['section_id']) == str(section_id) and sem_clash:
            conflicts.append({
                'type':   'section',
                'label':  'Section Conflict',
                'detail': (f'This section already has "{r["subject_name"]}"{sem_note} '
                           f'scheduled from {ts} to {te}.')
            })

        # Teacher conflict: same teacher can't teach two classes at the same time (same semester)
        if str(r['teacher_id']) == str(teacher_id) and sem_clash:
            conflicts.append({
                'type':   'teacher',
                'label':  'Teacher Conflict',
                'detail': (f'{r["teacher_name"]} is already teaching '
                           f'"{r["subject_name"]}"{sem_note} in Grade {r["grade_level"]} '
                           f'– {r["section_name"]} from {ts} to {te}.')
            })

        # Room conflict: room can't be double-booked in the same semester
        # Exception: "FIELD" is a shared open location — multiple sections can use it simultaneously
        FIELD_ROOMS = {
            'field', 'fields', 'field area', 'open field', 'grounds',
            'gym', 'gymnasium', 'covered court', 'court', 'snnhs covered court',
            'computer laboratory 1', 'computer laboratory 2',
            'computer lab 1', 'computer lab 2', 'comp lab 1', 'comp lab 2',
            'eim room 1', 'eim room 2',
            'he room',
        }
        def is_field(r_str): return r_str.strip().lower() in FIELD_ROOMS

        if room and room.strip() and r['room']:
            if r['room'].strip().lower() == room.strip().lower() and sem_clash:
                if not is_field(room):
                    conflicts.append({
                        'type':   'room',
                        'label':  'Room Conflict',
                        'detail': (f'Room "{room}" is already occupied by '
                                   f'"{r["subject_name"]}"{sem_note} ({r["section_name"]}) '
                                   f'from {ts} to {te}.')
                    })

    # Workload check: count distinct sections the teacher handles per semester
    if semester and semester != 'Whole Year':
        excl_w = " AND sc.id != ?" if exclude_id else ""
        args_w = [teacher_id, semester, semester] + ([exclude_id] if exclude_id else [])
        sec_q  = """
            SELECT DISTINCT sc.section_id
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id = sub.id
            WHERE sc.teacher_id = ? AND (sc.semester = ? OR (sc.semester IS NULL AND sub.semester = ?))
        """ + excl_w
        existing_sections = conn.execute(sec_q, args_w).fetchall()
        existing_sec_ids  = {str(r['section_id']) for r in existing_sections}

        if str(section_id) not in existing_sec_ids and                 len(existing_sec_ids) >= MAX_SECTIONS_PER_TEACHER:
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
    d                 = request.get_json(force=True) or {}
    section_id        = d.get('section_id')
    teacher_id        = d.get('teacher_id')
    day               = d.get('day')
    time_start        = d.get('time_start', '')
    time_end          = d.get('time_end', '')
    room              = d.get('room', '')
    subject_id        = d.get('subject_id')
    exclude_id        = d.get('exclude_id')
    semester_override = d.get('semester_override', '').strip()

    def get_workload(conn, tid, sid, sec_id, resolved_sem=None):
        # Use resolved semester if provided (e.g. WY subject with semester_override)
        # otherwise derive from subject
        if resolved_sem:
            semester = resolved_sem
        elif sid:
            row = conn.execute("SELECT semester FROM subjects WHERE id=?", (sid,)).fetchone()
            semester = (row['semester'] or None) if row else None
        else:
            semester = None

        # For WY subjects with no override, show workload per-sem breakdown
        if semester and semester != 'Whole Year':
            cnt = conn.execute("""
                SELECT COUNT(DISTINCT sc.section_id)
                FROM schedules sc
                WHERE sc.teacher_id = ? AND (
                    sc.semester = ?
                    OR (sc.semester IS NULL AND EXISTS (
                        SELECT 1 FROM subjects sub WHERE sub.id = sc.subject_id AND sub.semester = ?
                    ))
                )
            """, (tid, semester, semester)).fetchone()[0]

            is_new = conn.execute("""
                SELECT COUNT(*) FROM schedules sc
                WHERE sc.teacher_id = ? AND sc.section_id = ? AND (
                    sc.semester = ?
                    OR (sc.semester IS NULL AND EXISTS (
                        SELECT 1 FROM subjects sub WHERE sub.id = sc.subject_id AND sub.semester = ?
                    ))
                )
            """, (tid, sec_id, semester, semester)).fetchone()[0] == 0

            projected = cnt + 1 if is_new else cnt
            return {
                'current':   cnt,
                'projected': projected,
                'max':       MAX_SECTIONS_PER_TEACHER,
                'semester':  semester,
            }
        else:
            rows = conn.execute("""
                SELECT COALESCE(sc.semester, sub.semester) AS sem,
                       COUNT(DISTINCT sc.section_id) AS cnt
                FROM schedules sc
                JOIN subjects sub ON sc.subject_id = sub.id
                WHERE sc.teacher_id = ?
                GROUP BY COALESCE(sc.semester, sub.semester)
            """, (tid,)).fetchall()
            per_sem = {r['sem']: r['cnt'] for r in rows if r['sem']}
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
    # Resolve semester: honour semester_override for Whole Year subjects
    sub_sem_row = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone() if subject_id else None
    raw_sem     = (sub_sem_row['semester'] or '') if sub_sem_row else ''
    if raw_sem == 'Whole Year' and semester_override in ('1st Semester', '2nd Semester'):
        check_sem = semester_override
    elif raw_sem and raw_sem != 'Whole Year':
        check_sem = raw_sem
    else:
        check_sem = raw_sem or None
    conflicts = find_conflicts(conn, section_id, teacher_id, day,
                               time_start, time_end, room, exclude_id,
                               subject_id=subject_id, semester=check_sem)
    workload  = get_workload(conn, teacher_id, subject_id, section_id, resolved_sem=check_sem)
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
        SELECT sc.*, sub.subject_name, sub.subject_code, sub.semester AS subject_semester,
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

    # Build semester tabs — use sc.semester (stored), fall back to sub.semester for legacy NULL rows
    # Whole Year entries expand to show in both tabs
    raw_sems = set()
    for s in schedules_list:
        sem = s['semester'] or s['subject_semester'] or None
        if not sem:
            continue
        if sem == 'Whole Year':
            raw_sems.add('1st Semester')
            raw_sems.add('2nd Semester')
        else:
            raw_sems.add(sem)
    semesters_present = sorted(raw_sems)
    strands_list  = conn.execute("SELECT * FROM strands ORDER BY strand_code").fetchall()
    teachers_list = conn.execute("SELECT id,first_name,last_name FROM teachers ORDER BY last_name").fetchall()

    # BUG 4 FIX: pass all subjects so JS fallback is never empty
    all_subjects = conn.execute(
        "SELECT id, subject_name, subject_code, grade_level FROM subjects ORDER BY subject_name"
    ).fetchall()
    all_subjects_json = [dict(s) for s in all_subjects]

    conn.close()
    return render_template('schedule.html',
                           section=section,
                           schedules=schedules_list,
                           strands=strands_list,
                           teachers=teachers_list,
                           semesters=semesters_present,
                           max_sections=MAX_SECTIONS_PER_TEACHER,
                           all_subjects_json=all_subjects_json)


@app.route('/schedule/<int:sec_id>/add', methods=['POST'])
@login_required
def add_schedule(sec_id):
    d          = request.form
    time_start = d['time_start']
    time_end   = d['time_end']
    teacher_id = d['teacher_id']
    room       = d.get('room', '').strip()
    force      = d.get('force_save') == '1'

    # BUG 1 FIX: read ALL selected days, not just the first
    days = request.form.getlist('day')
    if not days:
        flash('Please select at least one day.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    if time_start >= time_end:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    conn = get_db()

    # Resolve subject semester
    subject_id       = d.get('subject_id')
    semester_override = d.get('semester_override', '').strip()  # from WY picker
    sub_row          = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone() if subject_id else None
    raw_sem          = (sub_row['semester'] or '') if sub_row else ''

    if raw_sem == 'Whole Year':
        if semester_override in ('1st Semester', '2nd Semester'):
            semesters_to_save = [semester_override]
        else:
            # No semester chosen — reject (frontend should have blocked this)
            conn.close()
            flash('Please select a semester (1st or 2nd) for this Whole Year subject.', 'danger')
            return redirect(url_for('schedule', sec_id=sec_id))
    elif raw_sem:
        semesters_to_save = [raw_sem]
    else:
        semesters_to_save = [None]

    strand_id = d.get('strand_id') or None

    # Check conflicts for every day × semester combination before inserting
    all_conflicts = []
    for day in days:
        for sem in semesters_to_save:
            day_conflicts = find_conflicts(conn, sec_id, teacher_id, day,
                                           time_start, time_end, room,
                                           subject_id=subject_id,
                                           semester=sem)
            sem_label = f' [{sem}]' if sem else ''
            for c in day_conflicts:
                c['detail'] = f'({day}{sem_label}) {c["detail"]}'
                all_conflicts.append(c)

    if all_conflicts and not force:
        for c in all_conflicts:
            flash(f'⚠️ {c["label"]}: {c["detail"]}', 'warning')
        flash('To save anyway, enable "Force save" in the form and resubmit.', 'warning')
        conn.close()
        return redirect(url_for('schedule', sec_id=sec_id))

    # Insert one row per day × semester — save the resolved semester on the row itself
    inserted = 0
    for day in days:
        for sem in semesters_to_save:
            conn.execute(
                "INSERT INTO schedules (section_id, subject_id, teacher_id, strand_id, day, time_start, time_end, room, semester) VALUES (?,?,?,?,?,?,?,?,?)",
                (sec_id, subject_id, teacher_id, strand_id, day, time_start, time_end, room, sem)
            )
            inserted += 1

    conn.commit()
    conn.close()

    label = f'{inserted} schedule entr{"ies" if inserted != 1 else "y"}'
    if raw_sem == 'Whole Year':
        label += f' ({semesters_to_save[0]})'
    if force and all_conflicts:
        flash(f'{label} saved with known conflicts.', 'warning')
    else:
        flash(f'{label} added successfully.', 'success')

    return redirect(url_for('schedule', sec_id=sec_id))



@app.route('/schedule/edit/<int:sch_id>/<int:sec_id>', methods=['POST'])
@login_required
def edit_schedule(sch_id, sec_id):
    d          = request.form
    time_start = d['time_start']
    time_end   = d['time_end']
    teacher_id = d['teacher_id']
    subject_id = d['subject_id']
    day        = d['day']
    room       = d.get('room', '').strip()
    strand_id  = d.get('strand_id') or None
    force      = d.get('force_save') == '1'

    if time_start >= time_end:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    conn = get_db()
    # Use the stored sc.semester for this entry (not sub.semester which may be 'Whole Year')
    stored_row  = conn.execute("SELECT semester FROM schedules WHERE id=?", (sch_id,)).fetchone()
    stored_sem  = (stored_row['semester'] or None) if stored_row else None
    if not stored_sem and subject_id:
        sub_sem_row = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone()
        stored_sem  = (sub_sem_row['semester'] or None) if sub_sem_row else None
    conflicts = find_conflicts(conn, sec_id, teacher_id, day,
                               time_start, time_end, room,
                               exclude_id=sch_id,
                               subject_id=subject_id,
                               semester=stored_sem)

    if conflicts and not force:
        for c in conflicts:
            flash(f'Warning {c["label"]}: {c["detail"]}', 'warning')
        flash('To save anyway, enable "Force save" and resubmit.', 'warning')
        conn.close()
        return redirect(url_for('schedule', sec_id=sec_id))

    conn.execute(
        "UPDATE schedules SET subject_id=?, teacher_id=?, strand_id=?, day=?, time_start=?, time_end=?, room=?, semester=? WHERE id=?",
        (subject_id, teacher_id, strand_id, day, time_start, time_end, room, stored_sem, sch_id)
    )

    # Optionally sync the paired Whole Year sibling — only if user checked "Also apply to paired"
    sync_pair      = d.get('sync_pair') == '1'
    paired_updated = False

    if sync_pair and stored_sem in ('1st Semester', '2nd Semester'):
        # Find sibling: same subject/section/day, different semester
        pair = conn.execute("""
            SELECT id FROM schedules
            WHERE subject_id=? AND section_id=? AND day=?
              AND id != ?
              AND (semester IS NULL OR semester != ?)
        """, (subject_id, sec_id, day, sch_id, stored_sem or '')).fetchone()
        if pair:
            conn.execute(
                "UPDATE schedules SET teacher_id=?, strand_id=?, time_start=?, time_end=?, room=? WHERE id=?",
                (teacher_id, strand_id, time_start, time_end, room, pair['id'])
            )
            paired_updated = True

    conn.commit()
    conn.close()

    if force and conflicts:
        msg = 'Schedule entry updated with known conflicts.'
        if paired_updated:
            msg += ' Paired semester entry also synced.'
        flash(msg, 'warning')
    else:
        if paired_updated:
            flash('Schedule entry updated — paired semester entry synced automatically.', 'success')
        else:
            flash('Schedule entry updated successfully.', 'success')
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

# ── STUDENTS ──────────────────────────────────────────────────

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
    total    = len(students_list)
    enrolled = sum(1 for s in students_list if s['enrollment_status'] == 'Enrolled')
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
    strand_id = request.form.get('strand_id') or None
    grade     = request.form.get('grade_level') or None
    status    = request.form.get('enrollment_status') or None

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
        flash(f'{added} student(s) imported successfully.{" " + str(skipped) + " skipped." if skipped else ""}', 'success')
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


@app.route('/students/reset_password/<int:sid>', methods=['POST'])
@login_required
def reset_student_password(sid):
    new_pw = request.form.get('new_password', '').strip()
    if not new_pw:
        flash('Password cannot be empty.', 'danger')
        return redirect(url_for('students'))
    conn = get_db()
    conn.execute("UPDATE students SET password=? WHERE id=?", (hash_password(new_pw), sid))
    conn.commit(); conn.close()
    flash('Student password reset successfully.', 'success')
    return redirect(url_for('students'))

@app.route('/students/reset_all_passwords', methods=['POST'])
@login_required
def reset_all_student_passwords():
    conn = get_db()
    students = conn.execute("SELECT id, student_id FROM students").fetchall()
    for s in students:
        conn.execute("UPDATE students SET password=? WHERE id=?", (hash_password(s['student_id']), s['id']))
    conn.commit(); conn.close()
    flash(f'All {len(students)} student passwords reset to their Student ID.', 'success')
    return redirect(url_for('students'))

@app.route('/students/auto_assign', methods=['POST'])
@login_required
def auto_assign_students():
    import random
    data       = request.get_json(force=True) or {}
    strand_id  = data.get('strand_id')
    grade      = data.get('grade_level')
    manual_ids = data.get('student_ids')

    conn = get_db()

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

    students_to_assign = list(students_to_assign)
    random.shuffle(students_to_assign)

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

    random.shuffle(section_slots)

    assigned_count = skipped_count = 0
    details = []

    for student in students_to_assign:
        placed = False
        for _ in range(len(section_slots)):
            sec = section_slots[0]
            section_slots.append(section_slots.pop(0))
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



# ── GRADES ─────────────────────────────────────────────────────

PASSING_GRADE = 75
WW_WEIGHT  = 0.30
PT_WEIGHT  = 0.50
QA_WEIGHT  = 0.20

def compute_quarterly_grade(ww, pt, qa):
    """WW 30% + PT 50% + QA 20%. Returns None if all inputs are None."""
    if ww is None and pt is None and qa is None:
        return None
    ww = ww or 0
    pt = pt or 0
    qa = qa or 0
    return round(ww * WW_WEIGHT + pt * PT_WEIGHT + qa * QA_WEIGHT, 2)

def honor_classification(avg):
    if avg is None: return None
    if avg >= 98:   return 'With Highest Honors'
    if avg >= 95:   return 'With Honors'
    if avg >= 90:   return 'Honors'
    return None

def get_section_subjects(conn, section_id):
    """Distinct subjects scheduled for this section.
    Uses schedule-level semester (sc.semester) as the effective semester for this section,
    falling back to subject-level semester. This handles subjects like Research Methods
    that appear in 1st Sem for some sections and 2nd Sem for others.
    """
    return conn.execute("""
        SELECT sub.id, sub.subject_name, sub.subject_code,
               COALESCE(MAX(sc.semester), sub.semester) AS semester
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id = sub.id
        WHERE sc.section_id = ?
        GROUP BY sub.id
        ORDER BY sub.subject_name
    """, (section_id,)).fetchall()

# ── Grades home: list sections ──
@app.route('/grades/open_period', methods=['POST'])
@login_required
def open_next_period():
    period = request.form.get('period')
    if period not in ALL_PERIODS:
        flash('Invalid period.', 'danger')
        return redirect(url_for('grades_home'))

    conn = get_db()
    settings = get_period_settings(conn)

    sem = request.form.get('semester', '1st Semester')
    if sem not in SEM_PERIODS:
        flash('Invalid semester.', 'danger')
        return redirect(url_for('grades_home'))

    # Enforce sequential unlock within this semester
    sem_periods = ALL_PERIODS
    idx_in_sem  = sem_periods.index(period) if period in sem_periods else 0
    if idx_in_sem > 0:
        prev = sem_periods[idx_in_sem - 1]
        prev_open = conn.execute(
            "SELECT is_open FROM grading_period_settings WHERE period=? AND semester=?",
            (prev, sem)
        ).fetchone()
        if not prev_open or not prev_open['is_open']:
            conn.close()
            flash(f'You must open {prev} before opening {period} in {sem}.', 'warning')
            return redirect(url_for('grades_home'))

    conn.execute(
        "UPDATE grading_period_settings SET is_open=1, opened_at=datetime('now'), opened_by=? WHERE period=? AND semester=?",
        (session.get('admin_name', 'Admin'), period, sem)
    )
    conn.commit()
    conn.close()
    flash(f'{period} grading period is now open for all teachers.', 'success')
    return redirect(url_for('grades_home'))

@app.route('/grades')
@login_required
def grades_home():
    conn = get_db()
    sections_raw = conn.execute("""
        SELECT s.id, s.section_name, s.grade_level,
               st.strand_code,
               (SELECT COUNT(*) FROM students st2 WHERE st2.section_id = s.id) AS student_count,
               (SELECT COUNT(DISTINCT sc.subject_id) FROM schedules sc WHERE sc.section_id = s.id) AS subject_count
        FROM sections s
        LEFT JOIN strands st ON s.strand_id = st.id
        ORDER BY s.grade_level, s.section_name
    """).fetchall()

    # Pending (Submitted) counts per section
    pending_rows = conn.execute(
        "SELECT section_id, COUNT(*) AS cnt FROM grade_submissions WHERE status='Submitted' GROUP BY section_id"
    ).fetchall()
    pending_by_sec = {r['section_id']: r['cnt'] for r in pending_rows}

    total_pending = sum(pending_by_sec.values())

    sections = []
    for s in sections_raw:
        d = dict(s)
        d['pending_count'] = pending_by_sec.get(s['id'], 0)
        sections.append(d)

    period_settings_raw = get_period_settings(conn)
    open_periods        = get_open_periods(conn)
    conn.close()
    # Build per-semester settings dict for template: sem -> {period -> settings}
    sem_period_settings = {}
    for (period, sem), ps in period_settings_raw.items():
        sem_period_settings.setdefault(sem, {})[period] = ps
    return render_template('grades_home.html', sections=sections, pending_count=total_pending,
                           sem_period_settings=sem_period_settings,
                           open_periods=open_periods, all_periods=ALL_PERIODS)

# ── Grade sheet: section × subject ──
ALL_PERIODS  = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
PERIOD_SHORT = {'Prelim':'Pre','Midterm':'Mid','Semi-Final':'S-F','Final':'Fin'}
PERIOD_ORDER = {p: i for i, p in enumerate(ALL_PERIODS)}

# Semester → periods mapping — each semester has all 4 periods independently
SEM_PERIODS = {
    '1st Semester': ['Prelim', 'Midterm', 'Semi-Final', 'Final'],
    '2nd Semester': ['Prelim', 'Midterm', 'Semi-Final', 'Final'],
}

def get_open_periods(conn):
    """Return list of periods currently open school-wide."""
    rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE is_open=1"
    ).fetchall()
    open_set = {r['period'] for r in rows}
    return [p for p in ALL_PERIODS if p in open_set]

def get_open_periods_for_subject(conn, subject_semester, active_sem=None):
    """Return open periods for a subject based on its semester.
    Each semester has independent period controls.
    Whole Year subjects follow whichever semester tab is active.
    """
    if not subject_semester or subject_semester not in SEM_PERIODS:
        # Whole Year or unset: use active semester's controls, default to 1st
        lookup_sem = active_sem or '1st Semester'
    else:
        lookup_sem = subject_semester
    rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? AND is_open=1",
        (lookup_sem,)
    ).fetchall()
    open_set = {r['period'] for r in rows}
    return [p for p in ALL_PERIODS if p in open_set]

def get_period_settings(conn):
    """Return dict of (period, semester) -> settings, plus nested by semester."""
    rows = conn.execute("SELECT * FROM grading_period_settings ORDER BY semester, id").fetchall()
    result = {}
    for r in rows:
        key = (r['period'], r['semester'])
        result[key] = dict(r)
    return result

def subjects_for_sem_tab(subjects_all, active_sem):
    """Subjects for a semester tab: that semester's subjects + Whole Year."""
    return [s for s in subjects_all
            if (s['semester'] or '') in (active_sem, 'Whole Year', '')]

@app.route('/grades/section/<int:sec_id>')
@login_required
def grade_sheet(sec_id):
    conn = get_db()
    section  = conn.execute("SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.id=?", (sec_id,)).fetchone()
    if not section:
        flash('Section not found.', 'danger')
        return redirect(url_for('grades_home'))

    subjects_all = get_section_subjects(conn, sec_id)
    students     = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    active_sem = request.args.get('sem', '1st Semester')
    if active_sem not in ('1st Semester', '2nd Semester'):
        active_sem = '1st Semester'
    subjects = subjects_for_sem_tab(subjects_all, active_sem)

    sel_sub_id  = request.args.get('subject_id', type=int)
    if not sel_sub_id and subjects:
        sel_sub_id = subjects[0]['id']
    sel_subject = next((s for s in subjects if s['id'] == sel_sub_id), None)

    QUARTERS   = ALL_PERIODS
    grades_raw = conn.execute(
        "SELECT g.student_id, g.quarter, g.written_works, g.performance_tasks, g.quarterly_assessment FROM grades g WHERE g.section_id=? AND g.subject_id=?",
        (sec_id, sel_sub_id or 0)
    ).fetchall() if sel_sub_id else []

    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['student_id'], {})[g['quarter']] = g

    student_grades = []
    for st in students:
        qgrades = {}
        for q in QUARTERS:
            row = grade_map.get(st['id'], {}).get(q)
            if row:
                qg = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment'])
                qgrades[q] = {'ww': row['written_works'], 'pt': row['performance_tasks'],
                               'qa': row['quarterly_assessment'], 'computed': qg}
            else:
                qgrades[q] = {'ww': None, 'pt': None, 'qa': None, 'computed': None}
        vals = [qgrades[q]['computed'] for q in QUARTERS if qgrades[q]['computed'] is not None]
        avg  = round(sum(vals)/len(vals), 2) if vals else None
        student_grades.append({'student': st, 'quarters': qgrades, 'average': avg,
                                'passing': avg is not None and avg >= PASSING_GRADE})

    sub_statuses = {}
    if sel_sub_id:
        rows = conn.execute(
            "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=?",
            (sel_sub_id, sec_id)
        ).fetchall()
        sub_statuses = {r['quarter']: r['status'] for r in rows}

    conn.close()
    return render_template('grade_sheet.html',
                           section=section, subjects=subjects, subjects_all=subjects_all,
                           active_sem=active_sem, sel_subject=sel_subject, sel_sub_id=sel_sub_id,
                           students=student_grades, quarters=QUARTERS,
                           q_statuses=sub_statuses, passing_grade=PASSING_GRADE)

@app.route('/grades/section/<int:sec_id>/clear', methods=['POST'])
@login_required
def clear_grades(sec_id):
    sub_id = request.form.get('subject_id', type=int)
    period = request.form.get('period', '').strip()
    if not sub_id:
        return jsonify({'ok': False, 'error': 'No subject specified.'}), 400
    if period not in ALL_PERIODS:
        return jsonify({'ok': False, 'error': 'Invalid period.'}), 400

    conn = get_db()
    # Only clear Draft periods — cannot clear Approved/Locked
    sub_row = conn.execute(
        "SELECT status FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=?",
        (sub_id, sec_id, period)
    ).fetchone()
    status = sub_row['status'] if sub_row else 'Draft'
    if status in ('Approved', 'Locked'):
        conn.close()
        return jsonify({'ok': False, 'error': f'{period} is {status} and cannot be cleared.'}), 400

    conn.execute(
        "DELETE FROM grades WHERE subject_id=? AND section_id=? AND quarter=?",
        (sub_id, sec_id, period)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'period': period})

# ── Save grades (bulk POST from grade sheet) ──
@app.route('/grades/section/<int:sec_id>/save', methods=['POST'])
@login_required
def save_grades(sec_id):
    d          = request.form
    subject_id = int(d['subject_id'])
    conn       = get_db()
    QUARTERS   = ['Prelim','Midterm','Semi-Final','Final']

    def fval(v):
        try: return float(v) if v.strip() != '' else None
        except: return None

    for key, val in d.items():
        # key format: grade_{student_id}_{quarter}_{component}
        parts = key.split('_')
        if len(parts) != 4 or parts[0] != 'grade': continue
        _, sid, quarter, component = parts
        if quarter not in QUARTERS: continue
        sid = int(sid)
        v   = fval(val)

        existing = conn.execute(
            "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
            (sid, subject_id, sec_id, quarter)
        ).fetchone()

        if existing:
            conn.execute(f"UPDATE grades SET {component}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                         (v, sid, subject_id, sec_id, quarter))
        else:
            conn.execute("""INSERT INTO grades (student_id,subject_id,section_id,quarter,written_works,performance_tasks,quarterly_assessment,midterm,finals)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                         (sid, subject_id, sec_id, quarter, None, None, None, None, None))
            conn.execute(f"UPDATE grades SET {component}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                         (v, sid, subject_id, sec_id, quarter))

    conn.commit()
    conn.close()
    flash('Grades saved successfully.', 'success')
    return redirect(url_for('grade_sheet', sec_id=sec_id, subject_id=subject_id))

# ── Save grades via AJAX ──
@app.route('/grades/save_cell', methods=['POST'])
def save_grade_cell():
    if 'admin_id' not in session and 'teacher_id' not in session:
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    d          = request.get_json(force=True) or {}
    student_id = d.get('student_id')
    subject_id = d.get('subject_id')
    section_id = d.get('section_id')
    quarter    = d.get('quarter')
    component  = d.get('component')
    value      = d.get('value')
    reason     = (d.get('reason') or '').strip()

    ALLOWED = {'written_works','performance_tasks','quarterly_assessment','midterm','finals'}
    if component not in ALLOWED:
        return jsonify({'ok': False, 'error': 'Invalid component'}), 400

    try: value = float(value) if value not in (None, '') else None
    except: return jsonify({'ok': False, 'error': 'Invalid value'}), 400

    conn = get_db()

    # Block edits if Approved or Locked
    sub_row = conn.execute(
        "SELECT status FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=?",
        (subject_id, section_id, quarter)
    ).fetchone()
    status = sub_row['status'] if sub_row else 'Draft'

    if status in ('Approved', 'Locked'):
        conn.close()
        return jsonify({'ok': False, 'error': f'Grades are {status} and cannot be edited.', 'status': status}), 403

    # Block teacher edits if grading period is not open
    if 'teacher_id' in session and 'admin_id' not in session:
        period_row = conn.execute(
            "SELECT is_open FROM grading_period_settings WHERE period=?", (quarter,)
        ).fetchone()
        if not period_row or not period_row['is_open']:
            conn.close()
            return jsonify({'ok': False, 'error': f'{quarter} is not yet open for encoding.'}), 403

    # Log admin edits — require a reason if value is changing
    old_row = conn.execute(
        "SELECT " + component + " FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
        (student_id, subject_id, section_id, quarter)
    ).fetchone()
    old_value = old_row[component] if old_row else None

    if old_value != value:
        # Only require a reason when editing an already-existing grade (not a fresh entry)
        if old_value is not None and not reason:
            conn.close()
            return jsonify({'ok': False, 'error': 'A reason is required for grade changes.', 'need_reason': True}), 400
        if old_value is not None:
            editor = session.get('admin_name') or session.get('teacher_name') or 'User'
            conn.execute(
                "INSERT INTO grade_edit_log (student_id,subject_id,section_id,quarter,component,old_value,new_value,reason,edited_by) VALUES (?,?,?,?,?,?,?,?,?)",
                (student_id, subject_id, section_id, quarter, component,
                 old_value, value, reason or 'Grade updated', editor)
            )

    existing = conn.execute(
        "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
        (student_id, subject_id, section_id, quarter)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE grades SET " + component + "=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
            (value, student_id, subject_id, section_id, quarter)
        )
    else:
        kw = {c: None for c in ALLOWED}
        kw[component] = value
        conn.execute(
            "INSERT INTO grades (student_id,subject_id,section_id,quarter,written_works,performance_tasks,quarterly_assessment,midterm,finals) VALUES (?,?,?,?,?,?,?,?,?)",
            (student_id, subject_id, section_id, quarter,
             kw['written_works'], kw['performance_tasks'], kw['quarterly_assessment'],
             kw['midterm'], kw['finals'])
        )

    row = conn.execute(
        "SELECT written_works,performance_tasks,quarterly_assessment FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
        (student_id, subject_id, section_id, quarter)
    ).fetchone()
    computed = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment']) if row else None
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'computed': computed,
                    'passing': computed is not None and computed >= PASSING_GRADE,
                    'status': status})

# ── Student profile page ──
@app.route('/students/<int:student_id>/profile')
@login_required
def student_profile(student_id):
    conn    = get_db()
    student = conn.execute("""
        SELECT s.*, sec.section_name, sec.id AS sec_id, sec.grade_level AS sec_grade,
               st.strand_code, st.strand_name
        FROM students s
        LEFT JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN strands  st  ON s.strand_id  = st.id
        WHERE s.id=?
    """, (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))

    subjects  = get_section_subjects(conn, student['sec_id']) if student['sec_id'] else []
    QUARTERS  = ['Prelim','Midterm','Semi-Final','Final']

    # Submission statuses per subject+quarter
    sub_statuses = {}
    if student['sec_id']:
        rows = conn.execute(
            "SELECT subject_id, quarter, status FROM grade_submissions WHERE section_id=?",
            (student['sec_id'],)
        ).fetchall()
        for r in rows:
            sub_statuses.setdefault(r['subject_id'], {})[r['quarter']] = r['status']

    grades_raw = conn.execute("""
        SELECT g.subject_id, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment
        FROM grades g WHERE g.student_id=?
    """, (student_id,)).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['subject_id'], {})[g['quarter']] = g

    QUARTERS = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
    subject_rows = []
    sem1_avgs = []
    sem2_avgs = []
    all_sub_avgs = []

    for sub in subjects:
        qgrades = {}
        has_any_grade = False
        for q in QUARTERS:
            row    = grade_map.get(sub['id'], {}).get(q)
            status = sub_statuses.get(sub['id'], {}).get(q, 'Draft')
            if row:
                qg = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment'])
                has_any_grade = True
            else:
                qg = None
            visible = status in ('Approved', 'Locked')
            qgrades[q] = {'grade': qg if visible else None,
                          'status': status, 'has_data': qg is not None, 'visible': visible}

        visible_grades = [qgrades[q]['grade'] for q in QUARTERS if qgrades[q]['grade'] is not None]
        sub_avg = round(sum(visible_grades)/len(visible_grades), 2) if visible_grades else None

        sub_sem = sub['semester'] or ''
        if sub_avg is not None:
            all_sub_avgs.append(sub_avg)
            if sub_sem == '1st Semester':   sem1_avgs.append(sub_avg)
            elif sub_sem == '2nd Semester': sem2_avgs.append(sub_avg)
            elif sub_sem in ('Whole Year', ''):
                sem1_avgs.append(sub_avg)
                sem2_avgs.append(sub_avg)

        subject_rows.append({
            'subject': sub, 'quarters': qgrades,
            'average': sub_avg, 'has_any_grade': has_any_grade,
            'passing': sub_avg is not None and sub_avg >= PASSING_GRADE
        })

    general_avg = round(sum(all_sub_avgs)/len(all_sub_avgs), 2) if all_sub_avgs else None
    sem1_avg    = round(sum(sem1_avgs)/len(sem1_avgs), 2) if sem1_avgs else None
    sem2_avg    = round(sum(sem2_avgs)/len(sem2_avgs), 2) if sem2_avgs else None
    honor       = honor_classification(general_avg)
    conn.close()
    return render_template('student_profile.html', student=student, subject_rows=subject_rows,
                           quarters=QUARTERS, general_avg=general_avg, honor=honor,
                           passing_grade=PASSING_GRADE)

# ── Teacher profile page ──
@app.route('/teachers/<int:teacher_id>/profile')
@login_required
def teacher_profile(teacher_id):
    conn    = get_db()
    teacher = conn.execute("SELECT * FROM teachers WHERE id=?", (teacher_id,)).fetchone()
    if not teacher:
        flash('Teacher not found.', 'danger')
        return redirect(url_for('teachers'))

    schedules = conn.execute("""
        SELECT sc.id, sc.day, sc.time_start, sc.time_end, sc.room,
               sc.semester AS row_semester,
               sub.subject_name, sub.subject_code, sub.semester AS sub_semester,
               sec.section_name, sec.grade_level,
               st.strand_code
        FROM schedules sc
        JOIN subjects  sub ON sc.subject_id  = sub.id
        JOIN sections  sec ON sc.section_id  = sec.id
        LEFT JOIN strands st ON sc.strand_id = st.id
        WHERE sc.teacher_id=?
        ORDER BY CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END, sc.time_start
    """, (teacher_id,)).fetchall()

    days_active    = len({s['day'] for s in schedules})
    sections_count = len({s['section_name'] for s in schedules})
    subjects_count = len({s['subject_code'] for s in schedules})

    # Workload per semester
    workload = {}
    for s in schedules:
        sem = s['row_semester'] or s['sub_semester'] or 'Other'
        if sem not in ('1st Semester','2nd Semester'): continue
        workload.setdefault(sem, set()).add(s['section_name'])
    workload_counts = {k: len(v) for k,v in workload.items()}

    # Grade encoding progress for this teacher
    assigned_subjects = conn.execute("""
        SELECT DISTINCT sc.subject_id, sub.subject_name, sc.section_id, sec.section_name
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN sections sec ON sc.section_id=sec.id
        WHERE sc.teacher_id=?
    """, (teacher_id,)).fetchall()

    encoding_progress = []
    for row in assigned_subjects:
        student_count = conn.execute(
            "SELECT COUNT(*) FROM students WHERE section_id=?", (row['section_id'],)
        ).fetchone()[0]
        encoded = conn.execute(
            "SELECT COUNT(DISTINCT quarter) FROM grade_submissions WHERE subject_id=? AND section_id=? AND status IN ('Approved','Locked')",
            (row['subject_id'], row['section_id'])
        ).fetchone()[0]
        encoding_progress.append({
            'subject_name': row['subject_name'], 'section_name': row['section_name'],
            'student_count': student_count, 'approved_quarters': encoded
        })

    conn.close()
    return render_template('teacher_profile.html', teacher=teacher, schedules=schedules,
                           days_active=days_active, sections_count=sections_count,
                           subjects_count=subjects_count, workload_counts=workload_counts,
                           encoding_progress=encoding_progress,
                           max_sections=8)

# ── Report card: single student ──
@app.route('/grades/student/<int:student_id>')
@login_required
def report_card(student_id):
    conn    = get_db()
    student = conn.execute("""
        SELECT s.*, sec.section_name, sec.grade_level, st.strand_code
        FROM students s
        LEFT JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN strands st   ON s.strand_id  = st.id
        WHERE s.id=?
    """, (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('grades_home'))

    subjects = get_section_subjects(conn, student['section_id']) if student['section_id'] else []

    QUARTERS = ['Prelim','Midterm','Semi-Final','Final']

    # Submission statuses
    sub_statuses = {}
    if student['section_id']:
        rows = conn.execute(
            "SELECT subject_id, quarter, status FROM grade_submissions WHERE section_id=?",
            (student['section_id'],)
        ).fetchall()
        for r in rows:
            sub_statuses.setdefault(r['subject_id'], {})[r['quarter']] = r['status']

    grades_raw = conn.execute("""
        SELECT g.subject_id, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment,
               g.midterm, g.finals
        FROM grades g WHERE g.student_id=?
    """, (student_id,)).fetchall()

    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['subject_id'], {})[g['quarter']] = g

    subject_rows = []
    all_approved_qg = []
    for sub in subjects:
        qgrades = {}
        has_any = False
        for q in QUARTERS:
            row    = grade_map.get(sub['id'], {}).get(q)
            status = sub_statuses.get(sub['id'], {}).get(q, 'Draft')
            if row:
                qg = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment'])
                has_any = True
            else:
                qg = None
            visible = status in ('Approved', 'Locked')
            qgrades[q] = {'grade': qg if visible else None,
                          'status': status, 'has_data': qg is not None, 'visible': visible}
            if visible and qg is not None:
                all_approved_qg.append(qg)

        # Midterm avg = Q1+Q2 approved average
        q1g = qgrades['Prelim']['grade']; q2g = qgrades['Midterm']['grade']
        midterm_avg = round((q1g + q2g) / 2, 2) if q1g is not None and q2g is not None else None

        # Finals avg = Q3+Q4 approved average
        q3g = qgrades['Semi-Final']['grade']; q4g = qgrades['Final']['grade']
        finals_avg  = round((q3g + q4g) / 2, 2) if q3g is not None and q4g is not None else None

        visible_grades = [qgrades[q]['grade'] for q in QUARTERS if qgrades[q]['grade'] is not None]
        sub_avg = round(sum(visible_grades)/len(visible_grades), 2) if visible_grades else None
        subject_rows.append({
            'subject': sub, 'quarters': qgrades,
            'midterm_avg': midterm_avg, 'finals_avg': finals_avg,
            'average': sub_avg, 'has_any': has_any,
            'passing': sub_avg is not None and sub_avg >= PASSING_GRADE
        })

    general_avg = round(sum(all_q_grades)/len(all_q_grades), 2) if all_q_grades else None
    honor       = honor_classification(general_avg)
    conn.close()
    return render_template('report_card.html', student=student, subject_rows=subject_rows,
                           quarters=QUARTERS, general_avg=general_avg, honor=honor,
                           passing_grade=PASSING_GRADE)

# ── Honor roll: per section ──
@app.route('/grades/honor_roll')
@login_required
def honor_roll():
    conn = get_db()
    sec_id = request.args.get('section_id', type=int)
    sections_list = conn.execute("""
        SELECT s.id, s.section_name, s.grade_level, st.strand_code
        FROM sections s LEFT JOIN strands st ON s.strand_id=st.id
        ORDER BY s.grade_level, s.section_name
    """).fetchall()

    honorees = []
    if sec_id:
        students = conn.execute("""
            SELECT id, student_id, first_name, last_name, middle_name
            FROM students WHERE section_id=? ORDER BY last_name, first_name
        """, (sec_id,)).fetchall()

        for st in students:
            grades_raw = conn.execute("""
                SELECT g.quarter, g.written_works, g.performance_tasks, g.quarterly_assessment
                FROM grades g WHERE g.student_id=?
            """, (st['id'],)).fetchall()
            all_qg = []
            for g in grades_raw:
                qg = compute_quarterly_grade(g['written_works'], g['performance_tasks'], g['quarterly_assessment'])
                if qg is not None: all_qg.append(qg)
            avg   = round(sum(all_qg)/len(all_qg), 2) if all_qg else None
            honor = honor_classification(avg)
            if honor:
                honorees.append({'student': st, 'avg': avg, 'honor': honor})

        honorees.sort(key=lambda x: x['avg'], reverse=True)
        for i, h in enumerate(honorees, 1):
            h['rank'] = i

    conn.close()
    sel_section = next((s for s in sections_list if s['id'] == sec_id), None)
    return render_template('honor_roll.html', sections=sections_list, honorees=honorees,
                           sel_section=sel_section, sec_id=sec_id)

# ── Grade summary per teacher ──
@app.route('/grades/teacher_summary')
@login_required
def grade_teacher_summary():
    conn = get_db()
    teachers_list = conn.execute("SELECT id, first_name, last_name FROM teachers ORDER BY last_name").fetchall()
    tid = request.args.get('teacher_id', type=int)

    summary = []
    if tid:
        # subjects this teacher is assigned to via schedules
        assigned = conn.execute("""
            SELECT DISTINCT sc.subject_id, sub.subject_name, sub.subject_code,
                            sc.section_id, sec.section_name, sec.grade_level
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id=sub.id
            JOIN sections sec ON sc.section_id=sec.id
            WHERE sc.teacher_id=?
            ORDER BY sec.grade_level, sec.section_name, sub.subject_name
        """, (tid,)).fetchall()

        QUARTERS = ['Prelim','Midterm','Semi-Final','Final']
        for row in assigned:
            grades_raw = conn.execute("""
                SELECT g.student_id, g.quarter,
                       g.written_works, g.performance_tasks, g.quarterly_assessment
                FROM grades g
                WHERE g.subject_id=? AND g.section_id=?
            """, (row['subject_id'], row['section_id'])).fetchall()

            student_count = conn.execute(
                "SELECT COUNT(*) FROM students WHERE section_id=?", (row['section_id'],)
            ).fetchone()[0]

            # grades encoded count
            encoded = len({(g['student_id'], g['quarter']) for g in grades_raw})
            total_slots = student_count * 4

            qg_all = []
            for g in grades_raw:
                qg = compute_quarterly_grade(g['written_works'], g['performance_tasks'], g['quarterly_assessment'])
                if qg is not None: qg_all.append(qg)
            class_avg = round(sum(qg_all)/len(qg_all), 2) if qg_all else None
            passing_count = sum(1 for q in qg_all if q >= PASSING_GRADE)

            summary.append({
                'subject_name': row['subject_name'], 'subject_code': row['subject_code'],
                'section_name': row['section_name'], 'grade_level': row['grade_level'],
                'student_count': student_count, 'encoded': encoded, 'total_slots': total_slots,
                'class_avg': class_avg, 'passing_count': passing_count,
            })

    sel_teacher = next((t for t in teachers_list if t['id'] == tid), None)
    conn.close()
    return render_template('grade_teacher_summary.html', teachers=teachers_list,
                           sel_teacher=sel_teacher, summary=summary, tid=tid)


# ── GRADE APPROVAL ──────────────────────────────────────────────

def get_submission_status(conn, subject_id, section_id, quarter):
    row = conn.execute(
        "SELECT status FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=?",
        (subject_id, section_id, quarter)
    ).fetchone()
    return row['status'] if row else 'Draft'

def upsert_submission(conn, subject_id, section_id, quarter, status,
                      approved_by=None, unlock_reason=None):
    existing = conn.execute(
        "SELECT id FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=?",
        (subject_id, section_id, quarter)
    ).fetchone()
    if existing:
        if status == 'Approved':
            conn.execute(
                "UPDATE grade_submissions SET status=?, approved_at=datetime('now'), approved_by=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND quarter=?",
                (status, approved_by, subject_id, section_id, quarter)
            )
        elif status == 'Locked':
            conn.execute(
                "UPDATE grade_submissions SET status=?, locked_at=datetime('now'), updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND quarter=?",
                (status, subject_id, section_id, quarter)
            )
        elif status == 'Draft':
            conn.execute(
                "UPDATE grade_submissions SET status=?, unlock_reason=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND quarter=?",
                (status, unlock_reason, subject_id, section_id, quarter)
            )
        else:
            conn.execute(
                "UPDATE grade_submissions SET status=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND quarter=?",
                (status, subject_id, section_id, quarter)
            )
    else:
        conn.execute(
            "INSERT INTO grade_submissions (subject_id,section_id,quarter,status,approved_by,unlock_reason) VALUES (?,?,?,?,?,?)",
            (subject_id, section_id, quarter, status, approved_by, unlock_reason)
        )

# approve_grades also accepts Submitted → Approved transition


@app.route('/grades/approve', methods=['POST'])
def approve_grades():
    if 'admin_id' not in session and 'teacher_id' not in session:
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    d          = request.get_json(force=True) or {}
    subject_id = d.get('subject_id')
    section_id = d.get('section_id')
    quarter    = d.get('quarter')
    action     = d.get('action')
    reason     = (d.get('reason') or '').strip()

    if action not in ('approve', 'lock', 'unlock', 'revert'):
        return jsonify({'ok': False, 'error': 'Invalid action'}), 400

    if action == 'unlock' and not reason:
        return jsonify({'ok': False, 'error': 'A reason is required to unlock grades.', 'need_reason': True}), 400

    conn = get_db()
    current = get_submission_status(conn, subject_id, section_id, quarter)

    valid = {'approve': current in ('Draft','Submitted'), 'lock': current == 'Approved', 'unlock': current == 'Locked', 'revert': current in ('Submitted','Approved')}
    if not valid[action]:
        conn.close()
        return jsonify({'ok': False, 'error': f'Cannot {action} from status "{current}"'}), 400

    status_map = {'approve': 'Approved', 'lock': 'Locked', 'unlock': 'Draft', 'revert': 'Draft'}
    new_status = status_map[action]
    upsert_submission(conn, subject_id, section_id, quarter, new_status,
                      approved_by=session.get('admin_name', 'Admin'),
                      unlock_reason=reason if action == 'unlock' else None)
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'status': new_status})

@app.route('/grades/submission_status')
def submission_status():
    if 'admin_id' not in session and 'teacher_id' not in session:
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    subject_id = request.args.get('subject_id', type=int)
    section_id = request.args.get('section_id', type=int)
    conn = get_db()
    rows = conn.execute(
        "SELECT quarter,status,approved_at,approved_by,locked_at,unlock_reason FROM grade_submissions WHERE subject_id=? AND section_id=?",
        (subject_id, section_id)
    ).fetchall()
    conn.close()
    return jsonify({r['quarter']: dict(r) for r in rows})

@app.route('/grades/edit_log')
def grade_edit_log_view():
    if 'admin_id' not in session and 'teacher_id' not in session:
        return jsonify({'ok': False, 'error': 'Not authenticated'}), 401
    subject_id = request.args.get('subject_id', type=int)
    section_id = request.args.get('section_id', type=int)
    quarter    = request.args.get('quarter')
    conn = get_db()
    logs = conn.execute(
        "SELECT gel.*, s.first_name||' '||s.last_name AS student_name, sub.subject_name FROM grade_edit_log gel JOIN students s ON gel.student_id=s.id JOIN subjects sub ON gel.subject_id=sub.id WHERE gel.subject_id=? AND gel.section_id=? AND (? IS NULL OR gel.quarter=?) ORDER BY gel.edited_at DESC",
        (subject_id, section_id, quarter, quarter)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in logs])


# ══════════════════════════════════════════════════════════════
# ── TEACHER PORTAL ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard():
    conn = get_db()
    tid  = session['teacher_id']
    teacher = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()

    # Assigned subjects via schedules
    assigned = conn.execute("""
        SELECT DISTINCT sc.subject_id, sub.subject_name, sub.subject_code,
               sc.section_id, sec.section_name, sec.grade_level,
               COALESCE(sc.semester, sub.semester) AS sem
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN sections sec ON sc.section_id=sec.id
        WHERE sc.teacher_id=?
        ORDER BY sec.grade_level, sec.section_name, sub.subject_name
    """, (tid,)).fetchall()

    # Submission statuses
    QUARTERS = ['Prelim','Midterm','Semi-Final','Final']
    status_map = {}
    for row in assigned:
        rows = conn.execute(
            "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=?",
            (row['subject_id'], row['section_id'])
        ).fetchall()
        status_map[(row['subject_id'], row['section_id'])] = {r['quarter']: r['status'] for r in rows}

    summary = []
    for row in assigned:
        sm = status_map.get((row['subject_id'], row['section_id']), {})
        q_statuses = [sm.get(q, 'Draft') for q in QUARTERS]
        summary.append({
            'subject_id':   row['subject_id'],
            'subject_name': row['subject_name'],
            'subject_code': row['subject_code'],
            'section_id':   row['section_id'],
            'section_name': row['section_name'],
            'grade_level':  row['grade_level'],
            'sem':          row['sem'],
            'q_statuses':   dict(zip(QUARTERS, q_statuses)),
        })

    conn.close()
    return render_template('teacher_dashboard.html', teacher=teacher, summary=summary, quarters=QUARTERS)

@app.route('/teacher/grade_sheet/<int:sec_id>/<int:sub_id>')
@teacher_required
def teacher_grade_sheet(sec_id, sub_id):
    conn = get_db()
    tid  = session['teacher_id']

    # Verify this teacher is assigned to this subject+section
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, sec_id, sub_id)
    ).fetchone()
    if not assigned:
        flash('You are not assigned to this subject.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    section  = conn.execute(
        "SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.id=?",
        (sec_id,)
    ).fetchone()
    subject  = conn.execute("SELECT * FROM subjects WHERE id=?", (sub_id,)).fetchone()
    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    QUARTERS = ['Prelim','Midterm','Semi-Final','Final']

    # Load submission statuses per quarter
    sub_rows = conn.execute(
        "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=?",
        (sub_id, sec_id)
    ).fetchall()
    q_statuses = {r['quarter']: r['status'] for r in sub_rows}

    # Load grades
    grades_raw = conn.execute("""
        SELECT g.student_id, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment,
               g.midterm, g.finals
        FROM grades g WHERE g.subject_id=? AND g.section_id=?
    """, (sub_id, sec_id)).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['student_id'], {})[g['quarter']] = g

    student_grades = []
    for st in students:
        qgrades = {}
        for q in QUARTERS:
            row = grade_map.get(st['id'], {}).get(q)
            if row:
                qg = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment'])
                qgrades[q] = {'ww': row['written_works'], 'pt': row['performance_tasks'],
                               'qa': row['quarterly_assessment'], 'midterm': row['midterm'],
                               'finals': row['finals'], 'computed': qg}
            else:
                qgrades[q] = {'ww': None, 'pt': None, 'qa': None, 'midterm': None, 'finals': None, 'computed': None}
        vals = [qgrades[q]['computed'] for q in QUARTERS if qgrades[q]['computed'] is not None]
        avg  = round(sum(vals)/len(vals), 2) if vals else None
        student_grades.append({'student': st, 'quarters': qgrades, 'average': avg,
                                'passing': avg is not None and avg >= PASSING_GRADE})

    sub_semester = subject['semester'] if subject else ''
    # For teacher grade sheet, we need to know which semester tab is active
    # Use the schedule's semester for this section as the active semester
    sched_sem_row = conn.execute(
        "SELECT COALESCE(sc.semester, sub.semester) AS sem FROM schedules sc "
        "JOIN subjects sub ON sc.subject_id=sub.id "
        "WHERE sc.teacher_id=? AND sc.section_id=? AND sc.subject_id=? LIMIT 1",
        (tid, sec_id, sub_id)
    ).fetchone()
    active_sem = sched_sem_row['sem'] if sched_sem_row else sub_semester
    if active_sem not in ('1st Semester', '2nd Semester'):
        active_sem = '1st Semester'
    open_periods = get_open_periods_for_subject(conn, sub_semester, active_sem)
    conn.close()
    return render_template('teacher_grade_sheet.html',
                           section=section, subject=subject,
                           students=student_grades, quarters=QUARTERS,
                           q_statuses=q_statuses, passing_grade=PASSING_GRADE,
                           sec_id=sec_id, sub_id=sub_id,
                           open_periods=open_periods)

# ── Export grades as CSV ──
@app.route('/teacher/grade_sheet/<int:sec_id>/<int:sub_id>/export')
@teacher_required
def teacher_export_grades(sec_id, sub_id):
    conn = get_db()
    tid  = session['teacher_id']

    # Verify assignment (teachers) or allow admin
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, sec_id, sub_id)
    ).fetchone()
    if not assigned:
        conn.close()
        flash('Not authorized.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    section = conn.execute("SELECT section_name, grade_level FROM sections WHERE id=?", (sec_id,)).fetchone()
    subject = conn.execute("SELECT subject_name, subject_code FROM subjects WHERE id=?", (sub_id,)).fetchone()
    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    ALL_PERIODS = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
    sel_period  = request.args.get('period', 'all')
    PERIODS     = ALL_PERIODS if sel_period == 'all' else [p for p in ALL_PERIODS if p == sel_period]
    if not PERIODS:
        PERIODS = ALL_PERIODS

    grades_raw = conn.execute(
        "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment FROM grades WHERE subject_id=? AND section_id=?",
        (sub_id, sec_id)
    ).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['student_id'], {})[g['quarter']] = g
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    headers = ['student_id', 'last_name', 'first_name', 'middle_name']
    for p in PERIODS:
        headers += [f'{p}_WW', f'{p}_PT', f'{p}_QA']
    writer.writerow(headers)

    # Data rows
    for st in students:
        row = [st['student_id'], st['last_name'], st['first_name'], st['middle_name'] or '']
        for p in PERIODS:
            g = grade_map.get(st['id'], {}).get(p)
            row += [g['written_works'] if g and g['written_works'] is not None else '',
                    g['performance_tasks'] if g and g['performance_tasks'] is not None else '',
                    g['quarterly_assessment'] if g and g['quarterly_assessment'] is not None else '']
        writer.writerow(row)

    period_label = sel_period.replace(' ','_').replace('-','') if sel_period != 'all' else 'All'
    filename = f"grades_{section['section_name']}_{subject['subject_code']}_{period_label}.csv".replace(' ','_')
    resp = make_response(output.getvalue())
    resp.headers['Content-Type']        = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

# ── Admin export (same logic, no teacher check) ──
@app.route('/grades/section/<int:sec_id>/export')
@login_required
def admin_export_grades(sec_id):
    sub_id = request.args.get('subject_id', type=int)
    if not sub_id:
        flash('No subject selected.', 'danger')
        return redirect(url_for('grade_sheet', sec_id=sec_id))

    conn = get_db()
    section = conn.execute("SELECT section_name, grade_level FROM sections WHERE id=?", (sec_id,)).fetchone()
    subject = conn.execute("SELECT subject_name, subject_code FROM subjects WHERE id=?", (sub_id,)).fetchone()
    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    ALL_PERIODS = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
    sel_period  = request.args.get('period', 'all')
    PERIODS     = ALL_PERIODS if sel_period == 'all' else [p for p in ALL_PERIODS if p == sel_period]
    if not PERIODS:
        PERIODS = ALL_PERIODS

    grades_raw = conn.execute(
        "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment FROM grades WHERE subject_id=? AND section_id=?",
        (sub_id, sec_id)
    ).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['student_id'], {})[g['quarter']] = g
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ['student_id', 'last_name', 'first_name', 'middle_name']
    for p in PERIODS:
        headers += [f'{p}_WW', f'{p}_PT', f'{p}_QA']
    writer.writerow(headers)

    for st in students:
        row = [st['student_id'], st['last_name'], st['first_name'], st['middle_name'] or '']
        for p in PERIODS:
            g = grade_map.get(st['id'], {}).get(p)
            row += [g['written_works'] if g and g['written_works'] is not None else '',
                    g['performance_tasks'] if g and g['performance_tasks'] is not None else '',
                    g['quarterly_assessment'] if g and g['quarterly_assessment'] is not None else '']
        writer.writerow(row)

    period_label = sel_period.replace(' ','_').replace('-','') if sel_period != 'all' else 'All'
    filename = f"grades_{section['section_name']}_{subject['subject_code']}_{period_label}.csv".replace(' ','_')
    resp = make_response(output.getvalue())
    resp.headers['Content-Type']        = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

# ── Import grades from CSV (teacher) ──
@app.route('/teacher/grade_sheet/<int:sec_id>/<int:sub_id>/import', methods=['POST'])
@teacher_required
def teacher_import_grades(sec_id, sub_id):
    tid = session['teacher_id']
    conn = get_db()

    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, sec_id, sub_id)
    ).fetchone()
    if not assigned:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403

    # Block if any period is not Draft
    locked_periods = conn.execute(
        "SELECT quarter FROM grade_submissions WHERE subject_id=? AND section_id=? AND status != 'Draft'",
        (sub_id, sec_id)
    ).fetchall()
    if locked_periods:
        names = ', '.join(r['quarter'] for r in locked_periods)
        conn.close()
        return jsonify({'ok': False, 'error': f'Cannot import: {names} is already submitted/approved/locked.'}), 400

    file = request.files.get('csv_file')
    if not file:
        conn.close()
        return jsonify({'ok': False, 'error': 'No file uploaded.'}), 400

    try:
        content_str = file.read().decode('utf-8-sig')  # handle BOM
        reader = csv.DictReader(io.StringIO(content_str))
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'Could not read CSV: {e}'}), 400

    PERIODS    = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
    COMPONENTS = ['WW', 'PT', 'QA']
    COMP_FULL  = {'WW': 'written_works', 'PT': 'performance_tasks', 'QA': 'quarterly_assessment'}

    # Build student lookup by student_id
    students = conn.execute(
        "SELECT id, student_id FROM students WHERE section_id=?", (sec_id,)
    ).fetchall()
    student_map = {s['student_id']: s['id'] for s in students}

    updated = skipped = errors = 0
    error_msgs = []

    for i, row in enumerate(reader, start=2):
        sid_str = (row.get('student_id') or '').strip()
        if not sid_str:
            skipped += 1
            continue

        db_sid = student_map.get(sid_str)
        if not db_sid:
            error_msgs.append(f"Row {i}: Student ID '{sid_str}' not found in this section.")
            errors += 1
            continue

        for p in PERIODS:
            for comp in COMPONENTS:
                col = f'{p}_{comp}'
                val_str = (row.get(col) or '').strip()
                if val_str == '':
                    continue
                try:
                    val = float(val_str)
                    if val < 0 or val > 100:
                        raise ValueError
                except ValueError:
                    error_msgs.append(f"Row {i}: Invalid value '{val_str}' for {col}.")
                    errors += 1
                    continue

                db_col = COMP_FULL[comp]
                existing = conn.execute(
                    "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                    (db_sid, sub_id, sec_id, p)
                ).fetchone()
                if existing:
                    conn.execute(
                        f"UPDATE grades SET {db_col}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                        (val, db_sid, sub_id, sec_id, p)
                    )
                else:
                    conn.execute(
                        "INSERT INTO grades (student_id,subject_id,section_id,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?)",
                        (db_sid, sub_id, sec_id, p,
                         val if db_col=='written_works' else None,
                         val if db_col=='performance_tasks' else None,
                         val if db_col=='quarterly_assessment' else None)
                    )
                updated += 1

    conn.commit()
    conn.close()
    return jsonify({
        'ok': True,
        'updated': updated,
        'skipped': skipped,
        'errors':  errors,
        'error_msgs': error_msgs[:10]  # cap at 10
    })

# ── Admin import ──
@app.route('/grades/section/<int:sec_id>/import', methods=['POST'])
@login_required
def admin_import_grades(sec_id):
    sub_id = request.args.get('subject_id', type=int)
    if not sub_id:
        return jsonify({'ok': False, 'error': 'No subject specified.'}), 400

    conn = get_db()
    file = request.files.get('csv_file')
    if not file:
        conn.close()
        return jsonify({'ok': False, 'error': 'No file uploaded.'}), 400

    try:
        content_str = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content_str))
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'Could not read CSV: {e}'}), 400

    PERIODS    = ['Prelim', 'Midterm', 'Semi-Final', 'Final']
    COMPONENTS = ['WW', 'PT', 'QA']
    COMP_FULL  = {'WW': 'written_works', 'PT': 'performance_tasks', 'QA': 'quarterly_assessment'}

    students = conn.execute(
        "SELECT id, student_id FROM students WHERE section_id=?", (sec_id,)
    ).fetchall()
    student_map = {s['student_id']: s['id'] for s in students}

    updated = skipped = errors = 0
    error_msgs = []

    for i, row in enumerate(reader, start=2):
        sid_str = (row.get('student_id') or '').strip()
        if not sid_str:
            skipped += 1
            continue
        db_sid = student_map.get(sid_str)
        if not db_sid:
            error_msgs.append(f"Row {i}: Student ID '{sid_str}' not found.")
            errors += 1
            continue

        for p in PERIODS:
            for comp in COMPONENTS:
                col     = f'{p}_{comp}'
                val_str = (row.get(col) or '').strip()
                if val_str == '':
                    continue
                try:
                    val = float(val_str)
                    if val < 0 or val > 100:
                        raise ValueError
                except ValueError:
                    error_msgs.append(f"Row {i}: Invalid value '{val_str}' for {col}.")
                    errors += 1
                    continue

                db_col   = COMP_FULL[comp]
                existing = conn.execute(
                    "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                    (db_sid, sub_id, sec_id, p)
                ).fetchone()
                if existing:
                    conn.execute(
                        f"UPDATE grades SET {db_col}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=?",
                        (val, db_sid, sub_id, sec_id, p)
                    )
                else:
                    conn.execute(
                        "INSERT INTO grades (student_id,subject_id,section_id,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?)",
                        (db_sid, sub_id, sec_id, p,
                         val if db_col=='written_works' else None,
                         val if db_col=='performance_tasks' else None,
                         val if db_col=='quarterly_assessment' else None)
                    )
                updated += 1

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'updated': updated, 'skipped': skipped, 'errors': errors, 'error_msgs': error_msgs[:10]})

@app.route('/teacher/submit_quarter', methods=['POST'])
@teacher_required
def teacher_submit_quarter():
    d          = request.get_json(force=True) or {}
    subject_id = d.get('subject_id')
    section_id = d.get('section_id')
    quarter    = d.get('quarter')
    tid        = session['teacher_id']

    # Verify assignment
    conn = get_db()
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, section_id, subject_id)
    ).fetchone()
    if not assigned:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403

    current = get_submission_status(conn, subject_id, section_id, quarter)
    if current != 'Draft':
        conn.close()
        return jsonify({'ok': False, 'error': f'Quarter is already {current}'}), 400

    # Upsert to Submitted
    existing = conn.execute(
        "SELECT id FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=?",
        (subject_id, section_id, quarter)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE grade_submissions SET status='Submitted', teacher_id=?, submitted_at=datetime('now'), updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND quarter=?",
            (tid, subject_id, section_id, quarter)
        )
    else:
        conn.execute(
            "INSERT INTO grade_submissions (teacher_id,subject_id,section_id,quarter,status,submitted_at) VALUES (?,?,?,?,'Submitted',datetime('now'))",
            (tid, subject_id, section_id, quarter)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'status': 'Submitted'})

@app.route('/teacher/profile')
@teacher_required
def teacher_portal_profile():
    conn    = get_db()
    tid     = session['teacher_id']
    teacher = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    schedules = conn.execute("""
        SELECT sc.id, sc.day, sc.time_start, sc.time_end, sc.room,
               sc.subject_id, sc.section_id,
               COALESCE(sc.semester, sub.semester) AS sem,
               sub.subject_name, sub.subject_code,
               sec.section_name, sec.grade_level, st.strand_code,
               '' AS teacher_name
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN sections sec ON sc.section_id=sec.id
        LEFT JOIN strands st ON sc.strand_id=st.id
        WHERE sc.teacher_id=?
        ORDER BY CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END, sc.time_start
    """, (tid,)).fetchall()
    conn.close()
    return render_template('teacher_portal_profile.html', teacher=teacher, schedules=schedules)

# ══════════════════════════════════════════════════════════════
# ── STUDENT PORTAL ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    conn    = get_db()
    sid     = session['student_session_id']
    student = conn.execute("""
        SELECT s.*, sec.section_name, sec.id AS sec_id,
               st.strand_code, st.strand_name
        FROM students s
        LEFT JOIN sections sec ON s.section_id=sec.id
        LEFT JOIN strands  st  ON s.strand_id=st.id
        WHERE s.id=?
    """, (sid,)).fetchone()

    subjects  = get_section_subjects(conn, student['sec_id']) if student['sec_id'] else []
    QUARTERS  = ['Prelim','Midterm','Semi-Final','Final']

    # Submission statuses
    sub_statuses = {}
    if student['sec_id']:
        rows = conn.execute(
            "SELECT subject_id, quarter, status FROM grade_submissions WHERE section_id=?",
            (student['sec_id'],)
        ).fetchall()
        for r in rows:
            sub_statuses.setdefault(r['subject_id'], {})[r['quarter']] = r['status']

    grades_raw = conn.execute(
        "SELECT subject_id, quarter, written_works, performance_tasks, quarterly_assessment FROM grades WHERE student_id=?",
        (sid,)
    ).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['subject_id'], {})[g['quarter']] = g

    subject_rows = []
    all_approved = []
    for sub in subjects:
        qgrades = {}
        has_any = False
        for q in QUARTERS:
            row    = grade_map.get(sub['id'], {}).get(q)
            status = sub_statuses.get(sub['id'], {}).get(q, 'Draft')
            qg     = compute_quarterly_grade(row['written_works'], row['performance_tasks'], row['quarterly_assessment']) if row else None
            if qg is not None: has_any = True
            visible = status in ('Approved', 'Locked')
            qgrades[q] = {'grade': qg if visible else None, 'status': status,
                          'has_data': qg is not None, 'visible': visible}
            if visible and qg is not None: all_approved.append(qg)

        has_approved_any = any(qgrades[q]['visible'] and qgrades[q]['grade'] is not None for q in QUARTERS)
        all_pending = has_any and not has_approved_any

        visible_grades = [qgrades[q]['grade'] for q in QUARTERS if qgrades[q]['grade'] is not None]
        sub_avg = round(sum(visible_grades)/len(visible_grades), 2) if visible_grades else None
        subject_rows.append({
            'subject': sub, 'quarters': qgrades,
            'average': sub_avg, 'has_any': has_any,
            'all_pending': all_pending,
            'passing': sub_avg is not None and sub_avg >= PASSING_GRADE
        })

    general_avg = round(sum(all_approved)/len(all_approved), 2) if all_approved else None
    honor       = honor_classification(general_avg)
    QUARTERS    = ['Prelim', 'Midterm', 'Semi-Final', 'Final']

    # Schedule
    schedule = conn.execute("""
        SELECT sc.id, sc.day, sc.time_start, sc.time_end, sc.room,
               sc.subject_id, sc.section_id,
               sub.subject_name, sub.subject_code,
               t.first_name||' '||t.last_name AS teacher_name,
               COALESCE(sc.semester, sub.semester) AS sem
        FROM schedules sc
        JOIN subjects  sub ON sc.subject_id=sub.id
        JOIN teachers  t   ON sc.teacher_id=t.id
        WHERE sc.section_id=?
        ORDER BY CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END, sc.time_start
    """, (student['sec_id'] or 0,)).fetchall()

    conn.close()
    return render_template('student_dashboard.html',
                           student=student, subject_rows=subject_rows,
                           quarters=QUARTERS, general_avg=general_avg,
                           honor=honor, passing_grade=PASSING_GRADE,
                           schedule=schedule)

@app.route('/student/profile')
@student_required
def student_portal_profile():
    conn    = get_db()
    sid     = session['student_session_id']
    student = conn.execute("""
        SELECT s.*, sec.section_name, sec.grade_level AS sec_grade,
               st.strand_code, st.strand_name
        FROM students s
        LEFT JOIN sections sec ON s.section_id=sec.id
        LEFT JOIN strands  st  ON s.strand_id=st.id
        WHERE s.id=?
    """, (sid,)).fetchone()
    conn.close()
    return render_template('student_portal_profile.html', student=student)

# ── Update grade_submissions approve route to handle Submitted status ──

# ══════════════════════════════════════════════════════════════
# ── TEACHER SUBJECTS MODULE ──────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.route('/teacher/subjects')
@teacher_required
def teacher_subjects():
    conn    = get_db()
    tid     = session['teacher_id']
    COLORS  = ['var(--blue-course)', 'var(--teal-course)', 'var(--yellow-course)', 'var(--pink-course)', 'var(--dark-teal-course)', 'var(--medium-blue-course)', 'var(--mint-green-course)', 'var(--green-course)', 'var(--orange-course)', 'var(--slate-blue-course)', 'var(--dark-green-course)', 'var(--orange-red-course)']
    teacher = conn.execute("SELECT first_name, last_name FROM teachers WHERE id=?", (tid,)).fetchone()
    initials = (teacher['first_name'][0] + teacher['last_name'][0]).upper() if teacher else '?'

    # All schedule rows for this teacher
    rows = conn.execute("""
        SELECT sc.subject_id, sc.section_id,
               sub.subject_name, sub.subject_code,
               sub.semester AS sub_semester,
               sub.grade_level,
               sec.section_name,
               (SELECT COUNT(*) FROM students s WHERE s.section_id=sec.id) AS student_count,
               sc.day, sc.time_start, sc.time_end, sc.room
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN sections sec ON sc.section_id=sec.id
        WHERE sc.teacher_id=?
        ORDER BY sub.subject_name, sec.section_name,
            CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END
    """, (tid,)).fetchall()
    conn.close()

    from collections import OrderedDict
    subjects_dict = OrderedDict()  # subject_id -> card data

    for r in rows:
        sub_id = r['subject_id']
        if sub_id not in subjects_dict:
            subjects_dict[sub_id] = {
                'subject_id':   sub_id,
                'subject_name': r['subject_name'],
                'subject_code': r['subject_code'],
                'semester':     r['sub_semester'] or '',
                'grade_level':  r['grade_level'] or '',
                'initials':     initials,
                'sections':     [],
                'schedules':    [],
                'seen_sections': set(),
            }
        card = subjects_dict[sub_id]
        # Add section once
        if r['section_id'] not in card['seen_sections']:
            card['seen_sections'].add(r['section_id'])
            card['sections'].append({
                'section_id':   r['section_id'],
                'section_name': r['section_name'],
                'student_count': r['student_count'],
            })
        # Add each schedule slot
        card['schedules'].append({
            'section_id': r['section_id'],
            'section_name': r['section_name'],
            'day':        r['day'],
            'time_start': r['time_start'],
            'time_end':   r['time_end'],
            'room':       r['room'],
        })

    # One card per subject+section combo, color by section_id
    color_map = {}
    color_idx = 0
    cards = []
    for sub_id, card in subjects_dict.items():
        del card['seen_sections']
        for sec in card['sections']:
            sec_id = sec['section_id']
            if sec_id not in color_map:
                color_map[sec_id] = COLORS[color_idx % len(COLORS)]
                color_idx += 1
            # Schedules for this specific section
            sec_scheds = [s for s in card['schedules'] if s['section_id'] == sec_id]
            cards.append({
                'subject_id':   sub_id,
                'subject_name': card['subject_name'],
                'subject_code': card['subject_code'],
                'semester':     card['semester'],
                'initials':     card['initials'],
                'color':        color_map[sec_id],
                'section_id':   sec_id,
                'section_name': sec['section_name'],
                'student_count': sec['student_count'],
                'schedules':    sec_scheds,
            })

    return render_template('teacher_subjects.html', cards=cards)

@app.route('/teacher/subjects/<int:sub_id>/section/<int:sec_id>')
@teacher_required
def teacher_subject_detail(sub_id, sec_id):
    conn = get_db()
    tid  = session['teacher_id']

    # Verify teacher is assigned to this subject+section
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND subject_id=? AND section_id=?",
        (tid, sub_id, sec_id)
    ).fetchone()
    if not assigned:
        conn.close()
        flash('Not authorized.', 'danger')
        return redirect(url_for('teacher_subjects'))

    subject = conn.execute("SELECT * FROM subjects WHERE id=?", (sub_id,)).fetchone()
    section = conn.execute("""
        SELECT sec.*, st.strand_code,
               (SELECT COUNT(*) FROM students s WHERE s.section_id=sec.id) AS student_count
        FROM sections sec LEFT JOIN strands st ON sec.strand_id=st.id
        WHERE sec.id=?
    """, (sec_id,)).fetchone()

    students = conn.execute("""
        SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name,
               s.gender, s.email, s.contact_no
        FROM students s WHERE s.section_id=?
        ORDER BY s.last_name, s.first_name
    """, (sec_id,)).fetchall()

    schedule = conn.execute("""
        SELECT sc.day, sc.time_start, sc.time_end, sc.room
        FROM schedules sc
        WHERE sc.teacher_id=? AND sc.subject_id=? AND sc.section_id=?
        ORDER BY CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END
    """, (tid, sub_id, sec_id)).fetchall()

    conn.close()
    return render_template('teacher_subject_detail.html',
                           subject=subject, section=section,
                           students=students, schedule=schedule)


# ══════════════════════════════════════════════════════════════
# ── STUDENT SUBJECTS MODULE ──────────────────────────────────
# ══════════════════════════════════════════════════════════════

@app.route('/student/subjects')
@student_required
def student_subjects():
    conn = get_db()
    sid  = session['student_session_id']
    student = conn.execute("""
        SELECT s.*, sec.id AS sec_id, sec.section_name
        FROM students s LEFT JOIN sections sec ON s.section_id=sec.id
        WHERE s.id=?
    """, (sid,)).fetchone()

    if not student['sec_id']:
        conn.close()
        return render_template('student_subjects.html', subjects=[], student=student)

    COLORS = ['var(--blue-course)', 'var(--teal-course)', 'var(--yellow-course)', 'var(--pink-course)', 'var(--dark-teal-course)', 'var(--medium-blue-course)', 'var(--mint-green-course)', 'var(--green-course)', 'var(--orange-course)', 'var(--slate-blue-course)', 'var(--dark-green-course)', 'var(--orange-red-course)']

    # One row per distinct subject (no schedule duplication)
    # One row per subject with deduplicated schedule slots
    all_rows = conn.execute("""
        SELECT sc.subject_id, sub.subject_name, sub.subject_code,
               sub.semester,
               t.first_name, t.last_name, t.email AS teacher_email,
               sc.day, sc.time_start, sc.time_end, sc.room
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN teachers t   ON sc.teacher_id=t.id
        WHERE sc.section_id=?
        ORDER BY sub.semester, sub.subject_name,
            CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END
    """, (student['sec_id'],)).fetchall()
    conn.close()

    from collections import OrderedDict
    subjects_dict = OrderedDict()
    for r in all_rows:
        sub_id = r['subject_id']
        if sub_id not in subjects_dict:
            subjects_dict[sub_id] = {
                'id':            sub_id,
                'subject_name':  r['subject_name'],
                'subject_code':  r['subject_code'],
                'semester':      r['semester'] or '',
                'first_name':    r['first_name'],
                'last_name':     r['last_name'],
                'teacher_email': r['teacher_email'],
                'schedules':     [],
                '_seen_slots':   set(),
            }
        # Deduplicate schedule slots by day+time (prevents Whole Year duplicates)
        slot_key = (r['day'], r['time_start'], r['time_end'])
        if slot_key not in subjects_dict[sub_id]['_seen_slots']:
            subjects_dict[sub_id]['_seen_slots'].add(slot_key)
            subjects_dict[sub_id]['schedules'].append({
                'day':        r['day'],
                'time_start': r['time_start'],
                'time_end':   r['time_end'],
                'room':       r['room'],
            })

    for sub in subjects_dict.values():
        del sub['_seen_slots']

    cards = []
    for i, (sub_id, sub) in enumerate(subjects_dict.items()):
        initials = (sub['first_name'][0] + sub['last_name'][0]).upper() if sub['first_name'] else '?'
        cards.append({'sub': sub, 'color': COLORS[i % len(COLORS)], 'initials': initials})
    return render_template('student_subjects.html', cards=cards, student=student)


@app.route('/student/subjects/<int:sub_id>')
@student_required
def student_subject_detail(sub_id):
    conn = get_db()
    sid  = session['student_session_id']
    student = conn.execute("""
        SELECT s.*, sec.id AS sec_id, sec.section_name
        FROM students s LEFT JOIN sections sec ON s.section_id=sec.id
        WHERE s.id=?
    """, (sid,)).fetchone()

    subject = conn.execute("SELECT * FROM subjects WHERE id=?", (sub_id,)).fetchone()

    # Teacher info
    teacher = conn.execute("""
        SELECT t.*, sc.day, sc.time_start, sc.time_end, sc.room,
               COALESCE(sc.semester, sub.semester) AS sem
        FROM schedules sc
        JOIN teachers t  ON sc.teacher_id=t.id
        JOIN subjects sub ON sc.subject_id=sub.id
        WHERE sc.section_id=? AND sc.subject_id=?
        ORDER BY CASE sc.day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END
    """, (student['sec_id'], sub_id)).fetchall()

    conn.close()

    if not teacher:
        flash('Subject not found in your schedule.', 'danger')
        return redirect(url_for('student_subjects'))

    return render_template('student_subject_detail.html',
                           subject=subject, teacher_rows=teacher,
                           student=student)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)