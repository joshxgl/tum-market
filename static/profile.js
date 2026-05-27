document.addEventListener("DOMContentLoaded", () => {
    const userNameEl = document.getElementById('userName');
    const userEmailEl = document.getElementById('userEmail');
    const userListingsGrid = document.getElementById('userListingsGrid');
    const profilePicContainer = document.getElementById('profilePicContainer');
    const profilePicInput = document.getElementById('profilePicInput');
    const logoutBtn = document.getElementById('logoutBtn');

    // User Profile Edit Elements
    const openUserEditModalBtn = document.getElementById('openUserEditModalBtn');
    const userEditModal = document.getElementById('userEditModal');
    const closeUserEditModalBtn = document.getElementById('closeUserEditModalBtn');
    const userEditForm = document.getElementById('userEditForm');
    const displayPhone = document.getElementById('displayPhone');
    const displaySkills = document.getElementById('displaySkills');
    const editUserSkillsInput = document.getElementById('editUserSkills');
    const editSkillsContainer = document.getElementById('editSkillsContainer');
    const editSkillsCounter = document.getElementById('editSkillsCounter');

    // Jobs and Appeal UI
    const userJobsGrid = document.getElementById('userJobsGrid');
    const appealModal = document.getElementById('appealModal');
    const closeAppealModalBtn = document.getElementById('closeAppealModalBtn');
    const appealForm = document.getElementById('appealForm');

    // Verification UI
    const verificationSection = document.getElementById('verificationSection');
    const resumeInput = document.getElementById('resumeInput');
    const resumeFileName = document.getElementById('resumeFileName');
    const submitVerificationBtn = document.getElementById('submitVerificationBtn');

    // Edit Modal Elements
    const editModal = document.getElementById('editModal');
    const closeEditModalBtn = document.getElementById('closeEditModalBtn');
    const clearAllBtn = document.getElementById('clearAllListingsBtn');
    const editAdForm = document.getElementById('editAdForm');
    const editAdTitleInput = document.getElementById('editAdTitle');
    const editAdTitleCounter = document.getElementById('editAdTitleCounter');
    const editAdImage = document.getElementById('editAdImage');
    const editImagePreview = document.getElementById('editImagePreview');
    const editImagePreviewContainer = document.getElementById('editImagePreviewContainer');

    // Cropper Elements
    const cropperModal = document.getElementById('cropperModal');
    const cropperImage = document.getElementById('cropperImage');
    const saveCropBtn = document.getElementById('saveCropBtn');
    const cancelCropBtn = document.getElementById('cancelCropBtn');
    let cropperInstance = null;
    let currentListings = [];
    let currentEditImageBase64 = null;
    let editSkillsArray = [];
    let verifiedSkillsArray = [];

    // Client-side Image Compression Helper
    async function compressImage(base64, maxWidth = 1000) {
        return new Promise((resolve) => {
            const img = new Image();
            img.src = base64;
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const ratio = maxWidth / Math.max(img.width, img.height);
                const width = ratio < 1 ? img.width * ratio : img.width;
                const height = ratio < 1 ? img.height * ratio : img.height;
                canvas.width = width;
                canvas.height = height;
                canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                resolve(canvas.toDataURL('image/jpeg', 0.7));
            };
        });
    }

    // API Helper
    async function requestJson(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            if (!res.ok) return { success: false, message: data.message || `Error ${res.status}` };
            return data;
        } catch (e) {
            return { success: false, message: "Connection lost. Please try again." };
        }
    }

    // Load Profile and Listings
    async function loadDashboard() {
        const sessionRes = await requestJson('/api/user/session');
        if (!sessionRes.logged_in) {
            window.location.href = '/';
            return;
        }

        userNameEl.textContent = sessionRes.name;
        userEmailEl.textContent = sessionRes.email;
        updateAvatar(sessionRes.name, sessionRes.profile_picture, sessionRes.is_admin);

        if (displayPhone) displayPhone.textContent = `📱 ${sessionRes.phone_number || 'No phone set'}`;
        if (displaySkills) {
            const skills = sessionRes.skills || 'None listed';
            displaySkills.textContent = `🛠️ Skills: ${skills}`;
        }
        
        verifiedSkillsArray = sessionRes.verified_skills ? sessionRes.verified_skills.split(',').map(s => s.trim()).filter(Boolean) : [];

        renderVerificationStatus(sessionRes);

        const listingsRes = await requestJson('/api/user/listings');
        if (listingsRes.success) {
            currentListings = listingsRes.listings;
            renderUserListings(listingsRes.listings);
            renderUserJobs(listingsRes.jobs);
            displayTotalViews(listingsRes.total_views);
            renderSubscriptionToggle(sessionRes.is_subscribed, sessionRes.subscription_updated_at);
        }
    }

    openUserEditModalBtn?.addEventListener('click', () => {
        document.getElementById('editUserName').value = userNameEl.textContent;
        document.getElementById('editUserPhone').value = displayPhone.textContent.replace('📱 ', '').replace('No phone set', '');
        
        const skillsText = displaySkills.textContent.replace('🛠️ Skills: ', '').replace('None listed', '');
        editSkillsArray = skillsText ? skillsText.split(',').map(s => s.trim()).filter(Boolean) : [];
        renderEditSkills();
        
        userEditModal.classList.add('active');
    });

    editUserSkillsInput?.addEventListener('input', () => {
        const len = editUserSkillsInput.value.length;
        if (editSkillsCounter) editSkillsCounter.textContent = `${len} / 30`;
        editUserSkillsInput.classList.remove('error');
    });

    if (closeUserEditModalBtn) closeUserEditModalBtn.onclick = () => userEditModal.classList.remove('active');

    editUserSkillsInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            const val = editUserSkillsInput.value.trim().replace(',', '');
            if (val && !editSkillsArray.includes(val)) {
                editSkillsArray.push(val);
                renderEditSkills();
            }
            if (editSkillsCounter) editSkillsCounter.textContent = '0 / 30';
            editUserSkillsInput.value = '';
        }
    });

    function renderEditSkills() {
        if (!editSkillsContainer) return;
        editSkillsContainer.innerHTML = editSkillsArray.map((skill, index) => `
            <span class="skill-badge-tag ${verifiedSkillsArray.includes(skill) ? 'is-verified' : ''}">
                ${verifiedSkillsArray.includes(skill) ? '<i class="fas fa-certificate skill-verified-badge" title="Admin Verified"></i>' : ''}
                <span>${skill}</span>
                <i class="fas fa-times" onclick="removeEditSkill(${index})"></i>
            </span>
        `).join('');
    }

    window.removeEditSkill = (index) => {
        editSkillsArray.splice(index, 1);
        renderEditSkills();
    };

    userEditForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            name: document.getElementById('editUserName').value.trim(),
            phone_number: document.getElementById('editUserPhone').value.trim(),
            skills: editSkillsArray.join(', ')
        };

        const res = await requestJson('/api/user/profile', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            userEditModal.classList.remove('active');
            loadDashboard();
        } else {
            alert(res.message);
        }
    });

    function renderVerificationStatus(user) {
        verificationSection.style.display = 'block';
        const content = document.getElementById('verificationStatusContent');
        
        if (user.is_skill_verified) {
            content.innerHTML = `<p style="color: #10b981; font-weight: bold;">✅ You are a Verified Taker. You can now apply for jobs in the Service Portal.</p>`;
        } else if (user.verification_status === 'pending') {
            content.innerHTML = `<p style="color: #f59e0b; font-weight: bold;">⏳ Verification Pending. Our admins are reviewing your resume.</p>`;
        }
    }

    resumeInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        const allowed = ['image/png', 'image/jpeg', 'image/webp'];
        if (file && allowed.includes(file.type)) {
            resumeFileName.textContent = file.name;
            submitVerificationBtn.style.display = 'block';
        } else {
            alert("PDFs are not allowed. Please select an image (.png, .jpg, or .webp).");
            resumeInput.value = '';
        }
    });

    submitVerificationBtn?.addEventListener('click', async () => {
        const file = resumeInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (e) => {
            submitVerificationBtn.disabled = true;
            submitVerificationBtn.textContent = "Uploading...";
            
            const compressedData = await compressImage(e.target.result);
            
            const res = await requestJson('/api/user/request-verification', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ doc: compressedData })
            });

            if (res.success) {
                alert("Request submitted successfully!");
                loadDashboard();
            } else {
                alert(res.message);
                submitVerificationBtn.disabled = false;
                submitVerificationBtn.textContent = "Submit for Review";
            }
        };
        reader.readAsDataURL(file);
    });

    function renderSubscriptionToggle(isSubscribed, updatedAt) {
        const infoPanel = document.querySelector('.profile-info');
        if (!infoPanel) return;

        let container = document.getElementById('subSettingContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'subSettingContainer';
            container.className = 'subscription-setting';
            infoPanel.appendChild(container);
        }

        const dateStr = updatedAt ? new Date(updatedAt).toLocaleString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        }) : 'Never';

        container.innerHTML = `
            <div class="switch-label">
                <div style="display: flex; flex-direction: column; gap: 2px;">
                    <span>Weekly Performance Emails</span>
                    <small class="sub-updated-at" id="subUpdateLabel">Last updated: ${dateStr}</small>
                </div>
                <div style="display: flex; align-items: center;">
                    <label class="switch">
                        <input type="checkbox" id="subCheckbox" ${isSubscribed ? 'checked' : ''}>
                        <span class="slider round"></span>
                    </label>
                </div>
            </div>
        `;

        document.getElementById('subCheckbox').onchange = async (e) => {
            const res = await requestJson('/api/user/subscription', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_subscribed: e.target.checked })
            });
            if (res.success) {
                const newDate = new Date(res.subscription_updated_at).toLocaleString(undefined, {
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                });
                document.getElementById('subUpdateLabel').textContent = `Last updated: ${newDate}`;
            } else {
                alert(res.message);
            }
        };
    }

    function displayTotalViews(count) {
        if (!userEmailEl) return;
        const parent = userEmailEl.parentElement;
        let statsEl = document.getElementById('userTotalViews');
        
        if (!statsEl) {
            statsEl = document.createElement('p');
            statsEl.id = 'userTotalViews';
            statsEl.className = 'profile-stats';
            parent.appendChild(statsEl);
        }
        
        statsEl.innerHTML = `📊 Total Shop Views: <strong>${count.toLocaleString()}</strong>`;
    }

    function renderUserJobs(jobs) {
        if (!userJobsGrid) return;
        if (!jobs || jobs.length === 0) {
            userJobsGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--muted); padding: 40px;">You haven\'t posted any service briefs yet.</p>';
            return;
        }

        userJobsGrid.innerHTML = jobs.map(j => `
            <div class="listing-card" style="background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
                <div style="padding: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <h3 style="color: var(--card-text); font-size: 1.2rem;">${j.title}</h3>
                        <span style="background: ${j.status === 'active' ? '#dcfce7' : '#fee2e2'}; color: ${j.status === 'active' ? '#10b981' : '#ef4444'}; padding: 4px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">
                            ${j.status}
                        </span>
                    </div>
                    <p style="font-weight: 800; color: var(--accent-2); margin-bottom: 15px;">Budget: ${j.budget}</p>
                    <p style="font-size: 0.9rem; color: #64748b;">Client: ${j.client_name} (${j.client_contact})</p>
                    ${j.status === 'suspended' ? `
                        <button onclick="openAppealModal(${j.id})" class="btn-view" style="width: 100%;">Appeal Suspension</button>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    window.openAppealModal = (id) => {
        document.getElementById('appealJobId').value = id;
        document.getElementById('appealReason').value = '';
        appealModal.classList.add('active');
    };

    closeAppealModalBtn.onclick = () => appealModal.classList.remove('active');

    appealForm.onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById('appealJobId').value;
        const reason = document.getElementById('appealReason').value.trim();

        const res = await requestJson(`/api/jobs/${id}/appeal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason })
        });

        if (res.success) {
            alert("Appeal submitted. You will be notified of the outcome.");
            appealModal.classList.remove('active');
        } else {
            alert(res.message);
        }
    };

    function updateAvatar(name, pic, isAdmin) {
        const adminBadge = isAdmin ? '<div class="admin-badge-large" title="System Administrator"><i class="fas fa-crown"></i> ADMIN</div>' : '';
        if (pic) {
            profilePicContainer.innerHTML = `<div class="profile-avatar-wrap"><img src="${pic}" alt="Profile" class="profile-page-avatar">${adminBadge}</div>`;
        } else {
            const parts = (name || 'U').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length - 1][0]);
            profilePicContainer.innerHTML = `<div class="profile-avatar-wrap"><div class="profile-page-initials">${initials.toUpperCase()}</div>${adminBadge}</div>`;
        }
    }

    function renderUserListings(listings) {
        if (listings.length === 0) {
            userListingsGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--muted); padding: 40px;">You haven\'t posted any items yet.</p>';
            return;
        }

        userListingsGrid.innerHTML = listings.map(item => `
            <div class="listing-card" style="background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
                <div style="padding: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <h3 style="color: var(--card-text); font-size: 1.2rem;">${item.title}</h3>
                        <span style="background: ${item.status === 'sold' ? '#fee2e2' : '#dcfce7'}; color: ${item.status === 'sold' ? '#ef4444' : '#10b981'}; padding: 4px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">
                            ${item.status}
                        </span>
                    </div>
                    <p style="font-size: 1.4rem; font-weight: 800; color: var(--accent-2); margin-bottom: 15px;">KES ${item.price.toLocaleString()}</p>
                    <div style="display: flex; justify-content: space-between; color: #64748b; font-size: 0.9rem; margin-bottom: 20px;">
                        <span>📍 ${item.location}</span>
                        <span>👁️ ${item.views || 0} views</span>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <button onclick="editListing(${item.id})" class="btn-view" style="grid-column: span 2; margin-bottom: 8px;">Edit Ad</button>
                        ${item.status !== 'sold' ? `
                            <button onclick="markAsSold(${item.id})" class="btn-sold" style="background: var(--accent-2); color: white; border: none; padding: 10px; border-radius: 10px; cursor: pointer; font-weight: 600;">Mark Sold</button>
                        ` : ''}
                        <button onclick="confirmDelete(${item.id})" class="btn-delete" style="background: #ef4444; color: white; border: none; padding: 10px; border-radius: 10px; cursor: pointer; font-weight: 600;">Delete Ad</button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    window.markAsSold = async (id) => {
        const res = await requestJson(`/api/listings/${id}/sold`, { method: 'PATCH' });
        if (res.success) {
            return loadDashboard();
        }
        alert(res.message || "Failed to mark as sold.");
    };

    clearAllBtn?.addEventListener('click', async () => {
        if (!confirm("Are you sure you want to delete ALL your listings? This cannot be undone.")) return;
        const res = await requestJson('/api/user/listings/clear', { method: 'DELETE' });
        if (res.success) {
            loadDashboard();
        } else {
            alert(res.message);
        }
    });

    window.editListing = (id) => {
        const item = currentListings.find(l => l.id === id);
        if (!item) return;

        document.getElementById('editAdId').value = item.id;
        document.getElementById('editAdTitle').value = item.title;
        document.getElementById('editAdPrice').value = item.price;
        document.getElementById('editAdLocation').value = item.location;
        document.getElementById('editAdCategory').value = item.category;
        document.getElementById('editAdPhone').value = item.seller_phone || '';
        
        if (item.image) {
            editImagePreview.src = item.image;
            editImagePreviewContainer.style.display = 'block';
        } else {
            editImagePreviewContainer.style.display = 'none';
        }
        
        if (editAdTitleCounter) {
            editAdTitleCounter.textContent = `${item.title.length} / 200`;
        }

        currentEditImageBase64 = null;
        editModal.classList.add('active');
    };

    closeEditModalBtn.onclick = () => editModal.classList.remove('active');

    editAdTitleInput?.addEventListener('input', () => {
        const length = editAdTitleInput.value.length;
        if (editAdTitleCounter) editAdTitleCounter.textContent = `${length} / 200`;
    });

    editAdImage.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = ['image/jpeg', 'image/png'];
        if (!allowedTypes.includes(file.type)) {
            alert("Only PNG and JPEG images are allowed.");
            editAdImage.value = '';
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            alert("File is too large (max 5MB).");
            editAdImage.value = '';
            return;
        }
        const reader = new FileReader();
        reader.onload = async (evt) => {
            currentEditImageBase64 = await compressImage(evt.target.result);
            editImagePreview.src = currentEditImageBase64;
            editImagePreviewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    };

    editAdForm.onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById('editAdId').value;

        const title = document.getElementById('editAdTitle').value.trim();
        const priceValue = document.getElementById('editAdPrice').value;
        const location = document.getElementById('editAdLocation').value.trim();
        const category = document.getElementById('editAdCategory').value;
        const phone = document.getElementById('editAdPhone').value.trim();

        if (!title || !priceValue || !location || !category || !phone) {
            alert("Please fill in all required fields.");
            return;
        }

        const price = parseFloat(priceValue);
        if (isNaN(price) || price <= 0) {
            alert("Price must be a positive number.");
            return;
        }

        const phoneRegex = /^\+?1?\d{9,15}$/;
        if (!phoneRegex.test(phone)) {
            alert("Please enter a valid phone number (9-15 digits).");
            return;
        }

        const payload = {
            title, price, location, category, seller_phone: phone
        };
        if (currentEditImageBase64) payload.image = currentEditImageBase64;

        const submitBtn = editAdForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Updating...';

        try {
            const res = await requestJson(`/api/listings/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.success) {
                editModal.classList.remove('active');
                loadDashboard();
            } else {
                alert(res.message);
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    };

    window.confirmDelete = async (id) => {
        if (!confirm("This will permanently remove this ad from TUM Market. Continue?")) return;
        const res = await requestJson(`/api/listings/${id}`, { 
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' } 
        });
        if (res.success) return loadDashboard();
        alert(res.message || "Failed to delete the listing.");
    };

    // Profile Picture Logic
    profilePicInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = ['image/jpeg', 'image/png'];
        if (!allowedTypes.includes(file.type)) {
            alert("Only PNG and JPEG images are allowed.");
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            alert("File is too large (max 5MB).");
            return;
        }

        const reader = new FileReader();
        reader.onload = (evt) => {
            cropperImage.src = evt.target.result;
            cropperModal.classList.add('active');
            
            if (cropperInstance) cropperInstance.destroy();
            
            cropperInstance = new Cropper(cropperImage, {
                aspectRatio: 1,
                viewMode: 1,
                dragMode: 'move',
                autoCropArea: 1,
                restore: false,
                guides: false,
                center: false,
                highlight: false,
                cropBoxMovable: false,
                cropBoxResizable: false,
                toggleDragModeOnDblclick: false,
            });
        };
        reader.readAsDataURL(file);
    });

    cancelCropBtn.addEventListener('click', () => {
        cropperModal.classList.remove('active');
        profilePicInput.value = '';
    });

    saveCropBtn.addEventListener('click', async () => {
        if (!cropperInstance) return;

        const canvas = cropperInstance.getCroppedCanvas({
            width: 400,
            height: 400
        });
        
        const croppedBase64 = canvas.toDataURL('image/jpeg', 0.8);
        cropperModal.classList.remove('active');
        uploadProfilePicture(croppedBase64);
    });

    async function uploadProfilePicture(base64Data) {
        const progressContainer = document.getElementById('uploadProgressContainer');
        const progressBar = document.getElementById('uploadProgressBar');
        
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/user/profile-picture');
            xhr.setRequestHeader('Content-Type', 'application/json');

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    progressBar.style.width = percent + '%';
                }
            };

            xhr.onload = () => {
                let res;
                try {
                    res = JSON.parse(xhr.responseText);
                } catch (e) {
                    res = { success: false, message: "Server error parsing response." };
                }
                
                if (res.success) {
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                        loadDashboard();
                    }, 600);
                } else {
                    alert(res.message);
                    progressContainer.style.display = 'none';
                }
            };
            xhr.send(JSON.stringify({ image: base64Data }));
        } catch (err) {
            alert("Upload failed.");
            progressContainer.style.display = 'none';
        }
    }

    logoutBtn.addEventListener('click', async () => {
        await requestJson('/api/logout', { method: 'POST' });
        localStorage.clear();
        window.location.href = '/';
    });

    loadDashboard();
});