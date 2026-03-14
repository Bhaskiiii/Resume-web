document.addEventListener('DOMContentLoaded', () => {

    // --- Theme Toggle ---
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;
    const icon = themeToggle.querySelector('i');

    themeToggle.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        if (body.classList.contains('dark-mode')) {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }

        // Save preference
        localStorage.setItem('theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
    });

    // Load preference
    if (localStorage.getItem('theme') === 'light') {
        body.classList.remove('dark-mode');
        icon.className = 'fas fa-moon';
    } else {
        body.classList.add('dark-mode');
        icon.className = 'fas fa-sun';
    }

    // --- Refined Reveal Animation ---
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');

                // If it's a container, reveal children with delay
                if (entry.target.classList.contains('skills-container') ||
                    entry.target.classList.contains('projects-grid') ||
                    entry.target.classList.contains('info-grid') ||
                    entry.target.classList.contains('contact-details') ||
                    entry.target.classList.contains('contact-form')) {
                    const children = entry.target.children;
                    Array.from(children).forEach((child, index) => {
                        setTimeout(() => child.classList.add('visible'), index * 100);
                    });
                }
            }
        });
    }, { threshold: 0.1 });

    // Apply reveal to sections and cards
    document.querySelectorAll('.section, .glass-card, .fade-up, .skills-container, .projects-grid').forEach(el => {
        el.classList.add('fade-up');
        revealObserver.observe(el);
    });

    // --- Magnetic Hover Effect ---
    const magneticElements = document.querySelectorAll('.btn, .floating-socials a, .nav-item');

    magneticElements.forEach(el => {
        el.addEventListener('mousemove', (e) => {
            const rect = el.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            el.style.transform = `translate(${x * 0.3}px, ${y * 0.3}px)`;
            if (el.classList.contains('btn')) {
                el.style.transform += ` scale(1.05)`;
            }
        });

        el.addEventListener('mouseleave', () => {
            el.style.transform = '';
        });
    });

    // --- Resume Download ---
    const downloadBtn = document.getElementById('download-resume');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.print();
        });
    }

    // --- Enhanced Form Validation ---
    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    // --- Back to Top Button ---
    const backToTopBtn = document.getElementById('back-to-top');
    if (backToTopBtn) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                backToTopBtn.classList.add('visible');
            } else {
                backToTopBtn.classList.remove('visible');
            }
        });

        backToTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // --- Backend API Configuration ---
    const isLocal = window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === ''; // Handle file:// protocol

    const API_URL = isLocal
        ? 'http://localhost:8000/api/contact'
        : 'https://your-production-backend.com/api/contact';

    const CHAT_API_URL = isLocal
        ? 'http://localhost:8000/api/chat'
        : 'https://your-production-backend.com/api/chat';

    // Navigation Highlighting
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('section');

    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (window.scrollY >= (sectionTop - 200)) {
                current = section.getAttribute('id');
            }
        });

        navItems.forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('href').slice(1) === current) {
                item.classList.add('active');
            }
        });
    });

    // Form Handling (Backend Integration)
    const contactForm = document.getElementById('contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const message = document.getElementById('message').value.trim();

            if (!name || !email || !message) {
                showFormMessage('Please fill in all required fields.', 'error');
                return;
            }

            if (!validateEmail(email)) {
                showFormMessage('Please enter a valid email address.', 'error');
                return;
            }

            const submitBtn = contactForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;

            // Get form data
            const formData = {
                name: document.getElementById('name').value.trim(),
                email: document.getElementById('email').value.trim(),
                phone: document.getElementById('phone').value.trim(),
                message: document.getElementById('message').value.trim()
            };

            // Loading state & Duplicate prevention
            if (submitBtn.disabled) return;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';

            try {
                // Change URL to matches your backend location
                const response = await fetch(API_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const result = await response.json();

                if (response.ok) {
                    showFormMessage('Message sent successfully! Your message has been saved and delivered. ✨', 'success');
                    contactForm.reset();
                } else {
                    let errorMessage = 'Failed to send message. Please try again.';
                    if (result.detail) {
                        if (typeof result.detail === 'string') {
                            errorMessage = result.detail;
                        } else if (Array.isArray(result.detail)) {
                            // Extract messages from FastAPI's validation errors
                            errorMessage = result.detail.map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`).join(', ');
                        }
                    }
                    showFormMessage(errorMessage, 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showFormMessage('Network error. Is the backend running?', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        });
    }

    function showFormMessage(text, type) {
        let msgDiv = document.getElementById('form-message');
        if (!msgDiv) {
            msgDiv = document.createElement('div');
            msgDiv.id = 'form-message';
            contactForm.appendChild(msgDiv);
        }

        msgDiv.textContent = text;
        msgDiv.className = `form-message ${type}`;

        // Auto-hide after 5 seconds
        setTimeout(() => {
            msgDiv.style.opacity = '0';
            setTimeout(() => msgDiv.remove(), 500);
        }, 5000);
    }

    // --- AI Chatbot Logic ---
    const chatBubble = document.getElementById('chat-bubble');
    const chatContainer = document.getElementById('chat-container');
    const closeChat = document.getElementById('close-chat');
    const chatInput = document.getElementById('chat-input');
    const sendChat = document.getElementById('send-chat');
    const chatMessages = document.getElementById('chat-messages');
    const suggestionBtns = document.querySelectorAll('.suggestion-btn');

    const toggleChat = () => chatContainer.classList.toggle('active');

    if (chatBubble) chatBubble.addEventListener('click', toggleChat);
    if (closeChat) closeChat.addEventListener('click', toggleChat);

    const addMessage = (text, sender) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        msgDiv.innerHTML = `<div class="message-content">${text}</div>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msgDiv;
    };

    const showTypingIndicator = () => {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot typing';
        typingDiv.innerHTML = `
            <div class="message-content">
                <div class="typing-dots">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return typingDiv;
    };

    const handleChat = async (message) => {
        if (!message) return;

        addMessage(message, 'user');
        chatInput.value = '';

        const typingIndicator = showTypingIndicator();

        try {
            const response = await fetch(CHAT_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });
            const data = await response.json();
            typingIndicator.remove();
            addMessage(data.response, 'bot');
        } catch (error) {
            console.error('Chat Error:', error);
            typingIndicator.remove();
            addMessage("I'm having trouble connecting right now. Please try again later!", 'bot');
        }
    };

    if (sendChat) {
        sendChat.addEventListener('click', () => handleChat(chatInput.value.trim()));
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleChat(chatInput.value.trim());
        });
    }

    suggestionBtns.forEach(btn => {
        btn.addEventListener('click', () => handleChat(btn.textContent));
    });

    // Smooth Scrolling for nav items
    navItems.forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            document.querySelector(targetId).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
    // --- Scroll-Driven Profile Animation ---
    const canvas = document.getElementById('profile-canvas');
    if (canvas) {
        const context = canvas.getContext('2d');
        const loader = document.getElementById('loader-wrapper');
        const frameCount = 121;
        const frames = [];
        let imagesLoaded = 0;

        // Configuration
        const currentFrame = index => (
            `assets/frames/ezgif-frame-${index.toString().padStart(3, '0')}.jpg`
        );

        // Preload images
        for (let i = 1; i <= frameCount; i++) {
            const img = new Image();
            img.src = currentFrame(i);
            img.onload = () => {
                imagesLoaded++;
                if (imagesLoaded === frameCount) {
                    // Hide loader after all images are ready
                    loader.style.opacity = '0';
                    setTimeout(() => loader.style.display = 'none', 500);
                    render(); // Initial render
                }
            };
            frames.push(img);
        }

        const setCanvasSize = () => {
            canvas.width = canvas.offsetWidth * window.devicePixelRatio;
            canvas.height = canvas.offsetHeight * window.devicePixelRatio;
            render();
        };

        const render = () => {
            const index = Math.min(frameCount, Math.max(1, Math.floor(getScrollProgress() * frameCount)));
            const img = frames[index - 1];
            if (img && img.complete) {
                const canvasAspect = canvas.width / canvas.height;
                const imgAspect = img.width / img.height;
                let drawWidth, drawHeight, offsetX, offsetY;

                if (canvasAspect > imgAspect) {
                    drawWidth = canvas.width;
                    drawHeight = canvas.width / imgAspect;
                    offsetX = 0;
                    offsetY = (canvas.height - drawHeight) / 2;
                } else {
                    drawWidth = canvas.height * imgAspect;
                    drawHeight = canvas.height;
                    offsetX = (canvas.width - drawWidth) / 2;
                    offsetY = 0;
                }

                context.clearRect(0, 0, canvas.width, canvas.height);
                context.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
            }
        };

        const getScrollProgress = () => {
            const html = document.documentElement;
            const progress = html.scrollTop / (html.scrollHeight - html.clientHeight);
            return Math.min(1, progress * 1.5); // 1.5x faster, capped at 100%
        };

        window.addEventListener('scroll', () => {
            requestAnimationFrame(render);
        });

        window.addEventListener('resize', setCanvasSize);
        setCanvasSize();
    }

    // --- Scroll-Driven Background Animation (Right Panel) ---
    const bgCanvas = document.getElementById('bg-canvas');
    if (bgCanvas) {
        const bgContext = bgCanvas.getContext('2d');
        const bgFrameCount = 288;
        const bgFrames = [];
        let bgImagesLoaded = 0;

        const currentBgFrame = index => (
            `assets/background_frames/ezgif-frame-${index.toString().padStart(3, '0')}.jpg`
        );

        // Preload background images
        for (let i = 1; i <= bgFrameCount; i++) {
            const img = new Image();
            img.src = currentBgFrame(i);
            img.onload = () => {
                bgImagesLoaded++;
                if (bgImagesLoaded === bgFrameCount) {
                    renderBg();
                }
            };
            bgFrames.push(img);
        }

        const setBgCanvasSize = () => {
            bgCanvas.width = bgCanvas.offsetWidth * window.devicePixelRatio;
            bgCanvas.height = bgCanvas.offsetHeight * window.devicePixelRatio;
            renderBg();
        };

        const renderBg = () => {
            if (window.innerWidth <= 992) return; // MOBILE FALLBACK: Skip background animation on small screens

            const html = document.documentElement;
            const progress = html.scrollTop / (html.scrollHeight - html.clientHeight);
            const index = Math.min(bgFrameCount, Math.max(1, Math.floor(progress * bgFrameCount)));
            const img = bgFrames[index - 1];

            if (img && img.complete) {
                const canvasAspect = bgCanvas.width / bgCanvas.height;
                const imgAspect = img.width / img.height;
                let drawWidth, drawHeight, offsetX, offsetY;

                if (canvasAspect > imgAspect) {
                    drawWidth = bgCanvas.width;
                    drawHeight = bgCanvas.width / imgAspect;
                    offsetX = 0;
                    offsetY = (bgCanvas.height - drawHeight) / 2;
                } else {
                    drawWidth = bgCanvas.height * imgAspect;
                    drawHeight = bgCanvas.height;
                    offsetX = (bgCanvas.width - drawWidth) / 2;
                    offsetY = 0;
                }

                bgContext.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
                bgContext.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
            }
        };

        window.addEventListener('scroll', () => {
            if (window.innerWidth > 992) {
                requestAnimationFrame(renderBg);
            }
        });

        const debounce = (func, wait) => {
            let timeout;
            return function (...args) {
                clearTimeout(timeout);
                timeout = setTimeout(() => func.apply(this, args), wait);
            };
        };

        window.addEventListener('resize', debounce(() => {
            setBgCanvasSize();
            // Also trigger profile resize if needed
            if (canvas) setCanvasSize();
        }, 100));

        setBgCanvasSize();
    }
});
