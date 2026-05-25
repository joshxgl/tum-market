document.addEventListener("DOMContentLoaded", () => {
    const listingsContainer = document.getElementById("listingsContainer");
    const searchForm = document.querySelector(".search-bar");
    const searchInput = searchForm?.querySelector('input[type="text"]');
    const searchCategorySelect = searchForm?.querySelector('select');
    const categoryCards = document.querySelectorAll(".category-card");
    const navLinks = document.querySelectorAll('.nav-link');

    const postAdBtn = document.querySelector(".btn-post");
    const loginBtn = document.querySelector(".btn-login");
    const adModal = document.getElementById("adModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const postAdForm = document.getElementById("postAdForm");
    const adImageInput = document.getElementById("adImage");
    const imagePreviewContainer = document.getElementById("imagePreviewContainer");
    const imagePreview = document.getElementById("imagePreview");

    const authModal = document.getElementById("authModal");
    const closeAuthBtn = document.getElementById("closeAuthBtn");
    const authForm = document.getElementById("authForm");
    const toggleAuthMode = document.getElementById("toggleAuthMode");
    const authTitle = document.getElementById("authTitle");
    const authSubmitBtn = document.getElementById("authSubmitBtn");
    const nameGroup = document.getElementById("nameGroup");

    const notificationBtn = document.getElementById("notificationBtn");
    const notificationDropdown = document.getElementById("notificationDropdown");
    const notificationList = document.getElementById("notificationList");
    const notificationBadge = document.getElementById("notiBadge");
    if (notificationDropdown && notificationDropdown.parentElement !== document.body) {
        document.body.appendChild(notificationDropdown);
    }
    const profileDropdown = document.getElementById("profileDropdown");

    const detailsModal = document.getElementById("detailsModal");
    const detailsModalBody = document.getElementById("detailsModalBody");

    const assistantWidget = document.getElementById('assistantWidget');
    const assistantToggle = document.getElementById('assistantToggle');
    const assistantPanel = document.getElementById('assistantPanel');
    const assistantClose = document.getElementById('assistantClose');
    const assistantForm = document.getElementById('assistantForm');
    const assistantInput = document.getElementById('assistantInput');
    const assistantMessages = document.getElementById('assistantMessages');
    const assistantWelcome = document.getElementById('assistantWelcome');

    const ASSISTANT_STARTUP_TEXT =
        'Welcome to TUM Market! I can help you search listings, post ads, sign in, check notifications, and contact sellers.';

    if (assistantWelcome) {
        assistantWelcome.textContent = ASSISTANT_STARTUP_TEXT;
    }

    let currentUploadedImageBase64 = "https://via.placeholder.com/300x180";
    let isLoginMode = true;
    let globalListings = [];
    let currentNotifications = [];
    let notificationsLoaded = false;

    function syncNavbarHeight() {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            document.documentElement.style.setProperty('--navbar-height', `${navbar.offsetHeight + 10}px`);
        }
    }

    function isLoggedIn() {
        return Boolean(localStorage.getItem("tum_market_user") && localStorage.getItem("tum_market_user_id"));
    }

    function openModal(modal) {
        modal?.classList.add("active");
        setAssistantOpen(false);
    }

    function closeModal(modal) {
        modal?.classList.remove("active");
    }

    function getProfilePicture(userId) {
        return localStorage.getItem(`profile_picture_${userId}`) || null;
    }

    function saveProfilePicture(userId, imageData) {
        if (!userId || !imageData) return;
        localStorage.setItem(`profile_picture_${userId}`, imageData);
    }

    function persistUser(data) {
        localStorage.setItem('tum_market_user', data.name);
        localStorage.setItem('tum_market_user_email', data.email || '');
        localStorage.setItem('tum_market_user_id', String(data.id));
        if (data.profile_picture) {
            saveProfilePicture(data.id, data.profile_picture);
        }
        applyAuthenticatedUI(data.name, data.id);
    }

    async function requestJson(url, options = {}) {
        const res = await fetch(url, options);
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = { success: false, message: `Server error (${res.status}).` };
        }
        if (!res.ok && data.success !== true) {
            return { success: false, message: data.message || `Request failed (${res.status}).` };
        }
        return data;
    }

    function checkExistingSession() {
        requestJson('/api/user/session')
            .then(data => {
                if (data.logged_in) {
                    persistUser(data);
                }
            })
            .catch(() => {
                const name = localStorage.getItem("tum_market_user");
                const id = localStorage.getItem("tum_market_user_id");
                if (name && id) applyAuthenticatedUI(name, id);
            });
    }

    function applyAuthenticatedUI(name, userId) {
        if (!loginBtn) return;
        const id = userId || localStorage.getItem('tum_market_user_id');
        const profilePic = id ? getProfilePicture(id) : null;
        if (profilePic) {
            loginBtn.innerHTML = `<img src="${profilePic}" alt="Profile" class="profile-avatar-nav">`;
        } else {
            const parts = (name || '').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 0 ? 'U' : (parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length - 1][0]));
            loginBtn.innerHTML = `<span class="profile-circle">${initials.toUpperCase()}</span>`;
        }
        loginBtn.classList.add('has-profile');
        loginBtn.setAttribute('title', 'Account menu');
        syncNavbarHeight();
    }

    function toggleProfileDropdown() {
        profileDropdown?.classList.toggle("active");
    }

    function displayListings(items) {
        if (!listingsContainer) return;
        listingsContainer.innerHTML = "";
        const activeItems = items.filter(i => i.status !== 'sold');

        if (!activeItems.length) {
            listingsContainer.innerHTML = `<div class="empty-state"><h2>No items found.</h2><p>Try a different search or category.</p></div>`;
            return;
        }

        activeItems.forEach(item => {
            const card = document.createElement("div");
            card.classList.add("listing-card");
            card.innerHTML = `
                <div class="card-image"><img src="${item.image}" alt="${item.title}"></div>
                <div class="card-info">
                    <span class="price">Ksh ${item.price}</span>
                    <h4>${item.title}</h4>
                    <p class="location">${item.location}</p>
                    <button type="button" class="btn-view" onclick="viewDetails(${item.id})">View</button>
                </div>
            `;
            listingsContainer.appendChild(card);
        });
    }

    function filterListings(searchText, category) {
        const query = (searchText || '').trim().toLowerCase();
        const selectedCategory = category || 'all';
        const filtered = globalListings.filter(item => {
            const matchesSearch = !query ||
                String(item.title || '').toLowerCase().includes(query) ||
                String(item.location || '').toLowerCase().includes(query);
            const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
            return matchesSearch && matchesCategory;
        });
        displayListings(filtered);
    }

    function setActiveCategory(category) {
        categoryCards.forEach(card => {
            card.classList.toggle('active', card.dataset.category === category);
        });
    }

    function fetchLiveListings() {
        fetch('/api/listings')
            .then(res => res.json())
            .then(data => {
                if (data.success && Array.isArray(data.listings)) {
                    globalListings = data.listings;
                    displayListings(globalListings);
                } else {
                    throw new Error('bad response');
                }
            })
            .catch(() => {
                listingsContainer.innerHTML = `<div class="empty-state"><h2>Unable to load listings.</h2><p>Please refresh the page.</p></div>`;
            });
    }

    window.viewDetails = function(id) {
        const item = globalListings.find(i => i.id === id);
        if (!item || !detailsModalBody) return;

        let phone = String(item.seller_phone || '').replace(/[^0-9+]/g, '');
        if (phone.startsWith('+')) phone = phone.slice(1);
        if (phone.startsWith('0')) phone = '254' + phone.slice(1);
        const waMessage = encodeURIComponent(`Hi, is the "${item.title}" still available?`);

        detailsModalBody.innerHTML = `
            <div class="details-card">
                <div class="details-image"><img src="${item.image}" alt="${item.title}"></div>
                <div class="details-info">
                    <h2>${item.title}</h2>
                    <p class="details-price"><strong>Price:</strong> Ksh ${item.price}</p>
                    <p><strong>Location:</strong> ${item.location}</p>
                    <p><strong>Category:</strong> ${item.category || '—'}</p>
                    <p><strong>Seller:</strong> ${item.posted_by}</p>
                    <a class="whatsapp-btn" href="https://wa.me/${phone}?text=${waMessage}" target="_blank" rel="noopener">💬 Message seller on WhatsApp</a>
                </div>
            </div>
        `;
        openModal(detailsModal);
    };

    function updateNotificationBadge(count) {
        if (!notificationBadge) return;
        notificationBadge.textContent = String(count);
        if (count > 0) {
            notificationBadge.hidden = false;
            notificationBadge.style.display = 'flex';
        } else {
            notificationBadge.hidden = true;
            notificationBadge.style.display = 'none';
        }
    }

    function positionNotificationDropdown() {
        if (!notificationBtn || !notificationDropdown) return;
        const rect = notificationBtn.getBoundingClientRect();
        const gap = 8;
        const panelWidth = Math.min(340, window.innerWidth - 24);
        const top = rect.bottom + gap;
        const maxHeight = Math.max(160, window.innerHeight - top - 12);

        let left = rect.right - panelWidth;
        left = Math.max(12, Math.min(left, window.innerWidth - panelWidth - 12));

        notificationDropdown.style.width = `${panelWidth}px`;
        notificationDropdown.style.left = `${left}px`;
        notificationDropdown.style.right = 'auto';
        notificationDropdown.style.top = `${top}px`;
        notificationDropdown.style.maxHeight = `${maxHeight}px`;
    }

    function setNotificationsOpen(open) {
        if (!notificationDropdown) return;
        notificationDropdown.classList.toggle('active', open);
        notificationBtn?.setAttribute('aria-expanded', String(open));
        notificationDropdown.setAttribute('aria-hidden', String(!open));
        if (open) {
            positionNotificationDropdown();
            requestAnimationFrame(positionNotificationDropdown);
        }
    }

    function onNotificationReposition() {
        if (notificationDropdown?.classList.contains('active')) {
            positionNotificationDropdown();
        }
    }

    window.addEventListener('resize', onNotificationReposition);
    window.addEventListener('scroll', onNotificationReposition, true);

    function renderNotifications() {
        if (!notificationList) return;
        if (!currentNotifications.length) {
            notificationList.innerHTML = `<div class="noti-item">No notifications available.</div>`;
            updateNotificationBadge(0);
            return;
        }
        notificationList.innerHTML = currentNotifications.map((item, index) => `
            <div class="noti-item" data-notification-index="${index}">
                <div class="noti-text">
                    <div class="noti-title">${item.title || 'Update'}</div>
                    <div class="noti-message">${item.message || 'New update available.'}</div>
                    ${item.time ? `<div class="noti-time">${item.time}</div>` : ''}
                </div>
                <button type="button" class="mark-read-btn" data-index="${index}">Mark as read</button>
            </div>
        `).join('');
        updateNotificationBadge(currentNotifications.length);
    }

    function loadNotifications() {
        return fetch('/api/notifications')
            .then(r => {
                if (!r.ok) throw new Error('http');
                return r.json();
            })
            .then(data => {
                notificationsLoaded = true;
                currentNotifications = Array.isArray(data) ? [...data] : [];
                renderNotifications();
                onNotificationReposition();
            })
            .catch(() => {
                notificationsLoaded = true;
                currentNotifications = [];
                if (notificationList) {
                    notificationList.innerHTML = `<div class="noti-item">Unable to load notifications.</div>`;
                }
                updateNotificationBadge(0);
            });
    }

    function toggleNotifications() {
        const willOpen = !notificationDropdown?.classList.contains('active');
        setNotificationsOpen(willOpen);
        if (!willOpen) return;
        if (!notificationsLoaded) {
            loadNotifications().then(onNotificationReposition);
        } else {
            renderNotifications();
            onNotificationReposition();
        }
    }

    const assistantResizeHandle = document.getElementById('assistantResizeHandle');

    function getAssistantHeightLimits() {
        return { min: 140, max: Math.min(Math.floor(window.innerHeight * 0.72), 440) };
    }

    function setAssistantPanelHeight(px) {
        if (!assistantPanel) return;
        const { min, max } = getAssistantHeightLimits();
        const height = Math.max(min, Math.min(max, Math.round(px)));
        assistantPanel.style.height = `${height}px`;
        assistantPanel.style.maxHeight = `${height}px`;
        localStorage.setItem('assistant_panel_custom_height', String(height));
    }

    function clearAssistantCustomHeight() {
        if (!assistantPanel) return;
        localStorage.removeItem('assistant_panel_custom_height');
        assistantPanel.style.height = '';
        assistantPanel.style.maxHeight = '';
    }

    function restoreAssistantCustomHeight() {
        const saved = Number(localStorage.getItem('assistant_panel_custom_height'));
        if (saved > 0) setAssistantPanelHeight(saved);
    }

    function applyAssistantSize(sizeKey) {
        if (!assistantPanel) return;
        const allowed = ['sm', 'md', 'lg'];
        const size = allowed.includes(sizeKey) ? sizeKey : 'md';
        assistantPanel.classList.remove('assistant-panel--sm', 'assistant-panel--md', 'assistant-panel--lg');
        assistantPanel.classList.add(`assistant-panel--${size}`);
        document.querySelectorAll('.assistant-size-btn').forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.assistantSize === size);
        });
        localStorage.setItem('assistant_panel_size', size);
        clearAssistantCustomHeight();
        syncAssistantLayout();
    }

    function initAssistantSize() {
        const saved = localStorage.getItem('assistant_panel_size');
        const isMobile = window.matchMedia('(max-width: 768px)').matches;
        const defaultSize = isMobile ? 'sm' : 'md';
        applyAssistantSize(saved || defaultSize);
        restoreAssistantCustomHeight();
    }

    function initAssistantResize() {
        if (!assistantResizeHandle || !assistantPanel) return;

        let startY = 0;
        let startH = 0;

        const stopDrag = () => {
            assistantResizeHandle.classList.remove('is-dragging');
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', stopDrag);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', stopDrag);
        };

        const onMove = (e) => {
            e.preventDefault();
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            setAssistantPanelHeight(startH + (startY - clientY));
        };

        const startDrag = (e) => {
            if (!assistantPanel.classList.contains('active')) return;
            e.preventDefault();
            e.stopPropagation();
            startY = e.touches ? e.touches[0].clientY : e.clientY;
            startH = assistantPanel.offsetHeight;
            assistantResizeHandle.classList.add('is-dragging');
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', stopDrag);
            document.addEventListener('touchmove', onMove, { passive: false });
            document.addEventListener('touchend', stopDrag);
        };

        assistantResizeHandle.addEventListener('mousedown', startDrag);
        assistantResizeHandle.addEventListener('touchstart', startDrag, { passive: false });
    }

    function syncAssistantLayout() {
        if (!assistantWidget || !assistantToggle) return;
        const size = assistantToggle.offsetHeight;
        assistantWidget.style.setProperty('--assistant-size', `${size}px`);

        if (!assistantPanel || window.matchMedia('(min-width: 769px)').matches) {
            assistantWidget.style.removeProperty('--assistant-panel-bottom');
            return;
        }

        const rect = assistantToggle.getBoundingClientRect();
        const gap = 12;
        const bottomPx = Math.max(12, window.innerHeight - rect.top + gap);
        assistantWidget.style.setProperty('--assistant-panel-bottom', `${bottomPx}px`);
    }

    function getAssistantReply(message) {
        const text = message.trim().toLowerCase();
        if (/post|ad|listing|sell/.test(text)) {
            return 'Tap Post Ad, fill in your item details, and submit. You must be logged in first.';
        }
        if (/login|sign|account|register/.test(text)) {
            return 'Use Login in the top bar to sign in or create an account.';
        }
        if (/search|find|buy|browse|category/.test(text)) {
            return 'Use the search bar or category chips to find items, then tap View for details.';
        }
        if (/notif|bell|alert/.test(text)) {
            return 'Tap the bell icon to read updates. Mark items as read when you are done.';
        }
        if (/profile|dashboard|my ad/.test(text)) {
            return 'Open My Dashboard from your profile menu to manage your listings.';
        }
        return 'Ask about searching, posting ads, logging in, notifications, or your dashboard.';
    }

    function appendAssistantMessage(text, sender = 'bot') {
        if (!assistantMessages) return;
        const messageEl = document.createElement('div');
        messageEl.className = `assistant-message ${sender}`;
        messageEl.textContent = text;
        assistantMessages.appendChild(messageEl);
        assistantMessages.scrollTop = assistantMessages.scrollHeight;
    }

    function setAssistantOpen(open) {
        if (!assistantPanel) return;
        assistantPanel.classList.toggle('active', open);
        assistantPanel.setAttribute('aria-hidden', String(!open));
        if (open) {
            syncAssistantLayout();
            requestAnimationFrame(syncAssistantLayout);
            assistantInput?.focus();
        }
    }

    assistantToggle?.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const willOpen = !assistantPanel?.classList.contains('active');
        setAssistantOpen(willOpen);
    });

    assistantClose?.addEventListener('click', () => setAssistantOpen(false));

    assistantForm?.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = assistantInput?.value.trim();
        if (!text) return;
        appendAssistantMessage(text, 'user');
        if (assistantInput) assistantInput.value = '';
        setTimeout(() => appendAssistantMessage(getAssistantReply(text), 'bot'), 280);
    });

    document.addEventListener('click', (e) => {
        if (!assistantPanel?.classList.contains('active')) return;
        const target = e.target;
        const inside = target.closest?.('#assistantPanel, #assistantToggle, .assistant-widget');
        if (!inside) setAssistantOpen(false);
    });

    document.querySelectorAll('.assistant-size-btn').forEach(btn => {
        btn.addEventListener('click', () => applyAssistantSize(btn.dataset.assistantSize));
    });

    window.addEventListener('resize', () => {
        syncAssistantLayout();
        syncNavbarHeight();
    });
    window.addEventListener('scroll', syncAssistantLayout, true);
    initAssistantSize();
    initAssistantResize();

    loginBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        if (isLoggedIn()) {
            toggleProfileDropdown();
        } else {
            openModal(authModal);
        }
    });

    document.getElementById("profileDdLogout")?.addEventListener("click", () => {
        fetch('/api/logout', { method: 'POST' }).finally(() => {
            localStorage.clear();
            window.location.reload();
        });
    });

    postAdBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        if (!isLoggedIn()) {
            openModal(authModal);
            return;
        }
        openModal(adModal);
    });

    closeModalBtn?.addEventListener("click", () => closeModal(adModal));
    closeAuthBtn?.addEventListener("click", () => closeModal(authModal));
    notificationBtn?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleNotifications();
    });

    notificationDropdown?.addEventListener('click', (e) => e.stopPropagation());

    notificationList?.addEventListener('click', (event) => {
        event.stopPropagation();
        const button = event.target.closest('.mark-read-btn');
        if (!button) return;
        const index = Number(button.dataset.index);
        if (index >= 0 && index < currentNotifications.length) {
            currentNotifications.splice(index, 1);
            renderNotifications();
        }
    });

    searchForm?.addEventListener("submit", (e) => {
        e.preventDefault();
        filterListings(searchInput?.value, searchCategorySelect?.value);
    });

    categoryCards.forEach(card => {
        card.addEventListener("click", () => {
            const selectedCategory = card.dataset.category;
            setActiveCategory(selectedCategory);
            filterListings(searchInput?.value, selectedCategory);
        });
    });

    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const selectedCategory = link.dataset.nav || 'all';
            setActiveCategory(selectedCategory);
            filterListings(searchInput?.value, selectedCategory);
            navLinks.forEach(other => other.classList.remove('active'));
            link.classList.add('active');
        });
    });

    toggleAuthMode?.addEventListener("click", (e) => {
        e.preventDefault();
        isLoginMode = !isLoginMode;
        if (isLoginMode) {
            authTitle.textContent = 'Login to TUM Market';
            authSubmitBtn.textContent = 'Login';
            nameGroup.style.display = 'none';
            toggleAuthMode.textContent = "Don't have an account? Sign up";
        } else {
            authTitle.textContent = 'Create an Account';
            authSubmitBtn.textContent = 'Sign Up';
            nameGroup.style.display = 'block';
            toggleAuthMode.textContent = 'Already have an account? Login';
        }
    });

    adImageInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            currentUploadedImageBase64 = evt.target.result;
            if (imagePreview) imagePreview.src = currentUploadedImageBase64;
            if (imagePreviewContainer) imagePreviewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });

    authForm?.addEventListener("submit", (e) => {
        e.preventDefault();
        const email = document.getElementById("authEmail").value.trim();
        const password = document.getElementById("authPassword").value.trim();
        const name = document.getElementById("authName")?.value.trim() || "";

        if (!email || !password || (!isLoginMode && !name)) {
            alert('Please fill in all required fields.');
            return;
        }

        const endpoint = isLoginMode ? '/api/login' : '/api/signup';
        const payload = isLoginMode ? { email, password } : { name, email, password };

        requestJson(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(data => {
                if (data.success) {
                    persistUser({
                        name: data.name || name,
                        email: data.email || email,
                        id: data.id,
                        profile_picture: data.profile_picture
                    });
                    alert(data.message);
                    closeModal(authModal);
                } else {
                    alert(data.message || 'Unable to authenticate.');
                }
            })
            .catch(() => alert('Could not reach the server. Make sure the app is running at http://127.0.0.1:5000'));
    });

    postAdForm?.addEventListener("submit", (e) => {
        e.preventDefault();
        if (!isLoggedIn()) {
            alert('Please log in to post an ad.');
            openModal(authModal);
            return;
        }

        fetch('/api/listings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: document.getElementById("adTitle").value,
                price: document.getElementById("adPrice").value,
                location: document.getElementById("adLocation").value,
                category: document.getElementById("adCategory").value,
                seller_phone: document.getElementById("adPhone").value,
                image: currentUploadedImageBase64
            })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    closeModal(adModal);
                    postAdForm.reset();
                    currentUploadedImageBase64 = "https://via.placeholder.com/300x180";
                    if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
                    fetchLiveListings();
                } else {
                    alert(data.message || 'Could not post listing.');
                }
            })
            .catch(() => alert('Network error. Please try again.'));
    });

    document.addEventListener('click', (e) => {
        const target = e.target;
        if (profileDropdown && loginBtn &&
            !profileDropdown.contains(target) && !loginBtn.contains(target)) {
            profileDropdown.classList.remove('active');
        }
        const inNotifications = target.closest?.('#notificationWrap, #notificationBtn, #notificationDropdown');
        if (notificationDropdown?.classList.contains('active') && !inNotifications) {
            setNotificationsOpen(false);
        }
    });

    const detailsCloseBtn = detailsModal?.querySelector('.close-btn');
    detailsCloseBtn?.addEventListener('click', () => closeModal(detailsModal));

    syncNavbarHeight();
    window.addEventListener('resize', syncNavbarHeight);
    window.addEventListener('load', syncNavbarHeight);

    checkExistingSession();
    fetchLiveListings();
    loadNotifications();
});
