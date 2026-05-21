document.addEventListener("DOMContentLoaded", () => {

    // --- DOM Elements ---
    const listingsContainer = document.getElementById("listingsContainer");
    const searchForm = document.querySelector(".search-bar");
    const searchInput = searchForm.querySelector('input[type="text"]');
    const searchCategorySelect = searchForm.querySelector('select');
    const categoryCards = document.querySelectorAll(".category-card");
    const navLinks = document.querySelectorAll('.nav-link');

    const postAdBtn = document.querySelector(".btn-post");
    const adModal = document.getElementById("adModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const postAdForm = document.getElementById("postAdForm");
    const adImageInput = document.getElementById("adImage");
    const imagePreviewContainer = document.getElementById("imagePreviewContainer");
    const imagePreview = document.getElementById("imagePreview");

    const loginBtn = document.querySelector(".btn-login");
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

    const detailsModal = document.getElementById("detailsModal");
    const detailsModalBody = document.getElementById("detailsModalBody");

    let currentUploadedImageBase64 = "https://via.placeholder.com/300x180";
    let isLoginMode = true;
    let globalListings = [];
    let currentNotifications = [];
    let notificationsLoaded = false;

    function openModal(modal) {
        modal.classList.add("active");
        closeAssistantPanel();
    }

    function closeModal(modal) {
        modal.classList.remove("active");
    }

    const assistantHistory = JSON.parse(localStorage.getItem('assistant_history') || '{}');

    function checkExistingSession() {
        const savedUserName = localStorage.getItem("tum_market_user");
        const savedUserId = localStorage.getItem("tum_market_user_id");
        if (savedUserName && savedUserId) {
            applyAuthenticatedUI(savedUserName, savedUserId);
        }
    }

    function deriveAssistantTopic(message) {
        const normalized = message.trim().toLowerCase();
        if (!normalized) return 'empty';
        if (/post|ad|listing/.test(normalized)) return 'posting';
        if (/login|sign|account/.test(normalized)) return 'auth';
        if (/search|find|buy|browse/.test(normalized)) return 'search';
        if (/notification|notify|alert/.test(normalized)) return 'notifications';
        if (/profile|picture|avatar|image/.test(normalized)) return 'profile';
        return 'general';
    }

    function saveAssistantHistory(topic) {
        assistantHistory[topic] = (assistantHistory[topic] || 0) + 1;
        localStorage.setItem('assistant_history', JSON.stringify(assistantHistory));
    }

    function getAssistantReply(message, topic) {
        const normalized = message.trim().toLowerCase();
        const usageCount = assistantHistory[topic] || 0;
        if (!normalized) {
            return "Please type a question and I will do my best to help.";
        }
        if (usageCount > 2) {
            return `I’ve seen questions like this ${usageCount + 1} times. For ${topic}, here’s the fastest help: ${getAssistantReply(message, 'help')}`;
        }
        if (topic === 'posting') {
            return "To post a listing, click Post Ad, fill in the item details, and submit. You need to be logged in first.";
        }
        if (topic === 'auth') {
            return "Use the Login button in the top bar to sign in or sign up. After login, your profile picture appears in the upper-right corner.";
        }
        if (topic === 'search') {
            return "Search on the page or use the category cards to find items. Click View for item details and to contact the seller.";
        }
        if (topic === 'notifications') {
            return "Click the bell icon to view notifications. You can mark items as read once you've checked them.";
        }
        if (topic === 'profile') {
            return "Your profile page lets you upload a picture. Once saved, it will show in the header instead of initials.";
        }
        return "I can help with posting ads, logging in, searching items, and contacting sellers. What would you like to do?";
    }

    function appendAssistantMessage(text, sender = 'bot') {
        const messageEl = document.createElement('div');
        messageEl.className = `assistant-message ${sender}`;
        messageEl.textContent = text;
        assistantMessages.appendChild(messageEl);
        assistantMessages.scrollTop = assistantMessages.scrollHeight;
    }

    function toggleAssistantPanel() {
        const isActive = assistantPanel.classList.toggle('active');
        assistantPanel.setAttribute('aria-hidden', String(!isActive));
        if (isActive) {
            assistantInput.focus();
        }
    }

    function closeAssistantPanel() {
        assistantPanel.classList.remove('active');
        assistantPanel.setAttribute('aria-hidden', 'true');
    }

    // ---- AI Assistant References ----
    const assistantToggle = document.getElementById('assistantToggle');
    const assistantPanel = document.getElementById('assistantPanel');
    const assistantClose = document.getElementById('assistantClose');
    const assistantForm = document.getElementById('assistantForm');
    const assistantInput = document.getElementById('assistantInput');
    const assistantMessages = document.getElementById('assistantMessages');

    assistantToggle.addEventListener('click', (e) => {
        e.preventDefault();
        toggleAssistantPanel();
    });

    assistantClose.addEventListener('click', () => closeAssistantPanel());

    assistantForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const userText = assistantInput.value.trim();
        if (!userText) {
            return;
        }
        appendAssistantMessage(userText, 'user');
        assistantInput.value = '';
        setTimeout(() => {
            appendAssistantMessage(getAssistantReply(userText), 'bot');
        }, 250);
    });

    document.addEventListener('click', (event) => {
        if (!assistantPanel.contains(event.target) && !assistantToggle.contains(event.target)) {
            closeAssistantPanel();
        }
    });

    function getProfilePhoto(userId) {
        return localStorage.getItem(`profile_picture_${userId}`) || null;
    }

    function applyAuthenticatedUI(name, userId) {
        const profilePic = getProfilePhoto(userId);
        if (profilePic) {
            loginBtn.innerHTML = `<img src="${profilePic}" alt="Profile" class="profile-avatar-nav">`;
        } else {
            const parts = (name || '').trim().split(/\s+/).filter(Boolean);
            const initials = parts.length === 0 ? 'U' : (parts.length === 1 ? parts[0][0] : (parts[0][0] + parts[parts.length-1][0]));
            const badge = (initials || 'U').toUpperCase();
            loginBtn.innerHTML = `<span class="profile-circle">${badge}</span>`;
        }
        loginBtn.setAttribute('title', 'Go to profile');
        loginBtn.classList.add('has-profile');
        loginBtn.id = "profileIcon";
    }

    function handleLogout() {
        localStorage.removeItem("tum_market_user");
        localStorage.removeItem("tum_market_user_email");
        localStorage.removeItem("tum_market_user_id");
        loginBtn.innerHTML = "Login";
        loginBtn.removeAttribute('title');
        loginBtn.classList.remove('has-profile');
        loginBtn.id = "";
        alert("Logged out");
        location.reload();
    }

    function setActiveCategory(category) {
        categoryCards.forEach(card => {
            card.classList.toggle('active', card.dataset.category === category);
        });
    }

    function displayListings(items) {
        listingsContainer.innerHTML = "";
        if (!items.length) {
            listingsContainer.innerHTML = `<div class="empty-state"><h2>No items found.</h2><p>Try a different search or category.</p></div>`;
            return;
        }

        items.forEach(item => {
            const card = document.createElement("div");
            card.classList.add("listing-card");
            card.innerHTML = `
                <div class="card-image">
                    <img src="${item.image}" alt="${item.title}">
                </div>
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

    function getListingById(id) {
        return globalListings.find(item => item.id === id);
    }

    function viewDetails(id) {
        const item = getListingById(id);
        if (!item) return;
        // prepare WhatsApp link (basic normalization for common local formats)
        const rawPhone = String(item.seller_phone || '').trim();
        let waNumber = rawPhone.replace(/[^0-9+]/g, '');
        if (waNumber.startsWith('+')) waNumber = waNumber.slice(1);
        if (waNumber.startsWith('0')) waNumber = '254' + waNumber.slice(1); // assume Kenya if local 0-prefix
        const waMessage = encodeURIComponent(`Hi, is the "${item.title}" still available? I'm interested.`);
        const waHref = `https://wa.me/${waNumber}?text=${waMessage}`;

        detailsModalBody.innerHTML = `
            <div class="details-card">
                <div class="details-image"><img src="${item.image}" alt="${item.title}"></div>
                <div class="details-info">
                    <h2>${item.title}</h2>
                    <p class="details-price"><strong>Price:</strong> Ksh ${item.price}</p>
                    <p><strong>Location:</strong> ${item.location}</p>
                    <p><strong>Category:</strong> ${item.category}</p>
                    <p><strong>Seller:</strong> ${item.posted_by}</p>
                    <p><strong>Phone:</strong> ${item.seller_phone}</p>
                    <div class="details-actions">
                        <a class="whatsapp-btn" href="${waHref}" target="_blank" rel="noopener">💬 Message seller on WhatsApp</a>
                    </div>
                </div>
            </div>
        `;
        openModal(detailsModal);
    }

    window.viewDetails = viewDetails;

    function updateNotificationBadge(count) {
        if (!notificationBadge) return;
        notificationBadge.textContent = count;
        notificationBadge.style.display = count > 0 ? 'flex' : 'none';
    }

    function renderNotifications() {
        if (!Array.isArray(currentNotifications) || !currentNotifications.length) {
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

    function markNotificationRead(index) {
        if (typeof index !== 'number' || index < 0 || index >= currentNotifications.length) return;
        currentNotifications.splice(index, 1);
        renderNotifications();
    }

    function toggleNotifications() {
        notificationDropdown.classList.toggle('active');
        if (notificationDropdown.classList.contains('active')) {
            if (notificationsLoaded) {
                renderNotifications();
            } else {
                loadNotifications();
            }
        }
    }

    window.toggleNotifications = toggleNotifications;
    window.loadNotifications = loadNotifications;
    window.renderNotifications = renderNotifications;
    window.markNotificationRead = markNotificationRead;

    // Profile dropdown handling
    let profileDropdownEl = null;

    function createProfileDropdown() {
        if (profileDropdownEl) return;
        profileDropdownEl = document.createElement('div');
        profileDropdownEl.id = 'profileDropdown';
        profileDropdownEl.className = 'profile-dropdown';
        profileDropdownEl.innerHTML = `
            <a href="/profile" class="profile-dd-item">Profile</a>
            <button type="button" class="profile-dd-item" id="profileDdLogout">Logout</button>
        `;
        // Append to nav so positioning is relative to nav-links
        const nav = loginBtn.parentElement || document.body;
        nav.appendChild(profileDropdownEl);

        document.getElementById('profileDdLogout').addEventListener('click', (ev) => {
            ev.preventDefault();
            handleLogout();
        });
    }

    function toggleProfileDropdown() {
        createProfileDropdown();
        profileDropdownEl.classList.toggle('active');
    }

    function closeProfileDropdown() {
        if (profileDropdownEl) profileDropdownEl.classList.remove('active');
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        const target = e.target;
        if (profileDropdownEl && !profileDropdownEl.contains(target) && !loginBtn.contains(target)) {
            closeProfileDropdown();
        }
        if (notificationDropdown && !notificationDropdown.contains(target) && !notificationBtn.contains(target)) {
            notificationDropdown.classList.remove('active');
        }
    });

    function loadNotifications() {
        fetch('/api/notifications')
            .then(r => r.json())
            .then(data => {
                notificationsLoaded = true;
                if (!Array.isArray(data)) {
                    currentNotifications = [];
                    notificationList.innerHTML = `<div class="noti-item">No notifications available.</div>`;
                    updateNotificationBadge(0);
                    return;
                }
                currentNotifications = data;
                renderNotifications();
            })
            .catch(() => {
                notificationsLoaded = true;
                currentNotifications = [];
                updateNotificationBadge(0);
                notificationList.innerHTML = `<div class="noti-item">Unable to load notifications.</div>`;
            });
    }

    notificationList.addEventListener('click', (event) => {
        const button = event.target.closest('.mark-read-btn');
        if (!button) return;
        const index = Number(button.dataset.index);
        markNotificationRead(index);
    });

    function filterListings(searchText, category) {
        const query = (searchText || '').trim().toLowerCase();
        const selectedCategory = category || 'all';
        const filtered = globalListings.filter(item => {
            const matchesSearch = !query || item.title.toLowerCase().includes(query) || item.location.toLowerCase().includes(query);
            const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
            return matchesSearch && matchesCategory;
        });
        displayListings(filtered);
    }

    function resetAdForm() {
        postAdForm.reset();
        currentUploadedImageBase64 = "https://via.placeholder.com/300x180";
        imagePreviewContainer.style.display = 'none';
        imagePreview.src = '';
    }

    function fetchLiveListings() {
        fetch('/api/listings')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    globalListings = data.listings;
                    displayListings(globalListings);
                }
            })
            .catch(() => {
                listingsContainer.innerHTML = `<div class="empty-state"><h2>Unable to load listings.</h2><p>Please refresh the page.</p></div>`;
            });
    }

    fetchLiveListings();
    loadNotifications();
    checkExistingSession();

    loginBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const savedUser = localStorage.getItem("tum_market_user");
        const savedUserId = localStorage.getItem("tum_market_user_id");
        if (savedUser && savedUserId) {
            // if logged in, toggle the profile dropdown instead of redirecting immediately
            toggleProfileDropdown();
            return;
        }
        authModal.classList.add("active");
    });

    postAdBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const savedUser = localStorage.getItem("tum_market_user");
        const savedUserId = localStorage.getItem("tum_market_user_id");
        if (!savedUser || !savedUserId) {
            authModal.classList.add("active");
            return;
        }
        openModal(adModal);
    });

    closeModalBtn.addEventListener("click", () => closeModal(adModal));
    closeAuthBtn.addEventListener("click", () => closeModal(authModal));
    notificationBtn.addEventListener("click", (e) => {
        e.preventDefault();
        toggleNotifications();
    });

    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        filterListings(searchInput.value, searchCategorySelect.value);
    });

    categoryCards.forEach(card => {
        card.addEventListener("click", () => {
            const selectedCategory = card.dataset.category;
            setActiveCategory(selectedCategory);
            filterListings(searchInput.value, selectedCategory);
        });
    });

    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const selectedCategory = link.dataset.nav || 'all';
            setActiveCategory(selectedCategory);
            filterListings(searchInput.value, selectedCategory);
            navLinks.forEach(other => other.classList.remove('active'));
            link.classList.add('active');
        });
    });

    toggleAuthMode.addEventListener("click", (e) => {
        e.preventDefault();
        isLoginMode = !isLoginMode;
        if (isLoginMode) {
            authTitle.innerText = 'Login to TUM Market';
            authSubmitBtn.innerText = 'Login';
            nameGroup.style.display = 'none';
            toggleAuthMode.innerText = "Don't have an account? Sign up";
        } else {
            authTitle.innerText = 'Create an Account';
            authSubmitBtn.innerText = 'Sign Up';
            nameGroup.style.display = 'block';
            toggleAuthMode.innerText = 'Already have an account? Login';
        }
    });

    authForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const email = document.getElementById('authEmail').value.trim();
        const password = document.getElementById('authPassword').value.trim();
        const name = document.getElementById('authName').value.trim();

        if (!email || !password || (!isLoginMode && !name)) {
            alert('Please fill in all required fields.');
            return;
        }

        const url = isLoginMode ? '/api/login' : '/api/signup';
        const payload = isLoginMode ? { email, password } : { name, email, password };

        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => r.json().then(data => ({ status: r.status, body: data })))
        .then(({ status, body }) => {
            if (body.success) {
                const userName = body.name || name;
                const userEmail = body.email || email;
                const userId = body.id || localStorage.getItem('tum_market_user_id');
                localStorage.setItem('tum_market_user', userName);
                localStorage.setItem('tum_market_user_email', userEmail);
                if (userId) {
                    localStorage.setItem('tum_market_user_id', userId);
                }
                applyAuthenticatedUI(userName, userId);
                alert(body.message);
                closeModal(authModal);
                checkExistingSession();
            } else {
                alert(body.message || 'Unable to authenticate.');
            }
        })
        .catch(() => {
            alert('Unable to reach the server. Please try again later.');
        });
    });

    adImageInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) {
            imagePreviewContainer.style.display = 'none';
            return;
        }
        const reader = new FileReader();
        reader.onload = function(evt) {
            currentUploadedImageBase64 = evt.target.result;
            imagePreview.src = currentUploadedImageBase64;
            imagePreviewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });

    postAdForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const title = document.getElementById("adTitle").value.trim();
        const price = document.getElementById("adPrice").value.trim();
        const location = document.getElementById("adLocation").value.trim();
        const category = document.getElementById("adCategory").value;
        const tier = document.getElementById("adTier").value;
        const sellerPhone = document.getElementById("adPhone").value.trim() || "0700000000";
        const userName = localStorage.getItem("tum_market_user");
        const userId = localStorage.getItem("tum_market_user_id");

        if (!userName || !userId) {
            alert("Please login before posting an ad.");
            authModal.classList.add("active");
            return;
        }

        if (!title || !price || !location || !category) {
            alert("Please fill in all required fields.");
            return;
        }

        fetch('/api/listings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                price,
                location,
                category,
                tier,
                seller_phone: sellerPhone,
                posted_by: userName,
                user_id: Number(userId),
                image: currentUploadedImageBase64
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                closeModal(adModal);
                resetAdForm();
                fetchLiveListings();
            } else {
                alert(data.message || 'Unable to post ad.');
            }
        })
        .catch(() => {
            alert('A network error occurred while posting the ad.');
        });
    });

});