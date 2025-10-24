// API Configuration
const { protocol, host } = window.location;
const API_BASE_URL = `${protocol}//${host}/api`;
const AUTH_STORAGE_KEY = 'zeiterfassung.auth';

// Global variables
let authToken = null;
let currentUser = null;
let sessionExpiredShown = false;
let appInitialized = false;
let currentEmployee = null;
// Use today's date as initial selection
const today = new Date();
let currentMonth = today.getMonth();
let currentYear = today.getFullYear();
let timeEntries = [];
let employees = [];
let revenueEntries = [];
let currentRevenueMonth = currentMonth;
let currentRevenueYear = currentYear;
let reportsOverviewSummaries = [];
let currentReportsMonth = currentMonth;
let currentReportsYear = currentYear;

// Format date as YYYY-MM-DD in local time
function formatDate(date) {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().split('T')[0];
}

function isAuthenticated() {
    return Boolean(authToken);
}

function isAdmin() {
    return currentUser?.role === 'admin';
}

function isEmployeeRole() {
    return currentUser?.role === 'employee';
}

function withAuthHeaders(additionalHeaders = {}) {
    const headers = { ...additionalHeaders };
    if (authToken) {
        headers.Authorization = `Bearer ${authToken}`;
    }
    return headers;
}

function isMonthLockedForDateString(dateStr) {
    if (!dateStr) {
        return false;
    }

    const parts = dateStr.split('-');
    if (parts.length < 2) {
        return false;
    }

    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);

    if (!Number.isFinite(year) || !Number.isFinite(month)) {
        return false;
    }

    const today = new Date();
    const entryMonthStart = new Date(year, month - 1, 1);
    const currentMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    return entryMonthStart < currentMonthStart;
}

function isEmployeeEditingLocked(dateStr) {
    return isEmployeeRole() && isMonthLockedForDateString(dateStr);
}

function updateAuthVisibility() {
    const loginContainer = document.getElementById('loginContainer');
    const appContainer = document.getElementById('appContainer');
    const logoutButton = document.getElementById('logoutButton');
    const userLabel = document.getElementById('currentUserLabel');

    if (isAuthenticated()) {
        loginContainer?.classList.add('hidden');
        appContainer?.classList.remove('hidden');
        if (logoutButton) {
            logoutButton.style.display = 'inline-flex';
        }
        if (userLabel) {
            const roleLabel = isAdmin() ? 'Admin' : 'Mitarbeiter';
            userLabel.textContent = `${currentUser?.username || ''} (${roleLabel})`;
        }
    } else {
        loginContainer?.classList.remove('hidden');
        appContainer?.classList.add('hidden');
        if (logoutButton) {
            logoutButton.style.display = 'none';
        }
        if (userLabel) {
            userLabel.textContent = '';
        }
    }
}

function applyRoleRestrictions() {
    const adminElements = document.querySelectorAll('[data-admin-only="true"]');
    adminElements.forEach(element => {
        if (isAdmin()) {
            element.classList.remove('hidden');
        } else {
            element.classList.add('hidden');
        }
    });

    const activeSection = document.querySelector('.section.active');
    if (activeSection?.classList.contains('hidden')) {
        const dashboardTab = document.querySelector('.nav-tab[data-section="dashboard"]');
        showSection('dashboard', dashboardTab);
    }
}

function resetAppData() {
    currentEmployee = null;
    timeEntries = [];
    employees = [];
    revenueEntries = [];
    reportsOverviewSummaries = [];

    const employeeSelect = document.getElementById('employeeSelect');
    if (employeeSelect) {
        employeeSelect.innerHTML = '<option value="">Mitarbeiter auswählen</option>';
    }

    const calendarContainer = document.getElementById('calendarContainer');
    if (calendarContainer) {
        calendarContainer.innerHTML = '';
    }

    const summary = document.getElementById('monthSummary');
    if (summary) {
        summary.style.display = 'none';
        summary.innerHTML = '';
    }

    const monthLockNotice = document.getElementById('monthLockNotice');
    if (monthLockNotice) {
        monthLockNotice.style.display = 'none';
        monthLockNotice.textContent = '';
    }

    const reportsContainer = document.getElementById('reportsOverviewContainer');
    if (reportsContainer) {
        reportsContainer.innerHTML = '<div class="loading">Bitte wählen Sie einen Zeitraum aus.</div>';
    }

    const revenueContainer = document.getElementById('revenueCalendarContainer');
    if (revenueContainer) {
        revenueContainer.innerHTML = '';
    }

    const employeeTableBody = document.getElementById('employeeTableBody');
    if (employeeTableBody) {
        employeeTableBody.innerHTML = '';
    }
}

