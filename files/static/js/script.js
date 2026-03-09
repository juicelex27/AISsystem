'use strict';

// ── MODAL ──────────────────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('active'); document.body.style.overflow = 'hidden'; }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.remove('active'); document.body.style.overflow = ''; }
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
    document.body.style.overflow = '';
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    document.body.style.overflow = '';
  }
});

// ── SIDEBAR TOGGLE ─────────────────────────────────────────────
const menuToggle = document.getElementById('menuToggle');
const sidebar    = document.getElementById('sidebar');
if (menuToggle && sidebar) {
  menuToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
}

// ── EDIT TEACHER ──────────────────────────────────────────────
function editTeacher(id) {
  fetch(`/teachers/get/${id}`).then(r => r.json()).then(data => {
    document.getElementById('edit_teacher_id').value = data.id;
    document.getElementById('edit_first_name').value = data.first_name;
    document.getElementById('edit_last_name').value  = data.last_name;
    document.getElementById('edit_email').value      = data.email;
    document.getElementById('edit_username').value   = data.username;
    document.getElementById('edit_teacher_form').action = `/teachers/edit/${data.id}`;
    openModal('editTeacherModal');
  });
}

// ── EDIT SUBJECT ──────────────────────────────────────────────
function editSubject(id) {
  fetch(`/subjects/get/${id}`).then(r => r.json()).then(data => {
    document.getElementById('edit_subject_id').value      = data.id;
    document.getElementById('edit_subject_code').value    = data.subject_code;
    document.getElementById('edit_subject_name').value    = data.subject_name;
    document.getElementById('edit_grade_level_sub').value = data.grade_level;
    document.getElementById('edit_strand').value          = data.strand || '';
    document.getElementById('edit_semester').value        = data.semester || '';
    document.getElementById('edit_subject_form').action   = `/subjects/edit/${data.id}`;
    openModal('editSubjectModal');
  });
}

// ── EDIT SECTION ──────────────────────────────────────────────
function editSection(id) {
  fetch(`/sections/get/${id}`).then(r => r.json()).then(data => {
    document.getElementById('edit_section_id').value      = data.id;
    document.getElementById('edit_grade_level_sec').value = data.grade_level;
    document.getElementById('edit_section_name').value    = data.section_name;
    document.getElementById('edit_strand_id').value       = data.strand_id || '';
    document.getElementById('edit_adviser_id').value      = data.adviser_id || '';
    document.getElementById('edit_student_limit').value   = data.student_limit || 40;
    document.getElementById('edit_section_form').action   = `/sections/edit/${data.id}`;
    openModal('editSectionModal');
  });
}

// ── EDIT STRAND ──────────────────────────────────────────────
function editStrand(id) {
  fetch(`/strands/get/${id}`).then(r => r.json()).then(data => {
    document.getElementById('edit_strand_id').value          = data.id;
    document.getElementById('edit_strand_code').value        = data.strand_code;
    document.getElementById('edit_strand_name').value        = data.strand_name;
    document.getElementById('edit_strand_description').value = data.description || '';
    document.getElementById('edit_strand_form').action       = `/strands/edit/${data.id}`;
    openModal('editStrandModal');
  });
}

// ── CONFIRM DELETE ────────────────────────────────────────────
function confirmDelete(formId) {
  if (confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
    document.getElementById(formId).submit();
  }
}

// ── AUTO DISMISS ALERTS ───────────────────────────────────────
document.querySelectorAll('.alert[data-autohide]').forEach(alert => {
  setTimeout(() => {
    alert.style.opacity = '0';
    alert.style.transform = 'translateY(-8px)';
    alert.style.transition = 'opacity .4s,transform .4s';
    setTimeout(() => alert.remove(), 400);
  }, 4000);
});

