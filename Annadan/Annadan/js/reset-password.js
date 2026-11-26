const forgotForm = document.querySelector('#forgot-form');
const resetForm = document.querySelector('#reset-form');
const resetMessage = document.querySelector('#reset-message');
let resetEmail = '';

forgotForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    resetEmail = forgotForm.elements.email.value.trim();
    try {
        const result = await AnnadanAPI.request('/auth/password/forgot', {
            method: 'POST', body: JSON.stringify({ email: resetEmail }),
        });
        resetMessage.textContent = result.development_code
            ? `${result.message} Development code: ${result.development_code}`
            : result.message;
    } catch (error) { resetMessage.textContent = error.message; }
});

resetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!resetEmail) {
        resetMessage.textContent = 'Enter your email and request a reset code first.';
        return;
    }
    try {
        const result = await AnnadanAPI.request('/auth/password/reset', {
            method: 'POST',
            body: JSON.stringify({
                email: resetEmail,
                code: resetForm.elements.code.value.trim(),
                new_password: resetForm.elements.new_password.value,
            }),
        });
        resetMessage.textContent = result.message;
        resetForm.reset();
    } catch (error) { resetMessage.textContent = error.message; }
});
