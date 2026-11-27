(async function loadProfile() {
    const message = document.querySelector('#profile-message');
    try {
        const [user, stats] = await Promise.all([
            AnnadanAPI.request('/users/me'),
            AnnadanAPI.request('/users/me/stats'),
        ]);

        document.querySelector('#profile-avatar').textContent = user.full_name.slice(0, 1).toUpperCase();
        document.querySelector('#profile-name').textContent = user.full_name;
        document.querySelector('#profile-role').textContent = user.role.replaceAll('_', ' ');
        document.querySelector('#profile-full-name').textContent = user.full_name;
        document.querySelector('#profile-email').textContent = user.email;
        document.querySelector('#profile-phone').textContent = user.phone;
        document.querySelector('#profile-account-type').textContent = user.role.replaceAll('_', ' ');

        const counters = document.querySelectorAll('[data-profile-stat]');
        counters.forEach((element) => {
            element.textContent = stats[element.dataset.profileStat] ?? 0;
        });
    } catch (error) {
        if (message) message.textContent = error.message;
    }
})();
