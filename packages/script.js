// ================================================
// Agentic AI - Professional Wiki JavaScript
// ================================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all features
    initSmoothScroll();
    initCopyButtons();
    initAnimations();
    initMobileMenu();
    initDiagrams();
    initThemeToggle();
});

// ================================================
// Smooth Scrolling
// ================================================

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// ================================================
// Copy Code Functionality
// ================================================

function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(button => {
        button.addEventListener('click', function() {
            const codeBlock = this.closest('.code-section').querySelector('code');
            const text = codeBlock.textContent;
            
            navigator.clipboard.writeText(text).then(() => {
                const originalText = this.textContent;
                this.textContent = '✓ Copied!';
                this.style.background = '#10b981';
                
                setTimeout(() => {
                    this.textContent = originalText;
                    this.style.background = '';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
                this.textContent = '✗ Failed';
                setTimeout(() => {
                    this.textContent = '📋 Copy';
                }, 2000);
            });
        });
    });
}

// ================================================
// Scroll Animations
// ================================================

function initAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .layer, .stat-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// ================================================
// Mobile Menu
// ================================================

function initMobileMenu() {
    const nav = document.querySelector('.nav-container');
    const navLinks = document.querySelector('.nav-links');
    
    if (!nav || !navLinks) return;

    // Create hamburger button
    const menuToggle = document.createElement('button');
    menuToggle.className = 'mobile-menu-toggle';
    menuToggle.setAttribute('aria-label', 'Toggle menu');
    menuToggle.innerHTML = '☰';

    // Insert before nav links
    nav.insertBefore(menuToggle, navLinks);

    // Toggle menu
    menuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        navLinks.classList.toggle('active');
        menuToggle.classList.toggle('active');
        menuToggle.innerHTML = navLinks.classList.contains('active') ? '✕' : '☰';
        
        // Prevent body scroll when menu is open
        if (navLinks.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    });

    // Close menu when clicking on a link
    const navLinksItems = navLinks.querySelectorAll('a');
    navLinksItems.forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('active');
            menuToggle.classList.remove('active');
            menuToggle.innerHTML = '☰';
            document.body.style.overflow = '';
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!nav.contains(e.target) && navLinks.classList.contains('active')) {
            navLinks.classList.remove('active');
            menuToggle.classList.remove('active');
            menuToggle.innerHTML = '☰';
            document.body.style.overflow = '';
        }
    });

    // Handle resize
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            navLinks.classList.remove('active');
            menuToggle.classList.remove('active');
            menuToggle.innerHTML = '☰';
            document.body.style.overflow = '';
        }
    });
}

// ================================================
// Mermaid Diagrams
// ================================================

function initDiagrams() {
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({
            theme: 'dark',
            themeVariables: {
                primaryColor: '#667eea',
                primaryTextColor: '#fff',
                primaryBorderColor: '#764ba2',
                lineColor: '#94a3b8',
                secondaryColor: '#8b5cf6',
                tertiaryColor: '#06b6d4',
                background: '#1e293b',
                mainBkg: '#1e293b',
                secondBkg: '#334155',
                tertiaryBkg: '#475569',
                textColor: '#f8fafc',
                fontSize: '16px',
                fontFamily: 'Inter, sans-serif'
            },
            flowchart: {
                curve: 'basis',
                padding: 20
            },
            sequence: {
                diagramMarginX: 50,
                diagramMarginY: 10,
                actorMargin: 50,
                width: 150,
                height: 65,
                boxMargin: 10,
                boxTextMargin: 5,
                noteMargin: 10,
                messageMargin: 35
            }
        });

        // Render all mermaid diagrams
        mermaid.run({
            querySelector: '.mermaid'
        });
    }
}

// ================================================
// Theme Toggle (Optional Enhancement)
// ================================================

function initThemeToggle() {
    // Check for saved theme preference or default to 'dark'
    const currentTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
}

// ================================================
// Navigation Active State
// ================================================

