// API Configuration
const API_BASE_URL = 'http://localhost:5001/api';

// Global variables
let currentEmployee = null;
let currentMonth = 5; // Juni (0-based)
let currentYear = 2025;
let timeEntries = [];
let employees = [];

// Format date as YYYY-MM-DD in local time
function formatDate(date) {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().split('T')[0];
}

// Initialize app
document.addEventListener('DOMContentLoaded', async function() {
    console.log('App initializing...');
    await loadEmployees();
    loadDashboard();
});

// API Functions
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            const message = data.error || data.message || `HTTP error! status: ${response.status}`;
            throw new Error(message);
        }

        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Load employees
async function loadEmployees() {
    try {
        console.log('Loading employees...');
        employees = await apiCall('/employees');
        console.log('Employees loaded:', employees);
        
        const select = document.getElementById('employeeSelect');
        select.innerHTML = '<option value="">Mitarbeiter auswählen</option>';
        
        employees.forEach(emp => {
            if (emp.is_active) {
                const option = document.createElement('option');
                option.value = emp.id;
                option.textContent = emp.name;
                select.appendChild(option);
            }
        });

        renderEmployeeList();
    } catch (error) {
        console.error('Error loading employees:', error);
        showError('Fehler beim Laden der Mitarbeiter: ' + error.message);
    }
}

