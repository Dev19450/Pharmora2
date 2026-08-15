/**
 * Pharmora Master Application Client Logic with POS Billing, Auto Stock Deduction & Anytime Stock Replenishment
 */

let chartInstances = {};
let currentDashboardData = null;
let currentTrendMode = 'monthly';
let currentStockMeasure = 'units';
let currentUser = null;
let posCart = [];
let invoiceHistoryData = [];

document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initNavigation();
    initChatbot();
    initUploadModal();
    initAssistantWizard();
    initTrendToggles();
    initStockMeasureToggles();
    initTableauControls();
    initPOSBilling();
    initInvoiceHistory();
    initAddStockModule();
    checkSession();
});

/* ==============================================================================
   Production-Ready Authentication, Confirmation Step & Dual 6-Box OTP System
   ============================================================================== */

let resendEmailTimerInterval = null;
let resendPhoneTimerInterval = null;
let otpExpiryTimerInterval = null;
let pendingRegistrationData = null;
let verificationState = { emailVerified: false, phoneVerified: false };

function initAuth() {
    const authOverlay = document.getElementById('auth-modal-overlay');
    const tabLogin = document.getElementById('tab-btn-login');
    const tabSignup = document.getElementById('tab-btn-signup');
    const formLogin = document.getElementById('form-login');
    const formSignup = document.getElementById('form-signup');
    const btnLogout = document.getElementById('btn-logout');

    // Multi-Step Containers
    const step1 = document.getElementById('signup-step1');
    const stepConfirm = document.getElementById('signup-step-confirm');
    const stepOtp = document.getElementById('otp-step-container');
    const stepSuccess = document.getElementById('signup-step-success');

    // Step 1 Controls
    const btnGotoConfirm = document.getElementById('btn-goto-confirm');
    const signupErrorAlert = document.getElementById('signup-error-alert');

    // Step 1.5 Confirmation Controls
    const chkConfirmEmail = document.getElementById('chk-confirm-email');
    const chkConfirmPhone = document.getElementById('chk-confirm-phone');
    const chkConfirmAccess = document.getElementById('chk-confirm-access');
    const btnBackToStep1 = document.getElementById('btn-back-to-step1');
    const btnRequestDualOtp = document.getElementById('btn-request-dual-otp');
    const confirmErrorAlert = document.getElementById('confirm-error-alert');

    // Step 2 OTP Verification Controls
    const badgeEmailDelivery = document.getElementById('badge-email-delivery');
    const badgePhoneDelivery = document.getElementById('badge-phone-delivery');
    const emailBoxes = document.querySelectorAll('.otp-box-email');
    const phoneBoxes = document.querySelectorAll('.otp-box-phone');
    const btnResendEmail = document.getElementById('btn-resend-email-otp');
    const btnResendPhone = document.getElementById('btn-resend-phone-otp');
    const resendEmailText = document.getElementById('resend-email-text');
    const resendPhoneText = document.getElementById('resend-phone-text');
    const alertEmailOtp = document.getElementById('alert-email-otp');
    const alertPhoneOtp = document.getElementById('alert-phone-otp');
    const statusEmailTag = document.getElementById('status-email-tag');
    const statusPhoneTag = document.getElementById('status-phone-tag');
    const btnVerifyDualOtp = document.getElementById('btn-verify-dual-otp');
    const otpGlobalError = document.getElementById('otp-global-error-alert');
    const btnBackSignup = document.getElementById('btn-back-signup');
    const otpExpiryCountdown = document.getElementById('otp-expiry-countdown');

    // Step 3 Success Controls
    const btnContinueDashboard = document.getElementById('btn-continue-dashboard');

    const loginErrorAlert = document.getElementById('login-error-alert');

    // 1. Tab Switching (Login <-> Create Account)
    if (tabLogin && tabSignup) {
        tabLogin.addEventListener('click', () => {
            tabLogin.classList.add('active');
            tabSignup.classList.remove('active');
            formLogin.style.display = 'block';
            formSignup.style.display = 'none';
            formSignup.reset();
            resetSignupWizard();
            if (loginErrorAlert) loginErrorAlert.style.display = 'none';
            if (signupErrorAlert) signupErrorAlert.style.display = 'none';
        });

        tabSignup.addEventListener('click', () => {
            tabSignup.classList.add('active');
            tabLogin.classList.remove('active');
            formSignup.style.display = 'block';
            formLogin.style.display = 'none';
            formLogin.reset();
            resetSignupWizard();
            if (loginErrorAlert) loginErrorAlert.style.display = 'none';
            if (signupErrorAlert) signupErrorAlert.style.display = 'none';
        });

        // Check URL parameter for initial auth mode
        const urlParams = new URLSearchParams(window.location.search);
        const authParam = urlParams.get('auth');
        if (authParam === 'register' || authParam === 'signup') {
            tabSignup.click();
        } else if (authParam === 'login') {
            tabLogin.click();
        }
    }

    // 2. Demo Quick Sign-in Buttons
    document.querySelectorAll('.demo-login-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (tabLogin) tabLogin.click();
            document.getElementById('login-email').value = btn.getAttribute('data-email');
            document.getElementById('login-password').value = btn.getAttribute('data-pass');
            formLogin.dispatchEvent(new Event('submit'));
        });
    });

    // 3. Login Submission Handler
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (loginErrorAlert) loginErrorAlert.style.display = 'none';

            const identifier = document.getElementById('login-email').value.trim();
            const password = document.getElementById('login-password').value;

            if (!identifier || !password) {
                showError(loginErrorAlert, "Please enter your Email / Mobile Phone and Password.");
                return;
            }

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identifier, password })
                });
                const data = await res.json();
                
                if (!data.success || data.error) {
                    showError(loginErrorAlert, data.error || "Authentication failed.");
                    return;
                }

                currentUser = data.user;
                applyUserRole(currentUser);
                if (authOverlay) authOverlay.style.display = 'none';
                loadDashboardData();
                fetchInvoiceHistory();
                fetchStockLogs();

                // If URL specified a tab, activate it
                const urlParams = new URLSearchParams(window.location.search);
                const targetTab = urlParams.get('tab');
                if (targetTab) {
                    const navItem = document.querySelector(`.nav-item[data-tab="${targetTab}"]`);
                    if (navItem) navItem.click();
                }
            } catch (err) {
                showError(loginErrorAlert, "Server connection failed. Please check network.");
            }
        });
    }

    // 4. STEP 1: Proceed to Contact Confirmation Step
    if (btnGotoConfirm) {
        btnGotoConfirm.addEventListener('click', () => {
            if (signupErrorAlert) signupErrorAlert.style.display = 'none';

            const name = document.getElementById('signup-name').value.trim();
            const email = document.getElementById('signup-email').value.trim();
            const phone = document.getElementById('signup-phone').value.trim();
            const password = document.getElementById('signup-password').value;
            const store_name = document.getElementById('signup-store').value.trim();
            const role = document.getElementById('signup-role').value;

            if (!name || !email || !phone || !password || !store_name) {
                showError(signupErrorAlert, "Please fill in all required registration fields.");
                return;
            }

            const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            if (!emailRegex.test(email)) {
                showError(signupErrorAlert, "Please enter a valid Email Address (e.g. sarah@pharmacy.com).");
                return;
            }

            const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
            if (cleanPhone.length < 10) {
                showError(signupErrorAlert, "Please enter a valid 10-15 digit Mobile Phone Number.");
                return;
            }

            pendingRegistrationData = { name, email, phone: cleanPhone, password, store_name, role };

            // Update confirmation details
            document.getElementById('confirm-display-email').innerText = email;
            document.getElementById('confirm-display-phone').innerText = cleanPhone.startsWith('+') ? cleanPhone : `+91 ${cleanPhone}`;

            chkConfirmEmail.checked = false;
            chkConfirmPhone.checked = false;
            chkConfirmAccess.checked = false;
            if (confirmErrorAlert) confirmErrorAlert.style.display = 'none';

            step1.style.display = 'none';
            stepConfirm.style.display = 'block';
        });
    }

    // Return to Step 1
    if (btnBackToStep1) {
        btnBackToStep1.addEventListener('click', () => {
            chkConfirmEmail.checked = false;
            chkConfirmPhone.checked = false;
            chkConfirmAccess.checked = false;
            if (confirmErrorAlert) confirmErrorAlert.style.display = 'none';
            stepConfirm.style.display = 'none';
            step1.style.display = 'block';
        });
    }

    // 5. STEP 1.5: Send Dual Verification Codes
    if (btnRequestDualOtp) {
        btnRequestDualOtp.addEventListener('click', async () => {
            if (confirmErrorAlert) confirmErrorAlert.style.display = 'none';

            if (!chkConfirmEmail.checked) {
                showError(confirmErrorAlert, "Please confirm that the Email Address belongs to you.");
                return;
            }
            if (!chkConfirmPhone.checked) {
                showError(confirmErrorAlert, "Please confirm that the Mobile Phone Number belongs to you.");
                return;
            }
            if (!chkConfirmAccess.checked) {
                showError(confirmErrorAlert, "Please confirm that you have active access to both channels.");
                return;
            }

            btnRequestDualOtp.disabled = true;
            btnRequestDualOtp.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Dispathing Codes...`;

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ...pendingRegistrationData, purpose: 'registration' })
                });
                const data = await res.json();

                btnRequestDualOtp.disabled = false;
                btnRequestDualOtp.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Send Verification Codes`;

                if (!data.success || data.error) {
                    showError(confirmErrorAlert, data.error || "Failed to initiate verification.");
                    return;
                }

                // Transition to Step 2 OTP Screen
                stepConfirm.style.display = 'none';
                stepOtp.style.display = 'block';

                document.getElementById('otp-display-email').innerText = data.target_email || pendingRegistrationData.email;
                document.getElementById('otp-display-phone').innerText = data.target_phone || pendingRegistrationData.phone;

                // Update Real Provider Delivery Badges
                updateDeliveryBadge(badgeEmailDelivery, data.email);
                updateDeliveryBadge(badgePhoneDelivery, data.mobile);

                // Reset verification state
                verificationState = { emailVerified: false, phoneVerified: false };
                updateChannelStatusUI();

                clearBoxes(emailBoxes);
                clearBoxes(phoneBoxes);
                if (emailBoxes[0]) emailBoxes[0].focus();

                startResendTimer('email', data.cooldown_seconds || 60);
                startResendTimer('phone', data.cooldown_seconds || 60);
                startExpiryTimer(data.expires_in_minutes || 5);

            } catch (err) {
                btnRequestDualOtp.disabled = false;
                btnRequestDualOtp.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Send Verification Codes`;
                showError(confirmErrorAlert, "Failed to connect to verification server.");
            }
        });
    }

    function updateDeliveryBadge(elem, channelData) {
        if (!elem || !channelData) return;
        if (channelData.providerAccepted) {
            elem.className = "badge badge-success";
            elem.innerHTML = `<i class="fa-solid fa-circle-check"></i> Code sent (${channelData.provider})`;
        } else {
            elem.className = "badge badge-danger";
            elem.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Provider failed (${channelData.provider})`;
        }
    }

    // 6. Setup 6-Box Numeric Input Navigation for a given box group
    function setupBoxGroup(boxes, onAllFilled, channelType) {
        boxes.forEach((box, index) => {
            box.addEventListener('input', (e) => {
                const val = box.value.replace(/[^0-9]/g, '');
                box.value = val.slice(0, 1);

                if (box.value) {
                    box.classList.add('filled');
                    if (index < boxes.length - 1) {
                        boxes[index + 1].focus();
                    } else {
                        const code = getBoxCode(boxes);
                        if (code.length === 6 && onAllFilled) {
                            onAllFilled(code);
                        }
                    }
                } else {
                    box.classList.remove('filled');
                }
            });

            box.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace') {
                    if (!box.value && index > 0) {
                        boxes[index - 1].focus();
                        boxes[index - 1].value = '';
                        boxes[index - 1].classList.remove('filled');
                    } else {
                        box.value = '';
                        box.classList.remove('filled');
                    }
                } else if (e.key === 'ArrowLeft' && index > 0) {
                    boxes[index - 1].focus();
                } else if (e.key === 'ArrowRight' && index < boxes.length - 1) {
                    boxes[index + 1].focus();
                }
            });

            box.addEventListener('paste', (e) => {
                e.preventDefault();
                const pasteData = (e.clipboardData || window.clipboardData).getData('text').trim().replace(/[^0-9]/g, '');
                if (!pasteData) return;

                for (let i = 0; i < boxes.length; i++) {
                    if (i < pasteData.length) {
                        boxes[i].value = pasteData[i];
                        boxes[i].classList.add('filled');
                    } else {
                        boxes[i].value = '';
                        boxes[i].classList.remove('filled');
                    }
                }

                const nextIndex = Math.min(pasteData.length, 5);
                boxes[nextIndex].focus();

                const fullCode = getBoxCode(boxes);
                if (fullCode.length === 6 && onAllFilled) {
                    onAllFilled(fullCode);
                }
            });
        });
    }

    function getBoxCode(boxes) {
        let code = '';
        boxes.forEach(b => { code += b.value.trim(); });
        return code;
    }

    function clearBoxes(boxes) {
        boxes.forEach(b => {
            b.value = '';
            b.classList.remove('filled');
            b.disabled = false;
        });
    }

    function lockBoxes(boxes) {
        boxes.forEach(b => {
            b.disabled = true;
        });
    }

    // Auto-verify when 6 digits of Email OTP are typed
    setupBoxGroup(emailBoxes, async (code) => {
        if (verificationState.emailVerified) return;
        if (alertEmailOtp) alertEmailOtp.innerText = "Verifying email code...";

        try {
            const res = await fetch('/api/auth/verify-email-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: pendingRegistrationData.email, otp_code: code })
            });
            const data = await res.json();

            if (data.success && data.email_verified) {
                verificationState.emailVerified = true;
                if (alertEmailOtp) alertEmailOtp.innerText = "";
                lockBoxes(emailBoxes);
                updateChannelStatusUI();
                if (!verificationState.phoneVerified && phoneBoxes[0]) {
                    phoneBoxes[0].focus();
                }
                checkIfFullyVerified();
            } else {
                if (alertEmailOtp) alertEmailOtp.innerText = data.error || "Incorrect email code.";
            }
        } catch (err) {
            if (alertEmailOtp) alertEmailOtp.innerText = "Verification failed. Check network.";
        }
    }, 'email');

    // Auto-verify when 6 digits of Mobile OTP are typed
    setupBoxGroup(phoneBoxes, async (code) => {
        if (verificationState.phoneVerified) return;
        if (alertPhoneOtp) alertPhoneOtp.innerText = "Verifying mobile code...";

        try {
            const res = await fetch('/api/auth/verify-phone-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: pendingRegistrationData.phone, otp_code: code })
            });
            const data = await res.json();

            if (data.success && data.phone_verified) {
                verificationState.phoneVerified = true;
                if (alertPhoneOtp) alertPhoneOtp.innerText = "";
                lockBoxes(phoneBoxes);
                updateChannelStatusUI();
                checkIfFullyVerified();
            } else {
                if (alertPhoneOtp) alertPhoneOtp.innerText = data.error || "Incorrect mobile code.";
            }
        } catch (err) {
            if (alertPhoneOtp) alertPhoneOtp.innerText = "Verification failed. Check network.";
        }
    }, 'phone');

    function updateChannelStatusUI() {
        if (statusEmailTag) {
            if (verificationState.emailVerified) {
                statusEmailTag.style.color = "var(--palette-lime)";
                statusEmailTag.innerHTML = `<i class="fa-solid fa-circle-check"></i> Verified`;
            } else {
                statusEmailTag.style.color = "var(--text-muted)";
                statusEmailTag.innerText = "Pending";
            }
        }

        if (statusPhoneTag) {
            if (verificationState.phoneVerified) {
                statusPhoneTag.style.color = "var(--palette-lime)";
                statusPhoneTag.innerHTML = `<i class="fa-solid fa-circle-check"></i> Verified`;
            } else {
                statusPhoneTag.style.color = "var(--text-muted)";
                statusPhoneTag.innerText = "Pending";
            }
        }
    }

    // 7. Verify Both / Primary Button
    if (btnVerifyDualOtp) {
        btnVerifyDualOtp.addEventListener('click', async () => {
            if (otpGlobalError) otpGlobalError.style.display = 'none';

            const emailCode = getBoxCode(emailBoxes);
            const phoneCode = getBoxCode(phoneBoxes);

            if (!verificationState.emailVerified && emailCode.length !== 6) {
                showError(otpGlobalError, "Please enter all 6 digits of the Email verification code.");
                return;
            }

            if (!verificationState.phoneVerified && phoneCode.length !== 6) {
                showError(otpGlobalError, "Please enter all 6 digits of the Mobile verification code.");
                return;
            }

            btnVerifyDualOtp.disabled = true;
            btnVerifyDualOtp.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Verifying Account...`;

            try {
                const res = await fetch('/api/auth/verify-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...pendingRegistrationData,
                        email_otp: emailCode,
                        phone_otp: phoneCode,
                        purpose: 'registration'
                    })
                });
                const data = await res.json();

                btnVerifyDualOtp.disabled = false;
                btnVerifyDualOtp.innerHTML = `<i class="fa-solid fa-circle-check"></i> Verify Email & Mobile`;

                if (!data.success || data.error) {
                    showError(otpGlobalError, data.error || "Verification failed.");
                    return;
                }

                if (data.email_verified) {
                    verificationState.emailVerified = true;
                    lockBoxes(emailBoxes);
                }
                if (data.phone_verified) {
                    verificationState.phoneVerified = true;
                    lockBoxes(phoneBoxes);
                }
                updateChannelStatusUI();

                if (data.fully_verified && data.user) {
                    currentUser = data.user;
                    applyUserRole(currentUser);
                    showSuccessScreen();
                } else {
                    showError(otpGlobalError, data.message || "Please verify the remaining channel.");
                }
            } catch (err) {
                btnVerifyDualOtp.disabled = false;
                btnVerifyDualOtp.innerHTML = `<i class="fa-solid fa-circle-check"></i> Verify Email & Mobile`;
                showError(otpGlobalError, "Verification failed. Check network connection.");
            }
        });
    }

    async function checkIfFullyVerified() {
        if (verificationState.emailVerified && verificationState.phoneVerified) {
            // Trigger completion
            if (btnVerifyDualOtp) btnVerifyDualOtp.click();
        }
    }

    function showSuccessScreen() {
        clearInterval(resendEmailTimerInterval);
        clearInterval(resendPhoneTimerInterval);
        clearInterval(otpExpiryTimerInterval);

        document.getElementById('success-email-val').innerText = pendingRegistrationData.email;
        document.getElementById('success-phone-val').innerText = pendingRegistrationData.phone;

        stepOtp.style.display = 'none';
        stepSuccess.style.display = 'block';
    }

    // Continue to Dashboard
    if (btnContinueDashboard) {
        btnContinueDashboard.addEventListener('click', () => {
            if (authOverlay) authOverlay.style.display = 'none';
            loadDashboardData();
            fetchInvoiceHistory();
            fetchStockLogs();
        });
    }

    // 8. Resend Email Code Handler
    if (btnResendEmail) {
        btnResendEmail.addEventListener('click', async () => {
            if (!pendingRegistrationData || verificationState.emailVerified) return;
            btnResendEmail.disabled = true;
            resendEmailText.innerText = "Sending...";

            try {
                const res = await fetch('/api/auth/resend-channel-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: pendingRegistrationData.email, channel: 'email' })
                });
                const data = await res.json();

                if (!data.success || data.error) {
                    if (alertEmailOtp) alertEmailOtp.innerText = data.error || "Unable to resend email code.";
                    btnResendEmail.disabled = false;
                    resendEmailText.innerText = "Resend Email Code";
                    return;
                }

                clearBoxes(emailBoxes);
                if (emailBoxes[0]) emailBoxes[0].focus();
                startResendTimer('email', data.cooldown_seconds || 60);
                if (data.delivery && data.delivery.email) {
                    updateDeliveryBadge(badgeEmailDelivery, data.delivery.email);
                }
                if (alertEmailOtp) alertEmailOtp.innerText = "";
            } catch (err) {
                btnResendEmail.disabled = false;
                resendEmailText.innerText = "Resend Email Code";
                if (alertEmailOtp) alertEmailOtp.innerText = "Failed to resend.";
            }
        });
    }

    // 9. Resend Mobile Code Handler
    if (btnResendPhone) {
        btnResendPhone.addEventListener('click', async () => {
            if (!pendingRegistrationData || verificationState.phoneVerified) return;
            btnResendPhone.disabled = true;
            resendPhoneText.innerText = "Sending...";

            try {
                const res = await fetch('/api/auth/resend-channel-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone: pendingRegistrationData.phone, channel: 'phone' })
                });
                const data = await res.json();

                if (!data.success || data.error) {
                    if (alertPhoneOtp) alertPhoneOtp.innerText = data.error || "Unable to resend mobile code.";
                    btnResendPhone.disabled = false;
                    resendPhoneText.innerText = "Resend Mobile Code";
                    return;
                }

                clearBoxes(phoneBoxes);
                if (phoneBoxes[0]) phoneBoxes[0].focus();
                startResendTimer('phone', data.cooldown_seconds || 60);
                if (data.delivery && data.delivery.mobile) {
                    updateDeliveryBadge(badgePhoneDelivery, data.delivery.mobile);
                }
                if (alertPhoneOtp) alertPhoneOtp.innerText = "";
            } catch (err) {
                btnResendPhone.disabled = false;
                resendPhoneText.innerText = "Resend Mobile Code";
                if (alertPhoneOtp) alertPhoneOtp.innerText = "Failed to resend.";
            }
        });
    }

    // 10. Change Email / Mobile -> Return to Step 1
    if (btnBackSignup) {
        btnBackSignup.addEventListener('click', () => {
            clearInterval(resendEmailTimerInterval);
            clearInterval(resendPhoneTimerInterval);
            clearInterval(otpExpiryTimerInterval);
            stepOtp.style.display = 'none';
            step1.style.display = 'block';
        });
    }

    // 11. Sign Out Button
    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            currentUser = null;
            clearInterval(resendEmailTimerInterval);
            clearInterval(resendPhoneTimerInterval);
            clearInterval(otpExpiryTimerInterval);
            window.location.href = '/';
        });
    }

    function resetSignupWizard() {
        clearInterval(resendEmailTimerInterval);
        clearInterval(resendPhoneTimerInterval);
        clearInterval(otpExpiryTimerInterval);
        step1.style.display = 'block';
        stepConfirm.style.display = 'none';
        stepOtp.style.display = 'none';
        stepSuccess.style.display = 'none';
        if (signupErrorAlert) signupErrorAlert.style.display = 'none';
    }

    function showError(elem, msg) {
        if (!elem) return;
        elem.style.display = 'block';
        elem.style.color = 'var(--accent-rose)';
        elem.innerText = msg;
    }

    function startResendTimer(channel, seconds) {
        let remaining = seconds;
        if (channel === 'email') {
            clearInterval(resendEmailTimerInterval);
            btnResendEmail.disabled = true;
            resendEmailText.innerText = `Resend in ${remaining}s`;

            resendEmailTimerInterval = setInterval(() => {
                remaining--;
                if (remaining <= 0) {
                    clearInterval(resendEmailTimerInterval);
                    btnResendEmail.disabled = false;
                    resendEmailText.innerText = "Resend Email Code";
                } else {
                    resendEmailText.innerText = `Resend in ${remaining}s`;
                }
            }, 1000);
        } else {
            clearInterval(resendPhoneTimerInterval);
            btnResendPhone.disabled = true;
            resendPhoneText.innerText = `Resend in ${remaining}s`;

            resendPhoneTimerInterval = setInterval(() => {
                remaining--;
                if (remaining <= 0) {
                    clearInterval(resendPhoneTimerInterval);
                    btnResendPhone.disabled = false;
                    resendPhoneText.innerText = "Resend Mobile Code";
                } else {
                    resendPhoneText.innerText = `Resend in ${remaining}s`;
                }
            }, 1000);
        }
    }

    function startExpiryTimer(minutes) {
        clearInterval(otpExpiryTimerInterval);
        let totalSeconds = minutes * 60;

        function updateDisplay() {
            const m = Math.floor(totalSeconds / 60);
            const s = totalSeconds % 60;
            if (otpExpiryCountdown) {
                otpExpiryCountdown.innerText = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
            }
        }

        updateDisplay();
        otpExpiryTimerInterval = setInterval(() => {
            totalSeconds--;
            if (totalSeconds <= 0) {
                clearInterval(otpExpiryTimerInterval);
                if (otpExpiryCountdown) otpExpiryCountdown.innerText = "Expired (00:00)";
                if (otpGlobalError) {
                    showError(otpGlobalError, "Verification codes have expired. Please request new codes.");
                }
            } else {
                updateDisplay();
            }
        }, 1000);
    }
}

async function checkSession() {
    const authOverlay = document.getElementById('auth-modal-overlay');
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        if (data.user) {
            currentUser = data.user;
            applyUserRole(currentUser);
            if (authOverlay) authOverlay.style.display = 'none';
            loadDashboardData();
            fetchInvoiceHistory();
            fetchStockLogs();
        } else {
            // Unauthenticated: Keep Auth Modal Overlay visible and block dashboard
            if (authOverlay) authOverlay.style.display = 'flex';
        }
    } catch (err) {
        console.log("No active session detected.");
        if (authOverlay) authOverlay.style.display = 'flex';
    }
}

function applyUserRole(user) {
    if (!user) return;

    document.getElementById('user-display-name').innerText = user.name;
    document.getElementById('user-display-store').innerText = user.store_name || "Pharmora Store";
    const badge = document.getElementById('user-role-badge');
    badge.innerText = user.role.toUpperCase();

    const uploadNav = document.querySelector('[data-tab="tab-upload"]');
    const reportsNav = document.querySelector('[data-tab="tab-reports"]');
    const exportBtn = document.getElementById('header-export-btn');
    const uploadBtn = document.getElementById('header-upload-btn');
    const kpiProfit = document.getElementById('kpi-card-profit');
    const kpiMargin = document.getElementById('kpi-card-margin');

    if (user.role === 'staff') {
        if (uploadNav) uploadNav.style.display = 'none';
        if (reportsNav) reportsNav.style.display = 'none';
        if (exportBtn) exportBtn.style.display = 'none';
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (kpiProfit) kpiProfit.style.display = 'none';
        if (kpiMargin) kpiMargin.style.display = 'none';
        badge.className = "badge badge-warning";
    } else if (user.role === 'manager') {
        if (uploadNav) uploadNav.style.display = 'flex';
        if (reportsNav) reportsNav.style.display = 'flex';
        if (exportBtn) exportBtn.style.display = 'inline-flex';
        if (uploadBtn) uploadBtn.style.display = 'inline-flex';
        if (kpiProfit) kpiProfit.style.display = 'block';
        if (kpiMargin) kpiMargin.style.display = 'block';
        badge.className = "badge badge-info";
    } else {
        if (uploadNav) uploadNav.style.display = 'flex';
        if (reportsNav) reportsNav.style.display = 'flex';
        if (exportBtn) exportBtn.style.display = 'inline-flex';
        if (uploadBtn) uploadBtn.style.display = 'inline-flex';
        if (kpiProfit) kpiProfit.style.display = 'block';
        if (kpiMargin) kpiMargin.style.display = 'block';
        badge.className = "badge badge-success";
    }
}

/* Navigation & Responsive Drawer */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const sidebar = document.getElementById('app-sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const sidebarCloseBtn = document.getElementById('sidebar-close-btn');

    // Mobile Drawer Open / Close Functions
    const openMobileSidebar = () => {
        if (sidebar) sidebar.classList.add('open');
        if (sidebarOverlay) sidebarOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // prevent background scrolling while drawer is open
    };

    const closeMobileSidebar = () => {
        if (sidebar) sidebar.classList.remove('open');
        if (sidebarOverlay) sidebarOverlay.classList.remove('active');
        document.body.style.overflow = '';
    };

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', openMobileSidebar);
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', closeMobileSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeMobileSidebar);
    }

    // Navigation Item Click Handling
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            if (!targetTab) return;

            navItems.forEach(i => i.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            item.classList.add('active');
            const targetPane = document.getElementById(targetTab);
            if (targetPane) {
                targetPane.classList.add('active');
                const titleText = item.querySelector('span') ? item.querySelector('span').innerText.trim() : item.innerText.trim();
                const pageTitleElem = document.getElementById('page-title-text');
                if (pageTitleElem) pageTitleElem.innerText = titleText;

                if (targetTab === 'tab-invoice-history') {
                    fetchInvoiceHistory();
                } else if (targetTab === 'tab-add-stock') {
                    fetchStockLogs();
                } else if (targetTab === 'tab-dashboard') {
                    // Trigger chart redraw on tab switch to ensure proper rendering on responsive container sizes
                    setTimeout(() => {
                        Object.values(chartInstances).forEach(chart => {
                            if (chart && typeof chart.resize === 'function') chart.resize();
                        });
                    }, 50);
                }
            }

            // Automatically close drawer on mobile upon selecting a menu item
            if (window.innerWidth <= 767) {
                closeMobileSidebar();
            }
        });
    });

    // Check URL parameter for initial tab
    const urlParams = new URLSearchParams(window.location.search);
    const initialTab = urlParams.get('tab');
    if (initialTab) {
        const targetNavItem = document.querySelector(`.nav-item[data-tab="${initialTab}"]`);
        if (targetNavItem) {
            targetNavItem.click();
        }
    }

    // Window Resize Handler for responsive chart recalculation
    window.addEventListener('resize', () => {
        if (window.innerWidth > 767) {
            closeMobileSidebar();
        }
        Object.values(chartInstances).forEach(chart => {
            if (chart && typeof chart.resize === 'function') {
                chart.resize();
            }
        });
    });
}

/* Add / Replenish Medicine Stock Engine */
function initAddStockModule() {
    const radioExisting = document.getElementById('radio-mode-existing');
    const radioNew = document.getElementById('radio-mode-new');
    const formExisting = document.getElementById('form-replenish-existing');
    const formNew = document.getElementById('form-create-new-med');

    const medSelect = document.getElementById('stock-add-med-select');
    const qtyInput = document.getElementById('stock-add-qty-input');

    if (radioExisting && radioNew) {
        radioExisting.addEventListener('change', () => {
            if (formNew) formNew.reset();
            formExisting.style.display = 'block';
            formNew.style.display = 'none';
            updateStockAddPreview();
        });
        radioNew.addEventListener('change', () => {
            if (formExisting) {
                formExisting.reset();
                if (medSelect) medSelect.value = '';
            }
            formExisting.style.display = 'none';
            formNew.style.display = 'block';
            updateStockAddPreview();
        });
    }

    if (medSelect) {
        medSelect.addEventListener('change', () => {
            if (!medSelect.value) {
                const batchInput = document.getElementById('stock-add-batch-input');
                if (batchInput) batchInput.value = '';
                if (qtyInput) qtyInput.value = '100';
            }
            updateStockAddPreview();
        });
    }
    if (qtyInput) qtyInput.addEventListener('input', updateStockAddPreview);

    // Form 1: Replenish Existing
    if (formExisting) {
        formExisting.addEventListener('submit', async (e) => {
            e.preventDefault();
            const medName = medSelect.value;
            const addedQty = intVal(qtyInput.value) || 0;
            const batch = document.getElementById('stock-add-batch-input')?.value || '';

            if (!medName) {
                alert("Please select a medicine.");
                return;
            }

            try {
                const res = await fetch('/api/stock/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'existing', medicine: medName, added_qty: addedQty, batch: batch })
                });
                const data = await res.json();
                if (data.error) {
                    alert(data.error);
                    return;
                }

                alert(data.message);
                formExisting.reset();
                if (medSelect) medSelect.value = '';
                updateStockAddPreview();
                loadDashboardData();
                fetchStockLogs();
            } catch (err) {
                alert("Failed to replenish stock.");
            }
        });
    }

    // Form 2: Create New Medicine
    if (formNew) {
        formNew.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                mode: 'new',
                medicine: document.getElementById('new-med-name').value,
                category: document.getElementById('new-med-category').value,
                company: document.getElementById('new-med-company').value,
                batch: document.getElementById('new-med-batch').value,
                added_qty: intVal(document.getElementById('new-med-stock').value) || 100,
                buy_price: floatVal(document.getElementById('new-med-buy-price').value) || 50.0,
                sell_price: floatVal(document.getElementById('new-med-sell-price').value) || 80.0,
                expiry: document.getElementById('new-med-expiry').value,
                supplier: document.getElementById('new-med-supplier').value
            };

            try {
                const res = await fetch('/api/stock/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.error) {
                    alert(data.error);
                    return;
                }

                alert(data.message);
                formNew.reset();
                loadDashboardData();
                fetchStockLogs();
            } catch (err) {
                alert("Failed to create new medicine.");
            }
        });
    }
}

function updateStockAddPreview() {
    const medSelect = document.getElementById('stock-add-med-select');
    const qtyInput = document.getElementById('stock-add-qty-input');
    const prevVal = document.getElementById('stock-add-prev-val');
    const qtyVal = document.getElementById('stock-add-qty-val');
    const newVal = document.getElementById('stock-add-new-val');

    const medName = medSelect?.value;
    const added = intVal(qtyInput?.value) || 0;

    if (!medName) {
        prevVal.innerText = "0 strips";
        qtyVal.innerText = `+ ${added} strips`;
        newVal.innerText = `${added} strips`;
        return;
    }

    const itemData = findMedicineData(medName);
    const currStock = itemData ? itemData.stock : 0;
    const resultStock = currStock + added;

    prevVal.innerText = `${currStock} strips`;
    qtyVal.innerText = `+ ${added} strips`;
    newVal.innerText = `${resultStock} strips`;
}

function populateAddStockMedSelector(meds) {
    const medSelect = document.getElementById('stock-add-med-select');
    if (!medSelect || !meds) return;

    const currentVal = medSelect.value;
    medSelect.innerHTML = '<option value="">-- Select Medicine to Add Stock --</option>' +
        meds.map(m => `<option value="${m.medicine}">${m.medicine} (Current Stock: ${m.stock} strips)</option>`).join('');
    
    if (currentVal) medSelect.value = currentVal;
    updateStockAddPreview();
}

async function fetchStockLogs() {
    try {
        const res = await fetch('/api/stock/log');
        const data = await res.json();
        const tbody = document.getElementById('table-stock-log-body');
        if (!tbody) return;

        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No stock additions recorded in current session.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.logs.map(l => `
            <tr>
                <td style="font-size:0.75rem;">${l.timestamp.split(' ')[1] || l.timestamp}</td>
                <td><strong>${l.medicine}</strong></td>
                <td><strong style="color:var(--primary);">+${l.added_qty}</strong></td>
                <td>${l.previous_stock} $\\rightarrow$ <strong style="color:var(--accent-emerald);">${l.new_stock}</strong></td>
                <td style="font-size:0.75rem; color:var(--text-muted);">${l.user}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error("Failed to fetch stock logs:", err);
    }
}

/* Invoice History Module */
function initInvoiceHistory() {
    const searchInput = document.getElementById('history-search-input');
    const paymentFilter = document.getElementById('history-payment-filter');

    if (searchInput) searchInput.addEventListener('input', debounce(() => fetchInvoiceHistory(), 300));
    if (paymentFilter) paymentFilter.addEventListener('change', () => fetchInvoiceHistory());
}

async function fetchInvoiceHistory() {
    const q = document.getElementById('history-search-input')?.value || '';
    const paymentMode = document.getElementById('history-payment-filter')?.value || 'ALL';

    try {
        const res = await fetch(`/api/pos/history?q=${encodeURIComponent(q)}&payment_mode=${encodeURIComponent(paymentMode)}`);
        const data = await res.json();
        
        if (data.invoices) {
            invoiceHistoryData = data.invoices;
            renderInvoiceHistoryTable(data.invoices, data.summary);
        }
    } catch (err) {
        console.error("Failed to fetch invoice history:", err);
    }
}

function renderInvoiceHistoryTable(invoices, summary) {
    if (summary) {
        document.getElementById('history-total-count').innerText = summary.total_count.toLocaleString('en-IN');
        document.getElementById('history-total-revenue').innerText = `₹${summary.total_revenue.toLocaleString('en-IN', {minimumFractionDigits:2})}`;
        document.getElementById('history-avg-value').innerText = `₹${summary.avg_invoice_value.toLocaleString('en-IN', {minimumFractionDigits:2})}`;
    }

    const tbody = document.getElementById('table-invoice-history-body');
    if (!tbody) return;

    if (!invoices || invoices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted);">No matching customer invoice records found.</td></tr>`;
        return;
    }

    tbody.innerHTML = invoices.map((inv, idx) => `
        <tr>
            <td><strong style="color:var(--primary);">${inv.invoice_no}</strong></td>
            <td style="font-size:0.8rem;">${inv.date}</td>
            <td><strong>${inv.customer_name}</strong></td>
            <td>${inv.customer_phone}</td>
            <td><span class="badge ${inv.payment_mode === 'UPI' ? 'badge-info' : inv.payment_mode === 'Card' ? 'badge-warning' : 'badge-success'}">${inv.payment_mode || 'Cash'}</span></td>
            <td>₹${inv.subtotal.toFixed(2)}</td>
            <td style="color:var(--accent-rose);">-₹${inv.discount_amount.toFixed(2)}</td>
            <td><strong style="color:var(--accent-emerald);">₹${inv.grand_total.toFixed(2)}</strong></td>
            <td style="font-size:0.8rem; color:var(--text-muted);">${inv.billed_by}</td>
            <td>
                <div style="display:flex; gap:0.35rem;">
                    <button class="btn btn-secondary" onclick="viewHistoryInvoiceModal(${idx})" style="padding:0.25rem 0.5rem; font-size:0.72rem;"><i class="fa-solid fa-eye"></i> View</button>
                    <a href="/api/pos/invoice/${inv.invoice_no}" target="_blank" class="btn btn-primary" style="padding:0.25rem 0.5rem; font-size:0.72rem;"><i class="fa-solid fa-file-pdf"></i> PDF</a>
                </div>
            </td>
        </tr>
    `).join('');
}

