/** Keep shared account labels in sync with the signed-in account. */
(function () {
    const roleNames = {
        donor: 'Food donor',
        receiver: 'Food receiver',
        delivery_partner: 'Delivery partner',
        admin: 'Administrator',
    };

    document.addEventListener('DOMContentLoaded', async function () {
        document.querySelectorAll('.logout').forEach((link) => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                window.AnnadanAPI.clearSession();
                window.location.href = 'index.html';
            });
        });

        const account = document.querySelector('.account');
        if (!account || !window.AnnadanAPI) return;

        const heading = account.querySelector('h4');
        const accountLink = account.querySelector('a');
        try {
            const user = await window.AnnadanAPI.currentUser();
            if (user) {
                if (heading) heading.textContent = `${roleNames[user.role] || user.role} 🟢`;
                const headerRole = document.querySelector('.profile-info span');
                if (headerRole) headerRole.textContent = roleNames[user.role] || user.role;
                if (accountLink) {
                    accountLink.textContent = 'View profile';
                    accountLink.href = user.role === 'admin' ? 'admin.html' : 'profile.html';
                }
            } else {
                if (heading) heading.textContent = 'Guest';
                if (accountLink) {
                    accountLink.textContent = 'Sign in';
                    accountLink.href = 'login.html';
                }
            }
        } catch (_error) {
            if (heading) heading.textContent = 'Guest';
            if (accountLink) {
                accountLink.textContent = 'Sign in';
                accountLink.href = 'login.html';
            }
        }
    });
})();
