from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, make_response
import sqlite3
import hashlib
import csv
import io
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = 'sis_secret_key_2024_secure'

@app.template_filter('clean_mn')
def clean_mn_filter(val):
    return clean_middle_name(val)
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
            semester TEXT,
            shs_type TEXT,
            default_teacher_id INTEGER,
            FOREIGN KEY (default_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS subject_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            UNIQUE(subject_id, teacher_id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS subject_section_offerings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            section_id INTEGER,  -- Allow NULL for "all sections" marker
            semester TEXT DEFAULT '',
            UNIQUE(subject_id, section_id, semester),
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE
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
            semester            TEXT NOT NULL DEFAULT '',
            quarter             TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),
            written_works       REAL,
            performance_tasks   REAL,
            quarterly_assessment REAL,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now')),
            UNIQUE(student_id, subject_id, section_id, semester, quarter),
            FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE,
            FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
            FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS grade_submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id  INTEGER,
            subject_id  INTEGER NOT NULL,
            section_id  INTEGER NOT NULL,
            semester    TEXT NOT NULL DEFAULT '',
            quarter     TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),
            status      TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Submitted','Approved','Locked')),
            submitted_at TEXT,
            approved_at TEXT,
            approved_by TEXT,
            locked_at   TEXT,
            unlock_reason TEXT,
            updated_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(subject_id, section_id, semester, quarter),
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
        conn.execute("ALTER TABLE subjects ADD COLUMN default_teacher_id INTEGER")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subjects ADD COLUMN shs_type TEXT")
    except Exception:
        pass
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subject_teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                UNIQUE(subject_id, teacher_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        """)
    except Exception:
        pass
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subject_section_offerings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                section_id INTEGER NOT NULL,
                UNIQUE(subject_id, section_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE
            )
        """)
    except Exception:
        pass
    # Seed legacy single default teacher into the new multi-teacher table (if any)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO subject_teachers (subject_id, teacher_id)
            SELECT id, default_teacher_id
            FROM subjects
            WHERE default_teacher_id IS NOT NULL
        """)
        conn.commit()
    except Exception:
        pass

    # Migrate existing JHS "assigned teachers" into subject_teachers so Subjects page
    # and scheduling suggestions are pre-populated.
    # Source of truth remains per-section assignments/schedules; this just builds the eligible set per subject.
    try:
        jhs_levels = ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10')
        conn.execute(f"""
            INSERT OR IGNORE INTO subject_teachers (subject_id, teacher_id)
            SELECT DISTINCT a.subject_id, a.teacher_id
            FROM assignments a
            JOIN sections sec ON sec.id = a.section_id
            WHERE sec.grade_level IN ({','.join('?' for _ in jhs_levels)})
        """, jhs_levels)
        conn.execute(f"""
            INSERT OR IGNORE INTO subject_teachers (subject_id, teacher_id)
            SELECT DISTINCT sc.subject_id, sc.teacher_id
            FROM schedules sc
            JOIN sections sec ON sec.id = sc.section_id
            WHERE sec.grade_level IN ({','.join('?' for _ in jhs_levels)})
        """, jhs_levels)
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE students ADD COLUMN password TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE grade_submissions ADD COLUMN submitted_at TEXT")
    except Exception:
        pass
    # Add semester column to grade_submissions
    try:
        conn.execute("ALTER TABLE grade_submissions ADD COLUMN semester TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    # Rebuild grade_submissions UNIQUE constraint to include semester
    try:
        tbl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='grade_submissions'").fetchone()
        if tbl and 'semester, quarter' not in (tbl['sql'] or ''):
            conn.executescript(
                "ALTER TABLE grade_submissions RENAME TO gs_sem_backup;"
                "CREATE TABLE grade_submissions ("
                "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "    teacher_id INTEGER,"
                "    subject_id INTEGER NOT NULL,"
                "    section_id INTEGER NOT NULL,"
                "    semester TEXT NOT NULL DEFAULT '',"
                "    quarter TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),"
                "    status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Submitted','Approved','Locked')),"
                "    submitted_at TEXT, approved_at TEXT, approved_by TEXT,"
                "    locked_at TEXT, unlock_reason TEXT,"
                "    updated_at TEXT DEFAULT (datetime('now')),"
                "    UNIQUE(subject_id, section_id, semester, quarter),"
                "    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,"
                "    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE"
                ");"
                "INSERT OR IGNORE INTO grade_submissions "
                "    (teacher_id,subject_id,section_id,semester,quarter,status,"
                "     submitted_at,approved_at,approved_by,locked_at,unlock_reason,updated_at) "
                "SELECT teacher_id,subject_id,section_id,COALESCE(semester,''),quarter,status,"
                "       submitted_at,approved_at,approved_by,locked_at,unlock_reason,updated_at "
                "FROM gs_sem_backup;"
                "DROP TABLE gs_sem_backup;"
            )
            conn.commit()
    except Exception:
        pass
    # Migrate grade_submissions semester='' — assign from subject semester
    try:
        empty_sub_rows = conn.execute(
            "SELECT DISTINCT gs.subject_id, gs.section_id FROM grade_submissions gs "
            "JOIN subjects sub ON gs.subject_id=sub.id "
            "WHERE gs.semester='' AND sub.semester IN ('1st Term','2nd Term','3rd Term','1st Semester','2nd Semester')"
        ).fetchall()
        for row in empty_sub_rows:
            sub = conn.execute("SELECT semester FROM subjects WHERE id=?", (row['subject_id'],)).fetchone()
            if sub and sub['semester'] in ('1st Term', '2nd Term', '3rd Term', '1st Semester', '2nd Semester'):
                conn.execute(
                    "UPDATE grade_submissions SET semester=? WHERE subject_id=? AND section_id=? AND semester=''",
                    (sub['semester'], row['subject_id'], row['section_id'])
                )
        conn.commit()
    except Exception:
        pass
    # Add semester column to grades table if missing
    try:
        conn.execute("ALTER TABLE grades ADD COLUMN semester TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    # Fix bare number grade_levels stored in students
    try:
        for num in ('7','8','9','10','11','12'):
            conn.execute("UPDATE students SET grade_level=? WHERE grade_level=?",
                         ('Grade ' + num, num))
        conn.commit()
    except Exception:
        pass
    # Create attendance tables if missing
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS attendance_events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, event_type TEXT NOT NULL DEFAULT 'school', event_date TEXT NOT NULL, time_start TEXT, time_end TEXT, late_allowance_minutes INTEGER DEFAULT 0, description TEXT, section_id INTEGER, subject_id INTEGER, teacher_id INTEGER, authorized_type TEXT DEFAULT 'teacher', authorized_id INTEGER, created_by TEXT, created_at TEXT DEFAULT (datetime('now')), FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE, FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE, FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE)")
        # Migrations for existing attendance_events table
        for _col, _def in [('created_by_student','INTEGER'),('is_shared','INTEGER DEFAULT 0')]:
            try:
                conn.execute(f"ALTER TABLE attendance_categories ADD COLUMN {_col} {_def}")
            except Exception:
                pass
        for _col, _def in [('time_start','TEXT'),('time_end','TEXT'),
                           ('late_allowance_minutes','INTEGER DEFAULT 0'),
                           ('authorized_type',"TEXT DEFAULT 'teacher'"),('authorized_id','INTEGER'),
                           ('is_compulsory',"INTEGER DEFAULT 1"),
                           ('recorded_scope',"TEXT DEFAULT 'all'"),
                           ('attendee_positions','TEXT'),
                           ('attendee_org_ids','TEXT'),
                           ('category_id','INTEGER REFERENCES attendance_categories(id) ON DELETE SET NULL')]:
            try:
                conn.execute(f"ALTER TABLE attendance_events ADD COLUMN {_col} {_def}")
            except Exception:
                pass
        conn.execute("CREATE TABLE IF NOT EXISTS attendance_authorized (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_type TEXT NOT NULL CHECK(person_type IN ('teacher','student')), person_id INTEGER NOT NULL, UNIQUE(event_id,person_type,person_id), FOREIGN KEY (event_id) REFERENCES attendance_events(id) ON DELETE CASCADE)")
        conn.execute("CREATE TABLE IF NOT EXISTS attendance_categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT, color TEXT DEFAULT '#6b7280', icon TEXT DEFAULT '🎯', created_by_student INTEGER, is_shared INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))")
        conn.execute("CREATE TABLE IF NOT EXISTS organizations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, short_name TEXT, description TEXT, org_type TEXT DEFAULT 'organization', color TEXT DEFAULT '#3b82f6', created_at TEXT DEFAULT (datetime('now')))")
        conn.execute("CREATE TABLE IF NOT EXISTS org_positions (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, position_name TEXT NOT NULL, rank_order INTEGER DEFAULT 0, UNIQUE(org_id, position_name), FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE)")
        conn.execute("CREATE TABLE IF NOT EXISTS org_members (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, position_id INTEGER, student_id INTEGER NOT NULL, school_year TEXT, is_active INTEGER DEFAULT 1, UNIQUE(org_id, student_id, school_year), FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE, FOREIGN KEY (position_id) REFERENCES org_positions(id) ON DELETE SET NULL, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)")
        for _col, _def in [
            ('category_id', 'INTEGER REFERENCES attendance_categories(id) ON DELETE SET NULL'),
            ('is_compulsory', 'INTEGER DEFAULT 1'),
        ]:
            try:
                conn.execute(f"ALTER TABLE attendance_events ADD COLUMN {_col} {_def}")
            except Exception: pass
        conn.execute("CREATE TABLE IF NOT EXISTS attendance_records (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, student_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Present' CHECK(status IN ('Present','Absent','Excused','Late')), note TEXT, recorded_at TEXT DEFAULT (datetime('now')), UNIQUE(event_id, student_id), FOREIGN KEY (event_id) REFERENCES attendance_events(id) ON DELETE CASCADE, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)")
        conn.commit()
    except Exception:
        pass
    # Fix bare number grade_levels stored in sections
    try:
        for num in ('7','8','9','10','11','12'):
            conn.execute("UPDATE sections SET grade_level=? WHERE grade_level=?",
                         ('Grade ' + num, num))
        conn.commit()
    except Exception:
        pass

    # Migrate grades with semester='' for NON-Whole-Year subjects only
    # WY subjects are skipped — their semester is determined by which teacher encoded them
    # and must be re-encoded by the teacher after the semester fix
    try:
        empty_grades = conn.execute(
            "SELECT DISTINCT g.student_id, g.subject_id, g.section_id, g.quarter "
            "FROM grades g "
            "JOIN subjects sub ON g.subject_id = sub.id "
            "WHERE g.semester='' AND sub.semester IN ('1st Term','2nd Term','3rd Term','1st Semester','2nd Semester')"
        ).fetchall()
        for row in empty_grades:
            sub = conn.execute("SELECT semester FROM subjects WHERE id=?", (row['subject_id'],)).fetchone()
            correct_sem = sub['semester']
            conn.execute(
                "UPDATE grades SET semester=? "
                "WHERE student_id=? AND subject_id=? AND section_id=? AND quarter=? AND semester=''",
                (correct_sem, row['student_id'], row['subject_id'], row['section_id'], row['quarter'])
            )
        if empty_grades:
            conn.commit()
    except Exception:
        pass
    # Recreate grades table with UNIQUE(student_id, subject_id, section_id, semester, quarter)
    try:
        tbl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='grades'").fetchone()
        if tbl and 'semester, quarter' not in (tbl['sql'] or ''):
            conn.executescript(
                "ALTER TABLE grades RENAME TO grades_old;"
                "CREATE TABLE grades ("
                "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "    student_id INTEGER NOT NULL,"
                "    subject_id INTEGER NOT NULL,"
                "    section_id INTEGER NOT NULL,"
                "    semester TEXT NOT NULL DEFAULT '',"
                "    quarter TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),"
                "    written_works REAL, performance_tasks REAL, quarterly_assessment REAL,"
                "    created_at TEXT DEFAULT (datetime('now')),"
                "    updated_at TEXT DEFAULT (datetime('now')),"
                "    UNIQUE(student_id, subject_id, section_id, semester, quarter),"
                "    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,"
                "    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,"
                "    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE"
                ");"
                "INSERT OR IGNORE INTO grades"
                "    (student_id,subject_id,section_id,semester,quarter,"
                "     written_works,performance_tasks,quarterly_assessment,created_at,updated_at)"
                "    SELECT student_id,subject_id,section_id,COALESCE(semester,''),quarter,"
                "           written_works,performance_tasks,quarterly_assessment,created_at,updated_at"
                "    FROM grades_old;"
                "DROP TABLE grades_old;"
            )
    except Exception:
        pass

    # Fix grade_submissions CHECK constraint to include 'Submitted' status
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
    # Rename Q1-Q4 and legacy Prelim/Midterm/Semi-Final/Final to 3-term names
    # SQLite CHECK constraint blocks direct UPDATE, so we recreate the tables if needed
    try:
        grades_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='grades'").fetchone()
        has_old_q = conn.execute("SELECT COUNT(*) FROM grades WHERE quarter IN ('Q1','Q2','Q3','Q4')").fetchone()[0]
        has_legacy = grades_sql and "CHECK(quarter IN ('Prelim','Midterm','Semi-Final','Final'))" in (grades_sql['sql'] or '')

        if has_old_q or has_legacy:
            conn.executescript("""
                ALTER TABLE grades RENAME TO grades_old;
                CREATE TABLE grades (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          INTEGER NOT NULL,
                    subject_id          INTEGER NOT NULL,
                    section_id          INTEGER NOT NULL,
                    semester            TEXT NOT NULL DEFAULT '',
                    quarter             TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),
                    written_works       REAL,
                    performance_tasks   REAL,
                    quarterly_assessment REAL,
                    created_at          TEXT DEFAULT (datetime('now')),
                    updated_at          TEXT DEFAULT (datetime('now')),
                    UNIQUE(student_id, subject_id, section_id, semester, quarter),
                    FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE,
                    FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
                    FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
                );
                INSERT INTO grades (id,student_id,subject_id,section_id,semester,quarter,
                                    written_works,performance_tasks,quarterly_assessment,created_at,updated_at)
                    SELECT id,student_id,subject_id,section_id,semester,
                           CASE quarter
                             WHEN 'Q1' THEN '1st Term'
                             WHEN 'Q2' THEN '2nd Term'
                             WHEN 'Q3' THEN '3rd Term'
                             WHEN 'Q4' THEN '3rd Term'
                             WHEN 'Prelim' THEN '1st Term'
                             WHEN 'Midterm' THEN '2nd Term'
                             WHEN 'Semi-Final' THEN '3rd Term'
                             WHEN 'Final' THEN '3rd Term'
                             ELSE quarter
                           END, written_works,performance_tasks,quarterly_assessment,created_at,updated_at
                    FROM grades_old;
                DROP TABLE grades_old;
            """)

        # Map any residual old names to new names
        for _old, _new in [('Prelim','1st Term'), ('Midterm','2nd Term'), ('Semi-Final','3rd Term'), ('Final','3rd Term')]:
            conn.execute("UPDATE grades SET quarter=? WHERE quarter=?", (_new, _old))

    except Exception as _e:
        pass  # already migrated or no old data

    try:
        gs_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='grade_submissions'").fetchone()
        has_old_sub = conn.execute("SELECT COUNT(*) FROM grade_submissions WHERE quarter IN ('Q1','Q2','Q3','Q4')").fetchone()[0]
        has_legacy_sub = gs_sql and "CHECK(quarter IN ('Prelim','Midterm','Semi-Final','Final'))" in (gs_sql['sql'] or '')

        if has_old_sub or has_legacy_sub:
            conn.executescript("""
                ALTER TABLE grade_submissions RENAME TO gs_old;
                CREATE TABLE grade_submissions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id  INTEGER,
                    subject_id  INTEGER NOT NULL,
                    section_id  INTEGER NOT NULL,
                    semester    TEXT NOT NULL DEFAULT '',
                    quarter     TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),
                    status      TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Submitted','Approved','Locked')),
                    submitted_at TEXT,
                    approved_at TEXT,
                    approved_by TEXT,
                    locked_at   TEXT,
                    unlock_reason TEXT,
                    updated_at  TEXT DEFAULT (datetime('now')),
                    UNIQUE(subject_id, section_id, semester, quarter),
                    FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
                    FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
                );
                INSERT INTO grade_submissions (id,teacher_id,subject_id,section_id,semester,quarter,status,submitted_at,approved_at,approved_by,locked_at,unlock_reason,updated_at)
                    SELECT id,teacher_id,subject_id,section_id,semester,
                           CASE quarter
                             WHEN 'Q1' THEN '1st Term'
                             WHEN 'Q2' THEN '2nd Term'
                             WHEN 'Q3' THEN '3rd Term'
                             WHEN 'Q4' THEN '3rd Term'
                             WHEN 'Prelim' THEN '1st Term'
                             WHEN 'Midterm' THEN '2nd Term'
                             WHEN 'Semi-Final' THEN '3rd Term'
                             WHEN 'Final' THEN '3rd Term'
                             ELSE quarter
                           END, status, submitted_at, approved_at, approved_by, locked_at, unlock_reason, updated_at
                    FROM gs_old;
                DROP TABLE gs_old;
            """)

        for _old, _new in [('Prelim','1st Term'), ('Midterm','2nd Term'), ('Semi-Final','3rd Term'), ('Final','3rd Term')]:
            conn.execute("UPDATE grade_submissions SET quarter=? WHERE quarter=?", (_new, _old))

    except Exception as _e:
        pass

    try:
        for _old, _new in [('Q1','1st Term'),('Q2','2nd Term'),('Q3','3rd Term'),('Q4','3rd Term')]:
            conn.execute("UPDATE grade_edit_log SET quarter=? WHERE quarter=?", (_new, _old))
    except Exception as _e:
        pass

    # Migrate old 4-period grading names to 3-term names in existing data
    try:
        period_map = {
            'Prelim': '1st Term',
            'Midterm': '2nd Term',
            'Semi-Final': '3rd Term',
            'Final': '3rd Term'
        }
        for table in ('grades', 'grade_submissions', 'grade_edit_log'):
            for old, new in period_map.items():
                conn.execute(f"UPDATE {table} SET quarter=? WHERE quarter=?", (new, old))

        # Migrate grading period settings and collapse duplicates after mapping
        for old, new in period_map.items():
            for row in conn.execute("SELECT id, semester FROM grading_period_settings WHERE period=?", (old,)).fetchall():
                existing = conn.execute("SELECT id FROM grading_period_settings WHERE period=? AND semester=?", (new, row['semester'])).fetchone()
                if existing:
                    conn.execute("DELETE FROM grading_period_settings WHERE id=?", (row['id'],))
                else:
                    conn.execute("UPDATE grading_period_settings SET period=? WHERE id=?", (new, row['id']))

        for sem in ('1st Term', '2nd Term', '3rd Term', 'Whole Year', '1st Semester', '2nd Semester'):
            for period in ('1st Term', '2nd Term', '3rd Term'):
                rows = conn.execute(
                    "SELECT id FROM grading_period_settings WHERE semester=? AND period=? ORDER BY is_open DESC, id",
                    (sem, period)
                ).fetchall()
                if len(rows) > 1:
                    keep = rows[0]['id']
                    for extra in rows[1:]:
                        conn.execute("DELETE FROM grading_period_settings WHERE id=?", (extra['id'],))
    except Exception:
        pass

    # Add semester column to grading_period_settings if missing
    try:
        conn.execute("ALTER TABLE grading_period_settings ADD COLUMN semester TEXT DEFAULT '1st Term'")
    except Exception:
        pass
    # Seed grading period settings for SHS semesters and JHS terms
    # Always ensure grading_period_settings has UNIQUE(period, semester)
    # Check by trying to insert a duplicate — if it fails with old constraint, recreate
    try:
        has_old = conn.execute(
            "SELECT COUNT(*) FROM grading_period_settings WHERE period='1st Term'"
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
            "    semester   TEXT NOT NULL DEFAULT 'Whole Year',"
            "    is_open    INTEGER NOT NULL DEFAULT 0,"
            "    opened_at  TEXT,"
            "    opened_by  TEXT,"
            "    UNIQUE(period, semester)"
            ");"
            "DROP TABLE grading_period_settings;"
            "ALTER TABLE grading_period_settings_new RENAME TO grading_period_settings;"
        )

    # Periods for each term scope (plus legacy semester scopes).
    period_semesters = [
        ('1st Term', '1st Term', 1),
        ('2nd Term', '2nd Term', 0),
        ('3rd Term', '3rd Term', 0),
        ('1st Term', 'Whole Year', 1),
        ('2nd Term', 'Whole Year', 0),
        ('3rd Term', 'Whole Year', 0),
        # legacy
        ('1st Term', '1st Semester', 1),
        ('2nd Term', '1st Semester', 0),
        ('3rd Term', '2nd Semester', 0),
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
    # Migrate org_members: UNIQUE(org_id,student_id,school_year) -> UNIQUE(org_id,position_id,student_id)
    try:
        idx_info = conn.execute("PRAGMA index_list(org_members)").fetchall()
        needs_mig = False
        for idx in idx_info:
            cols = {r["name"] for r in conn.execute("PRAGMA index_info(" + idx["name"] + ")")}
            if cols == {"org_id", "student_id", "school_year"}:
                needs_mig = True; break
        if needs_mig:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("CREATE TABLE IF NOT EXISTS org_members_new (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, position_id INTEGER, student_id INTEGER NOT NULL, school_year TEXT, is_active INTEGER DEFAULT 1, UNIQUE(org_id, position_id, student_id), FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE, FOREIGN KEY (position_id) REFERENCES org_positions(id) ON DELETE SET NULL, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)")
            conn.execute("INSERT OR IGNORE INTO org_members_new SELECT id,org_id,position_id,student_id,school_year,is_active FROM org_members")
            conn.execute("DROP TABLE org_members")
            conn.execute("ALTER TABLE org_members_new RENAME TO org_members")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
    except Exception:
        pass

    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO admins (username,password,full_name) VALUES (?,?,?)",
                    ('admin', hash_password('admin123'), 'System Administrator'))
    conn.commit()
    conn.close()

    # Drop unused midterm and finals columns from grades table (3-term system)
    try:
        # Check if columns exist
        columns = [row['name'] for row in conn.execute("PRAGMA table_info(grades)").fetchall()]
        if 'midterm' in columns or 'finals' in columns:
            conn.executescript("""
                ALTER TABLE grades RENAME TO grades_old;
                CREATE TABLE grades (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id          INTEGER NOT NULL,
                    subject_id          INTEGER NOT NULL,
                    section_id          INTEGER NOT NULL,
                    semester            TEXT NOT NULL DEFAULT '',
                    quarter             TEXT NOT NULL CHECK(quarter IN ('1st Term','2nd Term','3rd Term')),
                    written_works       REAL,
                    performance_tasks   REAL,
                    quarterly_assessment REAL,
                    created_at          TEXT DEFAULT (datetime('now')),
                    updated_at          TEXT DEFAULT (datetime('now')),
                    UNIQUE(student_id, subject_id, section_id, semester, quarter),
                    FOREIGN KEY (student_id)  REFERENCES students(id)  ON DELETE CASCADE,
                    FOREIGN KEY (subject_id)  REFERENCES subjects(id)  ON DELETE CASCADE,
                    FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
                );
                INSERT INTO grades (id,student_id,subject_id,section_id,semester,quarter,
                                   written_works,performance_tasks,quarterly_assessment,created_at,updated_at)
                    SELECT id,student_id,subject_id,section_id,semester,quarter,
                           written_works,performance_tasks,quarterly_assessment,created_at,updated_at
                    FROM grades_old;
                DROP TABLE grades_old;
            """)
    except Exception:
        pass

def any_role_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ('admin_id' in session or 'teacher_id' in session or 'student_session_id' in session):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


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
            # Check if this student is SSG Secretary General
            ssg_org = conn.execute(
                "SELECT o.id FROM organizations o WHERE o.org_type='government'"
            ).fetchone()
            is_secretary_general = False
            if ssg_org:
                is_secretary_general = bool(conn.execute(
                    "SELECT 1 FROM org_members om JOIN org_positions op ON om.position_id=op.id"
                    " WHERE om.org_id=? AND om.student_id=? AND op.position_name='Secretary General' AND om.is_active=1",
                    (ssg_org['id'], student['id'])
                ).fetchone())
            conn.close()
            session['student_session_id'] = student['id']
            session['student_name']       = student['first_name'] + ' ' + student['last_name']
            session['role']               = 'student'
            session['is_secretary_general'] = is_secretary_general
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

    # Per-teacher workload: count distinct sections per term (scope-aware).
    workload_rows = conn.execute("""
        SELECT DISTINCT sc.teacher_id,
               sc.section_id,
               COALESCE(NULLIF(sc.semester,''), sub.semester) AS scope
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id = sub.id
    """).fetchall()

    per_teacher_term_sections = {}
    for r in workload_rows:
        tid = r['teacher_id']
        per_teacher_term_sections.setdefault(tid, {t: set() for t in ALL_TERMS})
        scope = (r['scope'] or '').strip()
        for t in SEM_TERMS.get(scope, ALL_TERMS):
            if t in per_teacher_term_sections[tid]:
                per_teacher_term_sections[tid][t].add(str(r['section_id']))

    workload_map = {}
    for tid, term_sets in per_teacher_term_sections.items():
        workload_map[tid] = {t: len(sids) for t, sids in term_sets.items()}

    conn.close()
    return render_template('teachers.html',
                           teachers=tlist,
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
    try:
        conn.execute("UPDATE subjects SET default_teacher_id=NULL WHERE default_teacher_id=?", (tid,))
    except Exception:
        pass
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

# Replace the existing teacher_schedule route in app.py with this:

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
               sub.subject_name, sub.subject_code,
               COALESCE(NULLIF(sc.semester,''), sub.semester) AS semester,
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
 
    # Build term tabs from each row's scope.
    terms_present = set()
    for s in schedules_list:
        scope = (s['semester'] or '').strip()
        for t in SEM_TERMS.get(scope, []):
            terms_present.add(t)
    semesters_present = sorted(terms_present)
    sem_stats = {}
    for sem in semesters_present:
        # Include entries whose scope covers this term.
        sem_rows = [s for s in schedules_list if sem in SEM_TERMS.get((s['semester'] or '').strip(), [])]
        sem_stats[sem] = {
            'classes':  len(sem_rows),
            'days':     len(set(s['day']        for s in sem_rows)),
            'sections': len(set(s['section_id'] for s in sem_rows)),
        }
 
    all_sections = conn.execute(
        "SELECT id, grade_level, section_name FROM sections ORDER BY grade_level, section_name"
    ).fetchall()
    all_strands = conn.execute(
        "SELECT id, strand_code, strand_name FROM strands ORDER BY strand_code"
    ).fetchall()
 
    conn.close()
    return render_template('teacher_schedule.html',
                           teacher=teacher,
                           schedules=schedules_list,
                           days_active=days_active,
                           sections_count=sections_count,
                           semesters=semesters_present,
                           sem_stats=sem_stats,
                           all_sections=all_sections,
                           all_strands=all_strands)
 
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
    conn.execute(
        "INSERT INTO subjects (subject_code,subject_name,grade_level,strand,semester,default_teacher_id) VALUES (?,?,?,?,?,?)",
        (d['subject_code'], d['subject_name'], d['grade_level'], d.get('strand',''), d.get('semester',''), None)
    )
    conn.commit(); conn.close()
    flash('Subject added successfully.', 'success')
    return redirect(url_for('subjects'))

@app.route('/subjects/edit/<int:sid>', methods=['POST'])
@login_required
def edit_subject(sid):
    d = request.form
    conn = get_db()
    conn.execute(
        "UPDATE subjects SET subject_code=?,subject_name=?,grade_level=?,strand=?,semester=?,default_teacher_id=? WHERE id=?",
        (d['subject_code'], d['subject_name'], d['grade_level'], d.get('strand',''), d.get('semester',''), None, sid)
    )
    conn.commit(); conn.close()
    flash('Subject updated.', 'success')
    return redirect(url_for('subjects'))


@app.route('/subject_teachers')
@login_required
def subject_teachers():
    conn = get_db()
    subjects_list = conn.execute("""
        SELECT sub.id, sub.subject_code, sub.subject_name, sub.grade_level, sub.strand, sub.semester,
               COALESCE((
                   SELECT GROUP_CONCAT(name, ', ')
                   FROM (
                       SELECT t.first_name || ' ' || t.last_name AS name
                       FROM subject_teachers st
                       JOIN teachers t ON t.id = st.teacher_id
                       WHERE st.subject_id = sub.id
                       ORDER BY t.last_name, t.first_name
                   )
               ), '') AS teacher_names
        FROM subjects sub
        ORDER BY sub.grade_level, sub.subject_name
    """).fetchall()
    teachers_list = conn.execute(
        "SELECT id, first_name, last_name FROM teachers ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return render_template('subject_teachers.html', subjects=subjects_list, teachers=teachers_list)


@app.route('/subject_teachers/set/<int:sid>', methods=['POST'])
@login_required
def set_subject_teachers(sid):
    teacher_ids = [int(x) for x in request.form.getlist('teacher_ids') if str(x).isdigit()]
    conn = get_db()
    conn.execute("DELETE FROM subject_teachers WHERE subject_id=?", (sid,))
    for tid in sorted(set(teacher_ids)):
        conn.execute(
            "INSERT OR IGNORE INTO subject_teachers (subject_id, teacher_id) VALUES (?, ?)",
            (sid, tid)
        )
    conn.commit(); conn.close()
    flash('Eligible teacher(s) updated for this subject.', 'success')
    return redirect(url_for('subject_teachers'))

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
    tids = conn.execute(
        "SELECT teacher_id FROM subject_teachers WHERE subject_id=? ORDER BY teacher_id",
        (sid,)
    ).fetchall()
    sec_ids = conn.execute(
        "SELECT section_id FROM subject_section_offerings WHERE subject_id=? ORDER BY section_id",
        (sid,)
    ).fetchall()
    conn.close()
    if not s:
        return jsonify({}), 404
    d = dict(s)
    d['teacher_ids'] = [r['teacher_id'] for r in tids]
    d['offering_section_ids'] = [r['section_id'] for r in sec_ids]
    return jsonify(d)


@app.route('/shs/offerings')
@login_required
def shs_offerings():
    conn = get_db()
    subjects_list = conn.execute("""
        SELECT sub.id, sub.subject_code, sub.subject_name, sub.grade_level, sub.strand, sub.semester,
               COALESCE(NULLIF(sub.shs_type,''), '') AS shs_type,
               COALESCE((
                   SELECT GROUP_CONCAT(name, ', ')
                   FROM (
                       SELECT sec.section_name AS name
                       FROM subject_section_offerings sso
                       JOIN sections sec ON sec.id = sso.section_id
                       WHERE sso.subject_id = sub.id
                       ORDER BY sec.grade_level, sec.section_name
                   )
               ), '') AS offered_sections
        FROM subjects sub
        WHERE sub.grade_level IN ('11','12')
        ORDER BY sub.grade_level, sub.subject_name
    """).fetchall()
    sections_list = conn.execute("""
        SELECT id, grade_level, section_name
        FROM sections
        WHERE grade_level IN ('Grade 11','Grade 12')
        ORDER BY grade_level, section_name
    """).fetchall()
    conn.close()
    return render_template('shs_offerings.html', subjects=subjects_list, sections=sections_list)


@app.route('/shs/offerings/set/<int:sid>', methods=['POST'])
@login_required
def shs_set_offering(sid):
    shs_type_raw = request.form.get('shs_type')
    print(f"DEBUG: shs_type_raw = {repr(shs_type_raw)}")
    shs_type = (shs_type_raw or '').strip()
    print(f"DEBUG: shs_type after processing = {repr(shs_type)}")
    allowed_types = ('', 'Core', 'Elective', 'Field', 'Special')
    print(f"DEBUG: allowed_types = {allowed_types}")
    print(f"DEBUG: shs_type in allowed_types = {shs_type in allowed_types}")
    if shs_type not in allowed_types:
        print(f"DEBUG: validation failed for shs_type = {repr(shs_type)}")
        flash(f'Invalid SHS type: "{shs_type}" not in {allowed_types}', 'danger')
        return redirect(url_for('shs_offerings'))

    section_ids = [int(x) for x in request.form.getlist('section_ids') if str(x).isdigit()]
    field_terms = request.form.getlist('field_terms')

    conn = get_db()
    try:
        conn.execute("UPDATE subjects SET shs_type=? WHERE id=?", (shs_type, sid))
        
        if shs_type == 'Field' and field_terms:
            semester_value = ','.join(sorted(set(field_terms)))
            conn.execute("UPDATE subjects SET semester=? WHERE id=?", (semester_value, sid))
        elif shs_type == 'Field':
            conn.execute("UPDATE subjects SET semester='' WHERE id=?", (sid,))

        conn.execute("DELETE FROM subject_section_offerings WHERE subject_id=?", (sid,))
        
        if shs_type == 'Elective' and section_ids:
            for sec_id in sorted(set(section_ids)):
                conn.execute(
                    "INSERT OR IGNORE INTO subject_section_offerings (subject_id, section_id, semester) VALUES (?, ?, '')",
                    (sid, sec_id)
                )
        elif shs_type == 'Field':
            if section_ids and field_terms:
                for term in sorted(set(field_terms)):
                    for sec_id in sorted(set(section_ids)):
                        conn.execute(
                            "INSERT OR IGNORE INTO subject_section_offerings (subject_id, section_id, semester) VALUES (?, ?, ?)",
                            (sid, sec_id, term)
                        )
            elif field_terms and not section_ids:
                for term in sorted(set(field_terms)):
                    conn.execute(
                        "INSERT INTO subject_section_offerings (subject_id, section_id, semester) VALUES (?, NULL, ?)",
                        (sid, term)
                    )

        conn.commit()
        flash('SHS offering updated.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating SHS offering: {str(e)}', 'danger')
        print(f"Database error in shs_set_offering: {e}")
    finally:
        conn.close()
    
    return redirect(url_for('shs_offerings'))
 

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

@app.route('/api/all_students_basic')
@any_role_required
def api_all_students_basic():
    conn = get_db()
    rows = conn.execute(
        "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
        " FROM students s WHERE s.enrollment_status='Enrolled'"
        " ORDER BY s.last_name, s.first_name"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        mn = clean_middle_name(r['middle_name'] or '')
        mi = f' {mn[0].upper()}.' if mn else ''
        result.append({'id': r['id'], 'name': f"{r['last_name']}, {r['first_name']}{mi}", 'sid': r['student_id']})
    return jsonify(result)


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
        SELECT sub.id, sub.subject_name, sub.subject_code, sub.grade_level, sub.semester
        FROM subjects sub
        JOIN strand_subjects ss ON ss.subject_id=sub.id
        WHERE ss.strand_id=?
        ORDER BY sub.subject_name
    """, (stid,)).fetchall()
    conn.close()
    return jsonify([dict(s) for s in subs])