function viewHistoryInvoiceModal(index) {
    const inv = invoiceHistoryData[index];
    if (inv) renderInvoiceModal(inv);
}

/* POS Billing Engine */
function initPOSBilling() {
    const medSelect = document.getElementById('pos-med-select');
    const qtyInput = document.getElementById('pos-qty-input');
    const priceDisplay = document.getElementById('pos-price-display');
    const btnAddToCart = document.getElementById('btn-add-to-cart');
    const btnCheckout = document.getElementById('btn-process-pos-checkout');
    const discountInput = document.getElementById('pos-discount-input');
    const closeInvoiceBtn = document.getElementById('btn-close-invoice-modal');

    if (medSelect) medSelect.addEventListener('change', updatePOSStockPreview);
    if (qtyInput) qtyInput.addEventListener('input', updatePOSStockPreview);

    if (btnAddToCart) {
        btnAddToCart.addEventListener('click', () => {
            const medName = medSelect.value;
            const qty = intVal(qtyInput.value) || 1;
            if (!medName) {
                alert("Please select a medicine.");
                return;
            }

            const itemData = findMedicineData(medName);
            if (!itemData) return;

            if (qty > itemData.stock) {
                alert(`Insufficient Stock! Requested: ${qty} strips, Available: ${itemData.stock} strips.`);
                return;
            }

            const existingIndex = posCart.findIndex(i => i.medicine.lower() === medName.lower());
            if (existingIndex >= 0) {
                const totalQty = posCart[existingIndex].qty + qty;
                if (totalQty > itemData.stock) {
                    alert(`Cannot add ${qty} more strips. Total cart qty (${totalQty}) exceeds stock (${itemData.stock}).`);
                    return;
                }
                posCart[existingIndex].qty = totalQty;
                posCart[existingIndex].line_total = totalQty * itemData.unit_price;
                posCart[existingIndex].remaining_stock = itemData.stock - totalQty;
            } else {
                posCart.push({
                    medicine: itemData.medicine,
                    category: itemData.category,
                    unit_price: itemData.unit_price,
                    stock: itemData.stock,
                    qty: qty,
                    line_total: qty * itemData.unit_price,
                    remaining_stock: itemData.stock - qty
                });
            }

            renderPOSCart();
            if (medSelect) medSelect.value = "";
            if (qtyInput) qtyInput.value = "10";
            updatePOSStockPreview();
        });
    }

    if (discountInput) discountInput.addEventListener('input', calculatePOSCartTotals);
    if (btnCheckout) btnCheckout.addEventListener('click', processPOSCheckout);
    if (closeInvoiceBtn) {
        closeInvoiceBtn.addEventListener('click', () => {
            document.getElementById('invoice-receipt-modal').style.display = 'none';
        });
    }
}

