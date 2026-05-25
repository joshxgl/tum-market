document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const listingsContainer = document.getElementById("listingsContainer");
    const featuredContainer = document.getElementById("featuredContainer");
    const searchForm = document.querySelector(".search-bar");
    const adTitleInput = document.getElementById("adTitle");
    const adTitleCounter = document.getElementById("adTitleCounter");
    const searchInput = searchForm?.querySelector('input[type="text"]');
    const searchCategorySelect = searchForm?.querySelector('select');
    const categoryCards = document.querySelectorAll(".category-card");

    const postAdBtn = document.querySelector(".btn-post");
    const loginBtn = document.querySelector(".btn-login");
    const profileDropdown = document.getElementById("profileDropdown");
    
    const adModal = document.getElementById("adModal");
    const postAdForm = document.getElementById("postAdForm");
    const adImageInput = document.getElementById("adImage");
    const imagePreviewContainer = document.getElementById("imagePreviewContainer");
    const imagePreview = document.getElementById("imagePreview");

    const authModal = document.getElementById("authModal");
    const authForm = document.getElementById("authForm");
    const toggleAuthMode = document.getElementById("toggleAuthMode");
    const authTitle = document.getElementById("authTitle");
    const authSubmitBtn = document.getElementById("authSubmitBtn");
    const nameGroup = document.getElementById("nameGroup");

    const notificationBtn = document.getElementById("notificationBtn");
    const notificationDropdown = document.getElementById("notificationDropdown");
    const notificationList = document.getElementById("notificationList");
    const notificationBadge = document.getElementById("notiBadge");

    const detailsModal = document.getElementById("detailsModal");
    const detailsModalBody = document.getElementById("detailsModalBody");

    const assistantToggle = document.getElementById('assistantToggle');
    const assistantPanel = document.getElementById('assistantPanel');
    const assistantClose = document.getElementById('assistantClose');
    const assistantForm = document.getElementById('assistantForm');
    const assistantInput = document.getElementById('assistantInput');
    const assistantMessages = document.getElementById('assistantMessages');

    // State
    let currentUploadedImageBase64 = null;
    let isLoginMode = true;
    let globalListings = [];
    let currentNotifications = [];

    // --- Helpers ---
    async function requestJson(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            if (!res.ok) return { success: false, message: data.message || `Error ${res.status}` };
            return data;
        } catch (e) {
            return { success: false, message: "Server connection failed." };
        }
    }

    function isLoggedIn() {
        return !!localStorage.getItem("tum_market_user_id");
    }

    function syncNavbarHeight() {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            document.documentElement.style.setProperty('--navbar-height', `${navbar.offsetHeight + 10}px`);
        }
    }

    function openModal(modal) {
        modal?.classList.add("active");
    }

    function closeModal(modal) {
        modal?.classList.remove("active");
    }

    // --- Authentication ---
    function persistUser(data) {
        localStorage.setItem('tum_market_user', data.name);
        localStorage.setItem('tum_market_user_id', data.id);
        localStorage.setItem('tum_market_user_email', data.email);
        if (data.profile_picture) {
            localStorage.setItem('tum_market_profile_pic', data.profile_picture);
        }
        applyAuthenticatedUI(data.name, data.profile_picture);
    }

    function applyAuthenticatedUI(name, profilePic) {
        if (!loginBtn) return;
        loginBtn.classList.add('has-profile');
        
        const pic = profilePic || localStorage.getItem('tum_market_profile_pic');
        if (pic) {
            loginBtn.innerHTML = `<img src="${pic}" alt="Profile" class="profile-avatar-nav">`;
        } else {
            const parts = (name || 'User').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length - 1][0]);
            loginBtn.innerHTML = `<div class="profile-circle">${initials.toUpperCase()}</div>`;
        }

        // Using event listener instead of onclick to avoid conflicts
        loginBtn.addEventListener('click', toggleProfileDropdown);
    }

    function toggleProfileDropdown(e) {
        e.preventDefault();
        e.stopPropagation();
        profileDropdown?.classList.toggle('active');
    }

    function logout() {
        requestJson('/api/logout', { method: 'POST' }).then(() => {
            localStorage.clear();
            window.location.reload();
        });
    }

    function checkExistingSession() {
        requestJson('/api/user/session').then(data => {
            if (data.logged_in) persistUser(data);
        });
    }

    adTitleInput?.addEventListener('input', () => {
        const length = adTitleInput.value.length;
        if (adTitleCounter) adTitleCounter.textContent = `${length} / 200`;
    });

    // --- Listings ---
    async function fetchLiveListings() {
        const data = await requestJson('/api/listings');
        if (data.success) {
            globalListings = data.listings;
            renderListings(globalListings);
        }
    }

    function renderListings(items) {
        if (listingsContainer) listingsContainer.innerHTML = '';
        if (featuredContainer) {
            featuredContainer.innerHTML = '';
            items.filter(l => l.tier === 'premium').forEach(item => {
                featuredContainer.appendChild(createListingCard(item, true));
            });
        }
        items.forEach(item => {
            listingsContainer?.appendChild(createListingCard(item));
        });
    }

    function createListingCard(item, isFeatured = false) {
        const div = document.createElement('div');
        div.className = `listing-card ${isFeatured ? 'premium-featured-card' : ''}`;
        div.innerHTML = `
            ${isFeatured ? '<div class="featured-badge">FEATURED</div>' : ''}
            <div class="card-image">
                <img src="${item.image || 'https://via.placeholder.com/300x200?text=No+Image'}" alt="${item.title}">
            </div>
            <div class="card-info">
                <div class="price">KES ${item.price.toLocaleString()}</div>
                <h4>${item.title}</h4>
                <div class="location">📍 ${item.location}</div>
                <div class="card-actions"><button class="btn-view">View Details</button></div>
            </div>
        `;
        div.querySelector('.btn-view').onclick = () => showDetails(item);
        return div;
    }

    function showDetails(item) {
        if (!detailsModalBody) return;
        detailsModalBody.innerHTML = `
            <div class="details-card">
                <div class="details-image">
                    <img src="${item.image || 'https://via.placeholder.com/300x200?text=No+Image'}" alt="${item.title}">
                </div>
                <div class="details-info">
                    <h2>${item.title}</h2>
                    <p class="details-price">KES ${item.price.toLocaleString()}</p>
                    <p><strong>Category:</strong> ${item.category}</p>
                    <p><strong>Location:</strong> ${item.location}</p>
                    <p><strong>Seller:</strong> ${item.posted_by}</p>
                    <div class="details-actions">
                        <a href="https://wa.me/${item.seller_phone}?text=Hi, I am interested in your ${item.title} on TUM Market" 
                           target="_blank" class="whatsapp-btn">Contact Seller (WhatsApp)</a>
                    </div>
                </div>
            </div>
        `;
        openModal(detailsModal);
    }

    // --- Notifications ---
    async function loadNotifications() {
        const data = await requestJson('/api/notifications');
        if (Array.isArray(data)) {
            currentNotifications = data;
            updateNotiUI();
        }
    }

    function updateNotiUI() {
        if (!notificationList || !notificationBadge) return;
        notificationList.innerHTML = '';
        const unreadCount = currentNotifications.length;
        notificationBadge.textContent = unreadCount;
        notificationBadge.style.display = unreadCount > 0 ? 'flex' : 'none';

        if (unreadCount === 0) {
            notificationList.innerHTML = '<div class="noti-item">No new notifications</div>';
            return;
        }

        currentNotifications.forEach(n => {
            const div = document.createElement('div');
            div.className = 'noti-item';
            div.innerHTML = `
                <div class="noti-text">
                    <div class="noti-title">${n.title}</div>
                    <div class="noti-message">${n.message}</div>
                    <div class="noti-time">${n.time}</div>
                </div>
                <button class="mark-read-btn">Done</button>
            `;
            div.querySelector('.mark-read-btn').onclick = () => markNotiRead(n.id);
            notificationList.appendChild(div);
        });
    }

    async function markNotiRead(id) {
        const res = await requestJson(`/api/notifications/${id}/read`, { method: 'POST' });
        if (res.success) loadNotifications();
    }

    document.getElementById('clearNotisBtn')?.addEventListener('click', async () => {
        const res = await requestJson('/api/notifications/clear', { method: 'DELETE' });
        if (res.success) loadNotifications();
    });

    // --- Event Listeners ---
    toggleAuthMode?.addEventListener('click', () => {
        isLoginMode = !isLoginMode;
        authTitle.textContent = isLoginMode ? 'Login' : 'Sign Up';
        authSubmitBtn.textContent = isLoginMode ? 'Login' : 'Create Account';
        nameGroup.style.display = isLoginMode ? 'none' : 'block';
        toggleAuthMode.textContent = isLoginMode ? "Don't have an account? Sign up" : "Already have an account? Login";
    });

    authForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            email: document.getElementById('authEmail').value.trim(),
            password: document.getElementById('authPassword').value.trim()
        };
        if (!isLoginMode) payload.name = document.getElementById('authName').value.trim();

        const res = await requestJson(isLoginMode ? '/api/login' : '/api/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.success) {
            persistUser(res);
            closeModal(authModal);
        } else {
            alert(res.message);
        }
    });

    adImageInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            currentUploadedImageBase64 = evt.target.result;
            imagePreview.src = currentUploadedImageBase64;
            imagePreviewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });

    postAdForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!isLoggedIn()) {
            openModal(authModal);
            return;
        }

        const title = document.getElementById('adTitle').value.trim();
        const priceValue = document.getElementById('adPrice').value;
        const location = document.getElementById('adLocation').value.trim();
        const category = document.getElementById('adCategory').value;
        const phone = document.getElementById('adPhone').value.trim();
        const tier = document.getElementById('adTier').value;

        if (!title || !priceValue || !location || !category || !phone) {
            alert("Please fill in all required fields (Title, Price, Location, Category, and Phone).");
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
            title,
            price,
            location,
            category,
            seller_phone: phone,
            tier,
            image: currentUploadedImageBase64
        };

        const submitBtn = postAdForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Posting...';

        try {
            const res = await requestJson('/api/listings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.success) {
                closeModal(adModal);
                postAdForm.reset();
                currentUploadedImageBase64 = null;
                imagePreviewContainer.style.display = 'none';
                fetchLiveListings();
            } else {
                alert(res.message);
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });

    function applyFilters() {
        const query = searchInput?.value.toLowerCase() || '';
        const cat = searchCategorySelect?.value || 'All Categories';
        const filtered = globalListings.filter(l => {
            const matchesQuery = l.title.toLowerCase().includes(query) || l.location.toLowerCase().includes(query);
            const matchesCat = cat === 'All Categories' || l.category === cat;
            return matchesQuery && matchesCat;
        });
        renderListings(filtered);
    }

    searchInput?.addEventListener('input', applyFilters);
    searchCategorySelect?.addEventListener('change', applyFilters);
    categoryCards.forEach(card => card.addEventListener('click', () => {
        if (searchCategorySelect) searchCategorySelect.value = card.textContent.trim();
        applyFilters();
    }));

    assistantToggle?.addEventListener('click', () => assistantPanel.classList.toggle('active'));
    assistantClose?.addEventListener('click', () => assistantPanel.classList.remove('active'));
    assistantForm?.addEventListener('submit', (e) => {
        e.preventDefault();
        const msg = assistantInput.value.trim();
        if (!msg) return;
        const userDiv = document.createElement('div');
        userDiv.className = 'assistant-message user';
        userDiv.textContent = msg;
        assistantMessages.appendChild(userDiv);
        assistantInput.value = '';
        setTimeout(() => {
            const botDiv = document.createElement('div');
            botDiv.className = 'assistant-message bot';
            botDiv.textContent = "I'm looking into that! You can search by category or post an ad to get started.";
            assistantMessages.appendChild(botDiv);
            assistantMessages.scrollTop = assistantMessages.scrollHeight;
        }, 600);
    });

    document.addEventListener('click', (e) => {
        if (!profileDropdown?.contains(e.target) && !loginBtn?.contains(e.target)) profileDropdown?.classList.remove('active');
        if (!notificationDropdown?.contains(e.target) && !notificationBtn?.contains(e.target)) notificationDropdown?.classList.remove('active');
    });

    notificationBtn?.addEventListener('click', () => notificationDropdown?.classList.toggle('active'));
    postAdBtn?.addEventListener('click', () => isLoggedIn() ? openModal(adModal) : openModal(authModal));
    loginBtn?.addEventListener('click', () => !isLoggedIn() && openModal(authModal));
    document.getElementById('profileDdLogout')?.addEventListener('click', logout);
    document.querySelectorAll('.close-btn, #closeModalBtn, #closeAuthBtn').forEach(btn => btn.addEventListener('click', () => {
        closeModal(adModal); closeModal(authModal); closeModal(detailsModal);
    }));

    // Init
    syncNavbarHeight();
    window.addEventListener('resize', syncNavbarHeight);
    checkExistingSession();
    fetchLiveListings();
    loadNotifications();
});
    