function updateActiveNav() {
    const sections = document.querySelectorAll('.section[id]');
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

    function setActiveLink() {
        let current = '';
        const scrollPosition = window.pageYOffset + 200; // Offset for navbar height

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            
            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            
            if (href === `#${current}`) {
                link.classList.add('active');
            }
        });

        // Handle case when at the top of the page
        if (window.pageYOffset < 100) {
            navLinks.forEach(link => link.classList.remove('active'));
        }
    }

    // Update on scroll
    window.addEventListener('scroll', setActiveLink);
    
    // Initial check
    setActiveLink();
}

updateActiveNav();

// ================================================
// Stats Counter Animation
// ================================================

function animateCounters() {
    const counters = document.querySelectorAll('.stat-number');
    const speed = 200;

    const countUp = (counter) => {
        const target = +counter.getAttribute('data-target');
        const count = +counter.innerText.replace(/[^0-9]/g, '');
        const increment = target / speed;

        if (count < target) {
            counter.innerText = Math.ceil(count + increment);
            setTimeout(() => countUp(counter), 10);
        } else {
            counter.innerText = counter.getAttribute('data-target');
        }
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                counter.innerText = '0';
                countUp(counter);
                observer.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => {
        observer.observe(counter);
    });
}

animateCounters();

// ================================================
// Search Functionality (Optional)
// ================================================

function initSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const sections = document.querySelectorAll('.section');

        sections.forEach(section => {
            const text = section.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                section.style.display = 'block';
            } else {
                section.style.display = 'none';
            }
        });
    });
}

initSearch();

// ================================================
// External Links - Open in New Tab
// ================================================

document.querySelectorAll('a[href^="http"]').forEach(link => {
    link.setAttribute('target', '_blank');
    link.setAttribute('rel', 'noopener noreferrer');
});

// ================================================
// Progress Bar on Scroll
// ================================================

function initProgressBar() {
    // Create progress bar container
    const progressBarContainer = document.createElement('div');
    progressBarContainer.className = 'scroll-progress-bar';
    
    // Create progress bar fill
    const progressBarFill = document.createElement('div');
    progressBarFill.className = 'scroll-progress-fill';
    
    progressBarContainer.appendChild(progressBarFill);
    document.body.appendChild(progressBarContainer);

    // Update progress on scroll
    window.addEventListener('scroll', () => {
        const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (window.scrollY / windowHeight) * 100;
        progressBarFill.style.width = scrolled + '%';
    });
}

initProgressBar();

// ================================================
// Back to Top Button
// ================================================

function initBackToTop() {
    const backToTopBtn = document.createElement('button');
    backToTopBtn.innerHTML = '↑';
    backToTopBtn.className = 'back-to-top';
    backToTopBtn.style.cssText = `
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.3s ease, transform 0.3s ease;
        z-index: 1000;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    `;
    document.body.appendChild(backToTopBtn);

    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            backToTopBtn.style.opacity = '1';
        } else {
            backToTopBtn.style.opacity = '0';
        }
    });

    backToTopBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    backToTopBtn.addEventListener('mouseenter', () => {
        backToTopBtn.style.transform = 'translateY(-5px)';
    });

    backToTopBtn.addEventListener('mouseleave', () => {
        backToTopBtn.style.transform = 'translateY(0)';
    });
}

initBackToTop();

// ================================================
// Console Easter Egg
// ================================================

console.log('%c🤖 Agentic Multi-Stage Bot', 'color: #667eea; font-size: 20px; font-weight: bold;');
console.log('%cWelcome to the Agentic AI Wiki!', 'color: #764ba2; font-size: 14px;');
console.log('%cInterested in contributing? Check out our GitHub repo!', 'color: #94a3b8; font-size: 12px;');

// ================================================
// Export functions for external use
// ================================================

window.AgenticWiki = {
    initSmoothScroll,
    initCopyButtons,
    initAnimations,
    initMobileMenu,
    initDiagrams,
    initSearch
};