function setAuthState(authData) {
    authToken = authData?.token || null;
    currentUser = authData?.user || null;
    sessionExpiredShown = false;

    if (authToken && currentUser) {
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authData));
    } else {
        localStorage.removeItem(AUTH_STORAGE_KEY);
    }

    updateAuthVisibility();
    applyRoleRestrictions();
}

function clearAuthState() {
    authToken = null;
    currentUser = null;
    sessionExpiredShown = false;
    localStorage.removeItem(AUTH_STORAGE_KEY);
    currentMonth = today.getMonth();
    currentYear = today.getFullYear();
    currentRevenueMonth = currentMonth;
    currentRevenueYear = currentYear;
    currentReportsMonth = currentMonth;
    currentReportsYear = currentYear;
    resetAppData();
    updateAuthVisibility();
    applyRoleRestrictions();
}

function handleUnauthorized() {
    if (!sessionExpiredShown) {
        sessionExpiredShown = true;
        alert('Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.');
    }
    clearAuthState();
    const loginError = document.getElementById('loginError');
    if (loginError) {
        loginError.textContent = 'Bitte erneut anmelden.';
        loginError.style.display = 'block';
    }
}

async function handleLogin(event) {
    event.preventDefault();

    const usernameInput = document.getElementById('loginUsername');
    const passwordInput = document.getElementById('loginPassword');
    const loginError = document.getElementById('loginError');

    if (!usernameInput || !passwordInput) {
        return;
    }

    const credentials = {
        username: usernameInput.value.trim(),
        password: passwordInput.value,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            loginError.textContent = data.error || 'Anmeldung fehlgeschlagen.';
            loginError.style.display = 'block';
            return;
        }

        loginError.textContent = '';
        loginError.style.display = 'none';

        setAuthState(data);
        await initializeApp();
    } catch (error) {
        console.error('Login fehlgeschlagen:', error);
        if (loginError) {
            loginError.textContent = 'Anmeldung nicht möglich. Bitte später erneut versuchen.';
            loginError.style.display = 'block';
        }
    }
}

async function logout() {
    if (!isAuthenticated()) {
        clearAuthState();
        return;
    }

    try {
        await fetch(`${API_BASE_URL}/logout`, {
            method: 'POST',
            headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
        });
    } catch (error) {
        console.warn('Logout request failed:', error);
    }

    clearAuthState();
}

function setupApplicationEventListeners() {
    if (appInitialized) {
        return;
    }

    const employeeSelect = document.getElementById('employeeSelect');
    if (employeeSelect) {
        employeeSelect.addEventListener('change', async (e) => {
            if (!e.target.value) {
                return;
            }
            await loadCalendar();
        });
    }

    const reportsMonthSelect = document.getElementById('reportsMonthSelect');
    const reportsYearSelect = document.getElementById('reportsYearSelect');
    if (reportsMonthSelect && reportsYearSelect) {
        reportsMonthSelect.addEventListener('change', () => loadReportsOverview());
        reportsYearSelect.addEventListener('change', () => loadReportsOverview());
    }

    const reportsRefreshButton = document.getElementById('reportsRefreshButton');
    if (reportsRefreshButton) {
        reportsRefreshButton.addEventListener('click', () => loadReportsOverview());
    }

    const reportsExportButton = document.getElementById('reportsExportButton');
    if (reportsExportButton) {
        reportsExportButton.addEventListener('click', exportReportsOverview);
    }

    const reportsPdfExportButton = document.getElementById('reportsPdfExportButton');
    if (reportsPdfExportButton) {
        reportsPdfExportButton.addEventListener('click', exportReportsOverviewPdf);
    }

    const reportsPdfDetailedExportButton = document.getElementById('reportsPdfDetailedExportButton');
    if (reportsPdfDetailedExportButton) {
        reportsPdfDetailedExportButton.addEventListener('click', exportReportsOverviewPdfDetailed);
    }

    appInitialized = true;
}

function setInitialSelectValues() {
    const monthSelect = document.getElementById('monthSelect');
    const yearSelect = document.getElementById('yearSelect');
    const revMonthSelect = document.getElementById('revMonthSelect');
    const revYearSelect = document.getElementById('revYearSelect');
    const reportsMonthSelect = document.getElementById('reportsMonthSelect');
    const reportsYearSelect = document.getElementById('reportsYearSelect');

    if (monthSelect) monthSelect.value = String(currentMonth);
    if (yearSelect) yearSelect.value = String(currentYear);
    if (revMonthSelect) revMonthSelect.value = String(currentMonth);
    if (revYearSelect) revYearSelect.value = String(currentYear);
    if (reportsMonthSelect) reportsMonthSelect.value = String(currentReportsMonth);
    if (reportsYearSelect) reportsYearSelect.value = String(currentReportsYear);
}

