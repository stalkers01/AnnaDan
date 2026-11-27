const loginForm = document.querySelector('#login-form');
const loginMessage = document.querySelector('#login-message');
const loginButton = loginForm.querySelector('button[type="submit"]');

loginForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (!loginForm.reportValidity()) return;

    const formData = new FormData(loginForm);
    loginButton.disabled = true;
    loginButton.textContent = 'Signing in…';
    loginMessage.textContent = '';

    try {
        const result = await AnnadanAPI.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({
                email: String(formData.get('email')).trim(),
                password: String(formData.get('password')),
            }),
        });
        AnnadanAPI.saveSession(result);
        window.location.href = !result.user.email_verified ? 'verify.html' : (result.user.role === 'admin' ? 'admin.html' : 'index.html');
    } catch (error) {
        loginMessage.textContent = error.message;
    } finally {
        loginButton.disabled = false;
        loginButton.textContent = 'Sign in';
    }
});
