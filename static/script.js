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
    const navLinks = document.querySelectorAll(".nav-link");
    const searchSection = document.querySelector(".search-section");

    const postAdBtn = document.querySelector(".btn-post");
    const loginBtn = document.querySelector(".btn-login");
    const profileDropdown = document.getElementById("profileDropdown");
    const adminPanelLink = document.getElementById("adminPanelLink");
    
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

    const backToTopBtn = document.getElementById("backToTop");
    const progressCircle = backToTopBtn?.querySelector('.progress-ring__circle');
    const radius = 22; // Matches the 'r' attribute in HTML
    const circumference = 2 * Math.PI * radius;

    // State
    let currentUploadedImageBase64 = null;
    let isLoginMode = true;
    let globalListings = [];
    let currentNotifications = [];

    // --- Helpers ---
    if (progressCircle) {
        progressCircle.style.strokeDasharray = `${circumference} ${circumference}`;
        progressCircle.style.strokeDashoffset = circumference;
    }

    function setProgress(percent) {
        if (!progressCircle) return;
        const offset = circumference - (percent / 100 * circumference);
        progressCircle.style.strokeDashoffset = offset;
    }

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
        localStorage.setItem('tum_market_is_admin', data.is_admin);
        if (data.profile_picture) {
            localStorage.setItem('tum_market_profile_pic', data.profile_picture);
        }
        applyAuthenticatedUI(data.name, data.profile_picture, data.is_admin);
    }

    function applyAuthenticatedUI(name, profilePic, isAdmin) {
        if (!loginBtn) return;
        loginBtn.classList.add('has-profile');
        
        const adminBadge = (isAdmin || localStorage.getItem('tum_market_is_admin') === 'true') ? '<div class="admin-badge-nav"><i class="fas fa-crown"></i></div>' : '';
        const pic = profilePic || localStorage.getItem('tum_market_profile_pic');
        if (pic) {
            loginBtn.innerHTML = `<div class="avatar-nav-wrap"><img src="${pic}" alt="Profile" class="profile-avatar-nav">${adminBadge}</div>`;
        } else {
            const parts = (name || 'User').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length - 1][0]);
            loginBtn.innerHTML = `<div class="avatar-nav-wrap"><div class="profile-circle">${initials.toUpperCase()}</div>${adminBadge}</div>`;
        }

        // Using onclick assignment to ensure only one handler exists regardless of UI updates
        loginBtn.onclick = toggleProfileDropdown;

        // Conditionally show Admin Panel link
        if (adminPanelLink) {
            adminPanelLink.style.display = (isAdmin || localStorage.getItem('tum_market_is_admin') === 'true') ? 'block' : 'none';
        }
    }

    function toggleProfileDropdown(e) {
        e.preventDefault();
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
        const trendingRibbon = item.views > 50 ? '<div class="trending-ribbon">TRENDING</div>' : '';
        div.innerHTML = `
            ${isFeatured ? '<div class="featured-badge">FEATURED</div>' : ''}
            ${trendingRibbon}
            <div class="card-image">
                <img src="${item.image || 'https://via.placeholder.com/300x200?text=No+Image'}" alt="${item.title}">
            </div>
            <div class="card-info">
                <div class="price">KES ${item.price.toLocaleString()}</div>
                <h4>${item.title}</h4>
                <div class="location">
                    <span>📍 ${item.location}</span>
                    <span class="view-count">👁️ ${item.views || 0}</span>
                </div>
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
        // Log the view to the server
        requestJson(`/api/listings/${item.id}/view`, { method: 'POST' });
    }

    // --- Sticky Search Scroll Effect ---
    window.addEventListener('scroll', () => {
        const isStuck = window.scrollY > 20;
        searchSection?.classList.toggle('is-stuck', isStuck);
        backToTopBtn?.classList.toggle('active', isStuck);

        const scrollTotal = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollTotal > 0) {
            const scrollPercent = (window.scrollY / scrollTotal) * 100;
            setProgress(scrollPercent);
        }
    });

    backToTopBtn?.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // --- Notifications ---
    async function loadNotifications() {
        const data = await requestJson('/api/notifications');
        if (Array.isArray(data)) {
            currentNotifications = data;
            // Inject system WhatsApp notification at the start
            currentNotifications.unshift({
                id: 'sys-wa',
                title: '📌 Join Our Community',
                message: 'Follow our WhatsApp channel for instant updates and exclusive deals.',
                time: 'Always Active',
                is_system: true
            });
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
                ${n.is_system ? 
                    `<a href="https://whatsapp.com/channel/0029VbDArYa1CYoOgeLJQD3P" target="_blank" class="mark-read-btn" style="background:#25D366; text-decoration:none; display:inline-block; text-align:center;">Join</a>` : 
                    `<button class="mark-read-btn">Done</button>`
                }
            `;
            if (!n.is_system) {
                div.querySelector('.mark-read-btn').onclick = () => markNotiRead(n.id);
            }
            notificationList.appendChild(div);
        });
    }

    // --- Idle Detection for WhatsApp Modal ---
    let idleTimer;
    function resetIdleTimer() {
        clearTimeout(idleTimer);
        if (localStorage.getItem('hide_wa_channel') !== 'true') {
            idleTimer = setTimeout(showChannelInvitation, 45000); // 45 Seconds
        }
    }

    function showChannelInvitation() {
        const modal = document.getElementById('channelModal');
        if (modal) openModal(modal);
    }

    window.addEventListener('mousemove', resetIdleTimer);
    window.addEventListener('keypress', resetIdleTimer);

    document.getElementById('closeChannelModal')?.addEventListener('click', () => {
        closeModal(document.getElementById('channelModal'));
    });

    document.getElementById('dismissChannelForever')?.addEventListener('click', () => {
        localStorage.setItem('hide_wa_channel', 'true');
        closeModal(document.getElementById('channelModal'));
    });

    async function markNotiRead(id) {
        const res = await requestJson(`/api/notifications/${id}/read`, { method: 'POST' });
        if (res.success) return loadNotifications();
        alert(res.message || "Failed to mark notification as read.");
    }

    document.getElementById('clearNotisBtn')?.addEventListener('click', async () => {
        const res = await requestJson('/api/notifications/clear', { method: 'DELETE' });
        if (res.success) return loadNotifications();
        alert(res.message || "Failed to clear notifications.");
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
        if (!isLoginMode) {
            payload.name = document.getElementById('authName').value.trim();
            payload.phone_number = document.getElementById('authPhone').value.trim();
            payload.skills = document.getElementById('authSkills').value.trim();
        }

        const submitBtn = authForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="spinner"></span> ${isLoginMode ? 'Logging in...' : 'Creating Account...'}`;

        try {
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
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });

    // Password Visibility Toggle
    document.getElementById('togglePassword')?.addEventListener('click', function() {
        const passwordInput = document.getElementById('authPassword');
        const isPassword = passwordInput.type === 'password';
        passwordInput.type = isPassword ? 'text' : 'password';
        this.classList.toggle('fa-eye', !isPassword);
        this.classList.toggle('fa-eye-slash', isPassword);
    });

    adImageInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (evt) => {
            currentUploadedImageBase64 = await compressImage(evt.target.result);
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
        const cat = card.getAttribute('data-category');
        if (searchCategorySelect && cat) {
            searchCategorySelect.value = cat;
        }
        applyFilters();
    }));

    navLinks.forEach(link => link.addEventListener('click', (e) => {
        e.preventDefault();
        // Update UI active state
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        // Sync with the search category dropdown
        const navVal = link.getAttribute('data-nav');
        if (searchCategorySelect) {
            searchCategorySelect.value = (navVal === 'all') ? "" : navVal;
        }
        applyFilters();
    }));

    // --- Unified Click Management (Dropdowns & Assistant) ---
    document.addEventListener('click', (e) => {
        const closeIfOutside = (panel, btn) => {
            if (panel?.classList.contains('active') && !panel.contains(e.target) && !btn?.contains(e.target)) {
                panel.classList.remove('active');
            }
        };
        closeIfOutside(profileDropdown, loginBtn);
        closeIfOutside(notificationDropdown, notificationBtn);
        closeIfOutside(assistantPanel, assistantToggle);
    });

    assistantToggle?.addEventListener('click', (e) => {
        assistantPanel?.classList.toggle('active');
    });
    assistantClose?.addEventListener('click', () => assistantPanel.classList.remove('active'));

    assistantForm?.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = assistantInput.value.trim();
        if (!text) return;
        
        const appendMsg = (content, type) => {
            const div = document.createElement('div');
            div.className = `assistant-message ${type}`;
            div.textContent = content;
            assistantMessages.appendChild(div);
            assistantMessages.scrollTop = assistantMessages.scrollHeight;
        };

        appendMsg(text, 'user');
        assistantInput.value = '';
        setTimeout(() => appendMsg("I'm here to help! Search for items or post an ad to start selling.", 'bot'), 600);
    });

    // --- Interactive Resizer ---
    const resizeHandle = document.getElementById('assistantResizeHandle');
    let isResizing = false;

    resizeHandle?.addEventListener('mousedown', (e) => {
        isResizing = true;
        document.body.classList.add('is-resizing');
    });

    window.addEventListener('mousemove', (e) => {
        if (!isResizing || !assistantPanel) return;
        const offsetTop = assistantPanel.getBoundingClientRect().top;
        const newHeight = window.innerHeight - e.clientY - (window.innerHeight - assistantPanel.getBoundingClientRect().bottom);
        if (newHeight > 200 && newHeight < window.innerHeight * 0.8) {
            assistantPanel.style.height = `${newHeight}px`;
        }
    });

    window.addEventListener('mouseup', () => {
        isResizing = false;
        document.body.classList.remove('is-resizing');
    });
});
    