function updatePOSStockPreview() {
    const medSelect = document.getElementById('pos-med-select');
    const qtyInput = document.getElementById('pos-qty-input');
    const priceDisplay = document.getElementById('pos-price-display');
    const stockVal = document.getElementById('pos-current-stock-val');
    const remainVal = document.getElementById('pos-remaining-stock-val');

    const medName = medSelect?.value;
    const qty = intVal(qtyInput?.value) || 1;

    if (!medName) {
        if (priceDisplay) priceDisplay.value = "₹0";
        if (qtyInput && qtyInput.value === "") qtyInput.value = "10";
        if (stockVal) stockVal.innerText = "0 strips";
        if (remainVal) {
            remainVal.innerText = "0 strips";
            remainVal.style.color = "";
        }
        return;
    }

    const itemData = findMedicineData(medName);
    if (itemData) {
        if (priceDisplay) priceDisplay.value = `₹${itemData.unit_price.toFixed(2)}`;
        if (stockVal) stockVal.innerText = `${itemData.stock} strips`;
        const remaining = Math.max(itemData.stock - qty, 0);
        if (remainVal) {
            remainVal.innerText = `${remaining} strips`;
            remainVal.style.color = itemData.stock - qty < 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)';
        }
    }
}

function findMedicineData(medName) {
    if (!currentDashboardData || !currentDashboardData.stock_expiry) return null;

    const allMeds = currentDashboardData.parameterized_medicines || [];
    const found = allMeds.find(m => m.medicine.toLowerCase() === medName.toLowerCase());
    if (found) {
        return {
            medicine: found.medicine,
            category: found.category,
            unit_price: found.sales / Math.max(found.qty, 1),
            stock: found.stock
        };
    }
    return { medicine: medName, category: "General", unit_price: 150.0, stock: 300 };
}