async function initializeApp() {
    if (!isAuthenticated()) {
        return;
    }

    setupApplicationEventListeners();
    setInitialSelectValues();

    try {
        await loadEmployees();
        loadDashboard();

        if (isAdmin()) {
            await loadCommissionSettings();
            await loadCommissionThresholds();
            await loadRevenueCalendar();
        }
    } catch (error) {
        console.error('Fehler bei der Initialisierung:', error);
    }
}

function setupAuthHandlers() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }

    updateAuthVisibility();
    applyRoleRestrictions();

    const storedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
    if (storedAuth) {
        try {
            const parsed = JSON.parse(storedAuth);
            if (parsed?.token && parsed?.user) {
                setAuthState(parsed);
                initializeApp();
                return;
            }
        } catch (error) {
            console.warn('Gespeicherte Sitzung konnte nicht geladen werden:', error);
        }
    }

    clearAuthState();
}

// Initialize app
document.addEventListener('DOMContentLoaded', setupAuthHandlers);

// API Functions
async function apiCall(endpoint, options = {}) {
    try {
        const fetchOptions = {
            ...options,
            headers: withAuthHeaders({
                'Content-Type': 'application/json',
                ...(options.headers || {})
            })
        };

        const response = await fetch(`${API_BASE_URL}${endpoint}`, fetchOptions);

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
            handleUnauthorized();
            throw new Error(data.error || 'Authentifizierung erforderlich');
        }

        if (response.status === 403) {
            throw new Error(data.error || 'Keine Berechtigung');
        }

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
    if (!isAuthenticated()) {
        return;
    }
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
        if (!isAuthenticated()) {
            return;
        }
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
function showSection(sectionName, tabElement = null) {
    const targetSection = document.getElementById(sectionName);
    if (!targetSection || targetSection.classList.contains('hidden')) {
        return;
    }

    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });

    // Remove active class from all tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected section
    targetSection.classList.add('active');

    // Add active class to clicked tab or fallback to matching tab
    const activeTab = tabElement || (typeof event !== 'undefined' ? (event.currentTarget || event.target) : null);
    if (activeTab) {
        activeTab.classList.add('active');
    } else {
        const fallbackTab = document.querySelector(`.nav-tab[data-section="${sectionName}"]`);
        if (fallbackTab) {
            fallbackTab.classList.add('active');
        }
    }

    if (sectionName === 'reports') {
        loadReportsOverview();
    }
}

// Load reports overview
async function loadReportsOverview() {
    if (!isAdmin()) {
        return;
    }
    const container = document.getElementById('reportsOverviewContainer');
    const monthSelect = document.getElementById('reportsMonthSelect');
    const yearSelect = document.getElementById('reportsYearSelect');

    if (!container || !monthSelect || !yearSelect) {
        return;
    }

    const month = parseInt(monthSelect.value, 10);
    const year = parseInt(yearSelect.value, 10);

    if (!Number.isFinite(month) || !Number.isFinite(year)) {
        return;
    }

    currentReportsMonth = month;
    currentReportsYear = year;
    container.innerHTML = '<div class="loading">Lade Auswertungen...</div>';
    reportsOverviewSummaries = [];

    try {
        const overview = await apiCall(`/reports/overview/${year}/${month + 1}`);
        const summaries = buildReportsOverviewSummaries(overview.employees || []);

        reportsOverviewSummaries = summaries;

        renderReportsOverview({ month, year, summaries });
    } catch (error) {
        console.error('Error loading reports overview:', error);
        container.innerHTML = `<div class="error-message">Fehler beim Laden der Auswertungen: ${error.message}</div>`;
    }
}

function buildReportsOverviewSummaries(overviewEmployees) {
    if (!Array.isArray(overviewEmployees)) {
        return [];
    }

    return overviewEmployees
        .map(item => {
            const employee = item.employee || {};
            const summary = item.summary || {};

            const employeeName = employee.name || 'Unbekannt';

            return {
                employeeId: employee.id,
                employeeName,
                totalHours: Number(summary.total_hours ?? 0),
                workDays: Number(summary.work_days ?? 0),
                vacationDays: Number(summary.vacation_days ?? 0),
                sickDays: Number(summary.sick_days ?? 0),
                duftreiseBis18: Number(summary.total_duftreise_bis_18 ?? 0),
                duftreiseAb18: Number(summary.total_duftreise_ab_18 ?? 0),
                totalCommission: Number(summary.total_commission ?? 0),
                contractHoursMonth: Number(summary.contract_hours_month ?? 0),
            };
        })
        .sort((a, b) => a.employeeName.localeCompare(b.employeeName, 'de'));
}

