/* Christian Educators Global Network site script.
   Authentication is handled by the FastAPI backend with an HttpOnly cookie.
   No password or session token is stored in browser storage. */
(function () {
    "use strict";

    var API_BASE = (location.hostname === "127.0.0.1" || location.hostname === "localhost")
        ? "http://127.0.0.1:8000"
        : "";
    var IN_PAGES = location.pathname.toLowerCase().indexOf("/pages/") !== -1;

    function portalPath(file) {
        return IN_PAGES ? file : "pages/" + file;
    }

    function apiRequest(path, options) {
        var settings = options || {};
        settings.credentials = "include";
        return fetch(API_BASE + path, settings);
    }

    async function errorMessage(response, fallback) {
        try {
            var body = await response.json();
            if (typeof body.detail === "string") return body.detail;
            if (Array.isArray(body.detail)) {
                return body.detail.map(function (item) {
                    var name = item.loc && item.loc[item.loc.length - 1];
                    return (name ? String(name).replace(/_/g, " ") + ": " : "") + item.msg;
                }).join(". ");
            }
            return fallback;
        } catch (error) {
            return fallback;
        }
    }

    document.querySelectorAll("[data-year]").forEach(function (element) {
        element.textContent = new Date().getFullYear();
    });

    var main = document.querySelector("main");
    if (main && IN_PAGES && !document.querySelector("[data-go-back]")) {
        var breadcrumbs = document.createElement("nav");
        breadcrumbs.className = "breadcrumbs";
        breadcrumbs.setAttribute("aria-label", "Breadcrumb");
        var homeLink = document.createElement("a");
        homeLink.href = "../index.html";
        homeLink.textContent = "Home";
        var separator = document.createElement("span");
        separator.textContent = "/";
        separator.setAttribute("aria-hidden", "true");
        var currentPage = document.createElement("span");
        currentPage.textContent = document.title.split("|")[0].trim();
        currentPage.setAttribute("aria-current", "page");
        breadcrumbs.append(homeLink, separator, currentPage);
        var backButton = document.createElement("button");
        backButton.type = "button";
        backButton.className = "back-button";
        backButton.setAttribute("data-go-back", "");
        backButton.textContent = "← Back";
        backButton.addEventListener("click", function () {
            if (window.history.length > 1 && document.referrer) {
                window.history.back();
                return;
            }
            location.href = IN_PAGES ? "../index.html" : "index.html";
        });
        breadcrumbs.appendChild(backButton);
        main.insertBefore(breadcrumbs, main.firstChild);
    }

    var nav = document.querySelector(".site-nav");
    var toggle = document.querySelector(".nav-toggle");
    if (nav && toggle) {
        toggle.addEventListener("click", function () {
            var open = nav.classList.toggle("nav-open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });
    }

    var here = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    document.querySelectorAll(".nav-links a").forEach(function (link) {
        var href = (link.getAttribute("href") || "").toLowerCase();
        if (here && href.slice(-here.length) === here) {
            link.classList.add("is-active");
            link.setAttribute("aria-current", "page");
        }
    });

    var navGroups = {
        "academy.html": "about.html",
        "ministry-aged.html": "generosity.html",
        "support-teacher.html": "generosity.html",
        "sponsor-child.html": "generosity.html",
        "adopt-widow.html": "generosity.html",
        "membership.html": "get-involved.html",
        "join.html": "get-involved.html",
        "state-coordinator.html": "get-involved.html",
        "what_new.html": "calendar.html"
    };
    document.querySelectorAll(".nav-links a").forEach(function (link) {
        if (navGroups[here] && link.getAttribute("href").split("/").pop() === navGroups[here]) {
            link.classList.add("is-active");
        }
    });
    if (nav && toggle) {
        nav.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                nav.classList.remove("nav-open");
                toggle.setAttribute("aria-expanded", "false");
                toggle.focus();
            }
        });
    }

    // Native observers animate only entering content; no animation loop or library.
    if ("IntersectionObserver" in window && window.matchMedia) {
        var motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
        var revealObserver = null;
        var revealItems = [];
        function enableContentMotion() {
            if (motionPreference.matches) return;
            revealItems = Array.from(document.querySelectorAll(
                ".content-section > .section-label, .content-section > h2, .content-section > p, " +
                ".mission-card, .info-grid > article, .article-card, .steps > li, " +
                ".editorial-split > *, .facts-strip > div"
            ));
            revealObserver = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.08, rootMargin: "0px 0px -24px 0px" });
            var siblings = new Map();
            revealItems.forEach(function (item) {
                var index = siblings.get(item.parentNode) || 0;
                siblings.set(item.parentNode, index + 1);
                item.classList.add("reveal-item", "reveal-delay-" + (index % 4));
                revealObserver.observe(item);
            });
        }
        enableContentMotion();
        function stopContentMotion() {
            if (!motionPreference.matches) return;
            if (revealObserver) revealObserver.disconnect();
            revealItems.forEach(function (item) { item.classList.add("is-visible"); });
        }
        if (motionPreference.addEventListener) motionPreference.addEventListener("change", stopContentMotion);
        document.addEventListener("focusin", function (event) {
            var item = event.target.closest(".reveal-item");
            if (item) {
                item.classList.add("is-visible");
                if (revealObserver) revealObserver.unobserve(item);
            }
        });
        if (nav) {
            var sentinel = document.createElement("span");
            sentinel.className = "nav-sentinel";
            sentinel.setAttribute("aria-hidden", "true");
            nav.insertAdjacentElement("afterend", sentinel);
            var navObserver = new IntersectionObserver(function (entries) {
                nav.classList.toggle("is-scrolled", !entries[0].isIntersecting);
            });
            navObserver.observe(sentinel);
        }
    }

    apiRequest("/auth/me")
        .then(function (response) {
            return response.ok ? response.json() : null;
        })
        .then(function (member) {
            if (!member) {
                return;
            }
            document.querySelectorAll("[data-nav-portal]").forEach(function (link) {
                link.textContent = "My Dashboard";
                link.setAttribute("href", portalPath("member-dashboard.html"));
            });
            if (member.is_admin) {
                document.querySelectorAll("[data-nav-admin], [data-admin-link]").forEach(function (link) {
                    link.hidden = false;
                    link.setAttribute("href", portalPath("admin-dashboard.html"));
                });
            }
        })
        .catch(function () {
            /* Public pages remain usable when the local API is not running. */
        });

    function startFormRequest(form) {
        if (form.getAttribute("aria-busy") === "true") return null;
        var submit = form.querySelector("button[type=submit]");
        var label = submit ? submit.textContent : "";
        form.setAttribute("aria-busy", "true");
        if (submit) { submit.disabled = true; submit.textContent = "Please wait…"; }
        form.querySelectorAll(".form-error, .form-success").forEach(function (panel) {
            panel.hidden = true;
        });
        return function () {
            form.removeAttribute("aria-busy");
            if (submit) { submit.disabled = false; submit.textContent = label; }
        };
    }

    var loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!loginForm.reportValidity()) return;
            var finish = startFormRequest(loginForm);
            if (!finish) return;
            var error = loginForm.querySelector(".form-error");
            var email = loginForm.querySelector("[name=email]").value.trim();
            var password = loginForm.querySelector("[name=password]").value;

            try {
                var response = await apiRequest("/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: email, password: password })
                });

                if (!response.ok) {
                    error.textContent = await errorMessage(response, "Unable to sign in. Please check your details and try again.");
                    error.hidden = false;
                    return;
                }

                location.href = portalPath("member-dashboard.html");
            } catch (requestError) {
                error.textContent = "The sign-in service is unavailable. Please try again.";
                error.hidden = false;
            } finally {
                finish();
            }
        });
    }

    var createAccountForm = document.getElementById("create-account-form");
    if (createAccountForm) {
        createAccountForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!createAccountForm.reportValidity()) return;
            var finish = startFormRequest(createAccountForm);
            if (!finish) return;
            var error = createAccountForm.querySelector(".form-error");
            var firstName = createAccountForm.querySelector("[name=firstname]").value.trim();
            var lastName = createAccountForm.querySelector("[name=lastname]").value.trim();
            var email = createAccountForm.querySelector("[name=email]").value.trim();
            var password = createAccountForm.querySelector("[name=password]").value;

            try {
                var response = await apiRequest("/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        first_name: firstName,
                        last_name: lastName,
                        email: email,
                        password: password
                    })
                });

                if (!response.ok) {
                    error.textContent = await errorMessage(response, "Unable to create your account. Please try again.");
                    error.hidden = false;
                    return;
                }

                // The account is created either way, so reveal which outcome actually
                // happened instead of always claiming a verification email is coming.
                // Only an explicit false shows the warning, so an older API that does
                // not report email_sent still reads as success.
                var registration = await response.json();

                error.hidden = true;
                createAccountForm.hidden = true;
                document.getElementById(
                    registration.email_sent === false
                        ? "create-account-warning"
                        : "create-account-success"
                ).hidden = false;
            } catch (requestError) {
                error.textContent = "The account service is unavailable. Please try again.";
                error.hidden = false;
            } finally {
                finish();
            }
        });
    }

    var emailVerification = document.querySelector("[data-email-verification]");
    if (emailVerification) {
        var verificationToken = new URLSearchParams(location.search).get("token");
        var verificationStatus = emailVerification.querySelector("[data-verification-status]");
        var verificationError = emailVerification.querySelector("[data-verification-error]");
        var verificationLogin = emailVerification.querySelector("[data-verification-login]");

        if (!verificationToken) {
            verificationStatus.hidden = true;
            verificationError.textContent = "This verification link is incomplete.";
            verificationError.hidden = false;
        } else {
            apiRequest("/auth/verify-email", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: verificationToken })
            }).then(async function (response) {
                if (!response.ok) {
                    throw new Error(await errorMessage(response, "Unable to verify this email address."));
                }
                verificationStatus.textContent = "Your email has been verified. You can now log in.";
                verificationLogin.hidden = false;
            }).catch(function (error) {
                verificationStatus.hidden = true;
                verificationError.textContent = error.message;
                verificationError.hidden = false;
            });
        }
    }

    var requestPasswordResetForm = document.getElementById("request-password-reset-form");
    var resetPasswordForm = document.getElementById("reset-password-form");
    var passwordResetToken = new URLSearchParams(location.search).get("token");
    if (requestPasswordResetForm && resetPasswordForm && passwordResetToken) {
        requestPasswordResetForm.hidden = true;
        resetPasswordForm.hidden = false;
    }
    if (requestPasswordResetForm) {
        requestPasswordResetForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!requestPasswordResetForm.reportValidity()) {
                return;
            }
            var finish = startFormRequest(requestPasswordResetForm);
            if (!finish) return;
            var error = requestPasswordResetForm.querySelector(".form-error");
            var success = requestPasswordResetForm.querySelector(".form-success");
            try {
                var response = await apiRequest("/auth/request-password-reset", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: requestPasswordResetForm.querySelector("[name=email]").value.trim() })
                });
                if (!response.ok) {
                    throw new Error(await errorMessage(response, "Unable to request a password reset."));
                }
                success.textContent = (await response.json()).message;
                success.hidden = false;
                error.hidden = true;
            } catch (requestError) {
                error.textContent = requestError.message || "The account service is unavailable. Please try again.";
                error.hidden = false;
            } finally {
                finish();
            }
        });
    }
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!resetPasswordForm.reportValidity()) {
                return;
            }
            var finish = startFormRequest(resetPasswordForm);
            if (!finish) return;
            var error = resetPasswordForm.querySelector(".form-error");
            var success = resetPasswordForm.querySelector(".form-success");
            try {
                var response = await apiRequest("/auth/reset-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        token: passwordResetToken,
                        password: resetPasswordForm.querySelector("[name=password]").value
                    })
                });
                if (!response.ok) {
                    throw new Error(await errorMessage(response, "Unable to reset your password."));
                }
                success.textContent = (await response.json()).message;
                success.hidden = false;
                error.hidden = true;
            } catch (requestError) {
                error.textContent = requestError.message || "The account service is unavailable. Please try again.";
                error.hidden = false;
            } finally {
                finish();
            }
        });
    }

    var paymentResult = document.querySelector("[data-payment-result]");
    if (paymentResult) {
        var paymentReference = new URLSearchParams(location.search).get("reference");
        var paymentStatus = paymentResult.querySelector("[data-payment-status]");
        var paymentError = paymentResult.querySelector("[data-payment-error]");
        if (!paymentReference) {
            paymentStatus.hidden = true;
            paymentError.textContent = "We could not find your payment reference.";
            paymentError.hidden = false;
        } else {
            apiRequest("/payments/verify/" + encodeURIComponent(paymentReference))
                .then(async function (response) {
                    if (!response.ok) {
                        throw new Error(await errorMessage(response, "Unable to verify this payment."));
                    }
                    return response.json();
                })
                .then(function (payment) {
                    paymentStatus.textContent = payment.status === "success"
                        ? "Payment confirmed. Thank you for your support."
                        : "Your payment is still pending. Please check your Paystack receipt before trying again.";
                })
                .catch(function (error) {
                    paymentStatus.hidden = true;
                    paymentError.textContent = error.message;
                    paymentError.hidden = false;
                });
        }
    }

    function showDashboardError() {
        var panel = document.querySelector("[data-dashboard-error]");
        if (panel) { panel.hidden = false; panel.focus(); }
    }
    document.querySelectorAll("[data-dashboard-retry]").forEach(function (button) {
        button.addEventListener("click", function () { location.reload(); });
    });

    var dashboard = document.querySelector("[data-member-dashboard]");
    if (dashboard) {
        apiRequest("/member/dashboard")
            .then(function (response) {
                if (response.status === 401) {
                    location.href = portalPath("member-login.html");
                    return null;
                }
                if (!response.ok) throw new Error("Unable to load the member dashboard.");
                return response.json();
            })
            .then(function (member) {
                if (!member) {
                    return;
                }
                document.querySelectorAll("[data-member-name]").forEach(function (element) {
                    element.textContent = member.first_name;
                });
                document.querySelectorAll("[data-member-email]").forEach(function (element) {
                    element.textContent = member.email;
                });
                document.querySelectorAll("[data-member-status]").forEach(function (element) {
                    element.textContent = member.membership_status;
                });
                dashboard.hidden = false;
            })
            .catch(showDashboardError);
    }

    function fillAdminTable(tableId, rows, fields) {
        var body = document.querySelector("#" + tableId + " tbody");
        if (!body) {
            return;
        }
        body.replaceChildren();
        if (!rows.length) {
            var emptyRow = document.createElement("tr");
            var emptyCell = document.createElement("td");
            emptyCell.colSpan = fields.length;
            emptyCell.textContent = "No submissions yet.";
            emptyRow.appendChild(emptyCell);
            body.appendChild(emptyRow);
            return;
        }
        rows.forEach(function (row) {
            var tableRow = document.createElement("tr");
            fields.forEach(function (field) {
                var cell = document.createElement("td");
                cell.textContent = typeof row[field] === "boolean" ? (row[field] ? "Yes" : "No") : (row[field] || "—");
                tableRow.appendChild(cell);
            });
            body.appendChild(tableRow);
        });
    }

    var adminDashboard = document.querySelector("[data-admin-dashboard]");
    if (adminDashboard) {
        Promise.all([
            apiRequest("/admin/overview"),
            apiRequest("/admin/membership-applications"),
            apiRequest("/admin/contact-submissions"),
            apiRequest("/admin/newsletter-subscribers"),
            apiRequest("/admin/payments")
        ]).then(async function (responses) {
            var unauthorized = responses.some(function (response) {
                return response.status === 401;
            });
            if (unauthorized) {
                location.href = portalPath("member-login.html");
                return;
            }
            var denied = responses.some(function (response) {
                return response.status === 403;
            });
            if (denied) {
                adminDashboard.hidden = false;
                document.querySelector("[data-admin-access-error]").hidden = false;
                return;
            }
            if (responses.some(function (response) { return !response.ok; })) {
                throw new Error("Unable to load the admin dashboard.");
            }
            var data = await Promise.all(responses.map(function (response) {
                return response.json();
            }));
            document.querySelector("[data-admin-applications]").textContent = data[0].membership_applications;
            document.querySelector("[data-admin-contacts]").textContent = data[0].contact_submissions;
            document.querySelector("[data-admin-subscribers]").textContent = data[0].newsletter_subscribers;
            fillAdminTable("admin-applications", data[1], ["name", "email", "phone", "tier", "country", "location", "role", "organization", "church", "faith_agreement", "terms_accepted", "marketing_consent", "created_at"]);
            fillAdminTable("admin-contacts", data[2], ["name", "email", "topic", "message", "created_at"]);
            fillAdminTable("admin-subscribers", data[3], ["first_name", "email", "subscribed_at"]);
            fillAdminTable("admin-payments", data[4], ["reference", "email", "payment_type", "amount_ngn", "currency", "status", "created_at", "paid_at"]);
            adminDashboard.hidden = false;
        }).catch(showDashboardError);
    }

    var grantAdminForm = document.getElementById("grant-admin-form");
    if (grantAdminForm) {
        grantAdminForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!grantAdminForm.reportValidity()) {
                return;
            }
            var finish = startFormRequest(grantAdminForm);
            if (!finish) return;

            var error = grantAdminForm.querySelector(".form-error");
            var success = grantAdminForm.querySelector(".form-success");
            try {
                var response = await apiRequest("/admin/users/grant-admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        email: grantAdminForm.querySelector("[name=email]").value.trim()
                    })
                });
                if (!response.ok) {
                    error.textContent = await errorMessage(response, "Unable to grant administrator access.");
                    error.hidden = false;
                    success.hidden = true;
                    return;
                }
                var result = await response.json();
                success.textContent = result.message;
                success.hidden = false;
                error.hidden = true;
                grantAdminForm.reset();
            } catch (requestError) {
                error.textContent = "The admin service is unavailable. Please try again.";
                error.hidden = false;
                success.hidden = true;
            } finally {
                finish();
            }
        });
    }

    document.querySelectorAll("[data-logout]").forEach(function (button) {
        button.addEventListener("click", async function () {
            if (button.disabled) return;
            button.disabled = true;
            button.setAttribute("aria-busy", "true");
            var error = button.parentNode.querySelector("[data-logout-error]");
            if (!error) {
                error = document.createElement("p");
                error.className = "form-error";
                error.setAttribute("data-logout-error", "");
                error.setAttribute("role", "alert");
                button.insertAdjacentElement("afterend", error);
            }
            error.hidden = true;
            try {
                var response = await apiRequest("/auth/logout", { method: "POST" });
                if (!response.ok) throw new Error("Sign-out failed.");
                location.href = portalPath(button.getAttribute("data-logout") || "member-login.html");
            } catch (requestError) {
                error.textContent = "We couldn’t sign out. Your session may still be active. Please try again.";
                error.hidden = false;
            } finally {
                button.disabled = false;
                button.removeAttribute("aria-busy");
            }
        });
    });

    function connectPublicForm(formId, endpoint, getPayload, successId, warningId, unavailableMessage, onSuccess) {
        var form = document.getElementById(formId);
        if (!form) {
            return;
        }

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!form.reportValidity()) {
                return;
            }

            if (form.getAttribute("aria-busy") === "true") return;
            var submit = form.querySelector("button[type=submit]");
            var submitLabel = submit ? submit.textContent : "";
            form.setAttribute("aria-busy", "true");
            if (submit) { submit.disabled = true; submit.textContent = "Sending…"; }
            var error = form.querySelector(".form-error");
            if (error) error.hidden = true;
            var success = document.getElementById(successId);

            try {
                var response = await apiRequest(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(getPayload(form))
                });

                if (!response.ok) {
                    if (error) {
                        error.textContent = await errorMessage(response, "We could not submit the form. Please review your details and try again.");
                        error.hidden = false;
                    }
                    return;
                }

                var result = await response.json();

                if (onSuccess) {
                    await onSuccess(form, result);
                    return;
                }

                if (error) {
                    error.hidden = true;
                }

                // The submission is saved either way, so a confirmation email that
                // failed must not be reported as one that is on its way. Only an
                // explicit false shows the warning, so an older API that does not
                // report email_sent still reads as success.
                var warning = warningId ? document.getElementById(warningId) : null;
                var panel = (result.email_sent === false && warning) ? warning : success;

                form.hidden = true;
                if (panel) {
                    panel.hidden = false;
                    panel.focus({ preventScroll: true });
                    panel.scrollIntoView({ behavior: "auto", block: "center" });
                }
            } catch (requestError) {
                if (error) {
                    error.textContent = requestError.message || unavailableMessage;
                    error.hidden = false;
                }
            } finally {
                form.removeAttribute("aria-busy");
                if (submit) { submit.disabled = false; submit.textContent = submitLabel; }
            }
        });
    }

    connectPublicForm(
        "resend-verification-form",
        "/auth/request-email-verification",
        function (form) {
            return { email: form.querySelector("[name=email]").value.trim() };
        },
        "resend-verification-success",
        null,
        "The account service is unavailable. Please try again."
    );

    connectPublicForm(
        "join-form",
        "/membership-applications",
        function (form) {
            return {
                tier: form.querySelector("[name=tier]").value,
                first_name: form.querySelector("[name=firstname]").value.trim(),
                last_name: form.querySelector("[name=lastname]").value.trim(),
                email: form.querySelector("[name=email]").value.trim(),
                country: form.querySelector("[name=country]").value,
                role: form.querySelector("[name=role]").value,
                organization: form.querySelector("[name=organization]").value.trim(),
                phone: form.querySelector("[name=phone]").value.trim(),
                location: form.querySelector("[name=location]").value.trim(),
                church: form.querySelector("[name=church]").value.trim(),
                faith_agreement: form.querySelector("[name=faith_agreement]").checked,
                terms_accepted: document.getElementById("join-consent").checked,
                marketing_consent: document.getElementById("join-updates").checked
            };
        },
        "join-success",
        "join-warning",
        "The membership application service is unavailable. Please try again."
    );

    connectPublicForm(
        "contact-form",
        "/contact-submissions",
        function (form) {
            return {
                name: form.querySelector("[name=name]").value.trim(),
                email: form.querySelector("[name=email]").value.trim(),
                topic: form.querySelector("[name=topic]").value,
                message: form.querySelector("[name=message]").value.trim()
            };
        },
        "contact-success",
        "contact-warning",
        "The contact service is unavailable. Please try again."
    );

    connectPublicForm(
        "newsletter-form",
        "/newsletter-subscriptions",
        function (form) {
            return {
                first_name: form.querySelector("[name=firstname]").value.trim(),
                email: form.querySelector("[name=email]").value.trim()
            };
        },
        "newsletter-success",
        "newsletter-warning",
        "The newsletter service is unavailable. Please try again."
    );

    document.querySelectorAll("[data-enquiry-form]").forEach(function (form) {
        var id = form.id.replace(/-form$/, "");
        connectPublicForm(form.id, "/contact-submissions", function (current) {
            var parts = [];
            current.querySelectorAll("[data-message-field]").forEach(function (field) {
                if (field.value.trim()) {
                    parts.push(field.getAttribute("data-message-field") + ": " + field.value.trim());
                }
            });
            parts.push(current.querySelector("[name=message]").value.trim());
            return {
                name: current.querySelector("[name=name]").value.trim(),
                email: current.querySelector("[name=email]").value.trim(),
                topic: current.getAttribute("data-topic"),
                message: parts.join("\n\n")
            };
        }, id + "-success", id + "-warning", "We could not reach the team. Please try again or contact us on WhatsApp.");
    });

    // Only select existing choices: query parameters never become markup or new topics.
    var pageParams = new URLSearchParams(location.search);
    [["#join-tier", "tier"], ["#contact-topic", "topic"]].forEach(function (entry) {
        var select = document.querySelector(entry[0]);
        var value = pageParams.get(entry[1]);
        if (select && value && Array.from(select.options).some(function (option) { return option.value === value; })) {
            select.value = value;
        }
    });

})();