function renderPOSCart() {
    const tbody = document.getElementById('table-pos-cart-body');
    if (!tbody) return;

    if (posCart.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">Cart is empty. Select a medicine above to start billing.</td></tr>`;
        calculatePOSCartTotals();
        return;
    }

    tbody.innerHTML = posCart.map((item, idx) => `
        <tr>
            <td><strong>${item.medicine}</strong></td>
            <td>${item.qty} strips</td>
            <td>₹${item.unit_price.toFixed(2)}</td>
            <td><strong>₹${item.line_total.toFixed(2)}</strong></td>
            <td><span class="badge ${item.remaining_stock < 30 ? 'badge-danger' : 'badge-success'}">${item.remaining_stock} strips left</span></td>
            <td><button class="btn btn-secondary" onclick="removePOSCartItem(${idx})" style="padding:0.2rem 0.5rem; color:#f43f5e;"><i class="fa-solid fa-trash"></i></button></td>
        </tr>
    `).join('');

    calculatePOSCartTotals();
}

function removePOSCartItem(index) {
    posCart.splice(index, 1);
    renderPOSCart();
    updatePOSStockPreview();
}

function calculatePOSCartTotals() {
    const subtotal = posCart.reduce((sum, i) => sum + i.line_total, 0);
    const discountPct = floatVal(document.getElementById('pos-discount-input')?.value) || 0;
    
    const discountAmt = subtotal * (discountPct / 100.0);
    const taxable = subtotal - discountAmt;
    const taxAmt = taxable * 0.12;
    const grandTotal = taxable + taxAmt;

    const countEl = document.getElementById('pos-cart-count');
    const subtotalEl = document.getElementById('pos-cart-subtotal');
    const discountEl = document.getElementById('pos-cart-discount');
    const taxEl = document.getElementById('pos-cart-tax');
    const grandTotalEl = document.getElementById('pos-cart-grandtotal');

    if (countEl) countEl.innerText = `${posCart.length} items`;
    if (subtotalEl) subtotalEl.innerText = `₹${subtotal.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (discountEl) discountEl.innerText = `- ₹${discountAmt.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (taxEl) taxEl.innerText = `+ ₹${taxAmt.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (grandTotalEl) grandTotalEl.innerText = `₹${grandTotal.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
}

async function processPOSCheckout() {
    if (posCart.length === 0) {
        alert("Please add at least one medicine item to the billing cart.");
        return;
    }

    const customerName = document.getElementById('pos-customer-name').value || "Walk-in Customer";
    const customerPhone = document.getElementById('pos-customer-phone').value || "N/A";
    const discountPct = floatVal(document.getElementById('pos-discount-input').value) || 0;
    const paymentMode = document.getElementById('pos-payment-mode')?.value || "Cash";

    const payload = {
        customer_name: customerName,
        customer_phone: customerPhone,
        discount_pct: discountPct,
        payment_mode: paymentMode,
        items: posCart.map(i => ({ medicine: i.medicine, qty: i.qty }))
    };

    try {
        const btn = document.getElementById('btn-process-pos-checkout');
        btn.innerText = "Processing Checkout & Deducting Stock...";
        
        const res = await fetch('/api/pos/sell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        btn.innerHTML = `<i class="fa-solid fa-check-double"></i> Generate Customer Invoice & Deduct Stock`;

        if (data.error) {
            alert(`Checkout Error: ${data.error}\n${data.details ? data.details.join('\n') : ''}`);
            return;
        }

        posCart = [];
        renderPOSCart();
        renderInvoiceModal(data.invoice);
        
        // Clear POS Customer & Item Form Details
        const custNameInput = document.getElementById('pos-customer-name');
        const custPhoneInput = document.getElementById('pos-customer-phone');
        const medSelect = document.getElementById('pos-med-select');
        const qtyInput = document.getElementById('pos-qty-input');
        if (custNameInput) custNameInput.value = '';
        if (custPhoneInput) custPhoneInput.value = '';
        if (medSelect) medSelect.value = '';
        if (qtyInput) qtyInput.value = '10';
        updatePOSStockPreview();

        loadDashboardData();
        fetchInvoiceHistory();

    } catch (err) {
        alert("Checkout failed. Server connection error.");
    }
}

function renderInvoiceModal(inv) {
    const modal = document.getElementById('invoice-receipt-modal');
    const content = document.getElementById('invoice-receipt-content');
    const pdfBtn = document.getElementById('btn-download-invoice-pdf');

    pdfBtn.href = `/api/pos/invoice/${inv.invoice_no}`;

    content.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:0.75rem;">
            <div>
                <strong style="font-size:1.1rem; color:#fff;">${inv.store_name}</strong>
                <p style="font-size:0.75rem; color:var(--text-muted);">Tax Invoice #${inv.invoice_no}</p>
            </div>
            <div style="text-align:right;">
                <span class="badge ${inv.payment_mode === 'UPI' ? 'badge-info' : inv.payment_mode === 'Card' ? 'badge-warning' : 'badge-success'}">${inv.payment_mode || 'PAID'}</span>
                <p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.2rem;">${inv.date}</p>
            </div>
        </div>

        <div style="background:rgba(255,255,255,0.03); padding:0.6rem 0.85rem; border-radius:6px; margin-bottom:0.75rem; font-size:0.8rem;">
            <div><strong>Customer:</strong> ${inv.customer_name} (${inv.customer_phone})</div>
            <div><strong>Billed By:</strong> ${inv.billed_by}</div>
        </div>

        <div class="table-wrapper">
            <table class="data-table" style="font-size:0.78rem; margin-bottom:0.75rem;">
                <thead>
                    <tr><th>Medicine</th><th>Qty</th><th>Price</th><th>Stock Left</th><th>Total</th></tr>
                </thead>
                <tbody>
                    ${inv.items.map(item => `
                        <tr>
                            <td><strong>${item.medicine}</strong></td>
                            <td>${item.qty} strips</td>
                            <td>₹${item.unit_price.toFixed(2)}</td>
                            <td><strong style="color:var(--palette-lime);">${item.remaining_stock} remaining</strong></td>
                            <td>₹${item.line_total.toFixed(2)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div style="text-align:right; font-size:0.85rem; display:flex; flex-direction:column; gap:0.25rem;">
            <div>Subtotal: <strong>₹${inv.subtotal.toFixed(2)}</strong></div>
            <div>Discount (${inv.discount_pct}%): <strong style="color:var(--accent-rose);">- ₹${inv.discount_amount.toFixed(2)}</strong></div>
            <div>GST Tax (12%): <strong>+ ₹${inv.tax_amount.toFixed(2)}</strong></div>
            <div style="font-size:1.1rem; font-weight:800; color:var(--accent-emerald); margin-top:0.3rem;">Grand Total: ₹${inv.grand_total.toFixed(2)}</div>
        </div>
    `;

    modal.style.display = 'flex';
}

function populatePOSMedSelector(meds) {
    const medSelect = document.getElementById('pos-med-select');
    if (!medSelect || !meds) return;

    const currentVal = medSelect.value;
    medSelect.innerHTML = '<option value="">-- Choose Medicine --</option>' +
        meds.map(m => `<option value="${m.medicine}">${m.medicine} (Stock: ${m.stock} strips)</option>`).join('');
    
    if (currentVal) medSelect.value = currentVal;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        setTimeout(later, wait);
    };
}

function intVal(val) { return parseInt(val, 10); }
function floatVal(val) { return parseFloat(val); }
String.prototype.lower = function() { return this.toLowerCase(); };

function initTableauControls() {
    const controls = ['param-category', 'param-company', 'param-year', 'param-mode', 'param-measure', 'param-count'];
    controls.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => loadDashboardData());
        }
    });

    const resetBtn = document.getElementById('btn-reset-filters');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            document.getElementById('param-category').value = 'ALL';
            document.getElementById('param-company').value = 'ALL';
            document.getElementById('param-year').value = 'ALL';
            document.getElementById('param-mode').value = 'top';
            document.getElementById('param-measure').value = 'sales';
            document.getElementById('param-count').value = '10';
            loadDashboardData();
        });
    }
}

