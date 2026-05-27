document.addEventListener("DOMContentLoaded", () => {
    const feed = document.getElementById('serviceFeed');
    const modal = document.getElementById('jobModal');
    const postBtn = document.getElementById('postJobBtn');
    const closeBtn = document.querySelector('.close-modal');
    const jobForm = document.getElementById('jobForm');
    const skillsInput = document.getElementById('jobSkillsInput');
    const formSkillsContainer = document.getElementById('formSkillsContainer');
    const jobDescInput = document.getElementById('jobDesc');
    const jobDescCounter = document.getElementById('jobDescCounter');
    const toastContainer = document.getElementById('toastContainer');
    const clientNameInput = document.getElementById('clientName');
    const clientNameCounter = document.getElementById('clientNameCounter');
    const clientContactInput = document.getElementById('clientContact');
    const clientContactCounter = document.getElementById('clientContactCounter');
    const reportModal = document.getElementById('reportModal');
    const closeReportModal = document.getElementById('closeReportModal');
    const reportForm = document.getElementById('reportForm');
    const jobSuccessState = document.getElementById('jobSuccessState');
    const btnDone = document.getElementById('btnDone');
    const viewMyPostsLink = document.getElementById('viewMyPostsLink');
    const myDashboardLink = document.getElementById('myDashboardLink');
    const suspensionBanner = document.getElementById('suspensionBanner');

    // State Management
    let jobs = [];
    let currentFormSkills = [];
    let currentUser = { loggedIn: false, isVerifiedTaker: false, isSuspended: false };

    // --- API Helpers ---
    async function apiRequest(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            return data;
        } catch (e) {
            return { success: false, message: "Connection lost." };
        }
    }

    async function fetchSession() {
        const data = await apiRequest('/api/user/session');
        if (data.logged_in) {
            currentUser = { loggedIn: true, isVerifiedTaker: data.is_skill_verified, isSuspended: data.is_suspended };
            if (myDashboardLink) myDashboardLink.style.display = 'block';
            if (postBtn && !data.is_suspended) postBtn.style.display = 'block';
            if (suspensionBanner && data.is_suspended) suspensionBanner.style.display = 'block';
        }
        renderFeed(); // Re-render to update Apply button states
    }

    async function fetchJobs() {
        const data = await apiRequest('/api/jobs');
        if (data.success) {
            jobs = data.jobs;
            renderFeed();
        }
    }

    function renderFeed() {
        if (jobs.length === 0) {
            feed.innerHTML = '<div class="loading-state">No professional opportunities found.</div>';
            return;
        }

        const applyBtnHtml = job.has_applied 
            ? `<button class="btn-apply" disabled style="background:#10B981; cursor:default;">✓ Applied</button>`
            : `<button class="btn-apply" ${(!currentUser.loggedIn || !currentUser.isVerifiedTaker) ? 'data-restricted="true"' : ''} onclick="apply(${job.id})">Apply Now</button>`;

        feed.innerHTML = jobs.map(job => `
            <div class="job-card">
                <div class="card-header">
                    <div class="avatar-circle"></div>
                    <div class="meta-info">
                        <h4>${job.poster}</h4>
                        <span>${job.verified ? '<i class="fas fa-check-circle verified-icon"></i> Verified Client' : 'Client'} • 2h ago</span>
                    </div>
                </div>
                <div class="job-title">${job.title}</div>
                <p class="job-desc">${job.description}</p>
                <div class="skill-badges" style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 15px;">
                    ${(job.skills || []).map(skill => `<span class="badge" style="background:#EBF5FF; color:#1E40AF; padding:4px 10px; border-radius:16px; font-size:0.8rem; font-weight:700;">${skill}</span>`).join('')}
                </div>
                <div class="card-footer">
                    <div class="budget">${job.budget}</div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        ${applyBtnHtml}
                        <button class="btn-report" onclick="openReportModal(${job.id})">Report</button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span class="toast-message">${message}</span>
            <i class="fas fa-times close-toast"></i>
            <div class="toast-progress"></div>
        `;

        const dismiss = () => {
            toast.style.animation = 'toastSlideOut 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        };

        toast.querySelector('.close-toast').onclick = dismiss;
        toastContainer.appendChild(toast);
        setTimeout(() => { if(toast.parentElement) dismiss(); }, 4000);
    }

    // Character Counter for Job Description
    jobDescInput.addEventListener('input', () => {
        jobDescInput.classList.remove('error');
        jobDescCounter.textContent = `${jobDescInput.value.length} / 500`;
    });

    clientNameInput.addEventListener('input', () => {
        clientNameCounter.textContent = `${clientNameInput.value.length} / 100`;
    });

    clientContactInput.addEventListener('input', () => {
        clientContactCounter.textContent = `${clientContactInput.value.length} / 100`;
    });

    // No longer using dynamic skill input for job posting form
    // The `jobSkillsInput` and `formSkillsContainer` elements are removed from HTML
    // So, this logic is no longer needed.

    // Phase A: Ingestion - Handling the Project Brief submission
    jobForm.onsubmit = async (e) => {
        e.preventDefault();
        
        const clientName = document.getElementById('clientName').value.trim();
        const clientContact = document.getElementById('clientContact').value.trim();
        const jobTitle = document.getElementById('jobTitle').value.trim();
        const jobDesc = document.getElementById('jobDesc').value.trim();
        const requiredSkill = document.getElementById('requiredSkill').value;
        const budgetAmount = document.getElementById('budgetAmount').value;
        const budgetType = document.querySelector('input[name="budgetType"]:checked').value;

        if (!jobDesc) {
            jobDescInput.classList.add('error', 'shake');
            // Remove the shake class after the animation ends (400ms) so it can be re-triggered
            setTimeout(() => jobDescInput.classList.remove('shake'), 400);
            showToast("The project description cannot be empty.", "error");
            return;
        }

        // Regex validation for client_contact (email or phone)
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        // Kenyan mobile regex: supports 07..., 01..., +2547..., +2541..., 2547..., 2541...
        const phoneRegex = /^(?:0|\+?254)(?:1|7)\d{8}$/;

        if (!emailRegex.test(clientContact) && !phoneRegex.test(clientContact)) {
            clientContactInput.classList.add('error', 'shake');
            setTimeout(() => clientContactInput.classList.remove('shake'), 400);
            showToast("Client contact must be a valid email or phone number.", "error");
            return;
        }

        // Remove error class if validation passes after a previous failure
        clientContactInput.classList.remove('error');

        const payload = {
            client_name: clientName,
            client_contact: clientContact,
            job_title: jobTitle,
            job_description: jobDesc,
            required_skill: requiredSkill,
            budget_amount: budgetAmount,
            budget_type: budgetType
        };

        const res = await apiRequest('/api/submit-job', { // New endpoint
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            // Switch to success view
            jobForm.style.display = 'none';
            jobSuccessState.style.display = 'block';
            
            jobDescCounter.textContent = '0 / 500';
            clientNameCounter.textContent = '0 / 100';
            clientContactCounter.textContent = '0 / 100';
            jobForm.reset();
            fetchJobs(); // Update the feed in the background
        } else {
            showToast(res.message || "Login required to post jobs.", "error");
        }
    };

    // Report Modal Logic
    const reportReasonInput = document.getElementById('reportReason');
    const reportReasonCounter = document.getElementById('reportReasonCounter');

    window.apply = async (id) => {
        if (!currentUser.loggedIn) {
            showToast("Please login to apply for projects.", "error");
            return;
        }
        
        if (!currentUser.isVerifiedTaker) {
            showToast("Verification required. Only 'Verified Takers' can apply.", "error");
            return;
        }

        const res = await apiRequest(`/api/apply-job/${id}`, { method: 'POST' });
        if (res.success) {
            showToast(res.message, "success");
            fetchJobs(); // Instant UI update to reflect the "Applied" state
        } else {
            showToast(res.message, "error");
        }
    };

    window.openReportModal = (jobId) => {
        if (!currentUser.loggedIn) {
            showToast("Please login to report a job posting.", "error");
            return;
        }
        document.getElementById('reportJobId').value = jobId;
        reportReasonInput.value = '';
        reportReasonCounter.textContent = '0 / 300';
        reportReasonInput.classList.remove('error');
        reportModal.style.display = 'flex';
    };

    closeReportModal.onclick = () => reportModal.style.display = 'none';

    reportReasonInput.addEventListener('input', () => {
        reportReasonInput.classList.remove('error');
        reportReasonCounter.textContent = `${reportReasonInput.value.length} / 300`;
    });

    reportForm.onsubmit = async (e) => {
        e.preventDefault();
        const jobId = document.getElementById('reportJobId').value;
        const reason = reportReasonInput.value.trim();

        if (!reason) {
            reportReasonInput.classList.add('error', 'shake');
            setTimeout(() => reportReasonInput.classList.remove('shake'), 400);
            showToast("Please provide a reason for reporting.", "error");
            return;
        }

        const res = await apiRequest(`/api/jobs/${jobId}/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason })
        });

        if (res.success) {
            showToast(res.message, "success");
            reportModal.style.display = 'none';
        } else {
            showToast(res.message || "Failed to submit report.", "error");
        }
    };

    const resetJobModal = () => {
        modal.style.display = 'none';
        // Small delay to prevent visual flickering if reopened quickly
        setTimeout(() => {
            jobForm.style.display = 'block';
            jobSuccessState.style.display = 'none';
        }, 300);
    };

    // Modal toggles
    postBtn.onclick = () => modal.style.display = 'flex';
    closeBtn.onclick = resetJobModal;
    viewMyPostsLink.onclick = resetJobModal; // Close modal before navigating
    btnDone.onclick = resetJobModal;

    window.onclick = (e) => {
        if (e.target === modal) resetJobModal(); 
        if (e.target === reportModal) reportModal.style.display = 'none'; // Report Modal
        // Close appeal modal if clicked outside
        if (e.target === document.getElementById('appealModal')) {
            document.getElementById('appealModal').classList.remove('active');
        }
    };

    // Initial Load
    fetchSession();
    fetchJobs();
});