@app.route('/api/subject/<int:subject_id>/teachers/<int:section_id>')
@login_required
def api_subject_teachers(subject_id, section_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT t.id, t.first_name, t.last_name, t.email
        FROM teachers t
        JOIN assignments a ON a.teacher_id = t.id
        WHERE a.subject_id = ? AND a.section_id = ?
        ORDER BY t.last_name, t.first_name
    """, (subject_id, section_id)).fetchall()

    # Fallback: if no section-specific assignment exists, use the subject's eligible teachers (if set)
    if not rows:
        rows = conn.execute("""
            SELECT t.id, t.first_name, t.last_name, t.email
            FROM teachers t
            JOIN subject_teachers st ON st.teacher_id = t.id
            WHERE st.subject_id = ?
            ORDER BY t.last_name, t.first_name
        """, (subject_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

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
        (normalize_grade_level(d['grade_level']) or d['grade_level'], d['section_name'],
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
        (normalize_grade_level(d['grade_level']) or d['grade_level'], d['section_name'],
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
    term-scope-aware: section, teacher, and room conflicts are only flagged when
    the existing entry's term scope overlaps with the new entry's term scope.
    Overlap rules are derived from SEM_TERMS (supports legacy semester labels).
    Blank/None scopes are treated conservatively as overlapping everything.
    """
    # Resolve semester of the new entry from subject if not provided directly
    if semester is None and subject_id:
        row = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if row:
            semester = row['semester'] or None

    def scopes_overlap(scope_a, scope_b):
        """True if two scope strings can conflict with each other."""
        all_terms = globals().get('ALL_TERMS', ['1st Term', '2nd Term', '3rd Term'])
        scope_map = globals().get('SEM_TERMS', {}) or {}

        def scope_terms(scope):
            if not scope:
                return set(all_terms)
            return set(scope_map.get(scope, all_terms))

        return bool(scope_terms(scope_a) & scope_terms(scope_b))

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
        sem_clash    = scopes_overlap(semester, existing_sem)

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

    # Workload check: count distinct sections the teacher handles per term.
    if semester:
        all_terms = globals().get('ALL_TERMS', ['1st Term', '2nd Term', '3rd Term'])
        scope_map = globals().get('SEM_TERMS', {}) or {}

        def scope_terms(scope):
            if not scope:
                return set(all_terms)
            return set(scope_map.get(scope, all_terms))

        new_terms = scope_terms(semester)

        args_w = [teacher_id]
        excl_w = ""
        if exclude_id:
            excl_w = " AND sc.id != ?"
            args_w.append(exclude_id)

        existing_rows = conn.execute("""
            SELECT DISTINCT sc.section_id,
                   COALESCE(NULLIF(sc.semester,''), sub.semester) AS scope
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id = sub.id
            WHERE sc.teacher_id = ?
        """ + excl_w, args_w).fetchall()

        per_term_sections = {t: set() for t in all_terms}
        for r in existing_rows:
            scope = (r['scope'] or '').strip()
            for t in scope_terms(scope):
                if t in per_term_sections:
                    per_term_sections[t].add(str(r['section_id']))

        new_sec = str(section_id)
        for t in sorted(new_terms):
            if new_sec not in per_term_sections.get(t, set()) and len(per_term_sections.get(t, set())) >= MAX_SECTIONS_PER_TEACHER:
                teacher_row = conn.execute(
                    "SELECT first_name || ' ' || last_name AS name FROM teachers WHERE id=?",
                    (teacher_id,)
                ).fetchone()
                teacher_name = teacher_row['name'] if teacher_row else 'This teacher'
                conflicts.append({
                    'type':   'workload',
                    'label':  'Workload Limit Reached',
                    'detail': (f'{teacher_name} already covers '
                               f'{len(per_term_sections.get(t, set()))} section(s) in {t} — '
                               f'the maximum is {MAX_SECTIONS_PER_TEACHER} per term.')
                })
                break

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
        # Use resolved term scope if provided; otherwise derive from subject.
        if resolved_sem:
            scope = resolved_sem
        elif sid:
            row = conn.execute("SELECT semester FROM subjects WHERE id=?", (sid,)).fetchone()
            scope = (row['semester'] or None) if row else None
        else:
            scope = None

        all_terms = globals().get('ALL_TERMS', ['1st Term', '2nd Term', '3rd Term'])
        scope_map = globals().get('SEM_TERMS', {}) or {}

        def scope_terms(s):
            if not s:
                return set(all_terms)
            return set(scope_map.get(s, all_terms))

        # Build per-term distinct-section counts for this teacher.
        rows = conn.execute("""
            SELECT DISTINCT sc.section_id,
                   COALESCE(NULLIF(sc.semester,''), sub.semester) AS scope
            FROM schedules sc
            JOIN subjects sub ON sc.subject_id = sub.id
            WHERE sc.teacher_id = ?
        """, (tid,)).fetchall()

        per_term_sections = {t: set() for t in all_terms}
        for r in rows:
            rscope = (r['scope'] or '').strip()
            for t in scope_terms(rscope):
                if t in per_term_sections:
                    per_term_sections[t].add(str(r['section_id']))

        per_term = {t: len(sids) for t, sids in per_term_sections.items()}

        if not scope:
            busiest_term = max(per_term, key=per_term.get) if per_term else None
            busiest_cnt = per_term.get(busiest_term, 0) if busiest_term else 0
            return {
                'current':   busiest_cnt,
                'projected': busiest_cnt,
                'max':       MAX_SECTIONS_PER_TEACHER,
                'semester':  busiest_term,
                'per_sem':   per_term,
            }

        terms = sorted(scope_terms(scope))
        # Pick the term in this scope with the highest current load for display.
        busiest_term = max(terms, key=lambda t: per_term.get(t, 0)) if terms else None
        current = per_term.get(busiest_term, 0) if busiest_term else 0

        # Projected assumes adding a section impacts each term in the scope (if new to that term).
        projected_per_term = per_term.copy()
        new_sec = str(sec_id)
        for t in terms:
            if new_sec not in per_term_sections.get(t, set()):
                projected_per_term[t] = projected_per_term.get(t, 0) + 1
        projected = projected_per_term.get(busiest_term, current) if busiest_term else current

        return {
            'current':   current,
            'projected': projected,
            'max':       MAX_SECTIONS_PER_TEACHER,
            'semester':  busiest_term,
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
    if raw_sem == 'Whole Year':
        if semester_override in ('1st Term', '2nd Term', '3rd Term', 'Whole Year', '1st Semester', '2nd Semester'):
            check_sem = semester_override
        else:
            check_sem = raw_sem
    elif raw_sem:
        check_sem = raw_sem
    else:
        check_sem = None
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
        SELECT s.*, t.first_name, t.last_name, st.strand_code
        FROM sections s
        LEFT JOIN teachers t ON s.adviser_id=t.id
        LEFT JOIN strands st ON s.strand_id=st.id
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

    # Build term tabs — use sc.semester (stored), fall back to sub.semester for legacy NULL rows
    # Scopes expand to the term(s) they cover (Whole Year shows in all terms).
    raw_sems = set()
    for s in schedules_list:
        sem = s['semester'] or s['subject_semester'] or None
        if not sem:
            continue
        for t in SEM_TERMS.get(sem, []):
            raw_sems.add(t)
    semesters_present = sorted(raw_sems)
    strands_list  = conn.execute("SELECT * FROM strands ORDER BY strand_code").fetchall()
    teachers_list = conn.execute("SELECT id,first_name,last_name FROM teachers ORDER BY last_name").fetchall()
    teachers_json = [dict(t) for t in teachers_list]

    # BUG 4 FIX: pass all subjects so JS fallback is never empty
    all_subjects = conn.execute(
        "SELECT id, subject_name, subject_code, grade_level, semester FROM subjects ORDER BY subject_name"
    ).fetchall()
    all_subjects_json = [dict(s) for s in all_subjects]

    # Check how many subjects are already scheduled for this section (any subjects, not just JHS)
    total_scheduled_subjects = conn.execute(
        "SELECT COUNT(DISTINCT subject_id) FROM schedules WHERE section_id = ?",
        (sec_id,)
    ).fetchone()[0]

    auto_jhs_subjects = []
    show_auto_schedule_button = False
    if section['grade_level'] in ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10'):
        # For JHS, show subjects based on the section's strand
        if section['strand_id']:
            # Section has a strand - show only subjects for that strand
            rows = conn.execute("""
                SELECT sub.id AS subject_id, sub.subject_name, sub.subject_code,
                       a.teacher_id AS assigned_teacher_id,
                       COALESCE(
                           a.teacher_id,
                           sch.teacher_id,
                           (SELECT CASE WHEN COUNT(*)=1 THEN MAX(teacher_id) ELSE NULL END
                            FROM subject_teachers st WHERE st.subject_id = sub.id),
                           ''
                       ) AS teacher_id,
                       COALESCE(t.first_name, t2.first_name, td.first_name) AS teacher_first,
                       COALESCE(t.last_name, t2.last_name, td.last_name) AS teacher_last,
                       COALESCE(sch.day, '') AS scheduled_day,
                       COALESCE(sch.time_start, '') AS scheduled_time_start,
                       COALESCE(sch.id, '') AS schedule_id
                FROM subjects sub
                JOIN strand_subjects ss ON ss.subject_id = sub.id
                LEFT JOIN assignments a ON a.subject_id = sub.id AND a.section_id = ?
                LEFT JOIN teachers t ON t.id = a.teacher_id
                LEFT JOIN schedules sch ON sch.subject_id = sub.id AND sch.section_id = ?
                LEFT JOIN teachers t2 ON t2.id = sch.teacher_id
                LEFT JOIN teachers td ON td.id = (
                    SELECT CASE WHEN COUNT(*)=1 THEN MAX(teacher_id) ELSE NULL END
                    FROM subject_teachers st WHERE st.subject_id = sub.id
                )
                WHERE ss.strand_id = ? AND sub.grade_level IN ('7','8','9','10')
                ORDER BY sub.subject_name
            """, (sec_id, sec_id, section['strand_id'])).fetchall()
        else:
            # Section has no strand - show all JHS subjects
            rows = conn.execute("""
                SELECT sub.id AS subject_id, sub.subject_name, sub.subject_code,
                       a.teacher_id AS assigned_teacher_id,
                       COALESCE(
                           a.teacher_id,
                           sch.teacher_id,
                           (SELECT CASE WHEN COUNT(*)=1 THEN MAX(teacher_id) ELSE NULL END
                            FROM subject_teachers st WHERE st.subject_id = sub.id),
                           ''
                       ) AS teacher_id,
                       COALESCE(t.first_name, t2.first_name, td.first_name) AS teacher_first,
                       COALESCE(t.last_name, t2.last_name, td.last_name) AS teacher_last,
                       COALESCE(sch.day, '') AS scheduled_day,
                       COALESCE(sch.time_start, '') AS scheduled_time_start,
                       COALESCE(sch.id, '') AS schedule_id
                FROM subjects sub
                LEFT JOIN assignments a ON a.subject_id = sub.id AND a.section_id = ?
                LEFT JOIN teachers t ON t.id = a.teacher_id
                LEFT JOIN schedules sch ON sch.subject_id = sub.id AND sch.section_id = ?
                LEFT JOIN teachers t2 ON t2.id = sch.teacher_id
                LEFT JOIN teachers td ON td.id = (
                    SELECT CASE WHEN COUNT(*)=1 THEN MAX(teacher_id) ELSE NULL END
                    FROM subject_teachers st WHERE st.subject_id = sub.id
                )
                WHERE sub.grade_level IN ('7','8','9','10')
                ORDER BY sub.subject_name
            """, (sec_id, sec_id)).fetchall()
        auto_jhs_subjects = [dict(r) for r in rows]
        
        # Show auto-schedule button if there are available slots (less than 8 total subjects scheduled)
        show_auto_schedule_button = total_scheduled_subjects < 8

    conn.close()
    return render_template('schedule.html',
                           section=section,
                           schedules=schedules_list,
                           strands=strands_list,
                           teachers=teachers_list,
                           teachers_json=teachers_json,
                           semesters=semesters_present,
                           max_sections=MAX_SECTIONS_PER_TEACHER,
                           all_subjects_json=all_subjects_json,
                           auto_jhs_subjects=auto_jhs_subjects,
                           show_auto_schedule_button=show_auto_schedule_button)


@app.route('/schedule/<int:sec_id>/auto_create', methods=['POST'])
@login_required
def auto_create_schedule(sec_id):
    data = request.get_json(silent=True)
    subjects = []
    homeroom_id = None
    if data and isinstance(data, dict):
        subjects = data.get('subjects') or []
        homeroom_id = data.get('homeroom_subject')
    else:
        form_subjects = request.form.getlist('subject_id[]') or request.form.getlist('subject_id')
        form_teachers = request.form.getlist('teacher_id[]') or request.form.getlist('teacher_id')
        form_homerooms = request.form.getlist('is_homeroom[]') or []
        form_homeroom = request.form.get('homeroom_subject')
        homeroom_id = form_homeroom or None

        # Defensive parsing: the auto-schedule modal can include hidden teacher inputs per row
        # and also insert another set of hidden fields on submit. If that happens, the browser
        # submits extra teacher_id[] values and the lengths won't match.
        if form_subjects and form_teachers and len(form_subjects) != len(form_teachers):
            if len(form_teachers) > len(form_subjects):
                form_teachers = form_teachers[-len(form_subjects):]
            else:
                flash('Please select a teacher for every subject before creating the schedule.', 'danger')
                return redirect(url_for('schedule', sec_id=sec_id))

        if form_subjects and form_homerooms and len(form_homerooms) != len(form_subjects):
            if len(form_homerooms) > len(form_subjects):
                form_homerooms = form_homerooms[-len(form_subjects):]
            else:
                form_homerooms = []
        if form_subjects and form_teachers and len(form_subjects) == len(form_teachers):
            subjects = [
                {
                    'subject_id': sid,
                    'teacher_id': tid,
                    'is_homeroom': form_homerooms[idx] == '1' if idx < len(form_homerooms) else (str(sid) == str(homeroom_id))
                }
                for idx, (sid, tid) in enumerate(zip(form_subjects, form_teachers))
            ]

    if not subjects or not isinstance(subjects, list):
        flash('No subjects were provided for automatic schedule generation.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    conn = get_db()
    section = conn.execute(
        "SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.id=?",
        (sec_id,)
    ).fetchone()
    if not section or section['grade_level'] not in ('Grade 7', 'Grade 8', 'Grade 9', 'Grade 10'):
        conn.close()
        flash('Automatic schedule generation is only available for JHS sections.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    parsed = []
    seen_ids = set()
    teacher_workload = {}  # Track workload per teacher for THIS batch
    
    for item in subjects:
        subject_id = item.get('subject_id')
        teacher_id = item.get('teacher_id')
        is_homeroom = item.get('is_homeroom')
        
        if not subject_id or not teacher_id:
            conn.close()
            flash('Every subject requires a teacher selection.', 'danger')
            return redirect(url_for('schedule', sec_id=sec_id))
        
        subject_id = int(subject_id)
        teacher_id = int(teacher_id)
        
        # Track teacher workload - this is for the new subjects being added
        if teacher_id not in teacher_workload:
            teacher_workload[teacher_id] = set()
        teacher_workload[teacher_id].add(sec_id)
        
        # Check for duplicate subjects in THIS batch
        if subject_id in seen_ids:
            conn.close()
            flash('Duplicate subject selection detected.', 'danger')
            return redirect(url_for('schedule', sec_id=sec_id))
        seen_ids.add(subject_id)
        
        parsed.append({
            'subject_id': subject_id,
            'teacher_id': teacher_id,
            'is_homeroom': str(is_homeroom).lower() in ('1', 'true')
        })
    
    # Validate teacher workload - ensure no teacher teaches more than MAX_SECTIONS_PER_TEACHER sections
    for teacher_id, sections in teacher_workload.items():
        # Get existing sections this teacher teaches (any semester)
        existing_sections = conn.execute("""
            SELECT DISTINCT sc.section_id FROM schedules sc
            WHERE sc.teacher_id = ?
        """, (teacher_id,)).fetchall()
        existing_section_ids = {str(r['section_id']) for r in existing_sections}
        
        # Check if adding would exceed limit
        total_sections = len(existing_section_ids.union(sections))
        if total_sections > MAX_SECTIONS_PER_TEACHER:
            teacher = conn.execute("SELECT first_name || ' ' || last_name AS name FROM teachers WHERE id=?", (teacher_id,)).fetchone()
            conn.close()
            teacher_name = teacher['name'] if teacher else f"Teacher #{teacher_id}"
            flash(f'{teacher_name} would exceed maximum {MAX_SECTIONS_PER_TEACHER} sections. Currently has {len(existing_section_ids)}, would have {total_sections}.', 'danger')
            return redirect(url_for('schedule', sec_id=sec_id))

    homeroom_count = sum(1 for item in parsed if item['is_homeroom'])
    if homeroom_count > 1:
        conn.close()
        flash('Please select only one homeroom subject.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    if len(parsed) > 8:
        conn.close()
        flash('Too many subjects selected. The JHS automatic schedule supports up to 8 subjects.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    subject_ids = [item['subject_id'] for item in parsed]
    rows = conn.execute(
        f"SELECT id, subject_name, subject_code FROM subjects WHERE id IN ({','.join('?' for _ in subject_ids)})",
        subject_ids
    ).fetchall()
    if len(rows) != len(subject_ids):
        conn.close()
        flash('One or more selected subjects are not valid.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))
    subject_map = {r['id']: dict(r) for r in rows}

    def is_esp(subject):
        return 'ESP' in subject['subject_code'].upper() or 'ESP' in subject['subject_name'].upper()

    homeroom = next((item for item in parsed if item['is_homeroom']), None)
    esp = next((item for item in parsed if is_esp(subject_map[item['subject_id']]) and (not homeroom or item['subject_id'] != homeroom['subject_id'])), None)
    others = [item for item in parsed if item != homeroom and item != esp]

    # Define priority subjects that must be scheduled
    # Use IDs (hashable) rather than dict objects
    priority_subject_ids = set()
    if homeroom:
        priority_subject_ids.add(homeroom['subject_id'])
    if esp:
        priority_subject_ids.add(esp['subject_id'])
    # Assuming "first subject" refers to homeroom as it's scheduled in the first period

    # Validate teacher workload - ensure no teacher teaches more than MAX_SECTIONS_PER_TEACHER sections
    for teacher_id, sections in teacher_workload.items():
        # Get existing sections this teacher teaches (any semester)
        existing_sections = conn.execute("""
            SELECT DISTINCT sc.section_id FROM schedules sc
            WHERE sc.teacher_id = ?
        """, (teacher_id,)).fetchall()
        existing_section_ids = {str(r['section_id']) for r in existing_sections}
        
        # Check if adding would exceed limit
        total_sections = len(existing_section_ids.union(sections))
        if total_sections > MAX_SECTIONS_PER_TEACHER:
            teacher = conn.execute("SELECT first_name || ' ' || last_name AS name FROM teachers WHERE id=?", (teacher_id,)).fetchone()
            conn.close()
            teacher_name = teacher['name'] if teacher else f"Teacher #{teacher_id}"
            flash(f'{teacher_name} would exceed maximum {MAX_SECTIONS_PER_TEACHER} sections. Currently has {len(existing_section_ids)}, would have {total_sections}.', 'danger')
            return redirect(url_for('schedule', sec_id=sec_id))

    homeroom_count = sum(1 for item in parsed if item['is_homeroom'])
    if homeroom_count > 1:
        conn.close()
        flash('Please select only one homeroom subject.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    total_slots = 8
    if len(parsed) > total_slots:
        conn.close()
        flash('The automatic JHS schedule can only place up to 8 subjects.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

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
    if homeroom:
        assignments.append((homeroom, slots[0]))
        slots = slots[1:]

    last_slot = None
    if esp:
        last_slot = slots[-1]
        slots = slots[:-1]

    if len(others) > len(slots):
        conn.close()
        flash('There are more subjects than available JHS periods. Reduce the list or remove non-JHS subjects.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    # Randomize the 'others' list to distribute subjects randomly across available periods
    others_ordered = others.copy()
    random.shuffle(others_ordered)
    
    for idx, item in enumerate(others_ordered):
        assignments.append((item, slots[idx]))

    if esp:
        assignments.append((esp, last_slot))

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    scheduled_subject_ids = set()
    
    # Get existing schedules for this section to preserve locked subjects
    existing_schedules = conn.execute(
        "SELECT id, subject_id, teacher_id, day, time_start, time_end, room, semester FROM schedules WHERE section_id=?",
        (sec_id,)
    ).fetchall()
    existing_schedule_map = {}
    for sch in existing_schedules:
        key = (sch['subject_id'], sch['day'])
        existing_schedule_map[key] = sch
    
    # Get all locked subjects (those with assignments for this section)
    locked_subject_assignments = conn.execute(
        "SELECT DISTINCT subject_id FROM assignments WHERE section_id=?",
        (sec_id,)
    ).fetchall()
    locked_subject_ids = {row['subject_id'] for row in locked_subject_assignments}
    
    # For locked subjects, get their current teacher assignment
    locked_subject_teachers = {}
    for subject_id in locked_subject_ids:
        teacher_row = conn.execute(
            "SELECT teacher_id FROM assignments WHERE subject_id=? AND section_id=?",
            (subject_id, sec_id)
        ).fetchone()
        if teacher_row:
            locked_subject_teachers[subject_id] = teacher_row['teacher_id']
    
    # Identify which parsed items represent locked subjects
    parsed_locked_subject_ids = {item['subject_id'] for item in parsed if item['subject_id'] in locked_subject_ids}
    # Identify which parsed items are new (unlocked) subjects
    parsed_unlocked_subject_ids = {item['subject_id'] for item in parsed if item['subject_id'] not in locked_subject_ids}
    
    # Get all subject IDs being rescheduled (from assignments)
    subjects_to_reschedule = {item['subject_id'] for item, slot in assignments}
    
    # DELETE ONLY schedules for subjects being rescheduled (not locked subjects not in this batch)
    for subject_id in subjects_to_reschedule:
        conn.execute('DELETE FROM schedules WHERE section_id=? AND subject_id=?', (sec_id, subject_id))

    inserted = 0
    failed_subjects = []
    for day in days:
        day_used_slots = set()
        for item, slot in assignments:
            subject_id = item['subject_id']
            is_homeroom = item.get('is_homeroom', False)
            teacher_id = item['teacher_id']

            selected_slot = None
            use_time_start = None
            use_time_end = None

            # If this is a parsed locked subject with an existing schedule, preserve that exact time
            existing_key = (subject_id, day)
            if subject_id in parsed_locked_subject_ids and existing_key in existing_schedule_map:
                existing = existing_schedule_map[existing_key]
                use_time_start, use_time_end = (period_times[0][1], period_times[0][2]) if is_homeroom else (existing['time_start'], existing['time_end'])
                selected_slot = (None, use_time_start, use_time_end)
                day_used_slots.add(use_time_start)
            else:
                # Try ALL available slots for this subject, starting with preferred ones
                all_slots = period_times.copy()
                selected_slot = None
                use_time_start = None
                use_time_end = None

                # Priority order: homeroom -> ESP -> preferred slot -> all others
                if is_homeroom:
                    slot_priority = [period_times[0]]
                elif esp and item == esp:
                    slot_priority = [last_slot] if last_slot else []
                else:
                    slot_priority = [slot] + [s for s in all_slots if s != slot and s not in [period_times[0], last_slot]]

                for candidate in slot_priority:
                    if candidate[1] in day_used_slots:
                        continue

                    time_start, time_end = candidate[1], candidate[2]
                    conflicts = find_conflicts(conn, sec_id, teacher_id, day, time_start, time_end,
                                               room='', exclude_id=None, subject_id=subject_id, semester=None)
                    teacher_conflicts = [c for c in conflicts if c['type'] == 'teacher']
                    section_conflicts = [c for c in conflicts if c['type'] == 'section']

                    if teacher_conflicts or section_conflicts:
                        continue

                    selected_slot = candidate
                    use_time_start, use_time_end = time_start, time_end
                    break

            if selected_slot is None:
                if subject_id in priority_subject_ids:
                    failed_subjects.append((item, day))
                # For non-priority subjects, skip silently if no slot available
                continue

            day_used_slots.add(use_time_start)

            existing_record = conn.execute(
                """SELECT id FROM schedules 
                   WHERE section_id=? AND subject_id=? AND teacher_id=? AND day=? 
                   AND time_start=? AND time_end=?""",
                (sec_id, subject_id, teacher_id, day, use_time_start, use_time_end)
            ).fetchone()

            if not existing_record:
                conn.execute(
                    "INSERT INTO schedules (section_id, subject_id, teacher_id, strand_id, day, time_start, time_end, room, semester) VALUES (?,?,?,?,?,?,?,?,?)",
                    (sec_id, subject_id, teacher_id, section['strand_id'], day, use_time_start, use_time_end, '', 'Whole Year')
                )
                inserted += 1
                scheduled_subject_ids.add(subject_id)
    
    # Second pass: try to schedule failed subjects in any available slot, even if it means allowing some conflicts
    if failed_subjects:
        for item, day in failed_subjects:
            subject_id = item['subject_id']
            is_homeroom = item.get('is_homeroom', False)
            teacher_id = item['teacher_id']

            # For homeroom, MUST force 1st period
            if is_homeroom:
                slots_to_try = [period_times[0]]  # Only 1st period for homeroom
            else:
                slots_to_try = period_times.copy()  # Try all slots for non-homeroom

            # Try slots in priority order
            for candidate in slots_to_try:
                time_start, time_end = candidate[1], candidate[2]

                # Check if this slot is already used by this section today
                slot_used_by_section = conn.execute(
                    "SELECT id FROM schedules WHERE section_id=? AND day=? AND time_start=?",
                    (sec_id, day, time_start)
                ).fetchone()

                if slot_used_by_section:
                    continue  # Section already has something at this time

                # Check for teacher conflicts only (allow section conflicts since we're desperate)
                conflicts = find_conflicts(conn, sec_id, teacher_id, day, time_start, time_end,
                                           room='', exclude_id=None, subject_id=subject_id, semester=None)
                teacher_conflicts = [c for c in conflicts if c['type'] == 'teacher']

                if teacher_conflicts:
                    continue  # Teacher is busy, can't schedule here

                # Found a slot! Schedule it even if there might be other conflicts
                existing_record = conn.execute(
                    """SELECT id FROM schedules
                       WHERE section_id=? AND subject_id=? AND teacher_id=? AND day=?
                       AND time_start=? AND time_end=?""",
                    (sec_id, subject_id, teacher_id, day, time_start, time_end)
                ).fetchone()

                if not existing_record:
                    conn.execute(
                        "INSERT INTO schedules (section_id, subject_id, teacher_id, strand_id, day, time_start, time_end, room, semester) VALUES (?,?,?,?,?,?,?,?,?)",
                        (sec_id, subject_id, teacher_id, section['strand_id'], day, time_start, time_end, '', 'Whole Year')
                    )
                    inserted += 1
                    scheduled_subject_ids.add(subject_id)
                    break  # Successfully scheduled, move to next failed subject
    
    # RE-INSERT locked subjects that were NOT selected for rescheduling
    # These subjects keep their existing schedules intact
    for subject_id in locked_subject_ids:
        if subject_id not in subjects_to_reschedule:
            # This locked subject was not in the form submission, so preserve it completely
            teacher_id = locked_subject_teachers.get(subject_id)
            if teacher_id:
                for day in days:
                    existing_key = (subject_id, day)
                    if existing_key in existing_schedule_map:
                        existing = existing_schedule_map[existing_key]
                        conn.execute(
                            "INSERT INTO schedules (section_id, subject_id, teacher_id, strand_id, day, time_start, time_end, room, semester) VALUES (?,?,?,?,?,?,?,?,?)",
                            (sec_id, subject_id, teacher_id, section['strand_id'], day, 
                             existing['time_start'], existing['time_end'], existing['room'], existing['semester'])
                        )
                        inserted += 1

    conn.commit()
    conn.close()
    
    # Report results
    total_subjects = len(parsed)
    scheduled_count = len(scheduled_subject_ids)
    failed_count = len(failed_subjects) if 'failed_subjects' in locals() else 0
    
    if failed_count > 0:
        flash(f'Automatic JHS schedule created with {inserted} entries. {scheduled_count} subjects scheduled, but {failed_count} priority subjects could not be scheduled due to conflicts.', 'warning')
    else:
        flash(f'Automatic JHS schedule created with {inserted} entries across Monday to Friday. {scheduled_count} out of {total_subjects} subjects successfully scheduled.', 'success')
    
    return redirect(url_for('schedule', sec_id=sec_id))


@app.route('/schedule/<int:sec_id>/add', methods=['POST'])
@login_required
def add_schedule(sec_id):
    d          = request.form
    time_start = d['time_start']
    time_end   = d['time_end']
    teacher_id = d['teacher_id']
    room       = d.get('room', '').strip()
    force      = d.get('force_save') == '1'

    days = request.form.getlist('day')
    if not days:
        flash('Please select at least one day.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    if time_start >= time_end:
        flash('End time must be after start time.', 'danger')
        return redirect(url_for('schedule', sec_id=sec_id))

    conn = get_db()

    # Resolve subject + grade level
    subject_id = d.get('subject_id')
    sub_row    = conn.execute(
        "SELECT semester, grade_level FROM subjects WHERE id=?", (subject_id,)
    ).fetchone() if subject_id else None

    raw_sem    = (sub_row['semester'] or '') if sub_row else ''
    grade      = (sub_row['grade_level'] or '') if sub_row else ''

    # JHS subjects (Grade 7–10) are always Whole Year — no semester picker needed
    is_jhs = grade in ('7', '8', '9', '10')

    semester_override = d.get('semester_override', '').strip()

    if is_jhs:
        # JHS Whole Year: Force Whole Year silently regardless of what was posted
        semesters_to_save = ['Whole Year']
    elif raw_sem == 'Whole Year':
        # Non-JHS Whole Year: User must select a term scope
        if semester_override in ('1st Term', '2nd Term', '3rd Term', 'Whole Year', '1st Semester', '2nd Semester'):
            semesters_to_save = [semester_override]
        else:
            conn.close()
            flash('Please select a term (1st/2nd/3rd) for this Whole Year subject.', 'danger')
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

    # Insert one row per day × semester
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
    if is_jhs:
        label += ' (JHS Whole Year)'
    elif raw_sem == 'Whole Year':
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

    if sync_pair and stored_sem:
        # Sync all siblings: same subject/section/day, different scope (for Whole Year subjects)
        pairs = conn.execute("""
            SELECT id FROM schedules
            WHERE subject_id=? AND section_id=? AND day=?
              AND id != ?
              AND (semester IS NULL OR semester != ?)
        """, (subject_id, sec_id, day, sch_id, stored_sem or '')).fetchall()
        for pair in pairs:
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


# Add this route to app.py, near the existing flush_schedule route:

@app.route('/schedule/bulk_flush', methods=['POST'])
@login_required
def bulk_flush_schedules():
    section_ids = request.form.getlist('section_ids')
    if not section_ids:
        flash('No sections selected.', 'warning')
        return redirect(url_for('sections'))

    conn = get_db()
    total_deleted = 0
    section_names = []

    for sec_id in section_ids:
        try:
            sec_id_int = int(sec_id)
        except (ValueError, TypeError):
            continue
        section = conn.execute("SELECT section_name FROM sections WHERE id=?", (sec_id_int,)).fetchone()
        if not section:
            continue
        count = conn.execute(
            "SELECT COUNT(*) FROM schedules WHERE section_id=?", (sec_id_int,)
        ).fetchone()[0]
        conn.execute("DELETE FROM schedules WHERE section_id=?", (sec_id_int,))
        total_deleted += count
        if count > 0:
            section_names.append(section['section_name'])

    conn.commit()
    conn.close()

    if total_deleted == 0:
        flash('No schedule entries were cleared (sections had no schedules).', 'warning')
    elif len(section_names) == 1:
        flash(f'Cleared {total_deleted} schedule entr{"ies" if total_deleted != 1 else "y"} from {section_names[0]}.', 'success')
    else:
        flash(f'Cleared {total_deleted} schedule entr{"ies" if total_deleted != 1 else "y"} across {len(section_names)} section(s).', 'success')

    return redirect(url_for('sections'))

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
            normalize_grade_level(d.get('grade_level','').strip()),
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
            normalize_grade_level(d.get('grade_level','').strip()),
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

BLANK_MIDDLE = {'-', '.', '-.', '.-', 'n/a', 'none', 'na', 'N/A', 'None', 'NA', '--', '---'}

def clean_middle_name(val):
    if not val:
        return None
    v = val.strip()
    if not v or v in BLANK_MIDDLE or all(c in '.-' for c in v):
        return None
    return v

def normalize_grade_level(raw):
    import re
    if not raw:
        return None
    val = raw.strip()
    if val in ('Grade 7','Grade 8','Grade 9','Grade 10','Grade 11','Grade 12'):
        return val
    if val.isdigit() and val in ('7','8','9','10','11','12'):
        return 'Grade ' + val
    m = re.match(r'(?i)grade\s*(\d+)$', val)
    if m and m.group(1) in ('7','8','9','10','11','12'):
        return 'Grade ' + m.group(1)
    return val or None

@app.route('/students/bulk_add', methods=['POST'])
@login_required
def bulk_add_students():
    import csv, io
    # Accept file upload OR raw csv_data textarea (backward compat)
    file = request.files.get('csv_file')
    if file and file.filename:
        try:
            raw_bytes = file.read()
            # Try encodings in order: UTF-8 with BOM, plain UTF-8, Latin-1 (covers ñ, accents, etc.)
            for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
                try:
                    raw = raw_bytes.decode(enc).strip()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                flash('Could not read file — unsupported encoding. Please save the CSV as UTF-8.', 'danger')
                return redirect(url_for('students'))
        except Exception as e:
            flash(f'Could not read file: {e}', 'danger')
            return redirect(url_for('students'))
    else:
        raw = request.form.get('csv_data', '').strip()

    if not raw:
        flash('No data provided.', 'danger')
        return redirect(url_for('students'))

    # Default section — applied when a row has no section_name
    default_section_id = request.form.get('default_section_id') or None
    if default_section_id:
        default_section_id = int(default_section_id)

    reader = csv.DictReader(io.StringIO(raw))
    conn   = get_db()
    added = skipped = 0
    errors = []

    strand_lookup = {}
    for r in conn.execute("SELECT id, strand_code FROM strands").fetchall():
        strand_lookup[r['strand_code'].upper()] = r['id']
    section_lookup = {}
    for r in conn.execute("SELECT id, section_name FROM sections").fetchall():
        section_lookup[r['section_name'].strip().lower()] = r['id']

    # Build in-memory sets for fast duplicate detection within the same import
    seen_student_ids = set()
    seen_names       = set()  # (fname_lower, mname_lower, lname_lower)

    # Also load existing student_ids from DB for cross-import dedup
    existing_ids = {r[0] for r in conn.execute("SELECT student_id FROM students").fetchall()}

    for i, row in enumerate(reader, start=2):
        sid_val  = (row.get('student_id')         or '').strip()
        fname    = (row.get('first_name')          or '').strip()
        mname    = clean_middle_name((row.get('middle_name') or '').strip()) or ''
        lname    = (row.get('last_name')           or '').strip()
        gender   = (row.get('gender')              or '').strip()
        grade    = normalize_grade_level((row.get('grade_level') or '').strip())
        status   = (row.get('enrollment_status')   or '').strip()
        s_code   = (row.get('strand_code')         or '').strip()

        missing = []
        if not sid_val: missing.append('student_id')
        if not fname:   missing.append('first_name')
        if not mname:   missing.append('middle_name')
        if not lname:   missing.append('last_name')
        if not gender:  missing.append('gender')
        if not grade:   missing.append('grade_level')
        if not status:  missing.append('enrollment_status')
        if not s_code:  missing.append('strand_code')
        if missing:
            errors.append(f'Row {i}: missing required field(s): {", ".join(missing)}')
            skipped += 1
            continue

        # Duplicate student_id check (within this file)
        if sid_val in seen_student_ids:
            errors.append(f'Row {i}: duplicate student_id "{sid_val}" within this file — skipped.')
            skipped += 1
            continue
        seen_student_ids.add(sid_val)

        # Already in DB check
        if sid_val in existing_ids:
            errors.append(f'Row {i}: student_id "{sid_val}" already exists in the database — skipped.')
            skipped += 1
            continue

        # Duplicate name check (within this file)
        name_key = (fname.lower(), mname.lower(), lname.lower())
        if name_key in seen_names:
            errors.append(f'Row {i}: duplicate name "{fname} {mname} {lname}" within this file — skipped.')
            skipped += 1
            continue
        seen_names.add(name_key)

        strand_id_val = None
        if s_code:
            if s_code.isdigit():
                strand_id_val = int(s_code)
            else:
                strand_id_val = strand_lookup.get(s_code.upper())
                if strand_id_val is None:
                    errors.append(f'Row {i}: strand "{s_code}" not found in database — skipping strand.')

        try:
            conn.execute("""
                INSERT INTO students
                  (student_id, first_name, last_name, middle_name, gender, birthdate,
                   address, contact_no, email, guardian_name, guardian_contact,
                   grade_level, enrollment_status, strand_id, section_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                sid_val, fname, lname,
                clean_middle_name(mname),
                gender,
                row.get('birthdate','').strip() or None,
                row.get('address','').strip() or None,
                row.get('contact_no','').strip() or None,
                row.get('email','').strip() or None,
                row.get('guardian_name','').strip() or None,
                row.get('guardian_contact','').strip() or None,
                grade,
                status or 'Enrolled',
                strand_id_val,
                section_lookup.get((row.get('section_name') or '').strip().lower()) or default_section_id,
            ))
            added += 1
            existing_ids.add(sid_val)  # track for rest of this import
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
        # Match both "Grade 11" and bare "11"
        grade_bare = grade.replace('Grade ', '').strip()
        grade_full = 'Grade ' + grade_bare
        wheres.append("(s.grade_level = ? OR s.grade_level = ?)")
        args.extend([grade_full, grade_bare])
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

@app.route('/students/export')
@login_required
def export_students():
    import csv as _csv, io as _io
    conn = get_db()
    strand_id  = request.args.get('strand_id')
    grade      = request.args.get('grade_level')
    status     = request.args.get('enrollment_status')
    section_id = request.args.get('section_id')
    wheres, args = [], []
    if strand_id:  wheres.append("s.strand_id=?");        args.append(strand_id)
    if grade:      wheres.append("s.grade_level=?");      args.append(grade)
    if status:     wheres.append("s.enrollment_status=?"); args.append(status)
    if section_id: wheres.append("s.section_id=?");       args.append(section_id)
    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
    rows = conn.execute(
        "SELECT s.student_id, s.last_name, s.first_name, s.middle_name, "
        "s.gender, s.birthdate, s.grade_level, s.enrollment_status, "
        "s.contact_no, s.email, s.address, s.guardian_name, s.guardian_contact, "
        "sec.section_name, st.strand_code "
        "FROM students s "
        "LEFT JOIN sections sec ON s.section_id=sec.id "
        "LEFT JOIN strands st ON s.strand_id=st.id "
        + where_sql + " ORDER BY s.grade_level, s.last_name, s.first_name",
        args
    ).fetchall()
    conn.close()
    out = _io.StringIO()
    w = _csv.writer(out)
    w.writerow(['student_id','last_name','first_name','middle_name',
                'gender','birthdate','grade_level','enrollment_status',
                'contact_no','email','address',
                'guardian_name','guardian_contact',
                'section_name','strand_code'])
    for r in rows:
        w.writerow([
            r['student_id'], r['last_name'], r['first_name'], r['middle_name'] or '',
            r['gender'] or '', r['birthdate'] or '',
            r['grade_level'] or '', r['enrollment_status'] or 'Enrolled',
            r['contact_no'] or '', r['email'] or '', r['address'] or '',
            r['guardian_name'] or '', r['guardian_contact'] or '',
            r['section_name'] or '', r['strand_code'] or ''
        ])
    resp = make_response(out.getvalue())
    resp.headers['Content-Type']        = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="students.csv"'
    return resp

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
        grade_bare = str(grade).replace('Grade ', '').strip()
        grade_full = 'Grade ' + grade_bare
        q += " AND (grade_level = ? OR grade_level = ?)"
        q_args.extend([grade_full, grade_bare])

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
        grade_bare = str(grade).replace('Grade ', '').strip()
        grade_full = 'Grade ' + grade_bare
        sec_wheres.append("(s.grade_level = ? OR s.grade_level = ?)")
        sec_q_args.extend([grade_full, grade_bare])
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

    # Sort sections by available slots descending for even fill
    section_slots.sort(key=lambda s: s['available'], reverse=True)

    assigned_count = skipped_count = 0
    details = []
    rr_idx = 0  # round-robin index

    for student in students_to_assign:
        # Remove full sections
        section_slots = [s for s in section_slots if s['available'] > 0]
        if not section_slots:
            skipped_count += 1
            details.append({
                'student_id': student['id'],
                'name':   f"{student['first_name']} {student['last_name']}",
                'status': 'skipped',
                'reason': 'No available section slots'
            })
            continue

        # Round-robin: pick next section in rotation
        rr_idx = rr_idx % len(section_slots)
        sec = section_slots[rr_idx]
        rr_idx += 1

        conn.execute("UPDATE students SET section_id = ? WHERE id = ?", (sec['id'], student['id']))
        sec['available'] -= 1
        assigned_count += 1
        details.append({
            'student_id': student['id'],
            'name':    f"{student['first_name']} {student['last_name']}",
            'status':  'assigned',
            'section': sec['name'],
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
    if avg >= 97.5:  return 'With Highest Honors'
    if avg >= 94.5:  return 'With High Honors'
    if avg >= 89.5:  return 'With Honors'
    return None

def get_section_subjects(conn, section_id, active_sem=None):
    """Distinct subjects scheduled for this section, with teacher name(s).
    For Whole Year subjects, shows only the teacher assigned to active_sem.
    For regular subjects, shows all teachers for that subject.
    """
    rows = conn.execute("""
        SELECT sub.id, sub.subject_name, sub.subject_code,
               COALESCE(NULLIF(sub.semester,''), sc.semester) AS semester,
               sc.semester AS sched_semester,
               t.first_name || ' ' || t.last_name AS teacher_name,
               t.id AS teacher_id
        FROM (
            SELECT section_id, subject_id, teacher_id, semester FROM schedules WHERE section_id = ?
            UNION ALL
            SELECT section_id, subject_id, teacher_id, '' AS semester FROM assignments WHERE section_id = ?
        ) sc
        JOIN subjects sub ON sc.subject_id = sub.id
        JOIN teachers t   ON sc.teacher_id = t.id
        ORDER BY sub.subject_name, sc.semester, t.last_name
    """, (section_id, section_id)).fetchall()

    from collections import OrderedDict
    subjects = OrderedDict()
    for r in rows:
        sid = r['id']
        if sid not in subjects:
            subjects[sid] = {
                'id':           sid,
                'subject_name': r['subject_name'],
                'subject_code': r['subject_code'],
                'semester':     r['semester'] or '',
                'teachers':     [],
                '_seen_teachers': set(),
            }
        sub = subjects[sid]
        # For Whole Year subjects: include all assigned teachers
        is_wy = (sub['semester'] == 'Whole Year')
        sched_sem = r['sched_semester'] or ''
        # Removed filtering by active_sem for Whole Year subjects to show all teachers in summaries

        if r['teacher_id'] not in sub['_seen_teachers']:
            sub['_seen_teachers'].add(r['teacher_id'])
            sub['teachers'].append(r['teacher_name'])

    result = []
    for s in subjects.values():
        del s['_seen_teachers']
        result.append(s)
    return result

# ── Grades home: list sections ──
@app.route('/grades/open_period', methods=['POST'])
@login_required
def open_next_period():
    period = request.form.get('period')
    if period not in ALL_TERMS:
        flash('Invalid period.', 'danger')
        return redirect(url_for('grades_home'))

    conn = get_db()
    settings = get_period_settings(conn)

    sem = request.form.get('semester', '1st Term')
    if sem not in SEM_TERMS:
        flash('Invalid term scope.', 'danger')
        return redirect(url_for('grades_home'))

    # Enforce sequential unlock within this semester
    sem_periods = SEM_TERMS.get(sem, ALL_TERMS)
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
    flash(f'{period} grading period is now open for {sem}.', 'success')
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
                           open_periods=open_periods, all_periods=ALL_TERMS)

# ── Grade sheet: section × subject ──
ALL_TERMS    = ['1st Term', '2nd Term', '3rd Term']
TERM_ORDER   = {t: i for i, t in enumerate(ALL_TERMS)}

# Term scopes used across the system.
# NOTE: DB columns are still named `semester` for backward compatibility, but values
# now represent term scopes (plus "Whole Year").
#
# Backward-compatibility:
# - legacy '1st Semester' behaves like ['1st Term','2nd Term']
# - legacy '2nd Semester' behaves like ['3rd Term']
SEM_TERMS = {
    '1st Term':   ['1st Term'],
    '2nd Term':   ['2nd Term'],
    '3rd Term':   ['3rd Term'],
    'Whole Year': ['1st Term', '2nd Term', '3rd Term'],
    # legacy
    '1st Semester': ['1st Term', '2nd Term'],
    '2nd Semester': ['3rd Term'],
}

def normalize_term_scope(scope):
    """Map legacy semester labels to the closest term scope."""
    if not scope:
        return scope
    if scope == '1st Semester':
        return '1st Term'
    if scope == '2nd Semester':
        return '3rd Term'
    return scope

def get_open_periods(conn):
    """Return list of periods currently open school-wide."""
    rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE is_open=1"
    ).fetchall()
    open_set = {r['period'] for r in rows}
    return [p for p in ALL_TERMS if p in open_set]

def get_open_periods_for_subject(conn, subject_semester, active_sem=None):
    """Return open periods for a subject based on its term scope.
    Each term scope has independent controls.
    For blank/unset scopes, fall back to the active scope.
    """
    if not subject_semester or subject_semester not in SEM_TERMS:
        lookup_sem = active_sem or '1st Term'
    else:
        lookup_sem = subject_semester
    rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? AND is_open=1",
        (lookup_sem,)
    ).fetchall()
    open_set = {r['period'] for r in rows}
    return [p for p in ALL_TERMS if p in open_set]

def get_period_settings(conn):
    """Return dict of (period, semester) -> settings, plus nested by semester."""
    rows = conn.execute("SELECT * FROM grading_period_settings ORDER BY semester, id").fetchall()
    result = {}
    for r in rows:
        key = (r['period'], r['semester'])
        result[key] = dict(r)
    return result

def subjects_for_sem_tab(subjects_all, active_sem):
    """Subjects for a term tab: subjects whose scope covers that term + Whole Year/blank."""
    if not active_sem:
        return list(subjects_all)
    active_terms = set(SEM_TERMS.get(active_sem, ALL_TERMS))
    out = []
    for s in subjects_all:
        scope = (s.get('semester') or '').strip()
        if not scope or scope == 'Whole Year':
            out.append(s)
            continue
        scope_terms = set(SEM_TERMS.get(scope, ALL_TERMS))
        if active_terms & scope_terms:
            out.append(s)
    return out

@app.route('/grades/section/<int:sec_id>')
@login_required
def grade_sheet(sec_id):
    conn = get_db()
    section  = conn.execute("SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.id=?", (sec_id,)).fetchone()
    if not section:
        flash('Section not found.', 'danger')
        return redirect(url_for('grades_home'))

    students     = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    # For JHS sections (grades 7-10), always use 'Whole Year'
    is_jhs = section['grade_level'] in ('7', '8', '9', '10')
    if is_jhs:
        active_sem = 'Whole Year'
    else:
        active_sem = request.args.get('sem', '1st Term')
        if active_sem not in SEM_TERMS:
            active_sem = '1st Term'
    subjects_all = get_section_subjects(conn, sec_id, active_sem)
    subjects = subjects_for_sem_tab(subjects_all, active_sem)

    sel_sub_id  = request.args.get('subject_id', type=int)
    if not sel_sub_id and subjects:
        sel_sub_id = subjects[0]['id']
    sel_subject = next((s for s in subjects if s['id'] == sel_sub_id), None)

    # Determine which quarters apply to the selected subject in this semester
    if sel_subject:
        sub_scope = (sel_subject['semester'] or '').strip()
        sub_sem = sub_scope if (sub_scope and sub_scope in SEM_TERMS) else active_sem
        sem_q_rows = conn.execute(
            "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
            (sub_sem,)
        ).fetchall()
        QUARTERS = [r['period'] for r in sem_q_rows] if sem_q_rows else ALL_TERMS
    else:
        QUARTERS = ALL_TERMS
    grades_raw = conn.execute(
        "SELECT g.student_id, g.quarter, g.written_works, g.performance_tasks, g.quarterly_assessment FROM grades g WHERE g.section_id=? AND g.subject_id=? AND g.semester=?",
        (sec_id, sel_sub_id or 0,
         ('Whole Year' if (sel_subject and (sel_subject['semester'] or '').strip() == 'Whole Year')
          else (sel_subject['semester'] if (sel_subject and (sel_subject['semester'] or '').strip()) else active_sem)))
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
        gs_sem = active_sem if (not sel_subject or sel_subject['semester'] in ('', 'Whole Year')) else sel_subject['semester']
        rows = conn.execute(
            "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=?",
            (sel_sub_id, sec_id, gs_sem)
        ).fetchall()
        sub_statuses = {r['quarter']: r['status'] for r in rows}

    conn.close()
    return render_template('grade_sheet.html',
                           section=section, subjects=subjects, subjects_all=subjects_all,
                           active_sem=active_sem, sel_subject=sel_subject, sel_sub_id=sel_sub_id,
                           students=student_grades, quarters=QUARTERS,
                           q_statuses=sub_statuses, passing_grade=PASSING_GRADE)


@app.route('/debug/grades/<int:sec_id>')
@login_required
def debug_grades(sec_id):
    conn = get_db()
    # All grade rows with full context
    rows = conn.execute("""
        SELECT s.student_id AS sid, s.first_name, s.last_name,
               sub.subject_name, sub.subject_code,
               sub.semester AS sub_sem,
               sc.semester AS sched_sem,
               g.semester AS stored_sem,
               g.quarter,
               g.written_works AS ww,
               g.performance_tasks AS pt,
               g.quarterly_assessment AS qa
        FROM grades g
        JOIN students s   ON g.student_id  = s.id
        JOIN subjects sub ON g.subject_id  = sub.id
        LEFT JOIN schedules sc ON sc.subject_id = g.subject_id
                               AND sc.section_id = g.section_id
        WHERE g.section_id=?
        GROUP BY g.id
        ORDER BY s.last_name, sub.subject_name, g.semester, g.quarter
    """, (sec_id,)).fetchall()

    # Summary: grades with semester=''
    empty_sem = conn.execute(
        "SELECT COUNT(*) AS cnt FROM grades WHERE section_id=? AND semester=''", (sec_id,)
    ).fetchone()['cnt']

    conn.close()
    return jsonify({
        'empty_semester_count': empty_sem,
        'rows': [dict(r) for r in rows]
    })

@app.route('/grades/section/<int:sec_id>/summary')
@login_required
def grade_summary(sec_id):
    conn = get_db()
    section = conn.execute(
        "SELECT s.*, st.strand_code FROM sections s LEFT JOIN strands st ON s.strand_id=st.id WHERE s.id=?",
        (sec_id,)
    ).fetchone()
    if not section:
        flash('Section not found.', 'danger')
        conn.close()
        return redirect(url_for('grades_home'))

    is_jhs = section['grade_level'] in ('7', '8', '9', '10')
    if is_jhs:
        active_sem = 'Whole Year'
    else:
        active_sem = request.args.get('sem', '1st Term')
        if active_sem not in SEM_TERMS:
            active_sem = '1st Term'

    subjects = get_section_subjects(conn, sec_id, active_sem)
    subjects  = subjects_for_sem_tab(subjects, active_sem)

    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name FROM students "
        "WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    # Fetch all grades for this section
    all_grades = conn.execute(
        "SELECT student_id, subject_id, semester, quarter, written_works, performance_tasks, quarterly_assessment "
        "FROM grades WHERE section_id=?",
        (sec_id,)
    ).fetchall()

    # Quarters that belong to each semester (from grading_period_settings)
    sem_quarters_rows = conn.execute(
        "SELECT period, semester FROM grading_period_settings ORDER BY id"
    ).fetchall()
    sem_quarters_map = {}
    for r in sem_quarters_rows:
        sem_quarters_map.setdefault(r['semester'], [])
        if r['period'] not in sem_quarters_map[r['semester']]:
            sem_quarters_map[r['semester']].append(r['period'])

    conn.close()

    # grade_map[student_id][(subject_id,semester)][quarter] = computed_grade
    grade_map = {}
    for g in all_grades:
        qg = compute_quarterly_grade(g['written_works'], g['performance_tasks'], g['quarterly_assessment'])
        key = (g['subject_id'], g['semester'] or '')
        grade_map.setdefault(g['student_id'], {}).setdefault(key, {})[g['quarter']] = qg

    # Build rows: one per student
    rows = []
    for st in students:
        sub_grades = {}
        gen_vals   = []
        for sub in subjects:
            # Determine effective scope for this subject's grades
            sub_scope = (sub.get('semester') or '').strip()
            if sub_scope == 'Whole Year':
                eff_sem = 'Whole Year'
            elif sub_scope:
                eff_sem = sub_scope
            else:
                eff_sem = active_sem
            relevant_qs = sem_quarters_map.get(eff_sem, ALL_TERMS)
            grade_key = (sub['id'], eff_sem)
            q_vals = [
                grade_map.get(st['id'], {}).get(grade_key, {}).get(q)
                for q in relevant_qs
            ]
            q_vals = [v for v in q_vals if v is not None]
            avg = round(sum(q_vals) / len(q_vals), 2) if q_vals else None
            if avg is not None:
                gen_vals.append(avg)
            sub_grades[sub['id']] = {
                'avg':     avg,
                'passing': avg is not None and avg >= PASSING_GRADE,
            }
        gen_avg = round(sum(gen_vals) / len(gen_vals), 2) if gen_vals else None
        rows.append({
            'student':    dict(st),
            'sub_grades': sub_grades,
            'gen_avg':    gen_avg,
            'passing':    gen_avg is not None and gen_avg >= PASSING_GRADE,
        })

    return render_template('grade_summary.html',
                           section=section, subjects=subjects,
                           rows=rows, active_sem=active_sem,
                           passing_grade=PASSING_GRADE)


@app.route('/grades/section/<int:sec_id>/clear', methods=['POST'])
@login_required
def clear_grades(sec_id):
    sub_id = request.form.get('subject_id', type=int)
    period = request.form.get('period', '').strip()
    if not sub_id:
        return jsonify({'ok': False, 'error': 'No subject specified.'}), 400
    if period not in ALL_TERMS:
        return jsonify({'ok': False, 'error': 'Invalid term.'}), 400

    conn = get_db()
    # Only clear Draft periods — cannot clear Approved/Locked
    sem_for_clear = request.form.get('semester', '').strip()
    if not sem_for_clear:
        sem_for_clear = get_effective_semester(conn, sub_id, sec_id)
    status = get_submission_status(conn, sub_id, sec_id, period, sem_for_clear)
    if status in ('Approved', 'Locked'):
        conn.close()
        return jsonify({'ok': False, 'error': f'{period} is {status} and cannot be cleared.'}), 400

    sem = sem_for_clear
    # Delete for the given semester AND any legacy rows with semester=''
    conn.execute(
        "DELETE FROM grades WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (sub_id, sec_id, sem, period)
    )
    # Also clear legacy empty-semester rows for this subject/period
    conn.execute(
        "DELETE FROM grades WHERE subject_id=? AND section_id=? AND semester='' AND quarter=?",
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
    QUARTERS   = ['1st Term','2nd Term','3rd Term']

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
            conn.execute("""INSERT INTO grades (student_id,subject_id,section_id,quarter,written_works,performance_tasks,quarterly_assessment)
                            VALUES (?,?,?,?,?,?,?)""",
                         (sid, subject_id, sec_id, quarter, None, None, None))
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
    semester   = d.get('semester') or ''
    quarter    = d.get('quarter')
    component  = d.get('component')
    value      = d.get('value')
    reason     = (d.get('reason') or '').strip()

    ALLOWED = {'written_works','performance_tasks','quarterly_assessment'}
    if component not in ALLOWED:
        return jsonify({'ok': False, 'error': 'Invalid component'}), 400

    try: value = float(value) if value not in (None, '') else None
    except: return jsonify({'ok': False, 'error': 'Invalid value'}), 400

    conn = get_db()

    # Block edits if Approved or Locked
    status = get_submission_status(conn, subject_id, section_id, quarter, semester)

    if status in ('Approved', 'Locked'):
        conn.close()
        return jsonify({'ok': False, 'error': f'Grades are {status} and cannot be edited.', 'status': status}), 403

    # Block teacher edits if grading period is not open
    if 'teacher_id' in session and 'admin_id' not in session:
        period_row = conn.execute(
            "SELECT is_open FROM grading_period_settings WHERE period=? AND semester=?",
            (quarter, semester or '1st Term')
        ).fetchone()
        if not period_row or not period_row['is_open']:
            conn.close()
            return jsonify({'ok': False, 'error': f'{quarter} is not yet open for encoding.'}), 403

    # Log admin edits — require a reason if value is changing
    old_row = conn.execute(
        "SELECT " + component + " FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (student_id, subject_id, section_id, semester, quarter)
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
        "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (student_id, subject_id, section_id, semester, quarter)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE grades SET " + component + "=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
            (value, student_id, subject_id, section_id, semester, quarter)
        )
    else:
        kw = {c: None for c in ALLOWED}
        kw[component] = value
        conn.execute(
            "INSERT INTO grades (student_id,subject_id,section_id,semester,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?,?)",
            (student_id, subject_id, section_id, semester, quarter,
             kw['written_works'], kw['performance_tasks'], kw['quarterly_assessment'])
        )

    row = conn.execute(
        "SELECT written_works,performance_tasks,quarterly_assessment FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (student_id, subject_id, section_id, semester, quarter)
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
    QUARTERS  = ['1st Term','2nd Term','3rd Term']

    # Submission statuses per subject+quarter
    sub_statuses = {}
    if student['sec_id']:
        rows = conn.execute(
            "SELECT subject_id, semester, quarter, status FROM grade_submissions WHERE section_id=?",
            (student['sec_id'],)
        ).fetchall()
        for r in rows:
            sub_statuses[(r['subject_id'], r['semester'] or '', r['quarter'])] = r['status']

    grades_raw = conn.execute("""
        SELECT g.subject_id, g.semester, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment
        FROM grades g WHERE g.student_id=?
    """, (student_id,)).fetchall()
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['subject_id'], {}).setdefault(g['semester'] or '', {})[g['quarter']] = g

    QUARTERS = ['1st Term', '2nd Term', '3rd Term']
    subject_rows = []
    all_sub_avgs = []

    for sub in subjects:
        qgrades = {}
        has_any_grade = False
        sub_scope = (sub.get('semester') or '').strip()
        if sub_scope == 'Whole Year':
            sub_eff_sem = 'Whole Year'
        elif sub_scope:
            sub_eff_sem = sub_scope
        else:
            sub_eff_sem = 'Whole Year'
        for q in QUARTERS:
            row    = grade_map.get(sub['id'], {}).get(sub_eff_sem, {}).get(q)
            status = sub_statuses.get((sub['id'], sub_eff_sem, q), 'Draft')
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

        if sub_avg is not None:
            all_sub_avgs.append(sub_avg)

        subject_rows.append({
            'subject': sub, 'quarters': qgrades,
            'average': sub_avg, 'has_any_grade': has_any_grade,
            'passing': sub_avg is not None and sub_avg >= PASSING_GRADE
        })

    general_avg = round(sum(all_sub_avgs)/len(all_sub_avgs), 2) if all_sub_avgs else None
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

    # Workload per term (scope-aware)
    workload = {t: set() for t in ALL_TERMS}
    for s in schedules:
        scope = (s['row_semester'] or s['sub_semester'] or '').strip()
        for t in SEM_TERMS.get(scope, ALL_TERMS):
            if t in workload:
                workload[t].add(s['section_name'])
    workload_counts = {k: len(v) for k, v in workload.items() if v}

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
            "SELECT COUNT(DISTINCT quarter) FROM grade_submissions WHERE subject_id=? AND section_id=? AND status IN ('Approved','Locked') AND semester=?",
            (row['subject_id'], row['section_id'], get_effective_semester(conn, row['subject_id'], row['section_id']))
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
        SELECT s.*, sec.section_name, sec.grade_level AS sec_grade, st.strand_code
        FROM students s
        LEFT JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN strands st   ON s.strand_id  = st.id
        WHERE s.id=?
    """, (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('grades_home'))

    sec_id   = student['section_id']
    QUARTERS = ALL_TERMS

    # Submission statuses: (subject_id, scope, quarter) -> status
    sub_statuses = {}
    if sec_id:
        rows = conn.execute(
            "SELECT subject_id, semester, quarter, status FROM grade_submissions WHERE section_id=?",
            (sec_id,)
        ).fetchall()
        for r in rows:
            sub_statuses[(r['subject_id'], r['semester'] or '', r['quarter'])] = r['status']

    # All grades for this student with semester
    grades_raw = conn.execute("""
        SELECT g.subject_id, g.semester, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment
        FROM grades g WHERE g.student_id=?
    """, (student_id,)).fetchall()

    # grade_map[subject_id][semester][quarter] = row
    grade_map = {}
    for g in grades_raw:
        grade_map.setdefault(g['subject_id'], {}).setdefault(g['semester'] or '', {})[g['quarter']] = g

    def build_term_rows(subjects, term):
        rows_out = []
        sub_avgs = []
        for sub in subjects:
            sub_scope = (sub.get('semester') or '').strip()
            if sub_scope == 'Whole Year':
                eff_sem = 'Whole Year'
            elif sub_scope:
                eff_sem = sub_scope
            else:
                eff_sem = term

            quarters = [term]
            qgrades  = {}
            for q in quarters:
                row    = grade_map.get(sub['id'], {}).get(eff_sem, {}).get(q)
                status = sub_statuses.get((sub['id'], eff_sem, q), 'Draft')
                qg     = compute_quarterly_grade(
                    row['written_works'], row['performance_tasks'], row['quarterly_assessment']
                ) if row else None
                visible = status in ('Approved', 'Locked')
                qgrades[q] = {
                    'grade':    qg if visible else None,
                    'status':   status,
                    'has_data': qg is not None,
                    'visible':  visible,
                }
            visible_grades = [qgrades[q]['grade'] for q in quarters if qgrades[q]['grade'] is not None]
            sub_avg = round(sum(visible_grades) / len(visible_grades), 2) if visible_grades else None
            if sub_avg is not None:
                sub_avgs.append(sub_avg)
            rows_out.append({
                'subject': sub, 'quarters': qgrades, 'quarter_list': quarters,
                'average': sub_avg,
                'passing': sub_avg is not None and sub_avg >= PASSING_GRADE,
            })
        sem_avg = round(sum(sub_avgs) / len(sub_avgs), 2) if sub_avgs else None
        return rows_out, sem_avg

    # Build per-term subject rows
    sem_data = {}
    for term in ALL_TERMS:
        subs = get_section_subjects(conn, sec_id, term) if sec_id else []
        subs = subjects_for_sem_tab(subs, term)
        rows_out, term_avg = build_term_rows(subs, term)
        sem_data[term] = {'rows': rows_out, 'avg': term_avg}

    # General average across all terms
    all_avgs = [v for term in sem_data.values() for v in [term['avg']] if v is not None]
    general_avg = round(sum(all_avgs) / len(all_avgs), 2) if all_avgs else None
    honor = honor_classification(general_avg)

    conn.close()
    return render_template('report_card.html', student=student,
                           sem_data=sem_data, quarters=QUARTERS,
                           general_avg=general_avg, honor=honor,
                           passing_grade=PASSING_GRADE)

# ── Honor roll: per section ──
@app.route('/grades/honor_roll')
@login_required
def honor_roll():
    conn = get_db()
    sec_id     = request.args.get('section_id', type=int)
    active_sem = request.args.get('sem', '1st Term')
    if active_sem not in ALL_TERMS:
        active_sem = '1st Term'

    sections_list = conn.execute("""
        SELECT s.id, s.section_name, s.grade_level, st.strand_code
        FROM sections s LEFT JOIN strands st ON s.strand_id=st.id
        ORDER BY s.grade_level, s.section_name
    """).fetchall()

    # Get quarters that belong to this term scope
    sem_q_rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
        (active_sem,)
    ).fetchall()
    sem_quarters = [r['period'] for r in sem_q_rows] if sem_q_rows else [active_sem]

    honorees = []
    if sec_id:
        students = conn.execute("""
            SELECT id, student_id, first_name, last_name, middle_name
            FROM students WHERE section_id=? ORDER BY last_name, first_name
        """, (sec_id,)).fetchall()

        # Get subjects that cover this term.
        subjects_all_hr = get_section_subjects(conn, sec_id, active_sem)
        subjects = subjects_for_sem_tab(subjects_all_hr, active_sem)
        sub_ids  = [s['id'] for s in subjects]

        if sub_ids:
            # Only use Approved/Locked grades for honor roll — scoped to active semester
            sub_statuses_hr = {}
            qs_rows = conn.execute(
                "SELECT subject_id, semester, quarter, status FROM grade_submissions WHERE section_id=?",
                (sec_id,)
            ).fetchall()
            for r in qs_rows:
                sub_statuses_hr[(r['subject_id'], r['semester'] or '', r['quarter'])] = r['status']

            for st in students:
                sub_avgs = []
                all_subjects_have_grades = True
                for sub in subjects:
                    eff_sem = get_effective_semester(conn, sub['id'], sec_id, active_sem)
                    placeholders = ','.join('?'*len(sem_quarters))
                    grades_raw = conn.execute(
                        f"SELECT g.quarter, g.written_works, g.performance_tasks, g.quarterly_assessment "
                        f"FROM grades g "
                        f"WHERE g.student_id=? AND g.subject_id=? AND g.section_id=? "
                        f"AND g.semester=? "
                        f"AND g.quarter IN ({placeholders})",
                        [st['id'], sub['id'], sec_id, eff_sem] + sem_quarters
                    ).fetchall()
                    # Only count grades from Approved or Locked quarters
                    qvals = []
                    for g in grades_raw:
                        status = sub_statuses_hr.get((sub['id'], eff_sem, g['quarter']), 'Draft')
                        if status not in ('Approved', 'Locked'):
                            continue
                        qg = compute_quarterly_grade(g['written_works'], g['performance_tasks'], g['quarterly_assessment'])
                        if qg is not None:
                            qvals.append(qg)
                    if qvals:
                        sub_avgs.append(round(sum(qvals)/len(qvals), 2))
                    else:
                        all_subjects_have_grades = False

                if not sub_avgs:
                    continue
                avg   = round(sum(sub_avgs)/len(sub_avgs), 2)
                honor = honor_classification(avg)
                if honor:
                    honorees.append({'student': st, 'avg': avg, 'honor': honor})

        honorees.sort(key=lambda x: x['avg'], reverse=True)
        for i, h in enumerate(honorees, 1):
            h['rank'] = i

    conn.close()
    sel_section = next((s for s in sections_list if s['id'] == sec_id), None)
    return render_template('honor_roll.html', sections=sections_list, honorees=honorees,
                           sel_section=sel_section, sec_id=sec_id, active_sem=active_sem)

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

        QUARTERS = ['1st Term','2nd Term','3rd Term']
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

def get_submission_status(conn, subject_id, section_id, quarter, semester=''):
    row = conn.execute(
        "SELECT status FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (subject_id, section_id, semester, quarter)
    ).fetchone()
    if row:
        return row['status']
    # Fallback: check without semester for legacy rows
    row2 = conn.execute(
        "SELECT status FROM grade_submissions WHERE subject_id=? AND section_id=? AND quarter=? AND semester=''",
        (subject_id, section_id, quarter)
    ).fetchone()
    return row2['status'] if row2 else 'Draft'

def upsert_submission(conn, subject_id, section_id, quarter, status,
                      approved_by=None, unlock_reason=None, semester=''):
    existing = conn.execute(
        "SELECT id FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (subject_id, section_id, semester, quarter)
    ).fetchone()
    if existing:
        if status == 'Approved':
            conn.execute(
                "UPDATE grade_submissions SET status=?, approved_at=datetime('now'), approved_by=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
                (status, approved_by, subject_id, section_id, semester, quarter)
            )
        elif status == 'Locked':
            conn.execute(
                "UPDATE grade_submissions SET status=?, locked_at=datetime('now'), updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
                (status, subject_id, section_id, semester, quarter)
            )
        elif status == 'Draft':
            conn.execute(
                "UPDATE grade_submissions SET status=?, unlock_reason=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
                (status, unlock_reason, subject_id, section_id, semester, quarter)
            )
        else:
            conn.execute(
                "UPDATE grade_submissions SET status=?, updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
                (status, subject_id, section_id, semester, quarter)
            )
    else:
        conn.execute(
            "INSERT INTO grade_submissions (subject_id,section_id,semester,quarter,status,approved_by,unlock_reason) VALUES (?,?,?,?,?,?,?)",
            (subject_id, section_id, semester, quarter, status, approved_by, unlock_reason)
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
    semester = (d.get('semester') or '').strip()
    if not semester:
        semester = get_effective_semester(conn, subject_id, section_id)
    current = get_submission_status(conn, subject_id, section_id, quarter, semester)

    valid = {'approve': current in ('Draft','Submitted'), 'lock': current == 'Approved', 'unlock': current == 'Locked', 'revert': current in ('Submitted','Approved')}
    if not valid[action]:
        conn.close()
        return jsonify({'ok': False, 'error': f'Cannot {action} from status "{current}"'}), 400

    status_map = {'approve': 'Approved', 'lock': 'Locked', 'unlock': 'Draft', 'revert': 'Draft'}
    new_status = status_map[action]
    upsert_submission(conn, subject_id, section_id, quarter, new_status,
                      approved_by=session.get('admin_name', 'Admin'),
                      unlock_reason=reason if action == 'unlock' else None,
                      semester=semester)
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
    semester = request.args.get('semester', '').strip()
    if not semester:
        semester = get_effective_semester(conn, subject_id, section_id)
    rows = conn.execute(
        "SELECT quarter,status,approved_at,approved_by,locked_at,unlock_reason FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=?",
        (subject_id, section_id, semester)
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
               COALESCE(NULLIF(sc.semester,''), sub.semester) AS sem
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN sections sec ON sc.section_id=sec.id
        WHERE sc.teacher_id=?
        ORDER BY sec.grade_level, sec.section_name, sub.subject_name
    """, (tid,)).fetchall()

    # Submission statuses — scoped to each subject's effective semester
    QUARTERS = ['1st Term','2nd Term','3rd Term']
    status_map = {}
    for row in assigned:
        sub_sem = get_effective_semester(conn, row['subject_id'], row['section_id'])
        rows = conn.execute(
            "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=?",
            (row['subject_id'], row['section_id'], sub_sem)
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

    QUARTERS = ['1st Term','2nd Term','3rd Term']

    # Load submission statuses per quarter — semester determined after eff_sem computed below
    _tgs_sub_sem_raw = conn.execute("SELECT semester FROM subjects WHERE id=?", (sub_id,)).fetchone()
    _tgs_sub_sem = (_tgs_sub_sem_raw['semester'] or '') if _tgs_sub_sem_raw else ''

    sub_semester = (subject['semester'] or '').strip() if subject else ''

    # Active term tab (used for N/A subjects). For scoped subjects, eff_sem is derived from subject.
    req_sem = request.args.get('sem', '').strip()
    active_sem = req_sem if req_sem in ALL_TERMS else '1st Term'

    # Prefer schedule scope (if present) as a sensible default for N/A subjects.
    sched_scope_row = conn.execute(
        "SELECT sc.semester FROM schedules sc "
        "WHERE sc.teacher_id=? AND sc.section_id=? AND sc.subject_id=? "
        "AND sc.semester IS NOT NULL AND sc.semester != '' LIMIT 1",
        (tid, sec_id, sub_id)
    ).fetchone()
    if (not req_sem) and sched_scope_row:
        sched_scope = (sched_scope_row['semester'] or '').strip()
        terms = SEM_TERMS.get(sched_scope, [])
        if terms:
            active_sem = sorted(terms)[0]

    # Effective scope for grade storage
    eff_sem = get_effective_semester(conn, sub_id, sec_id, active_sem)

    # Load submission statuses scoped to this semester
    sub_rows = conn.execute(
        "SELECT quarter, status FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=?",
        (sub_id, sec_id, eff_sem)
    ).fetchall()
    q_statuses = {r['quarter']: r['status'] for r in sub_rows}

    # Get semester-scoped quarters
    sem_q_rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
        (eff_sem,)
    ).fetchall()
    QUARTERS = [r['period'] for r in sem_q_rows] if sem_q_rows else ['1st Term','2nd Term','3rd Term']

    # Load grades scoped to this semester
    grades_raw = conn.execute("""
        SELECT g.student_id, g.quarter,
               g.written_works, g.performance_tasks, g.quarterly_assessment
        FROM grades g WHERE g.subject_id=? AND g.section_id=? AND g.semester=?
    """, (sub_id, sec_id, eff_sem)).fetchall()
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

    open_periods = get_open_periods_for_subject(conn, sub_semester, active_sem)
    conn.close()
    return render_template('teacher_grade_sheet.html',
                           section=section, subject=subject,
                           students=student_grades, quarters=QUARTERS,
                           q_statuses=q_statuses, passing_grade=PASSING_GRADE,
                           sec_id=sec_id, sub_id=sub_id,
                           open_periods=open_periods,
                           active_sem=active_sem, eff_sem=eff_sem)

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

    ALL_TERMS = ['1st Term', '2nd Term', '3rd Term']
    sel_period  = request.args.get('period', 'all')
    PERIODS     = ALL_TERMS if sel_period == 'all' else [p for p in ALL_TERMS if p == sel_period]
    if not PERIODS:
        PERIODS = ALL_TERMS

    fallback_exp = request.args.get('semester') or '1st Term'
    eff_sem_exp  = get_effective_semester(conn, sub_id, sec_id, fallback_exp)
    grades_raw = conn.execute(
        "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment "
        "FROM grades WHERE subject_id=? AND section_id=? AND semester=?",
        (sub_id, sec_id, eff_sem_exp)
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

    ALL_TERMS = ['1st Term', '2nd Term', '3rd Term']
    sel_period  = request.args.get('period', 'all')
    PERIODS     = ALL_TERMS if sel_period == 'all' else [p for p in ALL_TERMS if p == sel_period]
    if not PERIODS:
        PERIODS = ALL_TERMS

    fallback_exp = request.args.get('semester') or '1st Term'
    grades_raw = conn.execute(
        "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment "
        "FROM grades WHERE subject_id=? AND section_id=? AND semester=?",
        (sub_id, sec_id, get_effective_semester(conn, sub_id, sec_id, fallback_exp))
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


# ── Export all grades for a teacher+section (single CSV; subjects distinguished by subject_id) ──
@app.route('/teacher/grade_sheet/<int:sec_id>/export_all_csv')
@teacher_required
def teacher_export_grades_all_csv(sec_id):
    conn = get_db()
    tid = session['teacher_id']

    assigned_rows = conn.execute(
        "SELECT DISTINCT subject_id FROM schedules WHERE teacher_id=? AND section_id=?",
        (tid, sec_id)
    ).fetchall()
    sub_ids = [r['subject_id'] for r in assigned_rows]
    if not sub_ids:
        conn.close()
        flash('No assigned subjects found for this section.', 'warning')
        return redirect(url_for('teacher_dashboard'))

    section = conn.execute(
        "SELECT section_name, grade_level FROM sections WHERE id=?",
        (sec_id,)
    ).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    req_sem = request.args.get('semester') or '1st Term'
    if req_sem == 'Whole Year':
        active_sem = 'Whole Year'
    else:
        active_sem = req_sem if req_sem in ALL_TERMS else '1st Term'

    sel_period = request.args.get('period', 'all')

    ph = ",".join(["?"] * len(sub_ids))
    subjects = conn.execute(
        f"SELECT id, subject_name, subject_code, semester FROM subjects WHERE id IN ({ph}) ORDER BY subject_name",
        sub_ids
    ).fetchall()

    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name "
        "FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    # Determine periods columns
    if sel_period != 'all':
        all_periods = [sel_period]
    else:
        all_periods = []
        for sub in subjects:
            eff_sem = get_effective_semester(conn, sub['id'], sec_id, active_sem)
            sem_q_rows = conn.execute(
                "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
                (eff_sem,)
            ).fetchall()
            base_periods = [r['period'] for r in sem_q_rows] if sem_q_rows else ALL_TERMS
            for p in base_periods:
                if p not in all_periods:
                    all_periods.append(p)
        if not all_periods:
            all_periods = ALL_TERMS

    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        'subject_id', 'subject_code', 'subject_name', 'semester',
        'student_id', 'last_name', 'first_name', 'middle_name'
    ]
    for p in all_periods:
        headers += [f'{p}_WW', f'{p}_PT', f'{p}_QA']
    writer.writerow(headers)

    for sub in subjects:
        sub_id = sub['id']
        eff_sem = get_effective_semester(conn, sub_id, sec_id, active_sem)
        grades_raw = conn.execute(
            "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment "
            "FROM grades WHERE subject_id=? AND section_id=? AND semester=?",
            (sub_id, sec_id, eff_sem)
        ).fetchall()
        grade_map = {}
        for g in grades_raw:
            grade_map.setdefault(g['student_id'], {})[g['quarter']] = g

        for st in students:
            row = [
                sub_id, sub['subject_code'] or '', sub['subject_name'] or '', eff_sem,
                st['student_id'], st['last_name'], st['first_name'], st['middle_name'] or ''
            ]
            for p in all_periods:
                g = grade_map.get(st['id'], {}).get(p)
                row += [
                    g['written_works'] if g and g['written_works'] is not None else '',
                    g['performance_tasks'] if g and g['performance_tasks'] is not None else '',
                    g['quarterly_assessment'] if g and g['quarterly_assessment'] is not None else '',
                ]
            writer.writerow(row)

    conn.close()

    period_label = sel_period.replace(' ', '_').replace('-', '') if sel_period != 'all' else 'All'
    safe_sem = (active_sem or '').replace(' ', '_')
    filename = f"grades_{section['section_name']}_Teacher_{safe_sem}_{period_label}_AllSubjects.csv".replace(' ', '_')
    csv_text = '\ufeff' + output.getvalue()
    resp = make_response(csv_text)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    return resp


# ── Admin export all subjects (XLSX; one sheet per subject) ──
@app.route('/grades/section/<int:sec_id>/export_all')
@login_required
def admin_export_grades_all(sec_id):
    # Backward-compat route: XLSX export removed, use combined CSV export instead.
    return admin_export_grades_all_csv(sec_id)


# ── Admin export all subjects (single CSV; subjects distinguished by subject_id) ──
@app.route('/grades/section/<int:sec_id>/export_all_csv')
@login_required
def admin_export_grades_all_csv(sec_id):
    conn = get_db()
    section = conn.execute(
        "SELECT id, section_name, grade_level FROM sections WHERE id=?",
        (sec_id,)
    ).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'danger')
        return redirect(url_for('grades_home'))

    # Match grade_sheet semester-tab behavior
    is_jhs = section['grade_level'] in ('7', '8', '9', '10')
    req_sem = request.args.get('semester') or request.args.get('sem') or '1st Term'
    if is_jhs:
        active_sem = 'Whole Year'
    else:
        if req_sem == 'Whole Year':
            active_sem = 'Whole Year'
        else:
            active_sem = req_sem if req_sem in ALL_TERMS else '1st Term'

    subjects_all = get_section_subjects(conn, sec_id, active_sem)
    subjects = subjects_for_sem_tab(subjects_all, active_sem)
    if not subjects:
        conn.close()
        flash('No subjects found for this section.', 'warning')
        return redirect(url_for('grade_sheet', sec_id=sec_id, sem=active_sem))

    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name "
        "FROM students WHERE section_id=? ORDER BY last_name, first_name",
        (sec_id,)
    ).fetchall()

    sel_period = request.args.get('period', 'all')

    # Determine the columns (periods) to include
    if sel_period != 'all':
        all_periods = [sel_period]
    else:
        all_periods = []
        for sub in subjects:
            eff_sem = get_effective_semester(conn, sub['id'], sec_id, active_sem)
            sem_q_rows = conn.execute(
                "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
                (eff_sem,)
            ).fetchall()
            base_periods = [r['period'] for r in sem_q_rows] if sem_q_rows else ALL_TERMS
            for p in base_periods:
                if p not in all_periods:
                    all_periods.append(p)
        if not all_periods:
            all_periods = ALL_TERMS

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        'subject_id', 'subject_code', 'subject_name', 'semester',
        'student_id', 'last_name', 'first_name', 'middle_name'
    ]
    for p in all_periods:
        headers += [f'{p}_WW', f'{p}_PT', f'{p}_QA']
    writer.writerow(headers)

    for sub in subjects:
        sub_id = sub['id']
        eff_sem = get_effective_semester(conn, sub_id, sec_id, active_sem)

        grades_raw = conn.execute(
            "SELECT student_id, quarter, written_works, performance_tasks, quarterly_assessment "
            "FROM grades WHERE subject_id=? AND section_id=? AND semester=?",
            (sub_id, sec_id, eff_sem)
        ).fetchall()
        grade_map = {}
        for g in grades_raw:
            grade_map.setdefault(g['student_id'], {})[g['quarter']] = g

        for st in students:
            row = [
                sub_id, sub.get('subject_code') or '', sub.get('subject_name') or '', eff_sem,
                st['student_id'], st['last_name'], st['first_name'], st['middle_name'] or ''
            ]
            for p in all_periods:
                g = grade_map.get(st['id'], {}).get(p)
                row += [
                    g['written_works'] if g and g['written_works'] is not None else '',
                    g['performance_tasks'] if g and g['performance_tasks'] is not None else '',
                    g['quarterly_assessment'] if g and g['quarterly_assessment'] is not None else '',
                ]
            writer.writerow(row)

    conn.close()

    period_label = sel_period.replace(' ', '_').replace('-', '') if sel_period != 'all' else 'All'
    safe_sem = (active_sem or '').replace(' ', '_')
    filename = f"grades_{section['section_name']}_{safe_sem}_{period_label}_AllSubjects.csv".replace(' ', '_')

    csv_text = '\ufeff' + output.getvalue()
    resp = make_response(csv_text)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    return resp

# ── Import grades from CSV (teacher) ──

def get_effective_semester(conn, subject_id, section_id, fallback_sem='1st Term'):
    """Get the effective scope for grade storage.
    - If subject has an explicit scope (1st/2nd/3rd Term or legacy 1st/2nd Semester): use it.
    - If subject is Whole Year: store under 'Whole Year'.
    - Otherwise: use fallback_sem (active term tab).
    """
    sub = conn.execute("SELECT semester FROM subjects WHERE id=?", (subject_id,)).fetchone()
    if not sub:
        return fallback_sem
    sub_sem = (sub['semester'] or '').strip()
    if sub_sem in ('1st Term', '2nd Term', '3rd Term', '1st Semester', '2nd Semester'):
        return sub_sem
    if sub_sem == 'Whole Year':
        return 'Whole Year'
    return fallback_sem
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

    # Block if any period is not Draft — scoped to this semester
    import_sem = request.form.get('semester') or request.args.get('semester') or '1st Term'
    import_eff_sem = get_effective_semester(conn, sub_id, sec_id, import_sem)
    locked_periods = conn.execute(
        "SELECT quarter FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=? AND status != 'Draft'",
        (sub_id, sec_id, import_eff_sem)
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

    # Determine effective semester for grade storage
    fallback_sem = request.form.get('semester') or request.args.get('semester') or '1st Term'
    eff_sem = get_effective_semester(conn, sub_id, sec_id, fallback_sem)

    # Scope to quarters for this semester only
    sem_q_rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id", (eff_sem,)
    ).fetchall()
    if sem_q_rows:
        PERIODS = [r['period'] for r in sem_q_rows]

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
                    "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                    (db_sid, sub_id, sec_id, eff_sem, p)
                ).fetchone()
                if existing:
                    conn.execute(
                        f"UPDATE grades SET {db_col}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                        (val, db_sid, sub_id, sec_id, eff_sem, p)
                    )
                else:
                    conn.execute(
                        "INSERT INTO grades (student_id,subject_id,section_id,semester,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?,?)",
                        (db_sid, sub_id, sec_id, eff_sem, p,
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

# ── Import all grades for a teacher+section (single CSV; subjects distinguished by subject_id) ──
@app.route('/teacher/grade_sheet/<int:sec_id>/import_all_csv', methods=['POST'])
@teacher_required
def teacher_import_grades_all_csv(sec_id):
    tid = session['teacher_id']
    conn = get_db()

    assigned_rows = conn.execute(
        "SELECT DISTINCT subject_id FROM schedules WHERE teacher_id=? AND section_id=?",
        (tid, sec_id)
    ).fetchall()
    allowed_subject_ids = {r['subject_id'] for r in assigned_rows}
    if not allowed_subject_ids:
        conn.close()
        return jsonify({'ok': False, 'error': 'No assigned subjects found for this section.'}), 400

    file = request.files.get('csv_file') or request.files.get('file')
    if not file:
        conn.close()
        return jsonify({'ok': False, 'error': 'No file uploaded.'}), 400

    try:
        content_str = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content_str))
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'Could not read CSV: {e}'}), 400

    fields = [f.strip() for f in (reader.fieldnames or []) if f]
    if 'subject_id' not in fields or 'student_id' not in fields:
        conn.close()
        return jsonify({'ok': False, 'error': "Invalid CSV format. Required columns: subject_id, student_id."}), 400

    students = conn.execute(
        "SELECT id, student_id FROM students WHERE section_id=?",
        (sec_id,)
    ).fetchall()
    student_map = {s['student_id']: s['id'] for s in students}

    req_sem = request.form.get('semester') or request.args.get('semester') or '1st Term'
    if req_sem == 'Whole Year':
        active_sem = 'Whole Year'
    else:
        active_sem = req_sem if req_sem in ALL_TERMS else '1st Term'

    total_updated = total_skipped = total_errors = 0
    skipped_locked_subjects = set()
    all_error_msgs = []

    eff_sem_cache = {}
    periods_cache = {}
    locked_cache = {}

    for line_no, row in enumerate(reader, start=2):
        sub_id_raw = (row.get('subject_id') or '').strip()
        if not sub_id_raw:
            total_skipped += 1
            continue
        try:
            sub_id = int(float(sub_id_raw))
        except Exception:
            total_errors += 1
            all_error_msgs.append(f"Row {line_no}: Invalid subject_id '{sub_id_raw}'.")
            continue

        if sub_id not in allowed_subject_ids:
            total_skipped += 1
            continue

        if sub_id not in eff_sem_cache:
            eff_sem_cache[sub_id] = get_effective_semester(conn, sub_id, sec_id, active_sem)
        eff_sem = eff_sem_cache[sub_id]

        if sub_id not in locked_cache:
            locked_periods = conn.execute(
                "SELECT quarter FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=? AND status != 'Draft'",
                (sub_id, sec_id, eff_sem)
            ).fetchall()
            locked_cache[sub_id] = bool(locked_periods)
        if locked_cache[sub_id]:
            skipped_locked_subjects.add(sub_id)
            total_skipped += 1
            continue

        if sub_id not in periods_cache:
            sem_q_rows = conn.execute(
                "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
                (eff_sem,)
            ).fetchall()
            periods_cache[sub_id] = [r['period'] for r in sem_q_rows] if sem_q_rows else ALL_TERMS
        periods = periods_cache[sub_id]

        updated, skipped, errors, error_msgs = _import_grades_rows(
            conn, sec_id, sub_id, eff_sem, periods, [row], student_map, start_row=line_no
        )
        total_updated += updated
        total_skipped += skipped
        total_errors += errors
        if error_msgs:
            all_error_msgs.extend(error_msgs)

    conn.commit()
    conn.close()
    return jsonify({
        'ok': True,
        'updated': total_updated,
        'skipped': total_skipped,
        'errors': total_errors,
        'skipped_locked_subjects': sorted(skipped_locked_subjects)[:10],
        'error_msgs': all_error_msgs[:10],
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

    # Determine effective semester for grade storage
    fallback_sem = request.args.get('semester') or '1st Term'
    eff_sem = get_effective_semester(conn, sub_id, sec_id, fallback_sem)

    # Scope to quarters for this semester only
    sem_q_rows = conn.execute(
        "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id", (eff_sem,)
    ).fetchall()
    if sem_q_rows:
        PERIODS = [r['period'] for r in sem_q_rows]

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
                    "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                    (db_sid, sub_id, sec_id, eff_sem, p)
                ).fetchone()
                if existing:
                    conn.execute(
                        f"UPDATE grades SET {db_col}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                        (val, db_sid, sub_id, sec_id, eff_sem, p)
                    )
                else:
                    conn.execute(
                        "INSERT INTO grades (student_id,subject_id,section_id,semester,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?,?)",
                        (db_sid, sub_id, sec_id, eff_sem, p,
                         val if db_col=='written_works' else None,
                         val if db_col=='performance_tasks' else None,
                         val if db_col=='quarterly_assessment' else None)
                    )
                updated += 1

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'updated': updated, 'skipped': skipped, 'errors': errors, 'error_msgs': error_msgs[:10]})


def _import_grades_rows(conn, sec_id, sub_id, eff_sem, periods, rows, student_map, start_row=2):
    """Shared import core for admin multi-subject import."""
    COMPONENTS = ['WW', 'PT', 'QA']
    COMP_FULL  = {'WW': 'written_works', 'PT': 'performance_tasks', 'QA': 'quarterly_assessment'}

    updated = skipped = errors = 0
    error_msgs = []

    for i, row in enumerate(rows, start=start_row):
        sid_str = (row.get('student_id') or '').strip()
        if not sid_str:
            skipped += 1
            continue
        db_sid = student_map.get(sid_str)
        if not db_sid:
            error_msgs.append(f"Row {i}: Student ID '{sid_str}' not found.")
            errors += 1
            continue

        for p in periods:
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
                    "SELECT id FROM grades WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                    (db_sid, sub_id, sec_id, eff_sem, p)
                ).fetchone()
                if existing:
                    conn.execute(
                        f"UPDATE grades SET {db_col}=?, updated_at=datetime('now') WHERE student_id=? AND subject_id=? AND section_id=? AND semester=? AND quarter=?",
                        (val, db_sid, sub_id, sec_id, eff_sem, p)
                    )
                else:
                    conn.execute(
                        "INSERT INTO grades (student_id,subject_id,section_id,semester,quarter,written_works,performance_tasks,quarterly_assessment) VALUES (?,?,?,?,?,?,?,?)",
                        (db_sid, sub_id, sec_id, eff_sem, p,
                         val if db_col == 'written_works' else None,
                         val if db_col == 'performance_tasks' else None,
                         val if db_col == 'quarterly_assessment' else None)
                    )
                updated += 1

    return updated, skipped, errors, error_msgs


# ── Admin import all subjects (XLSX; one sheet per subject) ──
@app.route('/grades/section/<int:sec_id>/import_all', methods=['POST'])
@login_required
def admin_import_grades_all(sec_id):
    # Backward-compat route: XLSX import removed, use combined CSV import instead.
    return admin_import_grades_all_csv(sec_id)


# ── Admin import all subjects (single CSV; subjects distinguished by subject_id) ──
@app.route('/grades/section/<int:sec_id>/import_all_csv', methods=['POST'])
@login_required
def admin_import_grades_all_csv(sec_id):
    conn = get_db()
    section = conn.execute(
        "SELECT id, grade_level FROM sections WHERE id=?",
        (sec_id,)
    ).fetchone()
    if not section:
        conn.close()
        return jsonify({'ok': False, 'error': 'Section not found.'}), 404

    file = request.files.get('csv_file') or request.files.get('xlsx_file') or request.files.get('file')
    if not file:
        conn.close()
        return jsonify({'ok': False, 'error': 'No file uploaded.'}), 400

    try:
        raw = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(raw))
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'Could not read CSV: {e}'}), 400

    # Match grade_sheet semester-tab behavior
    is_jhs = section['grade_level'] in ('7', '8', '9', '10')
    req_sem = request.args.get('semester') or request.args.get('sem') or '1st Term'
    if is_jhs:
        active_sem = 'Whole Year'
    else:
        if req_sem == 'Whole Year':
            active_sem = 'Whole Year'
        else:
            active_sem = req_sem if req_sem in ALL_TERMS else '1st Term'

    subjects_all = get_section_subjects(conn, sec_id, active_sem)
    subjects = subjects_for_sem_tab(subjects_all, active_sem)
    allowed_subject_ids = {s['id'] for s in subjects}

    students = conn.execute(
        "SELECT id, student_id FROM students WHERE section_id=?",
        (sec_id,)
    ).fetchall()
    student_map = {s['student_id']: s['id'] for s in students}

    total_updated = total_skipped = total_errors = 0
    all_error_msgs = []
    subjects_seen = set()
    subjects_skipped = 0

    eff_sem_cache = {}
    periods_cache = {}

    for line_no, row in enumerate(reader, start=2):
        sub_id_raw = (row.get('subject_id') or '').strip()
        if not sub_id_raw:
            total_skipped += 1
            continue
        try:
            sub_id = int(float(sub_id_raw))
        except Exception:
            total_errors += 1
            all_error_msgs.append(f"Row {line_no}: Invalid subject_id '{sub_id_raw}'.")
            continue

        if sub_id not in allowed_subject_ids:
            subjects_skipped += 1
            total_skipped += 1
            continue

        if sub_id not in eff_sem_cache:
            eff_sem_cache[sub_id] = get_effective_semester(conn, sub_id, sec_id, active_sem)
        eff_sem = eff_sem_cache[sub_id]

        if sub_id not in periods_cache:
            sem_q_rows = conn.execute(
                "SELECT period FROM grading_period_settings WHERE semester=? ORDER BY id",
                (eff_sem,)
            ).fetchall()
            periods_cache[sub_id] = [r['period'] for r in sem_q_rows] if sem_q_rows else ALL_TERMS
        periods = periods_cache[sub_id]

        updated, skipped, errors, error_msgs = _import_grades_rows(
            conn, sec_id, sub_id, eff_sem, periods, [row], student_map, start_row=line_no
        )
        total_updated += updated
        total_skipped += skipped
        total_errors += errors
        if error_msgs:
            all_error_msgs.extend(error_msgs)
        subjects_seen.add(sub_id)

    conn.commit()
    conn.close()
    return jsonify({
        'ok': True,
        'updated': total_updated,
        'skipped': total_skipped,
        'errors': total_errors,
        'subjects_processed': len(subjects_seen),
        'subjects_skipped': subjects_skipped,
        'error_msgs': all_error_msgs[:10],
    })

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

    semester = (d.get('semester') or '').strip()
    if not semester:
        semester = get_effective_semester(conn, subject_id, section_id)
    current = get_submission_status(conn, subject_id, section_id, quarter, semester)
    if current != 'Draft':
        conn.close()
        return jsonify({'ok': False, 'error': f'Quarter is already {current}'}), 400

    # Upsert to Submitted
    existing = conn.execute(
        "SELECT id FROM grade_submissions WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
        (subject_id, section_id, semester, quarter)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE grade_submissions SET status='Submitted', teacher_id=?, submitted_at=datetime('now'), updated_at=datetime('now') WHERE subject_id=? AND section_id=? AND semester=? AND quarter=?",
            (tid, subject_id, section_id, semester, quarter)
        )
    else:
        conn.execute(
            "INSERT INTO grade_submissions (teacher_id,subject_id,section_id,semester,quarter,status,submitted_at) VALUES (?,?,?,?,?,'Submitted',datetime('now'))",
            (tid, subject_id, section_id, semester, quarter)
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
               COALESCE(NULLIF(sc.semester,''), sub.semester) AS sem,
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
    QUARTERS  = ['1st Term','2nd Term','3rd Term']

    # Submission statuses
    sub_statuses = {}
    if student['sec_id']:
        rows = conn.execute(
            "SELECT subject_id, semester, quarter, status FROM grade_submissions WHERE section_id=?",
            (student['sec_id'],)
        ).fetchall()
        for r in rows:
            sub_statuses[(r['subject_id'], r['semester'] or '', r['quarter'])] = r['status']

    grades_raw = conn.execute(
        "SELECT subject_id, semester, quarter, written_works, performance_tasks, quarterly_assessment FROM grades WHERE student_id=?",
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
    QUARTERS    = ['1st Term', '2nd Term', '3rd Term']

    # Schedule
    schedule = conn.execute("""
        SELECT sc.id, sc.day, sc.time_start, sc.time_end, sc.room,
               sc.subject_id, sc.section_id,
               sub.subject_name, sub.subject_code,
               t.first_name||' '||t.last_name AS teacher_name,
               COALESCE(NULLIF(sc.semester,''), sub.semester) AS sem
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

    males   = [s for s in students if (s['gender'] or '').upper() == 'MALE']
    females = [s for s in students if (s['gender'] or '').upper() == 'FEMALE']
    others  = [s for s in students if (s['gender'] or '').upper() not in ('MALE','FEMALE')]

    conn.close()
    return render_template('teacher_subject_detail.html',
                           subject=subject, section=section,
                           students=students, schedule=schedule,
                           males=males, females=females, others=others)


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

    # Fetch all schedule rows — group by subject, collect all teachers+schedules
    all_rows = conn.execute("""
        SELECT sc.subject_id, sub.subject_name, sub.subject_code,
               COALESCE(sc.semester, sub.semester) AS semester,
               t.id AS teacher_id, t.first_name, t.last_name, t.email AS teacher_email,
               sc.day, sc.time_start, sc.time_end, sc.room
        FROM schedules sc
        JOIN subjects sub ON sc.subject_id=sub.id
        JOIN teachers t   ON sc.teacher_id=t.id
        WHERE sc.section_id=?
        ORDER BY sub.subject_name, sc.semester,
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
                'id':           sub_id,
                'subject_name': r['subject_name'],
                'subject_code': r['subject_code'],
                'semester':     r['semester'] or '',
                'teachers':     OrderedDict(),  # teacher_id -> {name, email, schedules}
            }
        sub = subjects_dict[sub_id]
        # Collect teacher info (deduplicated by teacher_id)
        tid = r['teacher_id']
        if tid not in sub['teachers']:
            sub['teachers'][tid] = {
                'first_name': r['first_name'],
                'last_name':  r['last_name'],
                'email':      r['teacher_email'],
                'schedules':  [],
                '_seen':      set(),
            }
        # Add schedule slot under the correct teacher, deduplicated
        slot_key = (r['day'], r['time_start'], r['time_end'])
        if slot_key not in sub['teachers'][tid]['_seen']:
            sub['teachers'][tid]['_seen'].add(slot_key)
            sub['teachers'][tid]['schedules'].append({
                'day':        r['day'],
                'time_start': r['time_start'],
                'time_end':   r['time_end'],
                'room':       r['room'],
            })

    # Clean up helper sets and build cards
    cards = []
    for i, (sub_id, sub) in enumerate(subjects_dict.items()):
        teachers = []
        for tid, t in sub['teachers'].items():
            del t['_seen']
            initials = (t['first_name'][0] + t['last_name'][0]).upper()
            t['initials'] = initials
            teachers.append(t)
        sub['teachers'] = teachers
        # Card initials = first teacher's initials
        card_initials = teachers[0]['initials'] if teachers else '?'
        cards.append({'sub': sub, 'color': COLORS[i % len(COLORS)], 'initials': card_initials})
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


# ══════════════════════════════════════════════════════════════
# ── ATTENDANCE MODULE ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════

def attendance_summary(conn, event_id):
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM attendance_records WHERE event_id=? GROUP BY status",
        (event_id,)
    ).fetchall()
    s = {'Present':0,'Absent':0,'Excused':0,'Late':0}
    for r in rows:
        s[r['status']] = r['cnt']
    return s


@app.route('/attendance')
@login_required
def attendance_home():
    conn = get_db()
    events = conn.execute(
        "SELECT ae.*, sec.section_name, sub.subject_name,"
        " t.first_name||' '||t.last_name AS teacher_name,"
        " ac.name AS category_name, ac.color AS category_color, ac.icon AS category_icon"
        " FROM attendance_events ae"
        " LEFT JOIN sections sec ON ae.section_id=sec.id"
        " LEFT JOIN subjects sub ON ae.subject_id=sub.id"
        " LEFT JOIN teachers t ON ae.teacher_id=t.id"
        " LEFT JOIN attendance_categories ac ON ae.category_id=ac.id"
        " ORDER BY ae.event_date DESC, ae.id DESC"
    ).fetchall()
    sections      = conn.execute("SELECT id,section_name,grade_level FROM sections ORDER BY grade_level,section_name").fetchall()
    subjects      = conn.execute("SELECT id,subject_name,subject_code FROM subjects ORDER BY subject_name").fetchall()
    teachers      = conn.execute("SELECT id,first_name,last_name FROM teachers ORDER BY last_name").fetchall()
    categories    = conn.execute("SELECT * FROM attendance_categories ORDER BY name").fetchall()
    organizations = conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()
    all_students  = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name"
        " FROM students WHERE enrollment_status='Enrolled' ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return render_template('attendance_home.html', events=events,
                           sections=sections, subjects=subjects, teachers=teachers,
                           all_students=all_students, categories=categories,
                           organizations=organizations)



@app.route('/attendance/create', methods=['POST'])
@login_required
def create_attendance_event():
    d = request.form
    conn = get_db()
    try:
        late_mins = int(d.get('late_allowance_minutes') or 0)
    except (ValueError, TypeError):
        late_mins = 0
    is_compulsory      = 1 if d.get('is_compulsory','1') == '1' else 0
    recorded_scope     = d.get('recorded_scope', 'all')
    attendee_positions = ','.join(request.form.getlist('attendee_positions')) or None
    attendee_org_ids   = ','.join(request.form.getlist('attendee_org_ids'))   or None
    conn.execute(
        "INSERT INTO attendance_events"
        " (title,event_type,event_date,time_start,time_end,late_allowance_minutes,"
        "  is_compulsory,recorded_scope,attendee_positions,attendee_org_ids,"
        "  description,category_id,section_id,subject_id,authorized_type,authorized_id,created_by)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d['title'].strip(), d['event_type'], d['event_date'],
         d.get('time_start','').strip() or None,
         d.get('time_end','').strip() or None,
         late_mins, is_compulsory, recorded_scope, attendee_positions, attendee_org_ids,
         d.get('description','').strip() or None,
         d.get('category_id') or None,
         d.get('section_id') or None, d.get('subject_id') or None,
         d.get('authorized_type','teacher'),
         d.get('authorized_id') or None,
         session.get('admin_name','Admin'))
    )
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Save authorized persons (multiple teachers and/or students)
    for person_id in request.form.getlist('authorized_teacher_ids'):
        if person_id:
            try:
                conn.execute("INSERT OR IGNORE INTO attendance_authorized (event_id,person_type,person_id) VALUES (?,?,?)", (eid,'teacher',int(person_id)))
            except Exception: pass
    for person_id in request.form.getlist('authorized_student_ids'):
        if person_id:
            try:
                conn.execute("INSERT OR IGNORE INTO attendance_authorized (event_id,person_type,person_id) VALUES (?,?,?)", (eid,'student',int(person_id)))
            except Exception: pass
    conn.commit(); conn.close()
    flash('Attendance event created.', 'success')
    return redirect(url_for('attendance_home'))


@app.route('/attendance/event/<int:eid>')
@login_required
def attendance_event(eid):
    conn = get_db()
    event = conn.execute(
        "SELECT ae.*, sec.section_name, sec.grade_level, sub.subject_name, sub.subject_code, "
        "t.first_name||\' \'||t.last_name AS teacher_name "
        "FROM attendance_events ae "
        "LEFT JOIN sections sec ON ae.section_id=sec.id "
        "LEFT JOIN subjects sub ON ae.subject_id=sub.id "
        "LEFT JOIN teachers t ON ae.teacher_id=t.id "
        "WHERE ae.id=?", (eid,)
    ).fetchone()
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('attendance_home'))
    scope = (event['recorded_scope'] if 'recorded_scope' in event.keys() else None) or 'all'

    if scope == 'by_position':
        pos_str  = event['attendee_positions'] if 'attendee_positions' in event.keys() else None
        pos_list = [p.strip() for p in (pos_str or '').split(',') if p.strip()]
        if pos_list:
            ph = ','.join('?' * len(pos_list))
            pos_rows = conn.execute(
                f"SELECT DISTINCT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
                f" sec.section_name, op.position_name, o.name AS org_name"
                f" FROM org_members om"
                f" JOIN students s ON om.student_id=s.id"
                f" JOIN org_positions op ON om.position_id=op.id"
                f" JOIN organizations o ON om.org_id=o.id"
                f" LEFT JOIN sections sec ON s.section_id=sec.id"
                f" WHERE op.position_name IN ({ph}) AND om.is_active=1"
                f" AND s.enrollment_status='Enrolled'"
                f" ORDER BY s.last_name, s.first_name", pos_list
            ).fetchall()
            students = [dict(r, id=int(r['id'])) for r in pos_rows]
        else:
            students = []
    elif scope == 'authorized_only':
        # Only the students listed in attendance_authorized for this event
        # Use subquery to avoid duplicate rows from multiple org memberships
        auth_rows = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
            " sec.section_name"
            " FROM attendance_authorized aa"
            " JOIN students s ON aa.person_id=s.id"
            " LEFT JOIN sections sec ON s.section_id=sec.id"
            " WHERE aa.event_id=? AND aa.person_type=\'student\'"
            " ORDER BY s.last_name, s.first_name", (eid,)
        ).fetchall()
        # For each authorized student, get their most relevant position (prefer govt over section)
        students_list = []
        for row in auth_rows:
            pos_row = conn.execute(
                "SELECT op.position_name, o.name AS org_name"
                " FROM org_members om"
                " JOIN org_positions op ON om.position_id=op.id"
                " JOIN organizations o ON om.org_id=o.id"
                " WHERE om.student_id=? AND om.is_active=1"
                " ORDER BY CASE o.org_type WHEN \'government\' THEN 0 WHEN \'section\' THEN 2 ELSE 1 END"
                " LIMIT 1", (row['id'],)
            ).fetchone()
            students_list.append({
                'id':           int(row['id']),
                'student_id':   row['student_id'],
                'first_name':   row['first_name'],
                'last_name':    row['last_name'],
                'middle_name':  row['middle_name'],
                'gender':       row['gender'],
                'section_name': row['section_name'],
                'position_name': pos_row['position_name'] if pos_row else '',
                'org_name':     pos_row['org_name'] if pos_row else '',
            })
        students = students_list
    elif event['event_type'] == 'school':
        rows = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
            " sec.section_name"
            " FROM students s LEFT JOIN sections sec ON s.section_id=sec.id"
            " WHERE s.enrollment_status=\'Enrolled\' ORDER BY s.last_name, s.first_name"
        ).fetchall()
        students = [dict(r, position_name='', org_name='') for r in rows]
    else:
        rows = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
            " sec.section_name"
            " FROM students s LEFT JOIN sections sec ON s.section_id=sec.id"
            " WHERE s.section_id=? AND s.enrollment_status=\'Enrolled\'"
            " ORDER BY s.last_name, s.first_name", (event['section_id'],)
        ).fetchall()
        students = [dict(r, position_name='', org_name='') for r in rows]

    records    = conn.execute(
        "SELECT student_id, status, note FROM attendance_records WHERE event_id=?", (eid,)
    ).fetchall()
    record_map = {int(r['student_id']): dict(r) for r in records}
    summary    = attendance_summary(conn, eid)
    authorized = conn.execute(
        "SELECT person_type, person_id FROM attendance_authorized WHERE event_id=?", (eid,)
    ).fetchall()
    conn.close()
    def get_gender(s):
        try: return (s['gender'] or '').upper()
        except (KeyError, IndexError): return (getattr(s, 'gender', '') or '').upper()
    males   = [s for s in students if get_gender(s) == 'MALE']
    females = [s for s in students if get_gender(s) == 'FEMALE']
    others  = [s for s in students if get_gender(s) not in ('MALE','FEMALE')]
    # Compute display stats scoped to the attendee list
    if scope in ('by_position', 'authorized_only'):
        sp = se = sq = sl = 0
        for st in students:
            rec = record_map.get(int(st['id']) if isinstance(st, dict) else st.id)
            if rec:
                s = rec['status'] if isinstance(rec, dict) else rec.status
                if s == 'Present':  sp += 1
                elif s == 'Absent': se += 1
                elif s == 'Excused': sq += 1
                elif s == 'Late':   sl += 1
            else:
                se += 1  # unscanned = absent
        stat_total   = len(students)
        stat_present = sp
        stat_absent  = se
        stat_excused = sq
        stat_late    = sl
    else:
        stat_total   = summary['Present'] + summary['Absent'] + summary['Excused'] + summary['Late']
        stat_present = summary['Present']
        stat_absent  = summary['Absent']
        stat_excused = summary['Excused']
        stat_late    = summary['Late']

    return render_template('attendance_event.html', event=event, scope=scope,
                           students=students, males=males, females=females, others=others,
                           record_map=record_map, summary=summary, authorized=authorized,
                           stat_total=stat_total, stat_present=stat_present,
                           stat_absent=stat_absent, stat_excused=stat_excused,
                           stat_late=stat_late)


@app.route('/attendance/event/<int:eid>/close', methods=['POST'])
@login_required
def close_attendance_event(eid):
    """Mark all unscanned attendees as Absent and lock the event."""
    conn = get_db()
    event = conn.execute(
        "SELECT scope, recorded_scope, attendee_positions, attendee_org_ids FROM attendance_events WHERE id=?", (eid,)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Event not found'}), 404

    scope    = (event['recorded_scope'] if 'recorded_scope' in event.keys() else None) or 'all'
    pos_str  = event['attendee_positions'] if 'attendee_positions' in event.keys() else None
    oid_str  = event['attendee_org_ids']   if 'attendee_org_ids'   in event.keys() else None
    pos_list = [p.strip() for p in (pos_str or '').split(',') if p.strip()]
    oid_list = [o.strip() for o in (oid_str or '').split(',') if o.strip()]

    if scope == 'by_position' and pos_list:
        ph = ','.join('?' * len(pos_list))
        students = conn.execute(
            f"SELECT DISTINCT s.id FROM org_members om"
            f" JOIN students s ON om.student_id=s.id"
            f" JOIN org_positions op ON om.position_id=op.id"
            f" WHERE op.position_name IN ({ph}) AND om.is_active=1"
            f" AND s.enrollment_status='Enrolled'", pos_list
        ).fetchall()
    elif scope == 'all':
        students = conn.execute(
            "SELECT id FROM students WHERE enrollment_status='Enrolled'"
        ).fetchall()
    else:
        students = []

    marked = 0
    for s in students:
        existing = conn.execute(
            "SELECT id FROM attendance_records WHERE event_id=? AND student_id=?", (eid, s['id'])
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO attendance_records (event_id,student_id,status) VALUES (?,?,?)",
                (eid, s['id'], 'Absent')
            )
            marked += 1
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'marked_absent': marked})


@app.route('/attendance/event/<int:eid>/save', methods=['POST'])
@login_required
def save_attendance(eid):
    d = request.get_json(force=True) or {}
    conn = get_db()
    for rec in d.get('records', []):
        sid = rec.get('student_id')
        status = rec.get('status', 'Present')
        note = (rec.get('note') or '').strip() or None
        if not sid or status not in ('Present','Absent','Excused','Late'):
            continue
        conn.execute(
            "INSERT INTO attendance_records (event_id,student_id,status,note) VALUES (?,?,?,?) "
            "ON CONFLICT(event_id,student_id) DO UPDATE SET "
            "status=excluded.status,note=excluded.note,recorded_at=datetime(\'now\')",
            (eid, sid, status, note)
        )
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/attendance/event/<int:eid>/scan', methods=['POST'])
@login_required
def scan_attendance(eid):
    from datetime import datetime, timedelta
    d = request.get_json(force=True) or {}
    sid_str = (d.get('student_id') or '').strip()
    conn = get_db()

    # Get event details for time-based auto status and scope
    event = conn.execute(
        "SELECT time_start, late_allowance_minutes, recorded_scope, attendee_positions, attendee_org_ids FROM attendance_events WHERE id=?", (eid,)
    ).fetchone()

    student = conn.execute(
        "SELECT id, first_name, last_name, middle_name FROM students WHERE student_id=?", (sid_str,)
    ).fetchone()
    if not student:
        conn.close()
        return jsonify({'ok': False, 'error': f'Student ID "{sid_str}" not found.'})

    # Scope check: restrict scanning based on recorded_scope
    scope_val = (event['recorded_scope'] if 'recorded_scope' in event.keys() else None) or 'all'
    if scope_val == 'by_position':
        pos_str  = event['attendee_positions'] if 'attendee_positions' in event.keys() else None
        oid_str  = event['attendee_org_ids']   if 'attendee_org_ids'   in event.keys() else None
        pos_list = [p.strip() for p in (pos_str or '').split(',') if p.strip()]
        oid_list = [o.strip() for o in (oid_str or '').split(',') if o.strip()]
        if pos_list:
            ph = ','.join('?' * len(pos_list))
            on_list = conn.execute(
                f"SELECT 1 FROM org_members om"
                f" JOIN org_positions op ON om.position_id=op.id"
                f" WHERE om.student_id=? AND om.is_active=1 AND op.position_name IN ({ph})",
                [student['id']] + pos_list
            ).fetchone()
            if not on_list:
                conn.close()
                mn = clean_middle_name(student['middle_name'] or '')
                mi = f' {mn[0].upper()}.' if mn else ''
                name = f"{student['last_name']}, {student['first_name']}{mi}"
                return jsonify({'ok': False, 'not_authorized': True,
                                'error': f'{name} does not hold any of the required positions for this event.'})
    if False and event and event['recorded_scope'] == 'authorized_only':
        is_auth = conn.execute(
            "SELECT 1 FROM attendance_authorized"
            " WHERE event_id=? AND person_type='student' AND person_id=?",
            (eid, student['id'])
        ).fetchone()
        if not is_auth:
            conn.close()
            mn = clean_middle_name(student['middle_name'] or '')
            mi = f' {mn[0].upper()}.' if mn else ''
            name = f"{student['last_name']}, {student['first_name']}{mi}"
            return jsonify({'ok': False, 'not_authorized': True,
                            'error': f'{name} is not on the attendee list for this event.'})

    # Auto-determine status from current time
    status = 'Present'
    time_info = ''
    if event and event['time_start']:
        try:
            now         = datetime.now()
            time_start  = datetime.strptime(event['time_start'], '%H:%M').replace(
                              year=now.year, month=now.month, day=now.day)
            allowance   = int(event['late_allowance_minutes'] or 0)
            cutoff      = time_start + timedelta(minutes=allowance)
            if now > cutoff:
                status = 'Late'
            time_info = f'{now.strftime("%I:%M %p")}'
        except Exception:
            pass

    conn.execute(
        "INSERT INTO attendance_records (event_id,student_id,status) VALUES (?,?,?) "
        "ON CONFLICT(event_id,student_id) DO UPDATE SET "
        "status=excluded.status,recorded_at=datetime(\'now\')",
        (eid, student['id'], status)
    )
    conn.commit(); conn.close()

    mn = clean_middle_name((student['middle_name'] or ''))
    mi = f' {mn[0].upper()}.' if mn else ''
    full_name = f"{student['last_name']}, {student['first_name']}{mi}"
    return jsonify({'ok': True, 'name': full_name, 'status': status,
                   'time_info': time_info, 'student_db_id': student['id']})


@app.route('/attendance/event/<int:eid>/delete', methods=['POST'])
@login_required
def delete_attendance_event(eid):
    conn = get_db()
    conn.execute("DELETE FROM attendance_events WHERE id=?", (eid,))
    conn.commit(); conn.close()
    flash('Attendance event deleted.', 'success')
    return redirect(url_for('attendance_home'))


# ── TEACHER: Class attendance ──

@app.route('/teacher/attendance')
@teacher_required
def teacher_attendance_home():
    tid  = session['teacher_id']
    conn = get_db()
    assignments = conn.execute(
        "SELECT DISTINCT sc.section_id, sc.subject_id, "
        "sec.section_name, sec.grade_level, sub.subject_name, sub.subject_code, "
        "(SELECT COUNT(*) FROM students s WHERE s.section_id=sc.section_id AND s.enrollment_status=\'Enrolled\') AS student_count, "
        "(SELECT COUNT(*) FROM attendance_events ae WHERE ae.section_id=sc.section_id AND ae.subject_id=sc.subject_id AND ae.teacher_id=?) AS event_count "
        "FROM schedules sc "
        "JOIN sections sec ON sc.section_id=sec.id "
        "JOIN subjects sub ON sc.subject_id=sub.id "
        "WHERE sc.teacher_id=? ORDER BY sec.grade_level, sec.section_name, sub.subject_name",
        (tid, tid)
    ).fetchall()
    conn.close()
    return render_template('teacher_attendance_home.html', assignments=assignments)


@app.route('/teacher/attendance/section/<int:sec_id>/subject/<int:sub_id>')
@teacher_required
def teacher_attendance_sheet(sec_id, sub_id):
    tid  = session['teacher_id']
    conn = get_db()
    # Verify this teacher teaches this section+subject
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, sec_id, sub_id)
    ).fetchone()
    if not assigned:
        flash('Not authorized.', 'danger')
        return redirect(url_for('teacher_attendance_home'))
    section = conn.execute("SELECT * FROM sections WHERE id=?", (sec_id,)).fetchone()
    subject = conn.execute("SELECT * FROM subjects WHERE id=?", (sub_id,)).fetchone()
    # All enrolled students in this section
    students = conn.execute(
        "SELECT id, student_id, first_name, last_name, middle_name, gender "
        "FROM students WHERE section_id=? AND enrollment_status=\'Enrolled\' "
        "ORDER BY last_name, first_name", (sec_id,)
    ).fetchall()
    # All attendance events for this section+subject by this teacher, ordered by date
    events = conn.execute(
        "SELECT id, title, event_date, time_start, late_allowance_minutes "
        "FROM attendance_events "
        "WHERE section_id=? AND subject_id=? AND teacher_id=? AND event_type=\'class\' "
        "ORDER BY event_date ASC, id ASC",
        (sec_id, sub_id, tid)
    ).fetchall()
    # All attendance records for these events
    event_ids = [e['id'] for e in events]
    records = {}
    if event_ids:
        placeholders = ','.join('?' * len(event_ids))
        rows = conn.execute(
            f"SELECT event_id, student_id, status FROM attendance_records "
            f"WHERE event_id IN ({placeholders})", event_ids
        ).fetchall()
        for r in rows:
            records[(r['event_id'], r['student_id'])] = r['status']
    conn.close()
    return render_template('teacher_attendance_sheet.html',
                           section=section, subject=subject,
                           students=students, events=events, records=records,
                           sec_id=sec_id, sub_id=sub_id)


@app.route('/teacher/attendance/section/<int:sec_id>/subject/<int:sub_id>/add_event', methods=['POST'])
@teacher_required
def teacher_add_attendance_event(sec_id, sub_id):
    tid = session['teacher_id']
    d   = request.form
    conn = get_db()
    assigned = conn.execute(
        "SELECT id FROM schedules WHERE teacher_id=? AND section_id=? AND subject_id=?",
        (tid, sec_id, sub_id)
    ).fetchone()
    if not assigned:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403
    try:
        late_mins = int(d.get('late_allowance_minutes') or 0)
    except (ValueError, TypeError):
        late_mins = 0
    conn.execute(
        "INSERT INTO attendance_events (title,event_type,event_date,time_start,time_end,"
        "late_allowance_minutes,section_id,subject_id,teacher_id,created_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d['title'].strip(), 'class', d['event_date'],
         d.get('time_start','').strip() or None,
         d.get('time_end','').strip() or None,
         late_mins, sec_id, sub_id, tid,
         session.get('teacher_name','Teacher'))
    )
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'event_id': eid})


@app.route('/teacher/attendance/event/<int:eid>/set_status', methods=['POST'])
@teacher_required
def teacher_set_status(eid):
    tid = session['teacher_id']
    d   = request.get_json(force=True) or {}
    student_id = d.get('student_id')
    status     = d.get('status')
    if status not in ('Present','Absent','Excused','Late'):
        return jsonify({'ok': False, 'error': 'Invalid status'}), 400
    conn = get_db()
    event = conn.execute(
        "SELECT id FROM attendance_events WHERE id=? AND teacher_id=?", (eid, tid)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403
    conn.execute(
        "INSERT INTO attendance_records (event_id,student_id,status) VALUES (?,?,?) "
        "ON CONFLICT(event_id,student_id) DO UPDATE SET "
        "status=excluded.status,recorded_at=datetime(\'now\')",
        (eid, student_id, status)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/teacher/attendance/event/<int:eid>/delete_event', methods=['POST'])
@teacher_required
def teacher_delete_attendance_event(eid):
    tid = session['teacher_id']
    conn = get_db()
    event = conn.execute(
        "SELECT section_id, subject_id FROM attendance_events WHERE id=? AND teacher_id=?", (eid, tid)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403
    sec_id = event['section_id']
    sub_id = event['subject_id']
    conn.execute("DELETE FROM attendance_events WHERE id=?", (eid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/teacher/attendance/event/<int:eid>')
@teacher_required
def teacher_attendance_event(eid):
    tid  = session['teacher_id']
    conn = get_db()
    # Allow teacher if they own it OR if they are in authorized persons list
    event = conn.execute(
        "SELECT ae.*, sec.section_name, sec.grade_level, sub.subject_name, sub.subject_code "
        "FROM attendance_events ae "
        "LEFT JOIN sections sec ON ae.section_id=sec.id "
        "LEFT JOIN subjects sub ON ae.subject_id=sub.id "
        "WHERE ae.id=? AND ae.event_type=\'class\' "
        "AND (ae.teacher_id=? OR EXISTS("
        "  SELECT 1 FROM attendance_authorized aa "
        "  WHERE aa.event_id=ae.id AND aa.person_type=\'teacher\' AND aa.person_id=?))",
        (eid, tid, tid)
    ).fetchone()
    if not event:
        flash('Event not found or not authorized.', 'danger')
        return redirect(url_for('teacher_attendance_home'))
    students = conn.execute(
        "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender "
        "FROM students s WHERE s.section_id=? AND s.enrollment_status=\'Enrolled\' "
        "ORDER BY s.last_name, s.first_name", (event['section_id'],)
    ).fetchall()
    records = conn.execute(
        "SELECT student_id, status, note FROM attendance_records WHERE event_id=?", (eid,)
    ).fetchall()
    record_map  = {r['student_id']: r for r in records}
    summary     = attendance_summary(conn, eid)
    authorized  = conn.execute(
        "SELECT person_type, person_id FROM attendance_authorized WHERE event_id=?", (eid,)
    ).fetchall()
    conn.close()
    return render_template('teacher_attendance_event.html', event=event,
                           students=students, record_map=record_map,
                           summary=summary, authorized=authorized)


@app.route('/teacher/attendance/event/<int:eid>/scan', methods=['POST'])
@teacher_required
def teacher_scan_attendance(eid):
    from datetime import datetime, timedelta
    tid  = session['teacher_id']
    d    = request.get_json(force=True) or {}
    sid_str = (d.get('student_id') or '').strip()
    conn = get_db()
    event = conn.execute(
        "SELECT time_start, late_allowance_minutes, section_id FROM attendance_events WHERE id=?", (eid,)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Event not found.'})
    student = conn.execute(
        "SELECT id, first_name, last_name, middle_name FROM students WHERE student_id=?", (sid_str,)
    ).fetchone()
    if not student:
        conn.close()
        return jsonify({'ok': False, 'error': f'Student ID "{sid_str}" not found.'})
    # Auto-determine status
    status = 'Present'
    time_info = ''
    if event['time_start']:
        try:
            now        = datetime.now()
            time_start = datetime.strptime(event['time_start'], '%H:%M').replace(
                             year=now.year, month=now.month, day=now.day)
            allowance  = int(event['late_allowance_minutes'] or 0)
            cutoff     = time_start + timedelta(minutes=allowance)
            if now > cutoff:
                status = 'Late'
            time_info = now.strftime('%I:%M %p')
        except Exception:
            pass
    conn.execute(
        "INSERT INTO attendance_records (event_id,student_id,status) VALUES (?,?,?) "
        "ON CONFLICT(event_id,student_id) DO UPDATE SET "
        "status=excluded.status,recorded_at=datetime(\'now\')",
        (eid, student['id'], status)
    )
    conn.commit(); conn.close()
    mn = clean_middle_name(student['middle_name'] or '')
    mi = f' {mn[0].upper()}.' if mn else ''
    full_name = f"{student['last_name']}, {student['first_name']}{mi}"
    return jsonify({'ok': True, 'name': full_name, 'status': status,
                   'time_info': time_info, 'student_db_id': student['id']})


@app.route('/teacher/attendance/event/<int:eid>/save', methods=['POST'])
@teacher_required
def teacher_save_attendance(eid):
    tid  = session['teacher_id']
    conn = get_db()
    event = conn.execute(
        "SELECT id FROM attendance_events WHERE id=? AND teacher_id=?", (eid, tid)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized'}), 403
    d = request.get_json(force=True) or {}
    for rec in d.get('records', []):
        sid = rec.get('student_id')
        status = rec.get('status', 'Present')
        note = (rec.get('note') or '').strip() or None
        if not sid or status not in ('Present','Absent','Excused','Late'):
            continue
        conn.execute(
            "INSERT INTO attendance_records (event_id,student_id,status,note) VALUES (?,?,?,?) "
            "ON CONFLICT(event_id,student_id) DO UPDATE SET "
            "status=excluded.status,note=excluded.note,recorded_at=datetime(\'now\')",
            (eid, sid, status, note)
        )
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/teacher/attendance/event/<int:eid>/delete', methods=['POST'])
@teacher_required
def teacher_delete_attendance(eid):
    tid = session['teacher_id']
    conn = get_db()
    conn.execute("DELETE FROM attendance_events WHERE id=? AND teacher_id=?", (eid, tid))
    conn.commit(); conn.close()
    flash('Attendance record deleted.', 'success')
    return redirect(url_for('teacher_attendance_home'))


# ── STUDENT: View attendance ──

@app.route('/student/attendance/event/<int:eid>/take')
@student_required
def student_take_attendance(eid):
    from datetime import datetime, timedelta
    sid = session['student_session_id']
    conn = get_db()
    authorized = conn.execute(
        "SELECT 1 FROM attendance_authorized WHERE event_id=? AND person_type=\'student\' AND person_id=?",
        (eid, sid)
    ).fetchone()
    event = conn.execute(
        "SELECT ae.*, ac.name AS category_name, ac.color AS category_color, ac.icon AS category_icon "
        "FROM attendance_events ae "
        "LEFT JOIN attendance_categories ac ON ae.category_id=ac.id "
        "WHERE ae.id=? AND ae.event_type=\'school\'", (eid,)
    ).fetchone()
    if not event or not authorized:
        flash('You are not authorized to take attendance for this event.', 'danger')
        conn.close()
        return redirect(url_for('student_attendance'))
    from datetime import datetime as _dt2
    now_hm = _dt2.now().strftime('%H:%M')
    event_closed = bool(event['time_end'] and now_hm > event['time_end'])
    if event['recorded_scope'] == 'all':
        students = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
            " sec.section_name FROM students s "
            "LEFT JOIN sections sec ON s.section_id=sec.id "
            "WHERE s.enrollment_status=\'Enrolled\' ORDER BY s.last_name, s.first_name"
        ).fetchall()
    elif event['recorded_scope'] == 'authorized_only':
        students = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
            " sec.section_name FROM attendance_authorized aa"
            " JOIN students s ON aa.person_id=s.id"
            " LEFT JOIN sections sec ON s.section_id=sec.id"
            " WHERE aa.event_id=? AND aa.person_type=\'student\'"
            " ORDER BY s.last_name, s.first_name", (eid,)
        ).fetchall()
    else:
        students = []
    records = conn.execute(
        "SELECT student_id, status, note FROM attendance_records WHERE event_id=?", (eid,)
    ).fetchall()
    record_map = {r['student_id']: r for r in records}
    summary = attendance_summary(conn, eid)
    conn.close()
    return render_template('student_take_attendance.html', event=event,
                           students=students, record_map=record_map, summary=summary,
                           event_closed=event_closed)


@app.route('/student/attendance/event/<int:eid>/scan', methods=['POST'])
@student_required
def student_scan_attendance(eid):
    from datetime import datetime, timedelta
    sid = session['student_session_id']
    d   = request.get_json(force=True) or {}
    sid_str = (d.get('student_id') or '').strip()
    conn = get_db()
    authorized = conn.execute(
        "SELECT 1 FROM attendance_authorized WHERE event_id=? AND person_type=\'student\' AND person_id=?",
        (eid, sid)
    ).fetchone()
    event = conn.execute(
        "SELECT time_start, time_end, late_allowance_minutes, recorded_scope, attendee_positions, attendee_org_ids FROM attendance_events WHERE id=?", (eid,)
    ).fetchone()
    if not authorized or not event:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized.'}), 403
    from datetime import datetime as _dt3
    if event['time_end']:
        if _dt3.now().strftime('%H:%M') > event['time_end']:
            conn.close()
            return jsonify({'ok': False, 'error': f'This event ended at {event["time_end"]}. Scanning is closed.'})
    student = conn.execute(
        "SELECT id, first_name, last_name, middle_name FROM students WHERE student_id=?", (sid_str,)
    ).fetchone()
    if not student:
        conn.close()
        return jsonify({'ok': False, 'error': f'Student ID "{sid_str}" not found.'})
    status = 'Present'
    time_info = ''
    if event['time_start']:
        try:
            now = datetime.now()
            ts  = datetime.strptime(event['time_start'], '%H:%M').replace(year=now.year, month=now.month, day=now.day)
            cutoff = ts + timedelta(minutes=int(event['late_allowance_minutes'] or 0))
            if now > cutoff: status = 'Late'
            time_info = now.strftime('%I:%M %p')
        except Exception:
            pass
    conn.execute(
        "INSERT INTO attendance_records (event_id,student_id,status) VALUES (?,?,?)"
        " ON CONFLICT(event_id,student_id) DO UPDATE SET status=excluded.status,recorded_at=datetime(\'now\')",
        (eid, student['id'], status)
    )
    conn.commit(); conn.close()
    mn = clean_middle_name(student['middle_name'] or '')
    mi = f' {mn[0].upper()}.' if mn else ''
    return jsonify({'ok': True, 'name': f"{student['last_name']}, {student['first_name']}{mi}",
                   'status': status, 'time_info': time_info, 'student_db_id': student['id']})


@app.route('/student/attendance/event/<int:eid>/save_auth', methods=['POST'])
@student_required
def student_save_attendance_authorized(eid):
    sid = session['student_session_id']
    d   = request.get_json(force=True) or {}
    conn = get_db()
    authorized = conn.execute(
        "SELECT 1 FROM attendance_authorized WHERE event_id=? AND person_type=\'student\' AND person_id=?",
        (eid, sid)
    ).fetchone()
    if not authorized:
        conn.close()
        return jsonify({'ok': False, 'error': 'Not authorized.'}), 403
    for rec in d.get('records', []):
        s = rec.get('student_id')
        status = rec.get('status', 'Present')
        note   = (rec.get('note') or '').strip() or None
        if not s or status not in ('Present','Absent','Excused','Late'): continue
        conn.execute(
            "INSERT INTO attendance_records (event_id,student_id,status,note) VALUES (?,?,?,?)"
            " ON CONFLICT(event_id,student_id) DO UPDATE SET status=excluded.status,note=excluded.note,recorded_at=datetime(\'now\')",
            (eid, s, status, note)
        )
    conn.commit(); conn.close()
    return jsonify({'ok': True})


# ── SSG Secretary General attendance management ──────────────

def ssg_secretary_required(f):
    """Decorator: only SSG Secretary General students can access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_secretary_general'):
            flash('Access restricted to SSG Secretary General.', 'danger')
            return redirect(url_for('student_attendance'))
        return f(*args, **kwargs)
    return decorated


@app.route('/student/attendance/categories')
@student_required
@ssg_secretary_required
def ssg_attendance_categories():
    conn = get_db()
    sid = session['student_session_id']
    # Own categories + admin-shared categories
    categories = conn.execute(
        "SELECT * FROM attendance_categories ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template('ssg_attendance_categories.html', categories=categories)


@app.route('/student/attendance/categories/add', methods=['POST'])
@student_required
@ssg_secretary_required
def ssg_add_attendance_category():
    d = request.form
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO attendance_categories (name,description,color,icon,created_by_student)"
            " VALUES (?,?,?,?,?)",
            (d['name'].strip(), d.get('description','').strip() or None,
             d.get('color','#3b82f6'), d.get('icon','🎯'),
             session['student_session_id'])
        )
        conn.commit()
        flash('Category created.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('ssg_attendance_categories'))


@app.route('/student/attendance/events/create', methods=['GET','POST'])
@student_required
@ssg_secretary_required
def ssg_create_attendance_event():
    conn = get_db()
    sid = session['student_session_id']
    if request.method == 'POST':
        d = request.form
        try:
            late_mins = int(d.get('late_allowance_minutes') or 0)
        except Exception:
            late_mins = 0
        is_compulsory      = 1 if d.get('is_compulsory','1') == '1' else 0
        recorded_scope     = d.get('recorded_scope', 'all')
        attendee_positions = ','.join(request.form.getlist('attendee_positions')) or None
        attendee_org_ids   = ','.join(request.form.getlist('attendee_org_ids'))   or None
        # Only allow categories created by this student or shared by admin (shared_to_student=1)
        cat_id = d.get('category_id') or None
        if cat_id:
            allowed_cat = conn.execute(
                "SELECT id FROM attendance_categories WHERE id=?"
                " AND (created_by_student=? OR is_shared=1)",
                (cat_id, sid)
            ).fetchone()
            if not allowed_cat:
                flash('You can only use your own categories or shared categories.', 'danger')
                conn.close()
                return redirect(url_for('ssg_create_attendance_event'))
        conn.execute(
            "INSERT INTO attendance_events"
            " (title,event_type,event_date,time_start,time_end,late_allowance_minutes,"
            "  is_compulsory,recorded_scope,attendee_positions,attendee_org_ids,"
            "  description,category_id,created_by)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d['title'].strip(), 'school', d['event_date'],
             d.get('time_start','').strip() or None,
             d.get('time_end','').strip() or None,
             late_mins, is_compulsory, recorded_scope, attendee_positions, attendee_org_ids,
             d.get('description','').strip() or None, cat_id,
             f"SSG:{session['student_name']}")
        )
        eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Save authorized scanners
        for person_id in request.form.getlist('authorized_student_ids'):
            if person_id:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO attendance_authorized (event_id,person_type,person_id) VALUES (?,?,?)",
                        (eid, 'student', int(person_id))
                    )
                except Exception: pass
        conn.commit()
        flash('Attendance event created.', 'success')
        conn.close()
        return redirect(url_for('student_attendance'))
    # GET
    sid_student = session['student_session_id']
    categories = conn.execute(
        "SELECT * FROM attendance_categories WHERE created_by_student=? OR is_shared=1 ORDER BY name",
        (sid_student,)
    ).fetchall()
    all_positions_data = conn.execute(
        "SELECT DISTINCT op.position_name, o.name AS org_name, o.org_type, o.id AS org_id"
        " FROM org_positions op JOIN organizations o ON op.org_id=o.id"
        " ORDER BY o.org_type DESC, op.rank_order, op.position_name"
    ).fetchall()
    conn.close()
    return render_template('ssg_create_event.html', categories=categories,
                           all_positions_data=[dict(r) for r in all_positions_data])


@app.route('/student/attendance')
@student_required
def student_attendance():
    sid = session['student_session_id']
    conn = get_db()
    student = conn.execute("SELECT id, section_id FROM students WHERE id=?", (sid,)).fetchone()
    school_events = conn.execute(
        "SELECT ae.id, ae.title, ae.event_date, ae.description, ae.is_compulsory, ar.status, ar.note "
        "FROM attendance_events ae "
        "LEFT JOIN attendance_records ar ON ar.event_id=ae.id AND ar.student_id=? "
        "WHERE ae.event_type=\'school\' ORDER BY ae.event_date DESC", (sid,)
    ).fetchall()
    class_events = conn.execute(
        "SELECT ae.id, ae.title, ae.event_date, ae.description, "
        "sub.subject_name, sub.subject_code, ar.status, ar.note "
        "FROM attendance_events ae "
        "LEFT JOIN subjects sub ON ae.subject_id=sub.id "
        "LEFT JOIN attendance_records ar ON ar.event_id=ae.id AND ar.student_id=? "
        "WHERE ae.event_type=\'class\' AND ae.section_id=? "
        "ORDER BY ae.event_date DESC",
        (sid, student['section_id'] or -1)
    ).fetchall()
    authorized_events = conn.execute(
        "SELECT ae.id, ae.title, ae.event_date, ae.time_start, ae.time_end "
        "FROM attendance_events ae "
        "JOIN attendance_authorized aa ON aa.event_id=ae.id "
        "WHERE aa.person_type=\'student\' AND aa.person_id=? AND ae.event_type=\'school\' "
        "ORDER BY ae.event_date DESC", (sid,)
    ).fetchall()
    conn.close()
    from datetime import datetime as _dt4
    conn.close()
    return render_template('student_attendance.html',
                           school_events=school_events, class_events=class_events,
                           authorized_events=authorized_events,
                           now_hm=_dt4.now().strftime('%H:%M'))


@app.route('/student/attendance/event/<int:eid>')
@student_required
def student_attendance_event(eid):
    sid = session['student_session_id']
    conn = get_db()
    student = conn.execute("SELECT id, section_id FROM students WHERE id=?", (sid,)).fetchone()
    event = conn.execute(
        "SELECT ae.*, sec.section_name, sub.subject_name, sub.subject_code "
        "FROM attendance_events ae "
        "LEFT JOIN sections sec ON ae.section_id=sec.id "
        "LEFT JOIN subjects sub ON ae.subject_id=sub.id "
        "WHERE ae.id=? AND (ae.event_type=\'school\' OR ae.section_id=?)",
        (eid, student['section_id'] or -1)
    ).fetchone()
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('student_attendance'))
    record = conn.execute(
        "SELECT status, note, recorded_at FROM attendance_records WHERE event_id=? AND student_id=?",
        (eid, sid)
    ).fetchone()
    summary = attendance_summary(conn, eid)
    conn.close()
    return render_template('student_attendance_event.html',
                           event=event, record=record, summary=summary)


# ══════════════════════════════════════════════════════════════
# ── ATTENDANCE CATEGORIES
# ══════════════════════════════════════════════════════════════

@app.route('/attendance/categories')
@login_required
def attendance_categories():
    conn = get_db()
    cats = conn.execute(
        "SELECT ac.*, COUNT(ae.id) AS event_count"
        " FROM attendance_categories ac"
        " LEFT JOIN attendance_events ae ON ae.category_id=ac.id"
        " GROUP BY ac.id ORDER BY ac.name"
    ).fetchall()
    conn.close()
    return render_template('attendance_categories.html', categories=cats)

@app.route('/attendance/categories/add', methods=['POST'])
@login_required
def add_attendance_category():
    d = request.form
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO attendance_categories (name,description,color,icon) VALUES (?,?,?,?)",
            (d['name'].strip(), d.get('description','').strip() or None,
             d.get('color','#6b7280'), d.get('icon','🎯'))
        )
        conn.commit()
        flash('Category added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('attendance_categories'))

@app.route('/attendance/categories/edit/<int:cid>', methods=['POST'])
@login_required
def edit_attendance_category(cid):
    d = request.form
    conn = get_db()
    conn.execute(
        "UPDATE attendance_categories SET name=?,description=?,color=?,icon=? WHERE id=?",
        (d['name'].strip(), d.get('description','').strip() or None,
         d.get('color','#6b7280'), d.get('icon','🎯'), cid)
    )
    conn.commit(); conn.close()
    flash('Category updated.', 'success')
    return redirect(url_for('attendance_categories'))

@app.route('/attendance/categories/share/<int:cid>', methods=['POST'])
@login_required
def share_attendance_category(cid):
    conn = get_db()
    current = conn.execute("SELECT is_shared FROM attendance_categories WHERE id=?", (cid,)).fetchone()
    if current:
        new_val = 0 if current['is_shared'] else 1
        conn.execute("UPDATE attendance_categories SET is_shared=? WHERE id=?", (new_val, cid))
        conn.commit()
        flash('Category ' + ('shared with SSG Secretary General.' if new_val else 'unshared.'), 'success')
    conn.close()
    return redirect(url_for('attendance_categories'))


@app.route('/attendance/categories/delete/<int:cid>', methods=['POST'])
@login_required
def delete_attendance_category(cid):
    conn = get_db()
    conn.execute("DELETE FROM attendance_categories WHERE id=?", (cid,))
    conn.commit(); conn.close()
    flash('Category deleted.', 'success')
    return redirect(url_for('attendance_categories'))

@app.route('/attendance/categories/get/<int:cid>')
@login_required
def get_attendance_category(cid):
    conn = get_db()
    c = conn.execute("SELECT * FROM attendance_categories WHERE id=?", (cid,)).fetchone()
    conn.close()
    return jsonify(dict(c)) if c else (jsonify({}), 404)


# ══════════════════════════════════════════════════════════════
# ── ORGANIZATIONS & POSITIONS
# ══════════════════════════════════════════════════════════════

@app.route('/organizations')
@login_required
def organizations():
    conn = get_db()
    # Auto-create Supreme Student Government with standard + dynamic positions
    auto_create_ssg(conn)

    # Auto-create section officer orgs for all sections
    sections_all = conn.execute("SELECT id, section_name, grade_level FROM sections ORDER BY grade_level, section_name").fetchall()
    for sec in sections_all:
        org_name = f"Section Officers — {sec['section_name']} (Grade {sec['grade_level']})"
        exists = conn.execute("SELECT id FROM organizations WHERE org_type='section' AND name=?", (org_name,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO organizations (name,short_name,org_type,color) VALUES (?,?,?,?)",
                (org_name, sec['section_name'], 'section', '#8b5cf6')
            )
            oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            # Only add standard positions on first creation — never re-add deleted ones
            for rank, pos in enumerate(STANDARD_SECTION_OFFICES_UNIQUE):
                conn.execute("INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)", (oid, pos, rank))
            # Note: 2 people can hold "Protocol Officer" — same position row, 2 org_members entries
        # If already exists, do NOT touch positions
    conn.commit()
    ssg = conn.execute(
        "SELECT o.*, COUNT(DISTINCT om.id) AS member_count"
        " FROM organizations o"
        " LEFT JOIN org_members om ON om.org_id=o.id AND om.is_active=1"
        " WHERE o.org_type='government'"
        " GROUP BY o.id ORDER BY o.name"
    ).fetchall()
    orgs = conn.execute(
        "SELECT o.*, COUNT(DISTINCT om.id) AS member_count"
        " FROM organizations o"
        " LEFT JOIN org_members om ON om.org_id=o.id AND om.is_active=1"
        " WHERE o.org_type NOT IN ('section','government')"
        " GROUP BY o.id ORDER BY o.name"
    ).fetchall()
    section_orgs = conn.execute(
        "SELECT o.*, COUNT(DISTINCT om.id) AS member_count,"
        " s.id AS sec_id, s.grade_level, s.section_name AS sec_name"
        " FROM organizations o"
        " LEFT JOIN org_members om ON om.org_id=o.id AND om.is_active=1"
        " LEFT JOIN sections s ON o.name = ('Section Officers — '||s.section_name||' (Grade '||s.grade_level||')')"
        " WHERE o.org_type='section'"
        " GROUP BY o.id ORDER BY s.grade_level, s.section_name"
    ).fetchall()
    conn.close()
    return render_template('organizations.html', orgs=orgs, section_orgs=section_orgs, ssg=ssg)

@app.route('/organizations/add', methods=['POST'])
@login_required
def add_organization():
    d = request.form
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO organizations (name,short_name,description,org_type,color) VALUES (?,?,?,?,?)",
            (d['name'].strip(), d.get('short_name','').strip() or None,
             d.get('description','').strip() or None,
             d.get('org_type','organization'), d.get('color','#3b82f6'))
        )
        conn.commit()
        flash('Organization added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('organizations'))

@app.route('/organizations/edit/<int:oid>', methods=['POST'])
@login_required
def edit_organization(oid):
    d = request.form
    conn = get_db()
    conn.execute(
        "UPDATE organizations SET name=?,short_name=?,description=?,org_type=?,color=? WHERE id=?",
        (d['name'].strip(), d.get('short_name','').strip() or None,
         d.get('description','').strip() or None,
         d.get('org_type','organization'), d.get('color','#3b82f6'), oid)
    )
    conn.commit(); conn.close()
    flash('Organization updated.', 'success')
    return redirect(url_for('organizations'))

@app.route('/organizations/delete/<int:oid>', methods=['POST'])
@login_required
def delete_organization(oid):
    conn = get_db()
    conn.execute("DELETE FROM organizations WHERE id=?", (oid,))
    conn.commit(); conn.close()
    flash('Organization deleted.', 'success')
    return redirect(url_for('organizations'))

@app.route('/organizations/get/<int:oid>')
@login_required
def get_organization(oid):
    conn = get_db()
    o = conn.execute("SELECT * FROM organizations WHERE id=?", (oid,)).fetchone()
    conn.close()
    return jsonify(dict(o)) if o else (jsonify({}), 404)

@app.route('/organizations/<int:oid>')
@login_required
def organization_detail(oid):
    conn = get_db()
    org = conn.execute("SELECT * FROM organizations WHERE id=?", (oid,)).fetchone()
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('organizations'))
    # Patch SSG positions if viewing the government org
    if org['org_type'] == 'government':
        auto_create_ssg(conn)
        org = conn.execute("SELECT * FROM organizations WHERE id=?", (oid,)).fetchone()

    positions = conn.execute(
        "SELECT op.*, COUNT(om.id) AS member_count"
        " FROM org_positions op"
        " LEFT JOIN org_members om ON om.position_id=op.id AND om.is_active=1"
        " WHERE op.org_id=? GROUP BY op.id ORDER BY op.rank_order, op.position_name",
        (oid,)
    ).fetchall()
    # Pre-group positions for government org view
    exec_positions   = [p for p in positions if p['position_name'] in STANDARD_SSG_OFFICES_NAMES]
    strand_positions = [p for p in positions if p['position_name'].startswith('Strand Governor')]
    grade_positions  = [p for p in positions if p['position_name'].startswith('Grade') and p['position_name'].endswith('Representative')]
    members = conn.execute(
        "SELECT om.id AS member_row_id, om.school_year, om.is_active,"
        " s.id AS student_db_id, s.first_name, s.last_name, s.middle_name,"
        " s.student_id AS sid_code, s.gender,"
        " op.position_name, op.rank_order,"
        " sec.section_name, sec.grade_level"
        " FROM org_members om"
        " JOIN students s ON om.student_id=s.id"
        " LEFT JOIN org_positions op ON om.position_id=op.id"
        " LEFT JOIN sections sec ON s.section_id=sec.id"
        " WHERE om.org_id=? AND om.is_active=1"
        " ORDER BY op.rank_order NULLS LAST, s.last_name, s.first_name",
        (oid,)
    ).fetchall()
    # ── Student eligibility rules ──────────────────────────────
    # Get IDs of students already holding SSG executive positions
    ssg_exec_ids = set()
    ssg_org = conn.execute(
        "SELECT id FROM organizations WHERE org_type='government'", ()
    ).fetchone()
    if ssg_org:
        ssg_exec_rows = conn.execute(
            "SELECT DISTINCT om.student_id FROM org_members om"
            " JOIN org_positions op ON om.position_id=op.id"
            " WHERE om.org_id=? AND om.is_active=1"
            " AND op.position_name IN ({})".format(
                ','.join('?' * len(STANDARD_SSG_OFFICES_NAMES))
            ),
            [ssg_org['id']] + STANDARD_SSG_OFFICES_NAMES
        ).fetchall()
        ssg_exec_ids = {r['student_id'] for r in ssg_exec_rows}

    # Build per-position eligible student lists
    # all_students_base: full enrolled list minus SSG execs (for non-SSG orgs)
    def exclude_ssg(rows):
        return [r for r in rows if r['id'] not in ssg_exec_ids]

    if org['org_type'] == 'government':
        # SSG execs: all enrolled, no restriction (they ARE the execs)
        all_students = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
            " FROM students s WHERE s.enrollment_status='Enrolled'"
            " ORDER BY s.last_name, s.first_name"
        ).fetchall()
        # Strand-scoped lists for strand rep positions
        strand_students = {}
        for sp in strand_positions:
            # Extract strand code from "Strand Representative — STEM (Science...)"
            import re
            m = re.match(r"Strand Governor — (\S+)", sp['position_name'])
            if m:
                scode = m.group(1)
                rows = conn.execute(
                    "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
                    " FROM students s"
                    " JOIN strands st ON s.strand_id=st.id"
                    " WHERE st.strand_code=? AND s.enrollment_status='Enrolled'"
                    " ORDER BY s.last_name, s.first_name", (scode,)
                ).fetchall()
                filtered_s = exclude_ssg(rows)
                strand_students[sp['id']] = filtered_s if filtered_s else list(rows)
            else:
                strand_students[sp['id']] = []
        # Grade-scoped lists for grade rep positions
        grade_students = {}
        for gp in grade_positions:
            import re
            m = re.match(r"Grade (.+) Representative", gp['position_name'])
            if m:
                glevel_num = m.group(1).strip()  # e.g. "11"
                # DB stores grade_level as "Grade 11" or just "11" — match both
                rows = conn.execute(
                    "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
                    " FROM students s"
                    " WHERE (s.grade_level=? OR s.grade_level=?)"
                    " AND s.enrollment_status='Enrolled'"
                    " ORDER BY s.last_name, s.first_name",
                    (glevel_num, f"Grade {glevel_num}")
                ).fetchall()
                filtered_g = exclude_ssg(rows)
                grade_students[gp['id']] = filtered_g if filtered_g else list(rows)
            else:
                grade_students[gp['id']] = []
    elif org['org_type'] == 'section':
        # Section officers: only students in that section, no SSG execs
        linked_section = conn.execute(
            "SELECT s.* FROM sections s"
            " WHERE ('Section Officers — '||s.section_name||' (Grade '||s.grade_level||')') = ?",
            (org['name'],)
        ).fetchone()
        if linked_section:
            rows = conn.execute(
                "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
                " FROM students s WHERE s.section_id=? AND s.enrollment_status='Enrolled'"
                " ORDER BY s.last_name, s.first_name", (linked_section['id'],)
            ).fetchall()
            filtered = exclude_ssg(rows)
            # If SSG exclusion removed everyone, fall back to full list
            all_students = filtered if filtered else list(rows)
        else:
            all_students = exclude_ssg(conn.execute(
                "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
                " FROM students s WHERE s.enrollment_status='Enrolled' ORDER BY s.last_name, s.first_name"
            ).fetchall())
        strand_students = {}
        grade_students  = {}
    else:
        rows = conn.execute(
            "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
            " FROM students s WHERE s.enrollment_status='Enrolled' ORDER BY s.last_name, s.first_name"
        ).fetchall()
        filtered = exclude_ssg(rows)
        all_students = filtered if filtered else list(rows)
        strand_students = {}
        grade_students  = {}

    conn.close()
    return render_template('organization_detail.html', org=org, positions=positions,
                           members=members, all_students=all_students,
                           standard_offices=STANDARD_SECTION_OFFICES_UNIQUE,
                           exec_positions=exec_positions,
                           strand_positions=strand_positions,
                           grade_positions=grade_positions,
                           strand_students=strand_students,
                           grade_students=grade_students,
                           ssg_exec_ids=list(ssg_exec_ids))

@app.route('/organizations/<int:oid>/add_position', methods=['POST'])
@login_required
def add_org_position(oid):
    d = request.form
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
            (oid, d['position_name'].strip(), int(d.get('rank_order') or 0))
        )
        conn.commit()
        flash('Position added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('organization_detail', oid=oid))


@app.route('/organizations/<int:oid>/delete_position/<int:pid>', methods=['POST'])
@login_required
def delete_org_position(oid, pid):
    conn = get_db()
    conn.execute("DELETE FROM org_positions WHERE id=? AND org_id=?", (pid, oid))
    conn.commit(); conn.close()
    flash('Position deleted.', 'success')
    return redirect(url_for('organization_detail', oid=oid))

@app.route('/organizations/<int:oid>/generate_positions', methods=['POST'])
@login_required
def generate_section_positions(oid):
    """Generate standard positions for a single section org (only adds missing ones)."""
    conn = get_db()
    org = conn.execute("SELECT org_type FROM organizations WHERE id=?", (oid,)).fetchone()
    if not org or org['org_type'] != 'section':
        flash('Not a section organization.', 'danger')
        conn.close()
        return redirect(url_for('organizations'))
    added = 0
    for rank, pos in enumerate(STANDARD_SECTION_OFFICES_UNIQUE):
        existing = conn.execute(
            "SELECT id FROM org_positions WHERE org_id=? AND position_name=?", (oid, pos)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
                (oid, pos, rank)
            )
            added += 1
    conn.commit(); conn.close()
    if added:
        flash(f'{added} position(s) generated.', 'success')
    else:
        flash('All standard positions already exist.', 'warning')
    return redirect(url_for('organizations'))


@app.route('/organizations/generate_all_sections', methods=['POST'])
@login_required
def generate_all_section_positions():
    """Generate standard positions for ALL section orgs that are missing them."""
    conn = get_db()
    section_orgs = conn.execute(
        "SELECT id FROM organizations WHERE org_type='section'"
    ).fetchall()
    total_added = 0
    for org in section_orgs:
        oid = org['id']
        for rank, pos in enumerate(STANDARD_SECTION_OFFICES_UNIQUE):
            existing = conn.execute(
                "SELECT id FROM org_positions WHERE org_id=? AND position_name=?", (oid, pos)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
                    (oid, pos, rank)
                )
                total_added += 1
    conn.commit(); conn.close()
    if total_added:
        flash(f'{total_added} position(s) generated across {len(section_orgs)} section(s).', 'success')
    else:
        flash('All sections already have standard positions.', 'warning')
    return redirect(url_for('organizations'))


@app.route('/organizations/delete_all_non_ssg', methods=['POST'])
@login_required
def delete_all_org_data():
    """Delete all members and positions from section/club/etc orgs. Excludes SSG (government type)."""
    conn = get_db()
    # Get all non-government org ids
    non_ssg_orgs = conn.execute(
        "SELECT id FROM organizations WHERE org_type != 'government'"
    ).fetchall()
    deleted_members = 0
    deleted_positions = 0
    for org in non_ssg_orgs:
        oid = org['id']
        r = conn.execute("DELETE FROM org_members WHERE org_id=?", (oid,))
        deleted_members += r.rowcount
        r = conn.execute("DELETE FROM org_positions WHERE org_id=?", (oid,))
        deleted_positions += r.rowcount
    conn.commit(); conn.close()
    flash(f'Cleared {deleted_members} member assignment(s) and {deleted_positions} position(s) from all sections and organizations (SSG preserved).', 'success')
    return redirect(url_for('organizations'))


@app.route('/organizations/<int:oid>/add_member', methods=['POST'])
@login_required
def add_org_member(oid):
    d = request.form
    student_id = int(d['student_id'])
    position_id = d.get('position_id') or None
    conn = get_db()
    try:
        org = conn.execute("SELECT org_type FROM organizations WHERE id=?", (oid,)).fetchone()

        # Rule: SSG exec students cannot hold section/strand/grade offices
        if org and org['org_type'] != 'government' and position_id:
            ssg_org = conn.execute("SELECT id FROM organizations WHERE org_type='government'").fetchone()
            if ssg_org:
                is_ssg_exec = conn.execute(
                    "SELECT 1 FROM org_members om JOIN org_positions op ON om.position_id=op.id"
                    " WHERE om.org_id=? AND om.student_id=? AND om.is_active=1"
                    " AND op.position_name IN ({})".format(
                        ','.join('?' * len(STANDARD_SSG_OFFICES_NAMES))
                    ),
                    [ssg_org['id'], student_id] + STANDARD_SSG_OFFICES_NAMES
                ).fetchone()
                if is_ssg_exec:
                    flash('This student holds an SSG executive position and cannot hold classroom, strand, or grade-level offices.', 'danger')
                    conn.close()
                    return redirect(url_for('organization_detail', oid=oid))

        conn.execute(
            "INSERT INTO org_members (org_id,student_id,position_id,school_year,is_active)"
            " VALUES (?,?,?,?,1)",
            (oid, student_id, position_id,
             d.get('school_year','').strip() or None)
        )
        conn.commit()
        flash('Member added.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('organization_detail', oid=oid))

@app.route('/organizations/<int:oid>/remove_member/<int:mid>', methods=['POST'])
@login_required
def remove_org_member(oid, mid):
    conn = get_db()
    conn.execute("DELETE FROM org_members WHERE id=? AND org_id=?", (mid, oid))
    conn.commit(); conn.close()
    flash('Member removed.', 'success')
    return redirect(url_for('organization_detail', oid=oid))

@app.route('/api/organizations/<int:oid>/members')
@login_required
def api_org_members(oid):
    conn = get_db()
    members = conn.execute(
        "SELECT om.student_id, s.first_name, s.last_name, s.middle_name,"
        " s.student_id AS sid_code, op.position_name"
        " FROM org_members om"
        " JOIN students s ON om.student_id=s.id"
        " LEFT JOIN org_positions op ON om.position_id=op.id"
        " WHERE om.org_id=? AND om.is_active=1"
        " ORDER BY op.rank_order NULLS LAST, s.last_name",
        (oid,)
    ).fetchall()
    conn.close()
    return jsonify([dict(m) for m in members])


@app.route('/api/debug/ssg_positions')
@login_required
def debug_ssg_positions():
    conn = get_db()
    ssg = conn.execute("SELECT id, name, org_type FROM organizations WHERE org_type='government'").fetchone()
    if not ssg:
        conn.close()
        return jsonify({'error': 'No government org found'})
    positions = conn.execute(
        "SELECT id, position_name, rank_order FROM org_positions WHERE org_id=? ORDER BY rank_order, position_name",
        (ssg['id'],)
    ).fetchall()
    conn.close()
    return jsonify({
        'ssg_id': ssg['id'],
        'ssg_name': ssg['name'],
        'org_type': ssg['org_type'],
        'position_count': len(positions),
        'positions': [dict(p) for p in positions]
    })


@app.route('/api/positions/all')
@any_role_required
def api_all_positions():
    """Return all position rows across all orgs with org info — no deduplication."""
    conn = get_db()
    rows = conn.execute(
        "SELECT op.id AS pos_id, op.position_name, o.name AS org_name, o.org_type, o.id AS org_id"
        " FROM org_positions op"
        " JOIN organizations o ON op.org_id=o.id"
        " ORDER BY CASE o.org_type WHEN 'government' THEN 0 WHEN 'section' THEN 1 ELSE 2 END,"
        " op.rank_order, op.position_name"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/positions/members')
@any_role_required
def api_position_members():
    """Return students who hold any of the given position names, optionally scoped to org_ids."""
    pos_names = [p.strip() for p in request.args.get('positions','').split(',') if p.strip()]
    org_ids   = [o.strip() for o in request.args.get('org_ids','').split(',') if o.strip()]
    if not pos_names:
        return jsonify([])
    conn = get_db()
    ph = ','.join('?' * len(pos_names))
    if org_ids:
        oh   = ','.join('?' * len(org_ids))
        rows = conn.execute(
            f"SELECT DISTINCT om.student_id, s.first_name, s.last_name, s.middle_name,"
            f" s.student_id AS sid_code, op.position_name, o.name AS org_name, o.org_type"
            f" FROM org_members om"
            f" JOIN students s ON om.student_id=s.id"
            f" JOIN org_positions op ON om.position_id=op.id"
            f" JOIN organizations o ON om.org_id=o.id"
            f" WHERE op.position_name IN ({ph}) AND om.org_id IN ({oh}) AND om.is_active=1"
            f" ORDER BY o.org_type DESC, op.position_name, s.last_name",
            pos_names + org_ids
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT DISTINCT om.student_id, s.first_name, s.last_name, s.middle_name,"
            f" s.student_id AS sid_code, op.position_name, o.name AS org_name, o.org_type"
            f" FROM org_members om"
            f" JOIN students s ON om.student_id=s.id"
            f" JOIN org_positions op ON om.position_id=op.id"
            f" JOIN organizations o ON om.org_id=o.id"
            f" WHERE op.position_name IN ({ph}) AND om.is_active=1"
            f" ORDER BY o.org_type DESC, op.position_name, s.last_name",
            pos_names
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])



@app.route('/attendance/event/<int:eid>/view')
@login_required
def attendance_event_view(eid):
    conn = get_db()
    event = conn.execute(
        "SELECT ae.*, sec.section_name, sec.grade_level, sub.subject_name, sub.subject_code,"
        " ac.name AS category_name, ac.color AS category_color, ac.icon AS category_icon"
        " FROM attendance_events ae"
        " LEFT JOIN sections sec ON ae.section_id=sec.id"
        " LEFT JOIN subjects sub ON ae.subject_id=sub.id"
        " LEFT JOIN attendance_categories ac ON ae.category_id=ac.id"
        " WHERE ae.id=? AND ae.event_type=\'class\'", (eid,)
    ).fetchone()
    if not event:
        flash("Class event not found.", "danger")
        return redirect(url_for("attendance_home"))
    students = conn.execute(
        "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name, s.gender,"
        " sec.section_name FROM students s"
        " LEFT JOIN sections sec ON s.section_id=sec.id"
        " WHERE s.section_id=? AND s.enrollment_status=\'Enrolled\'"
        " ORDER BY s.last_name, s.first_name", (event["section_id"],)
    ).fetchall()
    records = conn.execute(
        "SELECT student_id, status, note, recorded_at FROM attendance_records WHERE event_id=?", (eid,)
    ).fetchall()
    record_map = {r["student_id"]: r for r in records}
    summary    = attendance_summary(conn, eid)
    conn.close()
    return render_template("attendance_event_view.html", event=event,
                           students=students, record_map=record_map, summary=summary)


STANDARD_SECTION_OFFICES = [
    "President",
    "Vice President",
    "Secretary",
    "Treasurer",
    "Auditor",
    "Public Information and Relations Officer",
    "Protocol Officer I",
    "Protocol Officer II",
]

# 8 section offices — Protocol Officer has 2 named slots
STANDARD_SECTION_OFFICES_UNIQUE = [
    "President",
    "Vice President",
    "Secretary",
    "Treasurer",
    "Auditor",
    "Public Information and Relations Officer",
    "Protocol Officer I",
    "Protocol Officer II",
]

STANDARD_SSG_OFFICES_NAMES = [
    "President",
    "Vice President for Internal Affairs",
    "Vice President for External Affairs",
    "Secretary General",
    "Assistant Secretary",
    "Treasurer",
    "Assistant Treasurer",
    "Auditor",
    "Public Information and Relations Officer",
    "Protocol Officer I",
    "Protocol Officer II",
]

STANDARD_SSG_OFFICES = [
    ("President", 0),
    ("Vice President for Internal Affairs", 1),
    ("Vice President for External Affairs", 2),
    ("Secretary General", 3),
    ("Assistant Secretary", 4),
    ("Treasurer", 5),
    ("Assistant Treasurer", 6),
    ("Auditor", 7),
    ("Public Information and Relations Officer", 8),
    ("Protocol Officer I",  9),
    ("Protocol Officer II", 10),
]

def auto_create_ssg(conn):
    """Auto-create the SSG org. On first creation seeds all positions.
    On subsequent visits, only adds NEW positions from the standard list
    (e.g. Protocol Officer I/II replacing old Peace Officer/Sergeant-at-Arms).
    Deleted positions are never re-added."""
    SSG_NAME = "Supreme Student Government"
    ssg = conn.execute(
        "SELECT id FROM organizations WHERE org_type='government' AND name=?", (SSG_NAME,)
    ).fetchone()
    if ssg:
        oid = ssg["id"]
        # Patch: add any standard positions that don't exist yet
        # (handles renamed/new positions without re-adding deleted ones)
        existing_names = {r["position_name"] for r in conn.execute(
            "SELECT position_name FROM org_positions WHERE org_id=?", (oid,)
        ).fetchall()}
        for pos, rank in STANDARD_SSG_OFFICES:
            if pos not in existing_names:
                conn.execute(
                    "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
                    (oid, pos, rank)
                )
        # Rename old Strand Representatives to Strand Governors
        conn.execute(
            "UPDATE org_positions SET position_name = REPLACE(position_name, 'Strand Representative', 'Strand Governor')"
            " WHERE org_id=? AND position_name LIKE 'Strand Representative%'", (oid,)
        )
        # Fix any Grade Governor renames back to Grade Representative (revert previous mistake)
        conn.execute(
            "UPDATE org_positions SET position_name = REPLACE(position_name, ' Governor', ' Representative')"
            " WHERE org_id=? AND position_name LIKE 'Grade% Governor'", (oid,)
        )
        # Add missing Grade Representatives if they don't exist yet
        grades = conn.execute(
            "SELECT DISTINCT grade_level FROM sections ORDER BY grade_level"
        ).fetchall()
        existing_names2 = {r["position_name"] for r in conn.execute(
            "SELECT position_name FROM org_positions WHERE org_id=?", (oid,)
        ).fetchall()}
        for g in grades:
            pos = f"Grade {g['grade_level']} Representative"
            if pos not in existing_names2:
                conn.execute(
                    "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
                    (oid, pos, 15)
                )
        # Update ranks: Grade Representatives = 15 (above Strand Governors = 25)
        conn.execute(
            "UPDATE org_positions SET rank_order=15 WHERE org_id=? AND position_name LIKE 'Grade% Representative'", (oid,)
        )
        conn.execute(
            "UPDATE org_positions SET rank_order=25 WHERE org_id=? AND position_name LIKE 'Strand Governor%'", (oid,)
        )
        conn.commit()
        return oid

    # First-time creation only
    conn.execute(
        "INSERT INTO organizations (name,short_name,description,org_type,color) VALUES (?,?,?,?,?)",
        (SSG_NAME, "SSG", "Supreme Student Government", "government", "#3b82f6")
    )
    oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Standard executive positions
    for pos, rank in STANDARD_SSG_OFFICES:
        conn.execute(
            "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
            (oid, pos, rank)
        )

    # Strand curriculum representatives
    strands = conn.execute("SELECT strand_code, strand_name FROM strands ORDER BY strand_code").fetchall()
    for st in strands:
        pos = f"Strand Governor — {st['strand_code']} ({st['strand_name']})"
        conn.execute(
            "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
            (oid, pos, 25)
        )

    # Grade level curriculum representatives
    grades = conn.execute(
        "SELECT DISTINCT grade_level FROM sections ORDER BY grade_level"
    ).fetchall()
    for g in grades:
        pos = f"Grade {g['grade_level']} Representative"
        conn.execute(
            "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
            (oid, pos, 15)
        )

    return oid


@app.route("/sections/<int:sec_id>/officers")
@login_required
def section_officers(sec_id):
    conn = get_db()
    section = conn.execute(
        "SELECT s.*, t.first_name, t.last_name FROM sections s"
        " LEFT JOIN teachers t ON s.adviser_id=t.id WHERE s.id=?", (sec_id,)
    ).fetchone()
    if not section:
        flash("Section not found.", "danger")
        return redirect(url_for("sections"))
    org_name = f"Section Officers — {section['section_name']}"
    org = conn.execute(
        "SELECT * FROM organizations WHERE org_type=\'section\' AND name=?", (org_name,)
    ).fetchone()
    if not org:
        conn.execute(
            "INSERT INTO organizations (name,short_name,org_type,color) VALUES (?,?,?,?)",
            (org_name, section["section_name"], "section", "#8b5cf6")
        )
        oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for rank, pos in enumerate(STANDARD_SECTION_OFFICES_UNIQUE):
            conn.execute(
                "INSERT OR IGNORE INTO org_positions (org_id,position_name,rank_order) VALUES (?,?,?)",
                (oid, pos, rank)
            )
        conn.commit()
        org = conn.execute("SELECT * FROM organizations WHERE id=?", (oid,)).fetchone()
    else:
        oid = org["id"]
        # Do NOT re-add positions — admin manages them freely after creation
    positions = conn.execute(
        "SELECT op.*, COUNT(om.id) AS member_count"
        " FROM org_positions op"
        " LEFT JOIN org_members om ON om.position_id=op.id AND om.is_active=1"
        " WHERE op.org_id=? GROUP BY op.id ORDER BY op.rank_order, op.position_name", (oid,)
    ).fetchall()
    officers = conn.execute(
        "SELECT om.id AS member_row_id, om.school_year,"
        " s.id AS student_db_id, s.first_name, s.last_name, s.middle_name,"
        " s.student_id AS sid_code, s.gender,"
        " op.position_name, op.rank_order"
        " FROM org_members om"
        " JOIN students s ON om.student_id=s.id"
        " LEFT JOIN org_positions op ON om.position_id=op.id"
        " WHERE om.org_id=? AND om.is_active=1"
        " ORDER BY op.rank_order NULLS LAST, s.last_name", (oid,)
    ).fetchall()
    all_students = conn.execute(
        "SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name"
        " FROM students s WHERE s.section_id=? AND s.enrollment_status=\'Enrolled\'"
        " ORDER BY s.last_name, s.first_name", (sec_id,)
    ).fetchall()
    conn.close()
    return render_template("section_officers.html", section=section, org=org,
                           positions=positions, officers=officers,
                           all_students=all_students, sec_id=sec_id,
                           standard_offices=STANDARD_SECTION_OFFICES)


@app.route("/sections/<int:sec_id>/officers/add", methods=["POST"])
@login_required
def add_section_officer(sec_id):
    d = request.form
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO org_members (org_id,student_id,position_id,school_year,is_active) VALUES (?,?,?,?,1)",
            (int(d["org_id"]), int(d["student_id"]),
             d.get("position_id") or None, d.get("school_year","").strip() or None)
        )
        conn.commit()
        flash("Officer assigned.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("section_officers", sec_id=sec_id))


@app.route("/sections/<int:sec_id>/officers/remove/<int:mid>", methods=["POST"])
@login_required
def remove_section_officer(sec_id, mid):
    conn = get_db()
    conn.execute("DELETE FROM org_members WHERE id=?", (mid,))
    conn.commit(); conn.close()
    flash("Officer removed.", "success")
    return redirect(url_for("section_officers", sec_id=sec_id))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