function getTableauQueryParams() {
    const category = document.getElementById('param-category')?.value || 'ALL';
    const company = document.getElementById('param-company')?.value || 'ALL';
    const year = document.getElementById('param-year')?.value || 'ALL';
    const mode = document.getElementById('param-mode')?.value || 'top';
    const measure = document.getElementById('param-measure')?.value || 'sales';
    const top_n = document.getElementById('param-count')?.value || '10';

    return `category=${encodeURIComponent(category)}&company=${encodeURIComponent(company)}&year=${encodeURIComponent(year)}&mode=${encodeURIComponent(mode)}&measure=${encodeURIComponent(measure)}&top_n=${encodeURIComponent(top_n)}&stock_measure=${encodeURIComponent(currentStockMeasure)}`;
}

function initTrendToggles() {
    const btns = document.querySelectorAll('.trend-toggle-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTrendMode = btn.getAttribute('data-trend');
            if (currentDashboardData && currentDashboardData.sales_trends) {
                renderSalesTrendChart(currentDashboardData.sales_trends);
            }
        });
    });
}

function initStockMeasureToggles() {
    const btns = document.querySelectorAll('.stock-toggle-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentStockMeasure = btn.getAttribute('data-stock-measure');
            loadDashboardData();
        });
    });
}

async function loadDashboardData() {
    try {
        const queryStr = getTableauQueryParams();
        const response = await fetch(`/api/dashboard/full?${queryStr}`);
        const data = await response.json();
        
        if (data.error) {
            console.error(data.error);
            return;
        }

        currentDashboardData = data;
        populateFilterDropdowns(data.filter_options);
        populatePOSMedSelector(data.parameterized_medicines);
        populateAddStockMedSelector(data.parameterized_medicines);
        renderKPIs(data.kpis);
        renderCharts(data);
        renderTables(data);
        renderForecasting(data.forecasting);
        renderSeasonal(data.seasonal);
        renderAnomaliesAndClusters(data);
        renderMappingSummary(data.mapping_info);
        updatePOSStockPreview();
    } catch (err) {
        console.error("Failed to load dashboard data:", err);
    }
}