// ── TIMETABLE RENDERER ────────────────────────────────────────
// colorBy: 'subject_id' (default) or 'section_id'
function renderTimetable(schedules, containerId, deleteBase, colorBy = 'subject_id') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const DAYS       = ['Monday','Tuesday','Wednesday','Thursday','Friday'];
  const START_HOUR = 7;
  const END_HOUR   = 17;
  const SLOT_H     = 32;
  const COLS       = DAYS.length;

  const COLORS = [
    'var(--blue-course)',
    'var(--teal-course)',
    'var(--yellow-course)',
    'var(--pink-course)',
    'var(--dark-teal-course)',
    'var(--medium-blue-course)',
    'var(--mint-green-course)',
    'var(--green-course)',
    'var(--orange-course)',
    'var(--slate-blue-course)',
    'var(--dark-green-course)',
    'var(--orange-red-course)'
  ];

  const totalSlots = (END_HOUR - START_HOUR) * 2;
  const totalH     = totalSlots * SLOT_H;

  let html = `
    <div class="timetable-wrapper">
      <div class="timetable-header-row">
        <div class="tt-time-col">Time</div>
        ${DAYS.map(d => `<div class="tt-day-col">${d.slice(0,3)}</div>`).join('')}
      </div>
      <div style="display:flex;">
        <div style="width:80px;flex-shrink:0;border-right:1px solid var(--border);position:relative;height:${totalH}px;">`;

  for (let h = START_HOUR; h < END_HOUR; h++) {
    const top   = (h - START_HOUR) * 2 * SLOT_H;
    const label = h < 12 ? `${h}:00 AM` : h === 12 ? '12:00 PM' : `${h-12}:00 PM`;
    html += `<div style="position:absolute;top:${top}px;left:0;right:0;padding:4px 6px;font-size:10px;color:var(--text-muted);border-top:1px solid var(--border);">${label}</div>`;
  }
  html += `</div>`;

  html += `<div style="flex:1;display:grid;grid-template-columns:repeat(${COLS},1fr);position:relative;height:${totalH}px;">`;

  for (let col = 0; col < COLS; col++) {
    html += `<div style="position:relative;border-right:1px solid #f3f4f6;height:${totalH}px;">`;
    for (let slot = 0; slot < totalSlots; slot++) {
      const borderStyle = slot % 2 === 0 ? '1px solid #f3f4f6' : '1px dashed #f3f4f6';
      html += `<div style="position:absolute;top:${slot*SLOT_H}px;left:0;right:0;height:${SLOT_H}px;border-top:${borderStyle};"></div>`;
    }
    html += `</div>`;
  }

  const colorMap = {};
  let colorIdx = 0;

  schedules.forEach(sch => {
    const dayIdx = DAYS.indexOf(sch.day);
    if (dayIdx === -1) return;

    const [sh, sm] = sch.time_start.split(':').map(Number);
    const [eh, em] = sch.time_end.split(':').map(Number);
    const startMin = (sh - START_HOUR) * 60 + sm;
    const endMin   = (eh - START_HOUR) * 60 + em;
    if (startMin < 0 || endMin <= startMin) return;

    const topPx    = (startMin / 30) * SLOT_H;
    const heightPx = Math.max(((endMin - startMin) / 30) * SLOT_H, SLOT_H);
    const colPercent = (dayIdx / COLS) * 100;
    const colWidth   = (1 / COLS) * 100;

    const colorKey = sch[colorBy] ?? sch.subject_id;
    if (!colorMap[colorKey]) {
      colorMap[colorKey] = COLORS[colorIdx % COLORS.length];
      colorIdx++;
    }
    const color = colorMap[colorKey];

    const label12 = t => {
      const [hh, mm] = t.split(':').map(Number);
      const suffix = hh < 12 ? 'AM' : 'PM';
      const h12    = hh % 12 || 12;
      return `${h12}:${String(mm).padStart(2,'0')} ${suffix}`;
    };

    html += `
      <div class="tt-event" style="
        position:absolute;
        top:${topPx + 2}px;
        height:${heightPx - 4}px;
        left:calc(${colPercent}% + 3px);
        width:calc(${colWidth}% - 6px);
        background:${color};
        border-radius:6px;
        padding:4px 7px;
        overflow:hidden;
        z-index:2;
      " title="${sch.subject_name} • ${sch.teacher_name} • ${label12(sch.time_start)}–${label12(sch.time_end)}">
        <div style="font-size:11px;font-weight:700;color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${sch.subject_name}</div>
        <div style="font-size:10px;color:rgba(255,255,255,.8);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${sch.teacher_name}</div>
        <div style="font-size:10px;color:rgba(255,255,255,.7);">${label12(sch.time_start)}–${label12(sch.time_end)}</div>
        ${sch.room ? `<div style="font-size:10px;color:rgba(255,255,255,.6);">📍 ${sch.room}</div>` : ''}
        ${deleteBase ? `
        <form method="POST" action="${deleteBase}/${sch.id}" style="display:inline;" onsubmit="return confirm('Remove this schedule entry?')">
          <button type="submit" style="position:absolute;top:3px;right:4px;width:16px;height:16px;border-radius:50%;background:rgba(0,0,0,.25);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;" title="Remove">
            <svg viewBox="0 0 24 24" style="width:9px;height:9px;fill:white"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </form>` : ''}
      </div>`;
  });

  html += `</div></div></div>`;
  container.innerHTML = html;
}