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
            return body.detail || fallback;
        } catch (error) {
            return fallback;
        }
    }

    document.querySelectorAll("[data-year]").forEach(function (element) {
        element.textContent = new Date().getFullYear();
    });

    var main = document.querySelector("main");
    if (main && !document.querySelector("[data-go-back]")) {
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
        main.insertBefore(backButton, main.firstChild);
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
        }
    });

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

    var loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async function (event) {
            event.preventDefault();
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
            }
        });
    }

    var createAccountForm = document.getElementById("create-account-form");
    if (createAccountForm) {
        createAccountForm.addEventListener("submit", async function (event) {
            event.preventDefault();
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

                error.hidden = true;
                createAccountForm.hidden = true;
                document.getElementById("create-account-success").hidden = false;
            } catch (requestError) {
                error.textContent = "The account service is unavailable. Please try again.";
                error.hidden = false;
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
            }
        });
    }
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!resetPasswordForm.reportValidity()) {
                return;
            }
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

    var dashboard = document.querySelector("[data-member-dashboard]");
    if (dashboard) {
        apiRequest("/member/dashboard")
            .then(function (response) {
                if (!response.ok) {
                    location.href = portalPath("member-login.html");
                    return null;
                }
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
            .catch(function () {
                location.href = portalPath("member-login.html");
            });
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
                cell.textContent = row[field] || "—";
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
            apiRequest("/admin/newsletter-subscribers")
        ]).then(async function (responses) {
            var unauthorized = responses.some(function (response) {
                return response.status === 401;
            });
            if (unauthorized) {
                location.href = portalPath("member-dashboard.html");
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
            fillAdminTable("admin-applications", data[1], ["name", "email", "tier", "country", "created_at"]);
            fillAdminTable("admin-contacts", data[2], ["name", "email", "topic", "message", "created_at"]);
            fillAdminTable("admin-subscribers", data[3], ["first_name", "email", "subscribed_at"]);
            adminDashboard.hidden = false;
        }).catch(function () {
            location.href = portalPath("member-dashboard.html");
        });
    }

    var grantAdminForm = document.getElementById("grant-admin-form");
    if (grantAdminForm) {
        grantAdminForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!grantAdminForm.reportValidity()) {
                return;
            }

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
            }
        });
    }

    document.querySelectorAll("[data-logout]").forEach(function (button) {
        button.addEventListener("click", async function () {
            try {
                await apiRequest("/auth/logout", { method: "POST" });
            } finally {
                location.href = portalPath(button.getAttribute("data-logout") || "member-login.html");
            }
        });
    });

    function connectPublicForm(formId, endpoint, getPayload, successId, unavailableMessage, onSuccess) {
        var form = document.getElementById(formId);
        if (!form) {
            return;
        }

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!form.reportValidity()) {
                return;
            }

            var error = form.querySelector(".form-error");
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

                if (onSuccess) {
                    await onSuccess(form);
                    return;
                }

                if (error) {
                    error.hidden = true;
                }
                if (success) {
                    form.hidden = true;
                    success.hidden = false;
                    success.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            } catch (requestError) {
                if (error) {
                    error.textContent = requestError.message || unavailableMessage;
                    error.hidden = false;
                }
            }
        });
    }

    connectPublicForm(
        "join-form",
        "/membership-applications",
        function (form) {
            return {
                tier: form.querySelector("[name=tier]:checked").value,
                first_name: form.querySelector("[name=firstname]").value.trim(),
                last_name: form.querySelector("[name=lastname]").value.trim(),
                email: form.querySelector("[name=email]").value.trim(),
                country: form.querySelector("[name=country]").value,
                role: form.querySelector("[name=role]").value,
                organization: form.querySelector("[name=organization]").value.trim(),
                marketing_consent: document.getElementById("join-consent").checked
            };
        },
        "join-success",
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
        "The newsletter service is unavailable. Please try again."
    );

    var donateForm = document.getElementById("donate-form");
    if (donateForm) {
        var donateError = donateForm.querySelector(".form-error");
        donateError.textContent = "Online donations are temporarily unavailable while we finalise the organization payment account.";
        donateError.hidden = false;
        donateForm.querySelector("button[type=submit]").disabled = true;
        donateForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (!donateForm.reportValidity()) {
                return;
            }
            var error = donateForm.querySelector(".form-error");
            var customAmount = Number(donateForm.querySelector("[name=custom_amount]").value);
            var selectedAmount = donateForm.querySelector("[name=amount]:checked").value;
            var amount = customAmount || Number(selectedAmount);
            if (!amount || selectedAmount === "other" && !customAmount) {
                error.textContent = "Choose or enter a donation amount.";
                error.hidden = false;
                return;
            }
            try {
                var response = await apiRequest("/payments/initialize", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        payment_type: "donation",
                        email: donateForm.querySelector("[name=email]").value.trim(),
                        donation_amount: amount
                    })
                });
                if (!response.ok) {
                    error.textContent = await errorMessage(response, "Unable to start the secure payment checkout.");
                    error.hidden = false;
                    return;
                }
                location.href = (await response.json()).checkout_url;
            } catch (requestError) {
                error.textContent = requestError.message || "The payment service is unavailable. Please try again.";
                error.hidden = false;
            }
        });
    }
})();
