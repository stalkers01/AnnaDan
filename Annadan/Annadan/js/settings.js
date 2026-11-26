const settingsForm = document.querySelector('#settings-form');
const settingsMessage = document.querySelector('#settings-message');

(async function loadSettings() {
    try {
        const settings = await AnnadanAPI.request('/users/me/settings');
        settingsForm.elements.donationUpdates.checked = settings.donation_updates !== false;
        settingsForm.elements.requestUpdates.checked = settings.request_updates !== false;
        settingsForm.elements.emailUpdates.checked = settings.email_updates !== false;
        settingsForm.elements.smsUpdates.checked = settings.sms_updates === true;
        settingsForm.elements.preferredRole.value = settings.preferred_role || 'receiver';
    } catch (error) {
        settingsMessage.textContent = error.message;
    }
})();

settingsForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    const payload = {
        donation_updates: settingsForm.elements.donationUpdates.checked,
        request_updates: settingsForm.elements.requestUpdates.checked,
        email_updates: settingsForm.elements.emailUpdates.checked,
        sms_updates: settingsForm.elements.smsUpdates.checked,
        preferred_role: settingsForm.elements.preferredRole.value,
    };

    try {
        await AnnadanAPI.request('/users/me/settings', {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });
        settingsMessage.textContent = 'Your settings have been saved to your Annadan account.';
    } catch (error) {
        settingsMessage.textContent = error.message;
    }
});