function renderReportsOverview(data) {
    const container = document.getElementById('reportsOverviewContainer');

    if (!container) {
        return;
    }

    const monthNames = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
    const monthName = Number.isFinite(data.month) ? (monthNames[data.month] || '') : '';
    const title = monthName ? `Auswertungen ${monthName} ${data.year}` : `Auswertungen ${data.year}`;

    if (!data.summaries.length) {
        container.innerHTML = `
            <div class="month-summary">
                <div class="summary-title">${title}</div>
                <div class="reports-empty">Keine Daten für den ausgewählten Zeitraum vorhanden.</div>
            </div>
        `;
        return;
    }

    const cards = data.summaries.map(summary => `
        <div class="summary-item report-card">
            <div class="report-card-header">${summary.employeeName}</div>
            <div class="summary-value">${formatHoursMinutes(summary.totalHours)}</div>
            <div class="summary-label">Gesamtstunden</div>
            <div class="report-card-body">
                <div>Arbeitstage: <span>${summary.workDays}</span></div>
                <div>Urlaubstage: <span>${summary.vacationDays}</span></div>
                <div>Krankheitstage: <span>${summary.sickDays}</span></div>
                <div>Duftreisen vor 18 Uhr: <span>${summary.duftreiseBis18}</span></div>
                <div>Duftreisen nach 18 Uhr: <span>${summary.duftreiseAb18}</span></div>
                <div>Provision: <span>${summary.totalCommission.toFixed(2)}€</span></div>
            </div>
        </div>
    `).join('');

    container.innerHTML = `
        <div class="month-summary">
            <div class="summary-title">${title}</div>
            <div class="summary-grid reports-grid">${cards}</div>
        </div>
    `;
}

