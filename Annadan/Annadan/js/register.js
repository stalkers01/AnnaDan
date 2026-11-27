const form = document.querySelector('#register-form');
const password = document.querySelector('#password');
const confirmPassword = document.querySelector('#confirm-password');
const message = document.querySelector('#register-message');
const submitButton = form.querySelector('button[type="submit"]');

function checkPasswords() {
    confirmPassword.setCustomValidity(
        confirmPassword.value && confirmPassword.value !== password.value
            ? 'The passwords do not match.'
            : ''
    );
}

password.addEventListener('input', checkPasswords);
confirmPassword.addEventListener('input', checkPasswords);

form.addEventListener('submit', async function (event) {
    event.preventDefault();
    checkPasswords();
    if (!form.reportValidity()) return;

    const formData = new FormData(form);
    const payload = {
        full_name: String(formData.get('fullName')).trim(),
        email: String(formData.get('email')).trim(),
        phone: String(formData.get('phone')).trim(),
        role: String(formData.get('role')),
        password: String(formData.get('password')),
    };

    submitButton.disabled = true;
    submitButton.textContent = 'Creating account…';
    message.textContent = '';

    try {
        const result = await AnnadanAPI.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        AnnadanAPI.saveSession(result);
        message.textContent = `Welcome to Annadan, ${result.user.full_name}. Your account is ready.`;
        window.location.href = !result.user.email_verified ? 'verify.html' : 'index.html';
    } catch (error) {
        message.textContent = error.message;
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Create account';
    }
});
