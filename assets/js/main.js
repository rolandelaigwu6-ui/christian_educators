/* Christian Educators Global Network — site script
   1) Footer year  2) Mobile nav  3) Active nav link
   4) Demo member portal (localStorage). Replace with a real membership
      platform (e.g. NeonCRM) before accepting real logins.
   5) Demo form handler for donate / join / contact / newsletter forms. */
(function () {
    'use strict';
    var MEMBER_KEY = 'cegn_member';

    function readMember() {
        try { return JSON.parse(localStorage.getItem(MEMBER_KEY) || 'null'); }
        catch (e) { return null; }
    }
    function writeMember(member) {
        localStorage.setItem(MEMBER_KEY, JSON.stringify(member));
    }

    /* 1) Auto-update the year in footers */
    document.querySelectorAll('[data-year]').forEach(function (el) {
        el.textContent = new Date().getFullYear();
    });

    /* 2) Mobile navigation toggle */
    var nav = document.querySelector('.site-nav');
    var toggle = document.querySelector('.nav-toggle');
    if (nav && toggle) {
        toggle.addEventListener('click', function () {
            var open = nav.classList.toggle('nav-open');
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    /* 3) Highlight the current page in the navigation */
    var here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
    document.querySelectorAll('.nav-links a').forEach(function (a) {
        var href = (a.getAttribute('href') || '').toLowerCase();
        if (here && href.slice(-here.length) === here) a.classList.add('is-active');
    });

    /* 4) Demo member portal */
    var IN_PAGES = location.pathname.toLowerCase().indexOf('/pages/') !== -1;
    function portalPath(file) { return IN_PAGES ? file : 'pages/' + file; }
    document.querySelectorAll('[data-member-name]').forEach(function (el) {
        var member = readMember();
        if (member) el.textContent = member.name || member.email;
    });
    document.querySelectorAll('[data-nav-portal]').forEach(function (a) {
        if (readMember()) {
            a.textContent = 'My Dashboard';
            a.setAttribute('href', portalPath('member-dashboard.html'));
        }
    });
    document.querySelectorAll('[data-logout]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            localStorage.removeItem(MEMBER_KEY);
            location.href = portalPath(btn.getAttribute('data-logout') || 'member-login.html');
        });
    });
    document.querySelectorAll('[data-requires-member]').forEach(function (el) {
        var target = el.getAttribute('data-requires-member');
        if (!readMember() && target) location.href = portalPath(target);
    });

    /* Login (demo: any email + password of 4+ characters) */
    var loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var email = loginForm.querySelector('[name=email]').value.trim();
            var pass = loginForm.querySelector('[name=password]').value;
            var err = loginForm.querySelector('.form-error');
            if (!email || email.indexOf('@') === -1 || pass.length < 4) {
                err.hidden = false;
                return;
            }
            err.hidden = true;
            var member = readMember() || {};
            member.email = email;
            if (!member.name) member.name = email.split('@')[0];
            member.tier = member.tier || 'Member';
            writeMember(member);
            location.href = portalPath('member-dashboard.html');
        });
    }

    /* Create account (demo: stores name + email locally) */
    var createForm = document.getElementById('create-account-form');
    if (createForm) {
        createForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var name = createForm.querySelector('[name=firstname]').value.trim();
            var email = createForm.querySelector('[name=email]').value.trim();
            var pass = createForm.querySelector('[name=password]').value;
            var err = createForm.querySelector('.form-error');
            if (!name || !email || email.indexOf('@') === -1 || pass.length < 8) {
                err.hidden = false;
                return;
            }
            err.hidden = true;
            writeMember({ name: name, email: email, tier: 'Member' });
            location.href = portalPath('member-dashboard.html');
        });
    }

    /* 5) Generic demo forms: form[data-demo-form] reveals success block by id */
    document.querySelectorAll('form[data-demo-form]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var ok = document.getElementById(form.getAttribute('data-success'));
            if (ok) {
                ok.hidden = false;
                form.hidden = true;
                ok.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });
})();
