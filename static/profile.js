document.addEventListener("DOMContentLoaded", () => {
    const userNameEl = document.getElementById('userName');
    const userEmailEl = document.getElementById('userEmail');
    const userListingsGrid = document.getElementById('userListingsGrid');
    const profilePicContainer = document.getElementById('profilePicContainer');
    const profilePicInput = document.getElementById('profilePicInput');
    const logoutBtn = document.getElementById('logoutBtn');

    // Edit Modal Elements
    const editModal = document.getElementById('editModal');
    const closeEditModalBtn = document.getElementById('closeEditModalBtn');
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
        updateAvatar(sessionRes.name, sessionRes.profile_picture);

        const listingsRes = await requestJson('/api/user/listings');
        if (listingsRes.success) {
            currentListings = listingsRes.listings;
            renderUserListings(listingsRes.listings);
        }
    }

    function updateAvatar(name, pic) {
        if (pic) {
            profilePicContainer.innerHTML = `<img src="${pic}" alt="Profile" class="profile-page-avatar">`;
        } else {
            const parts = (name || 'U').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length - 1][0]);
            profilePicContainer.innerHTML = `<div class="profile-page-initials">${initials.toUpperCase()}</div>`;
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
                    <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 20px;">📍 ${item.location}</p>
                    
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
        if (res.success) loadDashboard();
    };

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
        reader.onload = (evt) => {
            currentEditImageBase64 = evt.target.result;
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
        const res = await requestJson(`/api/listings/${id}`, { method: 'DELETE' });
        if (res.success) loadDashboard();
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