// Load dashboard
async function loadDashboard() {
    try {
        console.log('Loading dashboard...');
        const activeEmployees = employees.filter(emp => emp.is_active).length;
        const withCommission = employees.filter(emp => emp.is_active && emp.has_commission).length;
        const totalHours = employees.filter(emp => emp.is_active).reduce((sum, emp) => sum + emp.contract_hours, 0);
        
        const statsGrid = document.getElementById('statsGrid');
        statsGrid.innerHTML = `
            <div class="stat-card">
                <div class="stat-number">${activeEmployees}</div>
                <div class="stat-label">Aktive Mitarbeiter</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">0</div>
                <div class="stat-label">Stunden diese Woche</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${withCommission}</div>
                <div class="stat-label">Mit Provision</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${totalHours}</div>
                <div class="stat-label">Vertragsstunden/Woche</div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showError('Fehler beim Laden des Dashboards: ' + error.message);
    }
}

// Show section
function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected section
    document.getElementById(sectionName).classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Load calendar
async function loadCalendar() {
    const employeeId = document.getElementById('employeeSelect').value;
    const month = parseInt(document.getElementById('monthSelect').value);
    const year = parseInt(document.getElementById('yearSelect').value);
    
    if (!employeeId) {
        alert('Bitte wählen Sie einen Mitarbeiter aus.');
        return;
    }
    
    currentEmployee = employees.find(emp => emp.id == employeeId);
    currentMonth = month;
    currentYear = year;
    
    try {
        // Load time entries for the month
        timeEntries = await apiCall(`/time-entries?employee_id=${employeeId}&year=${year}&month=${month + 1}`);
        console.log('Time entries loaded:', timeEntries);
        
        renderCalendar();
        renderMonthSummary();
    } catch (error) {
        console.error('Error loading calendar:', error);
        showError('Fehler beim Laden des Kalenders: ' + error.message);
    }
}

// Render calendar
function renderCalendar() {
    const container = document.getElementById('calendarContainer');
    const monthNames = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                       'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
    const dayNames = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
    
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());
    
    let html = `
        <div class="calendar-header">
            ${monthNames[currentMonth]} ${currentYear} - ${currentEmployee.name}
        </div>
        <div class="calendar">
    `;
    
    // Day headers
    dayNames.forEach(day => {
        html += `<div class="calendar-day-header">${day}</div>`;
    });
    
    // Calendar days
    const currentDate = new Date(startDate);
    for (let week = 0; week < 6; week++) {
        for (let day = 0; day < 7; day++) {
            const isCurrentMonth = currentDate.getMonth() === currentMonth;
            const dateStr = formatDate(currentDate);
            const entry = timeEntries.find(e => e.date === dateStr);
            
            let dayClass = 'calendar-day';
            if (!isCurrentMonth) dayClass += ' other-month';
            if (entry) dayClass += ' has-data';
            
            let dayInfo = '';
            if (entry) {
                if (entry.entry_type === 'vacation') {
                    dayInfo = '<div class="day-info">Urlaub</div>';
                } else if (entry.entry_type === 'sick') {
                    dayInfo = '<div class="day-info">Krank</div>';
                } else if (entry.start_time && entry.end_time) {
                    const hours = calculateHours(entry.start_time, entry.end_time, entry.pause_minutes || 0);
                    dayInfo = `<div class="day-info">${entry.start_time}-${entry.end_time}<br>${hours}h</div>`;
                }
            }
            
            html += `
                <div class="${dayClass}" onclick="openTimeModal('${dateStr}')">
                    <div class="day-number">${currentDate.getDate()}</div>
                    ${dayInfo}
                </div>
            `;
            
            currentDate.setDate(currentDate.getDate() + 1);
        }
    }
    
    html += '</div>';
    container.innerHTML = html;
}

// Render month summary
function renderMonthSummary() {
    const summary = document.getElementById('monthSummary');
    
    // Calculate statistics
    const workDays = timeEntries.filter(e => e.entry_type === 'work' && e.start_time && e.end_time).length;
    const vacationDays = timeEntries.filter(e => e.entry_type === 'vacation').length;
    const sickDays = timeEntries.filter(e => e.entry_type === 'sick').length;
    
    const totalHours = timeEntries.reduce((sum, entry) => {
        if (entry.entry_type === 'work' && entry.start_time && entry.end_time) {
            return sum + calculateHours(entry.start_time, entry.end_time, entry.pause_minutes || 0);
        }
        return sum;
    }, 0);
    
    const totalDuftreisen = timeEntries.reduce((sum, entry) => {
        return sum + (entry.duftreise_bis_18 || 0) + (entry.duftreise_ab_18 || 0);
    }, 0);
    
    const totalProvision = timeEntries.reduce((sum, entry) => {
        return sum + (entry.commission || 0);
    }, 0);
    
    summary.innerHTML = `
        <div class="summary-title">Monatsübersicht ${currentEmployee.name}</div>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-value">${totalHours.toFixed(1)}</div>
                <div class="summary-label">Gesamtstunden</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${workDays}</div>
                <div class="summary-label">Arbeitstage</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${vacationDays}</div>
                <div class="summary-label">Urlaubstage</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${sickDays}</div>
                <div class="summary-label">Krankheitstage</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${totalDuftreisen}</div>
                <div class="summary-label">Duftreisen gesamt</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${totalProvision.toFixed(2)}€</div>
                <div class="summary-label">Provision gesamt</div>
            </div>
        </div>
    `;
    
    summary.style.display = 'block';
}

// Calculate hours
function calculateHours(startTime, endTime, pause) {
    const start = new Date(`2000-01-01T${startTime}`);
    const end = new Date(`2000-01-01T${endTime}`);
    const diffMs = end - start;
    const diffHours = diffMs / (1000 * 60 * 60);
    return Math.max(0, diffHours - (pause / 60));
}

// Open time modal
function openTimeModal(dateStr) {
    const modal = document.getElementById('timeModal');
    const title = document.getElementById('modalTitle');
    const date = new Date(dateStr);
    
    title.textContent = `Zeiterfassung - ${date.toLocaleDateString('de-DE')}`;
    
    // Find existing entry
    const entry = timeEntries.find(e => e.date === dateStr);
    
    // Fill form
    document.getElementById('entryType').value = entry?.entry_type || 'work';
    document.getElementById('startTime').value = entry?.start_time || '';
    document.getElementById('endTime').value = entry?.end_time || '';
    document.getElementById('pause').value = entry?.pause_minutes || '';
    document.getElementById('provision').value = entry?.commission || '';
    document.getElementById('duftreisen1').value = entry?.duftreise_bis_18 || '';
    document.getElementById('duftreisen2').value = entry?.duftreise_ab_18 || '';
    document.getElementById('notes').value = entry?.notes || '';
    
    // Store current date
    modal.dataset.date = dateStr;
    modal.dataset.entryId = entry?.id || '';
    
    toggleFields();
    modal.classList.add('show');
}

// Close modal
function closeModal() {
    document.getElementById('timeModal').classList.remove('show');
}

// Toggle fields based on entry type
function toggleFields() {
    const type = document.getElementById('entryType').value;
    const workFields = ['timeGrid', 'pauseGroup', 'provisionGroup', 'duftreisen'];
    
    workFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.style.display = type === 'work' ? 'block' : 'none';
        }
    });
}

// Save entry
async function saveEntry() {
    const modal = document.getElementById('timeModal');
    const date = modal.dataset.date;
    const entryId = modal.dataset.entryId;
    
    const data = {
        employee_id: currentEmployee.id,
        date: date,
        entry_type: document.getElementById('entryType').value,
        start_time: document.getElementById('startTime').value || null,
        end_time: document.getElementById('endTime').value || null,
        pause_minutes: parseInt(document.getElementById('pause').value) || 0,
        commission: parseFloat(document.getElementById('provision').value) || 0,
        duftreise_bis_18: parseInt(document.getElementById('duftreisen1').value) || 0,
        duftreise_ab_18: parseInt(document.getElementById('duftreisen2').value) || 0,
        notes: document.getElementById('notes').value || null
    };
    
    try {
        if (entryId) {
            // Update existing entry
            await apiCall(`/time-entries/${entryId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        } else {
            // Create new entry
            await apiCall('/time-entries', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }
        
        closeModal();
        loadCalendar(); // Reload calendar
    } catch (error) {
        console.error('Error saving entry:', error);
        alert(error.message);
    }
}

// Export PDF
function exportPDF() {
    if (!currentEmployee) {
        alert('Bitte wählen Sie einen Mitarbeiter und laden Sie den Kalender.');
        return;
    }
    
    const url = `${API_BASE_URL}/reports/monthly/${currentEmployee.id}/${currentYear}/${currentMonth + 1}`;
    window.open(url, '_blank');
}

// Show error
function showError(message) {
    const container = document.querySelector('.content');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    container.insertBefore(errorDiv, container.firstChild);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Close modal when clicking outside
document.getElementById('timeModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Close employee modal when clicking outside
document.getElementById('employeeModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeEmployeeModal();
    }
});

// Render employee table
function renderEmployeeList() {
    const tbody = document.getElementById('employeeTableBody');
    tbody.innerHTML = '';

    employees.forEach(emp => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${emp.name}</td>
            <td>${emp.has_commission ? 'Ja' : 'Nein'}</td>
            <td>${emp.is_active ? 'Nein' : 'Ja'}</td>
            <td>${emp.start_date ? new Date(emp.start_date).toLocaleDateString('de-DE') : ''}</td>
            <td>${emp.end_date ? new Date(emp.end_date).toLocaleDateString('de-DE') : ''}</td>
        `;
        tr.onclick = () => openEmployeeModal(emp);
        tbody.appendChild(tr);
    });
}

function openEmployeeModal(emp = null) {
    const modal = document.getElementById('employeeModal');
    modal.classList.add('show');
    modal.dataset.id = emp ? emp.id : '';
    document.getElementById('employeeModalTitle').textContent = emp ? 'Mitarbeiter bearbeiten' : 'Neuer Mitarbeiter';
    document.getElementById('empName').value = emp?.name || '';
    document.getElementById('empHours').value = emp?.contract_hours || '';
    document.getElementById('empCommission').checked = emp?.has_commission || false;
    document.getElementById('empStart').value = emp?.start_date || formatDate(new Date());
    document.getElementById('empEnd').value = emp?.end_date || '';
    document.getElementById('empActive').checked = emp ? emp.is_active : true;
}

function closeEmployeeModal() {
    document.getElementById('employeeModal').classList.remove('show');
    document.getElementById('empName').value = '';
    document.getElementById('empHours').value = '';
    document.getElementById('empCommission').checked = false;
    document.getElementById('empStart').value = '';
    document.getElementById('empEnd').value = '';
    document.getElementById('empActive').checked = true;
    document.getElementById('employeeModal').dataset.id = '';
}

async function saveEmployee() {
    const name = document.getElementById('empName').value.trim();
    const hours = parseInt(document.getElementById('empHours').value) || 0;
    const commission = document.getElementById('empCommission').checked;

    if (!name || hours <= 0) {
        alert('Bitte Name und Vertragsstunden angeben.');
        return;
    }

    const startDate = document.getElementById('empStart').value;
    const endDate = document.getElementById('empEnd').value || null;
    const active = document.getElementById('empActive').checked;

    const payload = {
        name: name,
        contract_hours: hours,
        has_commission: commission,
        start_date: startDate,
        end_date: endDate,
        is_active: active
    };

    try {
        const modal = document.getElementById('employeeModal');
        if (modal.dataset.id) {
            await apiCall(`/employees/${modal.dataset.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
        } else {
            await apiCall('/employees', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }
        closeEmployeeModal();
        await loadEmployees();
    } catch (error) {
        console.error('Error saving employee:', error);
        alert('Fehler beim Speichern des Mitarbeiters: ' + error.message);
    }
}

