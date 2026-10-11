
const API = '/api';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const PERIODS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00'];
const COLORS = ['blue', 'pink', 'teal', 'green-card', 'purple', 'orange', 'red-card', 'lab'];
const WORKLOAD_COLORS = ['#36a9b5', '#665bc4', '#e9a13d', '#68b889', '#e06b86', '#4b8bd2'];

let timetableId = null;
let assignments = [];
let courses = [];
let recentAdjustments = [];

const $ = (id) => document.getElementById(id);

// ============================================================
// API HELPER
// ============================================================

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        }
    });

    const raw = await response.text();
    let data;

    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        data = { message: raw };
    }

    if (!response.ok) {
        throw new Error(
            data.error || data.message || `Request failed (${response.status})`
        );
    }

    return data;
}

function notify(message) {
    const el = $('toast');

    if (!el) {
        console.log(message);
        return;
    }

    el.textContent = message;
    el.classList.add('show');

    setTimeout(() => el.classList.remove('show'), 3000);
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function periodIndex(time) {
    const [hour, minute] = String(time || '').split(':').map(Number);

    return PERIODS.indexOf(
        `${String(hour).padStart(2, '0')}:${String(minute || 0).padStart(2, '0')}`
    );
}

function colorFor(item, index) {
    return item.is_lab ? 'lab' : COLORS[index % COLORS.length];
}

// ============================================================
// TIMETABLE RENDERING
// ============================================================

function renderTimetable() {
    const body = $('timetableBody');

    if (!body) return;

    if (!assignments.length) {
        body.innerHTML = `
            <tr>
                <td colspan="8" class="empty-cell">
                    No assignments found. Use “Regenerate with AI”
                    to create a timetable.
                </td>
            </tr>
        `;

        if ($('scheduledStat')) $('scheduledStat').textContent = '0';
        if ($('timetableCaption')) $('timetableCaption').textContent = 'No timetable loaded';

        renderAnalytics();
        return;
    }

    body.innerHTML = DAYS.map(day => {
        const cells = PERIODS.map((time, index) => {
            const item = assignments.find(a => {
                const start = periodIndex(a.start_time);
                const duration = Number(a.duration || 1);

                return a.day === day &&
                    (
                        start === index ||
                        (
                            start < index &&
                            start >= 0 &&
                            index < start + duration
                        )
                    );
            });

            if (!item) {
                return '<td><div class="class-card empty"></div></td>';
            }

            const first = periodIndex(item.start_time) === index;

            if (!first) {
                return '<td><div class="class-card empty"></div></td>';
            }

            const itemIndex = assignments.indexOf(item);

            return `
                <td>
                    <div class="class-card ${colorFor(item, itemIndex)}">
                        <strong>${escapeHtml(item.course_name || item.course_id)}</strong>
                        <span>♙ ${escapeHtml(item.faculty_id || 'Faculty N/A')}</span>
                        <span class="meta">
                            ⌖ ${escapeHtml(item.room_id || 'Room N/A')}<br>
                            ${escapeHtml(item.student_group_id || 'Group N/A')}
                        </span>
                    </div>
                </td>
            `;
        }).join('');

        return `
            <tr>
                <th>${day}<small>Weekly schedule</small></th>
                ${cells}
            </tr>
        `;
    }).join('');

    if ($('scheduledStat')) {
        $('scheduledStat').textContent = assignments.length;
    }

    if ($('timetableCaption')) {
        $('timetableCaption').textContent = timetableId
            ? `Showing saved timetable #${timetableId}`
            : 'Showing latest generated schedule';
    }

    renderAnalytics();
}

// ============================================================
// CONFLICT REPORTS
// ============================================================

function renderConflicts(items = []) {
    if ($('conflictStat')) {
        $('conflictStat').textContent = items.length;
    }

    if ($('conflictPill')) {
        $('conflictPill').textContent = items.length;
    }

    const list = $('conflictList');

    if (!list) return;

    list.innerHTML = items.length
        ? items.map(conflict => `
            <article class="conflict-card">
                <span class="conflict-tag">
                    ${escapeHtml(conflict.type || 'Scheduling conflict')}
                </span>

                <strong>
                    ${escapeHtml(conflict.title || conflict.course_name || 'Conflict detected')}
                </strong>

                <p>
                    ${escapeHtml(conflict.message || conflict.reason || 'Review this assignment.')}
                </p>

                <small>
                    ${escapeHtml(conflict.day || 'Day unavailable')}
                    · ${escapeHtml(conflict.start_time || 'Time unavailable')}
                </small>
            </article>
        `).join('')
        : `
            <div class="empty-state">
                No scheduling conflicts detected for this timetable.
            </div>
        `;
}

async function loadConflicts() {
    try {
        const url = timetableId
            ? `${API}/conflicts?timetable_id=${encodeURIComponent(timetableId)}`
            : `${API}/conflicts`;

        const data = await api(url);

        if (!data.success) {
            throw new Error(data.error || 'Could not load conflict reports.');
        }

        renderConflicts(data.conflicts || []);
        return true;
    } catch (error) {
        console.error('Conflict loading failed:', error);

        if ($('conflictList')) {
            $('conflictList').innerHTML = `
                <div class="empty-state">
                    Could not load conflict reports:
                    ${escapeHtml(error.message)}
                </div>
            `;
        }

        return false;
    }
}

// ============================================================
// WORKLOAD AND ROOM ANALYTICS
// ============================================================

function renderAnalytics() {
    const hoursByFaculty = {};
    const hoursByRoom = {};
    let totalHours = 0;

    assignments.forEach(assignment => {
        const hours = Math.max(1, Number(assignment.duration) || 1);
        totalHours += hours;

        const faculty = assignment.faculty_id || 'Unassigned';
        hoursByFaculty[faculty] = (hoursByFaculty[faculty] || 0) + hours;

        const room = assignment.room_id || 'Unassigned';
        hoursByRoom[room] = (hoursByRoom[room] || 0) + hours;
    });

    if ($('workloadHours')) {
        $('workloadHours').textContent = totalHours;
    }

    const facultyRows = Object.entries(hoursByFaculty)
        .sort((a, b) => b[1] - a[1]);

    if ($('workloadLegend') && $('workloadDonut')) {
        if (!facultyRows.length) {
            $('workloadLegend').innerHTML =
                '<span class="muted-note">No workload data available.</span>';

            $('workloadDonut').style.background = '#e9eaf3';
        } else {
            $('workloadLegend').innerHTML = facultyRows.slice(0, 4)
                .map(([faculty, hours], index) => `
                    <div class="legend-line">
                        <i style="background:${WORKLOAD_COLORS[index % WORKLOAD_COLORS.length]}"></i>
                        <span>
                            ${escapeHtml(faculty)}
                            <small>${hours} teaching hour${hours === 1 ? '' : 's'}</small>
                        </span>
                        <strong>${Math.round(hours / totalHours * 100)}%</strong>
                    </div>
                `).join('');

            let start = 0;

            const stops = facultyRows.map(([, hours], index) => {
                const from = start;
                start += hours / totalHours * 100;

                return `${WORKLOAD_COLORS[index % WORKLOAD_COLORS.length]} ${from}% ${start}%`;
            });

            $('workloadDonut').style.background =
                `conic-gradient(${stops.join(',')})`;
        }
    }

    const roomRows = Object.entries(hoursByRoom)
        .sort((a, b) => b[1] - a[1]);

    if ($('roomUtilization')) {
        $('roomUtilization').innerHTML = roomRows.length
            ? roomRows.slice(0, 5).map(([room, hours]) => `
                <div class="util-row">
                    <span>${escapeHtml(room)}</span>

                    <div class="util-track">
                        <div class="util-fill"
                             style="width:${Math.max(4, Math.round(hours / Math.max(totalHours, 1) * 100))}%">
                        </div>
                    </div>

                    <strong>${Math.round(hours / Math.max(totalHours, 1) * 100)}%</strong>
                </div>
            `).join('')
            : '<span class="muted-note">No room assignments yet.</span>';
    }

    if ($('statusList')) {
        $('statusList').innerHTML = `
            <div>
                <span class="status-check">✓</span>
                <span>
                    <strong>Scheduling API</strong>
                    <small>Connected to Flask</small>
                </span>
            </div>

            <div>
                <span class="status-check">${assignments.length ? '✓' : '•'}</span>
                <span>
                    <strong>Saved timetable</strong>
                    <small>
                        ${assignments.length
                            ? `${assignments.length} assignments · #${timetableId ?? 'latest'}`
                            : 'No saved assignments loaded'}
                    </small>
                </span>
            </div>

            <div>
                <span class="status-check">✓</span>
                <span>
                    <strong>Hard constraints</strong>
                    <small>Validated by CSP during generation</small>
                </span>
            </div>

            <div>
                <span class="status-check">✓</span>
                <span>
                    <strong>Conflict reports</strong>
                    <small>Connected to conflict detection API</small>
                </span>
            </div>
        `;
    }

    renderAdjustments();
}

// ============================================================
// PERSISTENT SUBSTITUTION HISTORY
// ============================================================

function renderAdjustments() {
    const count = $('adjustmentCount');
    const list = $('adjustmentList');

    if (!count || !list) return;

    count.textContent = recentAdjustments.length;

    if (!recentAdjustments.length) {
        list.innerHTML = `
            <div class="muted-note">
                No saved alternatives yet. Use “Find Alternative”
                to propose a new slot.
            </div>
        `;
        return;
    }

    list.innerHTML = recentAdjustments.slice(0, 4).map(item => `
        <div class="adjustment-item">
            <span class="adjustment-symbol">↗</span>

            <span>
                <strong>
                    ${escapeHtml(item.course_name || item.course_id)}
                    · alternative proposed
                </strong>

                ${escapeHtml(item.proposed_day || '—')} at
                ${escapeHtml(item.proposed_time || '—')}

                <small>
                    ${escapeHtml(item.proposed_room_id || '—')}
                    · ${escapeHtml(item.status || 'PROPOSED')}
                </small>
            </span>
        </div>
    `).join('');
}

async function loadSubstitutionHistory(showError = true) {
    try {
        const data = await api(`${API}/substitutions`);

        if (!data.success) {
            throw new Error('Could not load substitution history.');
        }

        recentAdjustments = data.substitutions || [];
        renderAdjustments();

        return true;
    } catch (error) {
        console.error('Substitution history loading failed:', error);

        if (showError) {
            notify(`Could not load substitution history: ${error.message}`);
        }

        return false;
    }
}

// ============================================================
// EXPORT TIMETABLE AS CSV
// ============================================================

function exportCsv() {
    if (!assignments.length) {
        notify('There are no assignments to export yet.');
        return;
    }

    const columns = [
        'course_id',
        'course_name',
        'faculty_id',
        'student_group_id',
        'room_id',
        'day',
        'start_time',
        'duration',
        'enrollment',
        'status'
    ];

    const quote = value =>
        `"${String(value ?? '').replace(/"/g, '""')}"`;

    const csv = [
        columns.join(','),
        ...assignments.map(assignment =>
            columns.map(key => quote(assignment[key])).join(',')
        )
    ].join('\r\n');

    const blob = new Blob(['\ufeff' + csv], {
        type: 'text/csv;charset=utf-8;'
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = `campusflow-timetable-${timetableId ?? 'latest'}.csv`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
    notify('Timetable CSV exported');
}

// ============================================================
// LOAD COURSES
// ============================================================

async function loadCourses() {
    try {
        const data = await api(`${API}/courses`);

        courses = Array.isArray(data)
            ? data
            : (data.courses || data.items || []);

        const select = $('courseSelect');

        if (!select) return;

        select.innerHTML = courses.length
            ? courses.map(course => `
                <option value="${escapeHtml(course.id || course.course_id)}">
                    ${escapeHtml(
                        course.name ||
                        course.course_name ||
                        course.id ||
                        course.course_id
                    )}
                </option>
            `).join('')
            : '<option value="">No courses available</option>';
    } catch (error) {
        if ($('courseSelect')) {
            $('courseSelect').innerHTML =
                '<option value="">Could not load courses</option>';
        }

        console.error('Course loading failed:', error);
    }
}

// ============================================================
// LOAD LATEST SAVED TIMETABLE
// ============================================================

async function loadTimetable() {
    try {
        const data = await api(`${API}/timetables`);
        const timetables = data.timetables || [];

        if (!timetables.length) {
            assignments = [];
            timetableId = null;

            if ($('scoreStat')) {
                $('scoreStat').textContent = '—';
            }

            renderTimetable();
            await loadConflicts();
            return;
        }

        const latest = timetables.reduce((a, b) =>
            Number(a.id) > Number(b.id) ? a : b
        );

        timetableId = latest.id;

        const detail = await api(`${API}/timetables/${timetableId}`);

        assignments =
            detail.assignments ||
            detail.timetable?.assignments ||
            [];

        if ($('scoreStat')) {
            $('scoreStat').textContent = latest.fitness_score != null
                ? `${Math.round(Number(latest.fitness_score) * 10) / 10}`
                : 'Available';
        }

        renderTimetable();
        await loadConflicts();
    } catch (error) {
        console.error('Timetable loading failed:', error);

        if ($('timetableBody')) {
            $('timetableBody').innerHTML = `
                <tr>
                    <td colspan="8" class="empty-cell">
                        Could not load timetable: ${escapeHtml(error.message)}
                    </td>
                </tr>
            `;
        }

        notify(`API error: ${error.message}`);
    }
}

// ============================================================
// GENERATE TIMETABLE
// ============================================================

async function generateSchedule() {
    const buttons = [$('generateBtn'), $('quickGenerateBtn')];

    buttons.forEach(button => {
        if (button) {
            button.disabled = true;

            if (button.id === 'generateBtn') {
                button.textContent = 'Generating…';
            }
        }
    });

    try {
        const data = await api(`${API}/schedule/generate`, {
            method: 'POST',
            body: JSON.stringify({
                name: 'CampusFlow Generated Timetable',
                academic_term: 'Fall 2026'
            })
        });

        if (data.success === false) {
            throw new Error(data.error || 'Schedule generation failed');
        }

        assignments = data.assignments || [];
        timetableId = data.timetable_id ?? null;

        if ($('scoreStat')) {
            $('scoreStat').textContent = data.fitness_score != null
                ? Number(data.fitness_score).toFixed(2)
                : '—';
        }

        renderTimetable();
        await loadConflicts();
        await loadCourses();

        notify(`Timetable generated: ${assignments.length} assignments`);
    } catch (error) {
        notify(`Generation failed: ${error.message}`);
    } finally {
        buttons.forEach(button => {
            if (button) {
                button.disabled = false;

                if (button.id === 'generateBtn') {
                    button.textContent = '✦ Regenerate with AI';
                }
            }
        });
    }
}

// ============================================================
// FIND ALTERNATIVE AND SAVE PROPOSAL
// ============================================================

async function reschedule() {
    const courseId = $('courseSelect')?.value;
    const result = $('rescheduleResult');

    if (!result) return;

    result.className = 'result-box';
    result.textContent = '';

    if (!courseId) {
        result.className = 'result-box result-error';
        result.textContent = 'Choose a course first.';
        return;
    }

    const course = assignments.find(
        assignment => String(assignment.course_id) === String(courseId)
    );

    const payload = {
        course_id: courseId,
        reason: $('reasonSelect')?.value || 'RESCHEDULE_REQUEST'
    };

    if (course) {
        payload.current_room_id = course.room_id;
        payload.current_day = course.day;
        payload.current_time = course.start_time;
    }

    if (timetableId) {
        payload.timetable_id = timetableId;
    }

    const button = $('rescheduleBtn');

    if (button) {
        button.disabled = true;
        button.textContent = 'Searching…';
    }

    try {
        const data = await api(`${API}/schedule/reschedule`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        const alternative = data.alternative || {};

        if (
            !alternative.room_id ||
            !alternative.day ||
            !alternative.start_time
        ) {
            throw new Error('The API did not return a complete alternative slot.');
        }

        result.className = 'result-box result-success';

        result.innerHTML = `
            <strong>Alternative found</strong><br>
            ${escapeHtml(alternative.day)} at
            ${escapeHtml(alternative.start_time)}<br>
            Room: ${escapeHtml(alternative.room_id)}<br>
            Utility: ${escapeHtml(alternative.utility_score ?? '—')}<br>
            <small>Saving proposal to the database…</small>
        `;

        const saveBody = {
            timetable_id: timetableId,
            course_id: courseId,
            reason: payload.reason,
            original_room_id: payload.current_room_id || null,
            original_day: payload.current_day || null,
            original_time: payload.current_time || null,
            proposed_room_id: alternative.room_id,
            proposed_day: alternative.day,
            proposed_time: alternative.start_time
        };

        await api(`${API}/substitutions`, {
            method: 'POST',
            body: JSON.stringify(saveBody)
        });

        await loadSubstitutionHistory(false);

        result.innerHTML = `
            <strong>Alternative found and saved</strong><br>
            ${escapeHtml(alternative.day)} at
            ${escapeHtml(alternative.start_time)}<br>
            Room: ${escapeHtml(alternative.room_id)}<br>
            Utility: ${escapeHtml(alternative.utility_score ?? '—')}<br>
            <small>
                Proposal saved. The actual timetable has not been changed.
            </small>
        `;

        notify('Alternative saved to substitution history');
    } catch (error) {
        result.className = 'result-box result-error';
        result.textContent = error.message;

        notify(`Rescheduling failed: ${error.message}`);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = 'Find Alternative';
        }
    }
}

// ============================================================
// DASHBOARD EVENT LISTENERS
// ============================================================

if ($('generateBtn')) {
    $('generateBtn').addEventListener('click', generateSchedule);
}

if ($('refreshBtn')) {
    $('refreshBtn').addEventListener('click', async () => {
        await loadTimetable();
        await loadCourses();
        await loadSubstitutionHistory(false);

        notify('Dashboard refreshed');
    });
}

if ($('rescheduleBtn')) {
    $('rescheduleBtn').addEventListener('click', reschedule);
}

if ($('quickGenerateBtn')) {
    $('quickGenerateBtn').addEventListener('click', generateSchedule);
}

if ($('quickRescheduleBtn')) {
    $('quickRescheduleBtn').addEventListener('click', () => {
        $('conflicts')?.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        $('courseSelect')?.focus();
    });
}

if ($('printBtn')) {
    $('printBtn').addEventListener('click', () => window.print());
}

if ($('exportBtn')) {
    $('exportBtn').addEventListener('click', exportCsv);
}

if ($('viewRoomsBtn')) {
    $('viewRoomsBtn').addEventListener('click', () => {
        notify('Room summary is based on the currently loaded timetable.');
    });
}

if ($('viewAdjustmentsBtn')) {
    $('viewAdjustmentsBtn').addEventListener('click', async () => {
        await loadSubstitutionHistory();

        $('adjustmentList')?.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        if (!recentAdjustments.length) {
            notify('No saved substitution proposals found.');
        }
    });
}

// ============================================================
// INITIALIZE DASHBOARD
// ============================================================

loadTimetable();
loadCourses();
loadSubstitutionHistory();