async function exportReportsOverview() {
    if (!isAdmin()) {
        return;
    }
    const monthSelect = document.getElementById('reportsMonthSelect');
    const yearSelect = document.getElementById('reportsYearSelect');

    const month = monthSelect ? parseInt(monthSelect.value, 10) : currentReportsMonth;
    const year = yearSelect ? parseInt(yearSelect.value, 10) : currentReportsYear;

    if (!Number.isFinite(month) || !Number.isFinite(year)) {
        alert('Bitte wählen Sie zuerst einen gültigen Monat und ein Jahr aus.');
        return;
    }

    currentReportsMonth = month;
    currentReportsYear = year;

    const monthNumber = String(month + 1).padStart(2, '0');
    const fileName = `auswertungen_${year}_${monthNumber}.csv`;
    const exportUrl = `${API_BASE_URL}/reports/overview/${year}/${month + 1}/export`;

    try {
        const response = await fetch(exportUrl, { headers: withAuthHeaders() });

        if (response.status === 401) {
            handleUnauthorized();
            return;
        }

        if (response.status === 403) {
            throw new Error('Keine Berechtigung');
        }

        if (!response.ok) {
            throw new Error(`Export fehlgeschlagen: ${response.status}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Export error:', error);
        alert(`Fehler beim Export der Auswertungen: ${error.message}`);
    }
}

async function exportReportsOverviewPdf() {
    if (!isAdmin()) {
        return;
    }
    const monthSelect = document.getElementById('reportsMonthSelect');
    const yearSelect = document.getElementById('reportsYearSelect');

    const month = monthSelect ? parseInt(monthSelect.value, 10) : currentReportsMonth;
    const year = yearSelect ? parseInt(yearSelect.value, 10) : currentReportsYear;

    if (!Number.isFinite(month) || !Number.isFinite(year)) {
        alert('Bitte wählen Sie zuerst einen gültigen Monat und ein Jahr aus.');
        return;
    }

    currentReportsMonth = month;
    currentReportsYear = year;

    const monthNumber = String(month + 1).padStart(2, '0');
    const fileName = `auswertungen_${year}_${monthNumber}.pdf`;
    const exportUrl = `${API_BASE_URL}/reports/overview/${year}/${month + 1}/export/pdf`;

    try {
        const response = await fetch(exportUrl, { headers: withAuthHeaders() });

        if (response.status === 401) {
            handleUnauthorized();
            return;
        }

        if (response.status === 403) {
            throw new Error('Keine Berechtigung');
        }

        if (!response.ok) {
            throw new Error(`Export fehlgeschlagen: ${response.status}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('PDF export error:', error);
        alert(`Fehler beim PDF-Export der Auswertungen: ${error.message}`);
    }
}

async function exportReportsOverviewPdfDetailed() {
    if (!isAdmin()) {
        return;
    }
    const monthSelect = document.getElementById('reportsMonthSelect');
    const yearSelect = document.getElementById('reportsYearSelect');

    const month = monthSelect ? parseInt(monthSelect.value, 10) : currentReportsMonth;
    const year = yearSelect ? parseInt(yearSelect.value, 10) : currentReportsYear;

    if (!Number.isFinite(month) || !Number.isFinite(year)) {
        alert('Bitte wählen Sie zuerst einen gültigen Monat und ein Jahr aus.');
        return;
    }

    currentReportsMonth = month;
    currentReportsYear = year;

    const monthNumber = String(month + 1).padStart(2, '0');
    const fileName = `auswertungen_${year}_${monthNumber}_detailliert.pdf`;
    const exportUrl = `${API_BASE_URL}/reports/overview/${year}/${month + 1}/export/pdf/detailed`;

    try {
        const response = await fetch(exportUrl, { headers: withAuthHeaders() });

        if (response.status === 401) {
            handleUnauthorized();
            return;
        }

        if (response.status === 403) {
            throw new Error('Keine Berechtigung');
        }

        if (!response.ok) {
            throw new Error(`Export fehlgeschlagen: ${response.status}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('PDF export error:', error);
        alert(`Fehler beim PDF-Export der Auswertungen: ${error.message}`);
    }
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
    if (!currentEmployee) {
        alert('Der ausgewählte Mitarbeiter konnte nicht geladen werden.');
        return;
    }
    currentMonth = month;
    currentYear = year;
    updateMonthLockNotice();

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

function updateMonthLockNotice() {
    const notice = document.getElementById('monthLockNotice');
    if (!notice) {
        return;
    }

    const monthString = String(currentMonth + 1).padStart(2, '0');
    const referenceDate = `${currentYear}-${monthString}-01`;

    if (isEmployeeRole() && isMonthLockedForDateString(referenceDate)) {
        notice.textContent = 'Der ausgewählte Monat ist abgeschlossen. Änderungen sind nicht mehr möglich.';
        notice.style.display = 'block';
    } else {
        notice.style.display = 'none';
        notice.textContent = '';
    }
}

// Render calendar
function renderCalendar() {
    updateMonthLockNotice();
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
            const lockedForEmployee = isEmployeeEditingLocked(dateStr);
            if (lockedForEmployee) dayClass += ' locked-day';
            
            let dayInfo = '';
            if (entry) {
                if (entry.entry_type === 'vacation') {
                    dayInfo = '<div class="day-info">Urlaub</div>';
                } else if (entry.entry_type === 'sick') {
                    dayInfo = '<div class="day-info">Krank</div>';
                } else if (entry.start_time && entry.end_time) {
                    const hours = calculateHours(entry.start_time, entry.end_time, entry.pause_minutes || 0);
                    dayInfo = `<div class="day-info">${entry.start_time}-${entry.end_time}<br>${formatHoursMinutes(hours)}</div>`;
                }
            }
            
            html += `
                <div class="${dayClass}" onclick="onCalendarDayClick('${dateStr}')">
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
    
    const totalDuftreiseBis18 = timeEntries.reduce((sum, entry) => {
        const value = Number(entry.duftreise_bis_18 ?? 0);
        return sum + (Number.isFinite(value) ? value : 0);
    }, 0);

    const totalDuftreiseAb18 = timeEntries.reduce((sum, entry) => {
        const value = Number(entry.duftreise_ab_18 ?? 0);
        return sum + (Number.isFinite(value) ? value : 0);
    }, 0);

    const totalProvision = timeEntries.reduce((sum, entry) => {
        const commission = Number(entry.commission ?? 0);
        return sum + (Number.isFinite(commission) ? commission : 0);
    }, 0);

    const safeTotalHours = Number.isFinite(totalHours) ? totalHours : 0;
    const safeTotalProvision = Number.isFinite(totalProvision) ? totalProvision : 0;
    
    summary.innerHTML = `
        <div class="summary-title">Monatsübersicht ${currentEmployee.name}</div>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-value">${formatHoursMinutes(safeTotalHours)}</div>
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
                <div class="summary-value">${totalDuftreiseBis18}</div>
                <div class="summary-label">Duftreisen vor 18 Uhr</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${totalDuftreiseAb18}</div>
                <div class="summary-label">Duftreisen nach 18 Uhr</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">${safeTotalProvision.toFixed(2)}€</div>
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

function formatHoursMinutes(totalHours) {
    if (!Number.isFinite(totalHours)) {
        return '0h00min';
    }

    const safeHours = Math.max(0, totalHours);
    const totalMinutes = Math.round(safeHours * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = String(totalMinutes % 60).padStart(2, '0');

    return `${hours}h${minutes}min`;
}

// Open time modal
function onCalendarDayClick(dateStr) {
    if (isEmployeeEditingLocked(dateStr)) {
        alert('Der ausgewählte Monat ist abgeschlossen. Änderungen sind nicht mehr möglich.');
        return;
    }
    openTimeModal(dateStr);
}

function openTimeModal(dateStr) {
    const modal = document.getElementById('timeModal');
    const title = document.getElementById('modalTitle');
    const date = new Date(dateStr);
    
    const formattedDate = date.toLocaleDateString('de-DE', {
        weekday: 'long',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
    const capitalizedDate = formattedDate
        ? formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1)
        : '';

    title.textContent = `Zeiterfassung – ${capitalizedDate}`;
    
    // Find existing entry
    const entry = timeEntries.find(e => e.date === dateStr);
    
    // Fill form
    document.getElementById('entryType').value = entry?.entry_type || 'work';
    document.getElementById('startTime').value = entry?.start_time || '';
    document.getElementById('endTime').value = entry?.end_time || '';
    const pauseInput = document.getElementById('pause');
    if (pauseInput) {
        if (entry && entry.pause_minutes !== null && entry.pause_minutes !== undefined) {
            pauseInput.value = entry.pause_minutes;
        } else if (!entry) {
            pauseInput.value = 30;
        } else {
            pauseInput.value = '';
        }
    }
    document.getElementById('provision').value = entry?.commission || '';
    document.getElementById('duftreisen1').value = entry?.duftreise_bis_18 || '';
    document.getElementById('duftreisen2').value = entry?.duftreise_ab_18 || '';
    document.getElementById('notes').value = entry?.notes || '';

    // Store current date
    modal.dataset.date = dateStr;
    modal.dataset.entryId = entry?.id || '';

    const deleteButton = document.getElementById('deleteEntryButton');
    if (deleteButton) {
        deleteButton.style.display = entry ? 'inline-flex' : 'none';
        deleteButton.disabled = !entry;
    }

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

    if (isEmployeeEditingLocked(date)) {
        alert('Der Monat ist abgeschlossen. Änderungen sind nicht mehr möglich.');
        return;
    }
    
    const startTimeValue = document.getElementById('startTime').value.trim();
    const endTimeValue = document.getElementById('endTime').value.trim();
    const notesValue = document.getElementById('notes').value.trim();

    const data = {
        employee_id: currentEmployee.id,
        date: date,
        entry_type: document.getElementById('entryType').value,
        start_time: startTimeValue || null,
        end_time: endTimeValue || null,
        pause_minutes: parseInt(document.getElementById('pause').value) || 0,
        commission: parseFloat(document.getElementById('provision').value) || 0,
        duftreise_bis_18: parseInt(document.getElementById('duftreisen1').value) || 0,
        duftreise_ab_18: parseInt(document.getElementById('duftreisen2').value) || 0,
        notes: notesValue || null
    };

    const isWorkType = data.entry_type === 'work';
    const hasStart = Boolean(data.start_time);
    const hasEnd = Boolean(data.end_time);
    const workFieldsEmpty = isWorkType && !hasStart && !hasEnd &&
        !data.notes && (data.pause_minutes === 0) && (data.commission === 0) &&
        (data.duftreise_bis_18 === 0) && (data.duftreise_ab_18 === 0);

    if (isWorkType && (hasStart !== hasEnd)) {
        alert('Bitte sowohl Start- als auch Endzeit angeben oder den Eintrag löschen.');
        return;
    }

    try {
        if (entryId && workFieldsEmpty) {
            const shouldDelete = confirm('Alle Pflichtfelder wurden geleert. Soll der Eintrag gelöscht werden?');
            if (shouldDelete) {
                await deleteEntryById(entryId);
                closeModal();
                await loadCalendar();
            } else {
                alert('Verwenden Sie zum Entfernen den Löschen-Button.');
            }
            return;
        }

        if (!entryId && workFieldsEmpty) {
            alert('Bitte Arbeitszeiten erfassen oder den Tag frei lassen.');
            return;
        }

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
        await loadCalendar(); // Reload calendar
    } catch (error) {
        console.error('Error saving entry:', error);
        alert(error.message);
    }
}

async function deleteEntryById(entryId) {
    await apiCall(`/time-entries/${entryId}`, {
        method: 'DELETE'
    });
}

async function deleteCurrentEntry() {
    const modal = document.getElementById('timeModal');
    const entryId = modal.dataset.entryId;
    const date = modal.dataset.date;

    if (!entryId) {
        return;
    }

    if (isEmployeeEditingLocked(date)) {
        alert('Der Monat ist abgeschlossen. Änderungen sind nicht mehr möglich.');
        return;
    }

    const confirmDelete = confirm('Möchten Sie diesen Eintrag wirklich löschen?');
    if (!confirmDelete) {
        return;
    }

    try {
        await deleteEntryById(entryId);
        closeModal();
        await loadCalendar();
    } catch (error) {
        console.error('Error deleting entry:', error);
        alert(error.message);
    }
}

// Export PDF
async function exportPDF() {
    if (!currentEmployee) {
        alert('Bitte wählen Sie einen Mitarbeiter und laden Sie den Kalender.');
        return;
    }

    const monthNumber = String(currentMonth + 1).padStart(2, '0');
    const exportUrl = `${API_BASE_URL}/reports/monthly/${currentEmployee.id}/${currentYear}/${currentMonth + 1}/export/pdf`;
    const sanitizedName = (currentEmployee.name || 'mitarbeiter').replace(/[^a-z0-9_-]+/gi, '_');
    const fileName = `arbeitszeit_${sanitizedName}_${currentYear}_${monthNumber}.pdf`;

    try {
        const response = await fetch(exportUrl, { headers: withAuthHeaders() });

        if (response.status === 401) {
            handleUnauthorized();
            return;
        }

        if (response.status === 403) {
            throw new Error('Keine Berechtigung');
        }

        if (!response.ok) {
            throw new Error(`Export fehlgeschlagen: ${response.status}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('PDF export error:', error);
        alert(`Fehler beim PDF-Export: ${error.message}`);
    }
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
    if (!isAdmin()) {
        return;
    }
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
    if (!isAdmin()) {
        alert('Keine Berechtigung.');
        return;
    }
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

// -------------------- Umsatzfunktionen --------------------

async function loadRevenueCalendar() {
    if (!isAdmin()) {
        return;
    }
    const month = parseInt(document.getElementById('revMonthSelect').value);
    const year = parseInt(document.getElementById('revYearSelect').value);

    currentRevenueMonth = month;
    currentRevenueYear = year;

    try {
        revenueEntries = await apiCall(`/revenue?year=${year}&month=${month + 1}`);
        renderRevenueCalendar();
    } catch (error) {
        console.error('Error loading revenue:', error);
        showError('Fehler beim Laden der Umsätze: ' + error.message);
    }
}

function renderRevenueCalendar() {
    const container = document.getElementById('revenueCalendarContainer');
    const monthNames = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
    const dayNames = ['So','Mo','Di','Mi','Do','Fr','Sa'];

    const firstDay = new Date(currentRevenueYear, currentRevenueMonth, 1);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());

    let html = `
        <div class="calendar-header">
            ${monthNames[currentRevenueMonth]} ${currentRevenueYear}
        </div>
        <div class="calendar">
    `;

    dayNames.forEach(d => {
        html += `<div class="calendar-day-header">${d}</div>`;
    });

    const currentDate = new Date(startDate);
    for (let week = 0; week < 6; week++) {
        for (let day = 0; day < 7; day++) {
            const isCurrentMonth = currentDate.getMonth() === currentRevenueMonth;
            const dateStr = formatDate(currentDate);
            const entry = revenueEntries.find(r => r.date === dateStr);

            let dayClass = 'calendar-day';
            if (!isCurrentMonth) dayClass += ' other-month';
            if (entry) dayClass += ' has-data';

            const info = entry ? `<div class="day-info">${entry.amount}€</div>` : '';

            html += `
                <div class="${dayClass}" onclick="openRevenueModal('${dateStr}')">
                    <div class="day-number">${currentDate.getDate()}</div>
                    ${info}
                </div>
            `;

            currentDate.setDate(currentDate.getDate() + 1);
        }
    }

    html += '</div>';
    container.innerHTML = html;
}

function openRevenueModal(dateStr) {
    if (!isAdmin()) {
        return;
    }
    const modal = document.getElementById('revenueModal');
    const title = document.getElementById('revenueModalTitle');
    const date = new Date(dateStr);

    title.textContent = `Umsatz - ${date.toLocaleDateString('de-DE')}`;

    const entry = revenueEntries.find(r => r.date === dateStr);

    document.getElementById('revenueAmount').value = entry?.amount || '';
    document.getElementById('revenueNotes').value = entry?.notes || '';

    modal.dataset.date = dateStr;
    modal.dataset.id = entry?.id || '';

    modal.classList.add('show');
}

function closeRevenueModal() {
    document.getElementById('revenueModal').classList.remove('show');
}

async function saveRevenue() {
    if (!isAdmin()) {
        alert('Keine Berechtigung.');
        return;
    }
    const modal = document.getElementById('revenueModal');
    const date = modal.dataset.date;
    const data = {
        date: date,
        amount: parseFloat(document.getElementById('revenueAmount').value) || 0,
        notes: document.getElementById('revenueNotes').value || null
    };

    try {
        await apiCall('/revenue', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        closeRevenueModal();
        loadRevenueCalendar();
    } catch (error) {
        console.error('Error saving revenue:', error);
        alert('Fehler beim Speichern des Umsatzes: ' + error.message);
    }
}

document.getElementById('revenueModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeRevenueModal();
    }
});

// -------------------- Provisionseinstellungen --------------------

async function loadCommissionSettings() {
    if (!isAdmin()) {
        return;
    }
    try {
        const data = await apiCall('/commission-settings');
        document.getElementById('commissionPercentage').value = data.percentage ?? '';
        document.getElementById('commissionMonthlyMax').value = data.monthly_max ?? '';
    } catch (error) {
        console.error('Error loading commission settings:', error);
    }
}

async function saveCommissionSettings() {
    if (!isAdmin()) {
        alert('Keine Berechtigung.');
        return;
    }
    const data = {
        percentage: parseFloat(document.getElementById('commissionPercentage').value) || 0,
        monthly_max: parseFloat(document.getElementById('commissionMonthlyMax').value) || 0
    };
    try {
        await apiCall('/commission-settings', { method: 'POST', body: JSON.stringify(data) });
        alert('Gespeichert');
    } catch (error) {
        console.error('Error saving commission settings:', error);
        alert('Fehler beim Speichern der Einstellungen: ' + error.message);
    }
}

async function loadCommissionThresholds() {
    if (!isAdmin()) {
        return;
    }
    try {
        const data = await apiCall('/commission-thresholds');
        renderThresholdTable(data);
    } catch (error) {
        console.error('Error loading thresholds:', error);
    }
}

function renderThresholdTable(data) {
    const tbody = document.getElementById('thresholdTableBody');
    tbody.innerHTML = '';
    const sorted = [...data].sort((a, b) => {
        if (a.weekday !== b.weekday) return a.weekday - b.weekday;
        if (a.employee_count !== b.employee_count) return a.employee_count - b.employee_count;
        const dateA = (a.valid_from || '1970-01-01');
        const dateB = (b.valid_from || '1970-01-01');
        return dateB.localeCompare(dateA);
    });
    sorted.forEach(th => {
        const validFrom = formatDateInput(th.valid_from);
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="number" class="th-weekday" value="${th.weekday ?? ''}"></td>
            <td><input type="number" class="th-count" value="${th.employee_count ?? ''}"></td>
            <td><input type="number" class="th-value" step="0.01" value="${th.threshold ?? ''}"></td>
            <td><input type="date" class="th-valid-from" value="${validFrom}"></td>`;
        tbody.appendChild(tr);
    });
}

function addThresholdRow() {
    const tbody = document.getElementById('thresholdTableBody');
    const tr = document.createElement('tr');
    const today = new Date().toISOString().split('T')[0];
    tr.innerHTML = `
        <td><input type="number" class="th-weekday"></td>
        <td><input type="number" class="th-count"></td>
        <td><input type="number" class="th-value" step="0.01"></td>
        <td><input type="date" class="th-valid-from" value="${today}"></td>`;
    tbody.appendChild(tr);
}

async function saveThresholds() {
    if (!isAdmin()) {
        alert('Keine Berechtigung.');
        return;
    }
    const rows = document.querySelectorAll('#thresholdTableBody tr');
    try {
        for (const row of rows) {
            const weekday = parseInt(row.querySelector('.th-weekday').value);
            const employee_count = parseInt(row.querySelector('.th-count').value);
            const threshold = parseFloat(row.querySelector('.th-value').value) || 0;
            const valid_from_input = row.querySelector('.th-valid-from')?.value;
            const valid_from = formatDateInput(valid_from_input);
            if (isNaN(weekday) || isNaN(employee_count)) continue;
            await apiCall('/commission-thresholds', {
                method: 'POST',
                body: JSON.stringify({ weekday, employee_count, threshold, valid_from })
            });
        }
        alert('Gespeichert');
        loadCommissionThresholds();
    } catch (error) {
        console.error('Error saving thresholds:', error);
        alert('Fehler beim Speichern der Schwellen: ' + error.message);
    }
}

function formatDateInput(value) {
    const dateString = (value && value.trim()) || '';
    if (dateString === '') {
        return '1970-01-01';
    }
    const parsed = new Date(dateString);
    if (Number.isNaN(parsed.getTime())) {
        return '1970-01-01';
    }
    return parsed.toISOString().split('T')[0];
}