function populateFilterDropdowns(options) {
    if (!options) return;

    const catSelect = document.getElementById('param-category');
    const compSelect = document.getElementById('param-company');
    const yrSelect = document.getElementById('param-year');

    if (catSelect && catSelect.options.length <= 1) {
        options.categories.forEach(c => catSelect.add(new Option(c, c)));
    }
    if (compSelect && compSelect.options.length <= 1) {
        options.companies.forEach(c => compSelect.add(new Option(c, c)));
    }
    if (yrSelect && yrSelect.options.length <= 1) {
        options.years.forEach(y => yrSelect.add(new Option(y, y)));
    }
}

function renderKPIs(kpis) {
    if (!kpis) return;
    document.getElementById('kpi-total-sales').innerText = `₹${kpis.total_sales.toLocaleString('en-IN')}`;
    document.getElementById('kpi-total-profit').innerText = `₹${kpis.total_profit.toLocaleString('en-IN')}`;
    document.getElementById('kpi-total-orders').innerText = kpis.total_orders.toLocaleString('en-IN');
    document.getElementById('kpi-avg-margin').innerText = `${kpis.avg_margin}%`;
    document.getElementById('kpi-stock-value').innerText = `₹${kpis.total_stock_value.toLocaleString('en-IN')}`;
}

function renderCharts(data) {
    renderParameterizedBarChart(data.parameterized_medicines);
    renderStockDistributionPieChart(data.stock_distribution);
    renderSalesTrendChart(data.sales_trends);
}

// ==========================================================================
// Official Pharmora Color Palette Configuration
// ==========================================================================
const PHARMORA_PALETTE = {
    primaryGreen: '#22C55E', // Revenue, Sales, Profit, Growth
    cyan: '#06B6D4',         // Orders, Quantity, Activity
    blue: '#3B82F6',         // Inventory, Stock, Assets
    purple: '#8B5CF6',       // Analytics, AI Insights, Forecast
    amber: '#F59E0B',        // Alerts, Expiring, Low Stock
    pink: '#EC4899',         // Expenses, Discounts, Returns
    lime: '#A3E635',         // Positive Variance, Uplift
    slate: '#94A3B8',        // Neutral Data, Labels, Axes

    categoryList: [
        '#22C55E', // Painkiller
        '#06B6D4', // Antibiotic
        '#3B82F6', // Vitamins
        '#8B5CF6', // Gastric
        '#F59E0B', // Diabetes
        '#F97316', // Supplements
        '#EC4899', // Cold
        '#A3E635', // Lime
        '#94A3B8', // Others
        '#6366F1'  // Indigo
    ],

    barList: [
        '#22C55E',
        '#06B6D4',
        '#3B82F6',
        '#8B5CF6',
        '#A3E635',
        '#F59E0B',
        '#EC4899',
        '#94A3B8'
    ]
};

function renderParameterizedBarChart(meds) {
    if (!meds) return;
    
    const mode = document.getElementById('param-mode')?.value || 'top';
    const measure = document.getElementById('param-measure')?.value || 'sales';
    const titleHeader = document.getElementById('chart-parameterized-title');

    const measureLabels = {
        sales: 'Sales Amount (₹)',
        qty: 'Quantity Sold (Units)',
        profit: 'Net Profit (₹)',
        margin: 'Profit Margin (%)'
    };

    const modeText = mode === 'least' ? '📉 Least Selling Medicines (Bottom N)' : '🔥 Top Selling Medicines';
    if (titleHeader) {
        titleHeader.innerText = `${modeText} by ${measureLabels[measure]}`;
    }

    const labels = meds.map(m => m.medicine);
    const bgColors = mode === 'least' 
        ? meds.map(() => 'rgba(236, 72, 153, 0.85)') 
        : meds.map((_, idx) => PHARMORA_PALETTE.barList[idx % PHARMORA_PALETTE.barList.length]);
    
    const borderColors = mode === 'least' 
        ? meds.map(() => '#EC4899') 
        : meds.map((_, idx) => PHARMORA_PALETTE.barList[idx % PHARMORA_PALETTE.barList.length]);

    createOrUpdateChart('chart-parameterized-medicines', {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: measureLabels[measure],
                data: meds.map(m => m.metric_value),
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: getChartDarkOptions()
    });
}

function renderStockDistributionPieChart(dist) {
    if (!dist || !dist.labels) return;

    createOrUpdateChart('chart-stock-distribution', {
        type: 'doughnut',
        data: {
            labels: dist.labels.map((l, idx) => `${l} (${dist.percentages[idx]}%)`),
            datasets: [{
                data: dist.percentages,
                backgroundColor: PHARMORA_PALETTE.categoryList.slice(0, dist.labels.length),
                borderColor: '#111822',
                borderWidth: 2,
                hoverOffset: 6
            }]
        },
        options: {
            ...getChartDarkOptions(),
            cutout: '62%',
            plugins: {
                legend: { 
                    position: 'right', 
                    labels: { 
                        color: '#F8FAFC', 
                        font: { family: 'Plus Jakarta Sans', size: 11, weight: 500 },
                        usePointStyle: true,
                        boxWidth: 8,
                        padding: 10
                    } 
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 32, 0.95)',
                    titleColor: '#F8FAFC',
                    bodyColor: '#F8FAFC',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(ctx) {
                            const idx = ctx.dataIndex;
                            const val = dist.values[idx];
                            const label = dist.labels[idx];
                            const pct = dist.percentages[idx];
                            const valStr = dist.measure === 'value' ? `₹${val.toLocaleString('en-IN')}` : `${val} units`;
                            return `${label}: ${pct}% (${valStr})`;
                        }
                    }
                }
            }
        }
    });
}

