// Configuration
const API_BASE_URL = 'https://resume-web-4.onrender.com'; // Change to your local URL if testing locally

// State Management
let currentToken = localStorage.getItem('admin_token');
let currentPage = 'messages';

// DOM Elements
const loginContainer = document.getElementById('login-container');
const dashboardContainer = document.getElementById('dashboard-container');
const loginForm = document.getElementById('login-form');
const logoutBtn = document.getElementById('logout-btn');
const navLinks = document.querySelectorAll('.nav-links li');
const tableContainer = document.getElementById('table-container');
const loadingSpinner = document.getElementById('loading-spinner');
const pageTitle = document.getElementById('page-title');
const refreshBtn = document.getElementById('refresh-btn');

// --- Initialization ---
function init() {
    if (currentToken) {
        showDashboard();
    } else {
        showLogin();
    }
}

// --- UI Switching ---
function showLogin() {
    loginContainer.style.display = 'flex';
    dashboardContainer.style.display = 'none';
}

function showDashboard() {
    loginContainer.style.display = 'none';
    dashboardContainer.style.display = 'flex';
    loadData();
}

// --- Authentication ---
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('login-error');

    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/api/admin/login`, {
            method: 'POST',
            body: formData,
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });

        if (response.ok) {
            const data = await response.json();
            currentToken = data.access_token;
            localStorage.setItem('admin_token', currentToken);
            showDashboard();
        } else {
            errorMsg.textContent = 'Invalid credentials. Please try again.';
        }
    } catch (err) {
        errorMsg.textContent = 'Connection error. Check backend.';
    }
});

logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('admin_token');
    currentToken = null;
    showLogin();
});

// --- Navigation ---
navLinks.forEach(link => {
    link.addEventListener('click', () => {
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        currentPage = link.dataset.page;
        pageTitle.textContent = currentPage === 'messages' ? 'Contact Messages' : 'Chat History';
        loadData();
    });
});

refreshBtn.addEventListener('click', loadData);

// --- Data Fetching ---
async function loadData() {
    tableContainer.innerHTML = '';
    loadingSpinner.style.display = 'block';

    const endpoint = currentPage === 'messages' ? '/api/admin/messages' : '/api/admin/chats';
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });

        if (response.status === 401) {
            handleAuthError();
            return;
        }

        const data = await response.json();
        renderData(data);
    } catch (err) {
        tableContainer.innerHTML = '<p class="error-msg">Error loading data. Is the backend running?</p>';
    } finally {
        loadingSpinner.style.display = 'none';
    }
}

function renderData(data) {
    if (data.length === 0) {
        tableContainer.innerHTML = '<p class="text-dim">No data available yet.</p>';
        return;
    }

    if (currentPage === 'messages') {
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Message</th>
                        <th>Phone</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
        `;
        data.forEach(msg => {
            const date = new Date(msg.created_at).toLocaleDateString();
            html += `
                <tr>
                    <td><b>${msg.name}</b></td>
                    <td>${msg.email}</td>
                    <td>${msg.message}</td>
                    <td>${msg.phone || '-'}</td>
                    <td class="date-col">${date}</td>
                </tr>
            `;
        });
        html += '</tbody></table>';
        tableContainer.innerHTML = html;
    } else {
        let html = '<div class="chat-list">';
        data.forEach(chat => {
            const date = new Date(chat.timestamp).toLocaleString();
            html += `
                <div class="chat-entry">
                    <div class="chat-user">User: ${chat.user_message}</div>
                    <div class="chat-bot">Bot: ${chat.bot_reply}</div>
                    <div class="chat-time">${date}</div>
                </div>
            `;
        });
        html += '</div>';
        tableContainer.innerHTML = html;
    }
}

function handleAuthError() {
    localStorage.removeItem('admin_token');
    currentToken = null;
    showLogin();
    alert('Session expired. Please login again.');
}

// Start
init();
