/* ============================================================
   KMRL Document Management System - Client-side JavaScript
   Handles: sidebar toggle, delete confirmation, instant table
   filtering, and small UX utilities.
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ---------------- Sidebar toggle (mobile) ----------------
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });
    }

    // ---------------- Confirm before delete ----------------
    document.querySelectorAll('.delete-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            const confirmed = confirm('Are you sure you want to delete this item? This action cannot be undone.');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // ---------------- Auto-dismiss flash alerts ----------------
    document.querySelectorAll('.alert').forEach(function (alertEl) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ---------------- Live table filter (Documents page) ----------------
    const liveFilter = document.getElementById('liveFilter');
    const statusFilter = document.getElementById('statusFilter');
    const docsTable = document.getElementById('docsTable');

    function filterTable() {
        if (!docsTable) return;
        const searchTerm = (liveFilter ? liveFilter.value : '').toLowerCase();
        const statusTerm = statusFilter ? statusFilter.value : '';

        docsTable.querySelectorAll('tbody tr').forEach(function (row) {
            const text = row.innerText.toLowerCase();
            const rowStatus = row.getAttribute('data-status') || '';

            const matchesSearch = text.includes(searchTerm);
            const matchesStatus = !statusTerm || rowStatus === statusTerm;

            row.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
        });
    }

    if (liveFilter) liveFilter.addEventListener('keyup', filterTable);
    if (statusFilter) statusFilter.addEventListener('change', filterTable);

    // ---------------- Instant search suggestions (Search page) ----------------
    const searchInput = document.querySelector('.search-form input[name="q"]');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                // Placeholder for future AJAX live-suggestions via /api/search
            }, 300);
        });
    }

});

// ---------------- Toast Notification Helper ----------------
function showToast(message, type) {
    type = type || 'info';
    const container = document.querySelector('.page-body') || document.body;

    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.innerHTML = `<i class="bi bi-info-circle-fill me-2"></i>${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;

    container.prepend(toast);

    setTimeout(function () {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(toast);
        if (bsAlert) bsAlert.close();
    }, 4000);
}