function renderSalesTrendChart(trends) {
    if (!trends) return;
    
    let dataset = [];
    let labels = [];
    
    if (currentTrendMode === 'monthly' && trends.monthly) {
        labels = trends.monthly.map(m => m.month);
        dataset = [
            { 
                label: 'Sales (₹)', 
                data: trends.monthly.map(m => m.sales), 
                borderColor: '#22C55E', 
                backgroundColor: 'rgba(34, 197, 94, 0.12)', 
                fill: true, 
                tension: 0.38,
                pointBackgroundColor: '#22C55E',
                pointBorderColor: '#0B0F14',
                pointRadius: 4,
                pointHoverRadius: 6
            },
            { 
                label: 'Profit (₹)', 
                data: trends.monthly.map(m => m.profit), 
                borderColor: '#06B6D4', 
                backgroundColor: 'rgba(6, 182, 212, 0.10)', 
                fill: true, 
                tension: 0.38,
                pointBackgroundColor: '#06B6D4',
                pointBorderColor: '#0B0F14',
                pointRadius: 4,
                pointHoverRadius: 6
            }
        ];
    } else if (currentTrendMode === 'weekly' && trends.weekly) {
        labels = trends.weekly.map(w => w.week);
        dataset = [
            { 
                label: 'Weekly Sales (₹)', 
                data: trends.weekly.map(w => w.sales), 
                borderColor: '#A3E635', 
                backgroundColor: 'rgba(163, 230, 53, 0.12)', 
                fill: true, 
                tension: 0.38,
                pointBackgroundColor: '#A3E635',
                pointRadius: 4
            }
        ];
    } else if (currentTrendMode === 'daily' && trends.daily) {
        labels = trends.daily.map(d => d.date);
        dataset = [
            { 
                label: 'Daily Sales (₹)', 
                data: trends.daily.map(d => d.sales), 
                borderColor: '#22C55E', 
                backgroundColor: 'rgba(34, 197, 94, 0.12)', 
                fill: true, 
                tension: 0.38,
                pointBackgroundColor: '#22C55E',
                pointRadius: 3
            }
        ];
    } else if (currentTrendMode === 'yearly' && trends.yearly) {
        labels = trends.yearly.map(y => y.year);
        dataset = [
            { 
                label: 'Yearly Sales (₹)', 
                data: trends.yearly.map(y => y.sales), 
                borderColor: '#3B82F6', 
                backgroundColor: 'rgba(59, 130, 246, 0.15)', 
                fill: true, 
                tension: 0.38,
                pointBackgroundColor: '#3B82F6',
                pointRadius: 5
            }
        ];
    }

    createOrUpdateChart('chart-monthly-sales', {
        type: 'line',
        data: { labels: labels, datasets: dataset },
        options: getChartDarkOptions()
    });
}

function getChartDarkOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { 
                labels: { 
                    color: '#F8FAFC', 
                    font: { family: 'Plus Jakarta Sans', size: 12, weight: 600 },
                    usePointStyle: true,
                    boxWidth: 8
                } 
            },
            tooltip: {
                backgroundColor: 'rgba(17, 24, 32, 0.95)',
                titleColor: '#F8FAFC',
                bodyColor: '#F8FAFC',
                borderColor: 'rgba(148, 163, 184, 0.2)',
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                cornerRadius: 8
            }
        },
        scales: {
            x: { 
                ticks: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans', size: 11 } }, 
                grid: { color: 'rgba(148, 163, 184, 0.08)' } 
            },
            y: { 
                ticks: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans', size: 11 } }, 
                grid: { color: 'rgba(148, 163, 184, 0.08)' } 
            }
        }
    };
}

function createOrUpdateChart(canvasId, config) {
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }
    const ctx = document.getElementById(canvasId);
    if (ctx) {
        chartInstances[canvasId] = new Chart(ctx, config);
    }
}

