const message = document.querySelector('#verify-message');
const emailForm = document.querySelector('#email-verify-form');
const phoneForm = document.querySelector('#phone-verify-form');

(async function checkSession() {
    try {
        const user = await AnnadanAPI.currentUser(true);
        if (!user) window.location.href = 'login.html';
        else if (user.email_verified) message.textContent = 'Email already verified. You can continue using Annadan.';
    } catch (error) {
        message.textContent = error.message;
    }
})();

document.querySelector('#resend-email-code').addEventListener('click', async () => {
    try {
        const result = await AnnadanAPI.request('/auth/otp/request', { method: 'POST' });
        message.textContent = result.development_code
            ? `${result.message} Development code: ${result.development_code}`
            : result.message;
    } catch (error) { message.textContent = error.message; }
});

emailForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
        const result = await AnnadanAPI.request('/auth/otp/verify', {
            method: 'POST',
            body: JSON.stringify({ code: emailForm.elements.code.value.trim() }),
        });
        message.textContent = result.message;
        const user = await AnnadanAPI.currentUser(true);
        if (user && user.email_verified) window.location.href = user.role === 'admin' ? 'admin.html' : 'index.html';
    } catch (error) { message.textContent = error.message; }
});

document.querySelector('#send-phone-code').addEventListener('click', async () => {
    try {
        const result = await AnnadanAPI.request('/auth/phone/otp/request', {
            method: 'POST', body: JSON.stringify({ channel: 'sms' }),
        });
        message.textContent = result.message;
    } catch (error) { message.textContent = error.message; }
});

phoneForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
        const result = await AnnadanAPI.request('/auth/phone/otp/verify', {
            method: 'POST', body: JSON.stringify({ code: phoneForm.elements.code.value.trim() }),
        });
        message.textContent = result.message;
    } catch (error) { message.textContent = error.message; }
});