function renderProductHighlights(prod) {
    if (!prod) return;

    // 1. Top Profit Leader
    const profitSumm = prod.profit_summary || {};
    const topProfit = (prod.highest_profit && prod.highest_profit[0]) ? prod.highest_profit[0] : null;
    const nameElem = document.getElementById('hl-top-profit-name');
    const valElem = document.getElementById('hl-top-profit-val');
    const descElem = document.getElementById('hl-top-profit-desc');
    
    if (topProfit && nameElem && valElem) {
        nameElem.innerText = topProfit.medicine;
        valElem.innerText = `₹${topProfit.profit.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        if (descElem) descElem.innerText = `${topProfit.category} | ${topProfit.margin}% Margin (₹${topProfit.sales.toLocaleString('en-IN')} Sales)`;
    }

    // 2. Fast Moving Velocity Leader
    const topFast = (prod.fast_moving && prod.fast_moving[0]) ? prod.fast_moving[0] : null;
    const fastNameElem = document.getElementById('hl-top-fast-name');
    const fastValElem = document.getElementById('hl-top-fast-val');
    const fastDescElem = document.getElementById('hl-top-fast-desc');
    
    if (topFast && fastNameElem && fastValElem) {
        fastNameElem.innerText = topFast.medicine;
        fastValElem.innerText = `${topFast.qty_sold.toLocaleString('en-IN')} units`;
        if (fastDescElem) fastDescElem.innerText = `~${topFast.monthly_velocity} units/mo | ₹${topFast.sales.toLocaleString('en-IN')} Revenue`;
    }

    // 3. Dead Stock / Locked Capital
    const deadSumm = prod.dead_stock_summary || {};
    const deadCapitalElem = document.getElementById('hl-dead-capital-val');
    const deadUnitsElem = document.getElementById('hl-dead-units-count');
    const deadStockCountElem = document.getElementById('hl-dead-stock-count');
    const badgeDeadLocked = document.getElementById('badge-dead-stock-locked');

    if (deadCapitalElem) {
        deadCapitalElem.innerText = `₹${(deadSumm.total_locked_capital || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    }
    if (deadUnitsElem) {
        deadUnitsElem.innerText = `${(deadSumm.total_dead_units || 0).toLocaleString('en-IN')} unsold units idle in store`;
    }
    if (deadStockCountElem) {
        deadStockCountElem.innerText = `${deadSumm.count || (prod.dead_stock ? prod.dead_stock.length : 0)} SKUs Idle`;
    }
    if (badgeDeadLocked) {
        badgeDeadLocked.innerHTML = `<i class="fa-solid fa-lock"></i> ₹${(deadSumm.total_locked_capital || 0).toLocaleString('en-IN')} Locked`;
    }
}

function renderTables(data) {
    if (!data) return;

    const stock = data.stock_expiry;
    const prod = data.product_analytics || data.product_performance || {};

    // Render Intelligence Highlights
    renderProductHighlights(prod);

    const redAlertTbody = document.getElementById('table-red-alert-body');
    if (redAlertTbody && stock && stock.red_alert) {
        redAlertTbody.innerHTML = stock.red_alert.length === 0 
            ? `<tr><td colspan="5" style="text-align:center; color:#10b981;">No critical expiry red alerts detected! Stock burn rate is healthy.</td></tr>`
            : stock.red_alert.map(item => `
                <tr>
                    <td><strong>${item.medicine}</strong></td>
                    <td>${item.stock} units</td>
                    <td><span class="badge badge-danger">${item.days_to_expiry} Days</span></td>
                    <td>${item.daily_rate} / day</td>
                    <td style="color:#f43f5e; font-size:0.8rem;">${item.risk_reason}</td>
                </tr>
            `).join('');
    }

    const lowStockTbody = document.getElementById('table-low-stock-body');
    if (lowStockTbody && stock && stock.low_stock) {
        lowStockTbody.innerHTML = stock.low_stock.map(item => `
            <tr>
                <td><strong>${item.medicine}</strong></td>
                <td>${item.category}</td>
                <td><span class="badge ${item.stock < 10 ? 'badge-danger' : 'badge-warning'}">${item.stock} units</span></td>
                <td>${item.expiry}</td>
            </tr>
        `).join('');
    }

    // 1. Highest Profit Medicines Table
    const profitTbody = document.getElementById('table-profit-body');
    if (profitTbody && prod && prod.highest_profit) {
        profitTbody.innerHTML = prod.highest_profit.length === 0
            ? `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No profit records available for current filter.</td></tr>`
            : prod.highest_profit.slice(0, 10).map(item => `
                <tr>
                    <td><strong style="color:#F8FAFC;">${item.medicine}</strong></td>
                    <td><span style="font-size:0.8rem; color:var(--text-muted);">${item.category || 'General'}</span></td>
                    <td>₹${item.sales.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                    <td style="color:var(--color-primary-green); font-weight:700;">₹${item.profit.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                    <td><span class="badge badge-success">${item.margin}%</span></td>
                    <td><strong style="color:var(--color-cyan); font-size:0.82rem;">${item.profit_share || 0}%</strong></td>
                    <td><span class="badge ${item.margin >= 40 ? 'badge-success' : 'badge-info'}" style="font-size:0.7rem;">${item.tag || 'Profit Driver'}</span></td>
                </tr>
            `).join('');
    }

    const abcTbody = document.getElementById('table-abc-xyz-body');
    if (abcTbody && data.abc_xyz && data.abc_xyz.matrix) {
        abcTbody.innerHTML = data.abc_xyz.matrix.slice(0, 10).map(item => `
            <tr>
                <td><strong>${item.medicine}</strong></td>
                <td>₹${item.total_sales.toLocaleString('en-IN')}</td>
                <td><span class="badge ${item.abc_class.includes('A') ? 'badge-danger' : item.abc_class.includes('B') ? 'badge-warning' : 'badge-info'}">${item.abc_class}</span></td>
                <td><span class="badge badge-info">${item.xyz_class}</span></td>
            </tr>
        `).join('');
    }

    // 2. Fast Moving Products Table
    const fastTbody = document.getElementById('table-fast-moving-body');
    if (fastTbody && prod && prod.fast_moving) {
        fastTbody.innerHTML = prod.fast_moving.length === 0
            ? `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No fast moving products found.</td></tr>`
            : prod.fast_moving.slice(0, 15).map(item => `
                <tr>
                    <td><strong style="color:#F8FAFC;">${item.medicine}</strong></td>
                    <td><span style="font-size:0.78rem; color:var(--text-muted);">${item.category}</span></td>
                    <td><strong style="color:var(--color-cyan);">${item.qty_sold.toLocaleString('en-IN')} units</strong></td>
                    <td>~${item.monthly_velocity || 0} / mo</td>
                    <td><strong style="color:#F8FAFC;">${item.stock} strips</strong></td>
                    <td><span class="badge ${item.stock_coverage_days < 15 ? 'badge-danger' : 'badge-info'}">${item.stock_coverage_days} d</span></td>
                    <td><span class="badge ${item.status_color === 'danger' ? 'badge-danger' : item.status_color === 'success' ? 'badge-success' : 'badge-info'}" style="font-size:0.7rem;">${item.status}</span></td>
                </tr>
            `).join('');
    }

    // 3. Dead Stock / Slow Moving Inventory Table
    const slowTbody = document.getElementById('table-slow-moving-body');
    const deadList = prod.dead_stock || prod.slow_moving || [];
    if (slowTbody) {
        slowTbody.innerHTML = deadList.length === 0
            ? `<tr><td colspan="7" style="text-align:center; color:var(--color-primary-green);">All inventory is turning over actively! No dead stock detected.</td></tr>`
            : deadList.slice(0, 15).map(item => `
                <tr>
                    <td><strong style="color:#F8FAFC;">${item.medicine}</strong></td>
                    <td><strong style="color:var(--accent-rose);">${item.stock} units</strong></td>
                    <td>₹${(item.buy_price || 0).toFixed(2)}</td>
                    <td><strong style="color:#f43f5e; font-family:'Outfit';">₹${(item.locked_capital || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
                    <td><span class="badge ${item.days_idle > 60 ? 'badge-danger' : 'badge-warning'}">${item.days_idle || 0} d idle</span></td>
                    <td><span class="badge badge-warning" style="font-size:0.7rem;">${item.risk_level || 'Slow Turn'}</span></td>
                    <td><span class="badge badge-danger" style="font-size:0.72rem; font-weight:600;"><i class="fa-solid fa-tag"></i> ${item.action || 'Clearance Sale'}</span></td>
                </tr>
            `).join('');
    }
}

function renderForecasting(fc) {
    if (!fc) return;
    
    if (fc.models_prediction) {
        document.getElementById('fc-next-week').innerText = `₹${fc.models_prediction.next_week_sales.toLocaleString('en-IN')}`;
        document.getElementById('fc-next-month').innerText = `₹${fc.models_prediction.next_month_sales.toLocaleString('en-IN')}`;
        document.getElementById('fc-next-year').innerText = `₹${fc.models_prediction.next_year_sales.toLocaleString('en-IN')}`;

        if (fc.models_prediction.model_breakdown) {
            document.getElementById('ml-lr-pred').innerText = `₹${fc.models_prediction.model_breakdown.linear_regression.toLocaleString('en-IN')}`;
            document.getElementById('ml-rf-pred').innerText = `₹${fc.models_prediction.model_breakdown.random_forest.toLocaleString('en-IN')}`;
            document.getElementById('ml-gb-pred').innerText = `₹${fc.models_prediction.model_breakdown.xgboost_gb.toLocaleString('en-IN')}`;
        }
    }

    const reorderTbody = document.getElementById('table-reorder-body');
    if (reorderTbody && fc.reorder_suggestions) {
        reorderTbody.innerHTML = fc.reorder_suggestions.map(item => `
            <tr>
                <td><strong>${item.medicine}</strong></td>
                <td>${item.current_stock} units</td>
                <td>${item.reorder_point} units</td>
                <td><strong style="color:#5DD62C;">${item.recommended_reorder} units</strong></td>
                <td><span class="badge ${item.status === 'CRITICAL_REORDER' ? 'badge-danger' : 'badge-warning'}">${item.status}</span></td>
            </tr>
        `).join('');
    }

    const stockRecsTbody = document.getElementById('table-stock-recs-body');
    if (stockRecsTbody && fc.stock_recommendations) {
        stockRecsTbody.innerHTML = fc.stock_recommendations.slice(0, 10).map(item => `
            <tr>
                <td><strong>${item.medicine}</strong></td>
                <td>${item.category}</td>
                <td><span class="badge ${item.type === 'increase' ? 'badge-danger' : item.type === 'reduce' ? 'badge-warning' : 'badge-success'}">${item.action} Stock</span></td>
                <td style="font-size:0.82rem; color:#94a3b8;">${item.reason}</td>
            </tr>
        `).join('');
    }
}

function renderSeasonal(s) {
    if (!s) return;
    document.getElementById('rainy-meds').innerText = s.rainy.medicines.join(', ');
    document.getElementById('summer-meds').innerText = s.summer.medicines.join(', ');
    document.getElementById('winter-meds').innerText = s.winter.medicines.join(', ');
}

function renderAnomaliesAndClusters(data) {
    const anomalyContainer = document.getElementById('anomalies-list');
    if (anomalyContainer && data.anomalies) {
        anomalyContainer.innerHTML = data.anomalies.length === 0
            ? '<p style="color:#94a3b8;">No statistical anomalies detected in transaction logs.</p>'
            : data.anomalies.map(a => `
                <div style="padding:0.75rem; background:rgba(255,255,255,0.03); border-radius:8px; margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between; font-weight:600; font-size:0.85rem;">
                        <span>${a.date} - ${a.medicine}</span>
                        <span style="color:#f59e0b;">₹${a.sales} (${a.qty} units)</span>
                    </div>
                    <p style="font-size:0.75rem; color:#94a3b8; margin-top:0.25rem;">${a.reason}</p>
                </div>
            `).join('');
    }
}

function renderMappingSummary(mapping) {
    const summaryTbody = document.getElementById('table-mapping-summary-body');
    if (!summaryTbody || !mapping) return;

    summaryTbody.innerHTML = Object.entries(mapping).map(([targetCol, info]) => {
        const isMatched = info.status === "MATCHED";
        return `
            <tr>
                <td><strong>${targetCol}</strong></td>
                <td><code>${isMatched ? info.original : 'Not Found (Auto Defaulted)'}</code></td>
                <td><span class="badge ${isMatched ? 'badge-success' : 'badge-warning'}">${info.status}</span></td>
            </tr>
        `;
    }).join('');
}

function initAssistantWizard() {
    const btn = document.getElementById('btn-run-assistant');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const payload = {
            location: document.getElementById('wizard-location').value,
            population: parseInt(document.getElementById('wizard-population').value) || 50000,
            budget: parseFloat(document.getElementById('wizard-budget').value) || 500000,
            store_size: parseInt(document.getElementById('wizard-size').value) || 400,
            nearby_hospitals: parseInt(document.getElementById('wizard-hospitals').value) || 2,
            nearby_clinics: parseInt(document.getElementById('wizard-clinics').value) || 5
        };

        try {
            const res = await fetch('/api/assistant/new-pharmacy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            document.getElementById('assistant-results-container').style.display = 'block';
            document.getElementById('wizard-proj-revenue').innerText = `₹${data.projected_monthly_sales.toLocaleString('en-IN')}`;
            document.getElementById('wizard-market-score').innerText = `${data.market_score} / 10`;

            const budgetTbody = document.getElementById('table-wizard-budget-body');
            budgetTbody.innerHTML = Object.entries(data.budget_allocation).map(([cat, amt]) => `
                <tr>
                    <td>${cat}</td>
                    <td><strong>₹${amt.toLocaleString('en-IN')}</strong></td>
                </tr>
            `).join('');

            const stockTbody = document.getElementById('table-wizard-stock-body');
            stockTbody.innerHTML = data.recommended_initial_stock.map(item => `
                <tr>
                    <td><strong>${item.medicine}</strong></td>
                    <td>${item.qty} units</td>
                    <td>${item.expected_sales} units/mo</td>
                    <td style="font-size:0.8rem; color:#94a3b8;">${item.reason}</td>
                </tr>
            `).join('');

        } catch (err) {
            console.error("Assistant query failed:", err);
        }
    });
}

function initUploadModal() {
    const uploadInput = document.getElementById('file-upload-input');
    const uploadBtn = document.getElementById('btn-upload-file');
    if (!uploadBtn || !uploadInput) return;

    uploadBtn.addEventListener('click', async () => {
        if (!uploadInput.files[0]) {
            alert("Please select a sales.csv or sales.xlsx file to upload.");
            return;
        }

        const formData = new FormData();
        formData.append('file', uploadInput.files[0]);

        try {
            uploadBtn.innerText = "Processing & Mapping...";
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const result = await res.json();
            uploadBtn.innerText = "Upload & Map Sheet";

            if (result.error) {
                alert(result.error);
                return;
            }

            alert(result.message);
            loadDashboardData();

        } catch (err) {
            uploadBtn.innerText = "Upload & Map Sheet";
            alert("Failed to upload sales sheet.");
        }
    });
}

function initChatbot() {
    const trigger = document.getElementById('chatbot-trigger');
    const drawer = document.getElementById('chatbot-drawer');
    const closeBtn = document.getElementById('chatbot-close');
    const sendBtn = document.getElementById('chatbot-send');
    const input = document.getElementById('chatbot-input');
    const messages = document.getElementById('chatbot-messages');

    if (!trigger || !drawer) return;

    trigger.addEventListener('click', () => drawer.classList.toggle('open'));
    if (closeBtn) closeBtn.addEventListener('click', () => drawer.classList.remove('open'));

    document.querySelectorAll('.chat-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.innerText.trim();
            handleSend();
        });
    });

    async function handleSend() {
        const query = input.value.trim();
        if (!query) return;

        messages.innerHTML += `<div class="chat-bubble user">${query}</div>`;
        input.value = '';
        messages.scrollTop = messages.scrollHeight;

        try {
            const res = await fetch('/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            const data = await res.json();

            messages.innerHTML += `<div class="chat-bubble bot">${data.answer}</div>`;
            messages.scrollTop = messages.scrollHeight;
        } catch (err) {
            messages.innerHTML += `<div class="chat-bubble bot">Sorry, unable to process your question at the moment.</div>`;
        }
    }

    sendBtn.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
}
