(async function loadActivity() {
    const panel = document.querySelector('#activity-panel');
    try {
        const stats = await AnnadanAPI.request('/users/me/stats');
        document.querySelectorAll('[data-activity-stat]').forEach((element) => {
            element.textContent = stats[element.dataset.activityStat] ?? 0;
        });

        const requests = await AnnadanAPI.request('/requests/mine');
        panel.replaceChildren();
        if (!requests.length) {
            panel.append(
                Object.assign(document.createElement('h2'), { textContent: 'No activity yet' }),
                Object.assign(document.createElement('p'), { textContent: 'Your donations and requests will appear here after you use Annadan.' })
            );
            return;
        }

        const heading = document.createElement('h2');
        heading.textContent = 'Recent activity';
        panel.append(heading);
        requests.forEach((item) => {
            const row = document.createElement('p');
            row.textContent = `${item.donation.title} — ${item.status.replaceAll('_', ' ')} — ${item.quantity} ${item.donation.quantity_unit}`;
            panel.append(row);
        });
    } catch (error) {
        panel.textContent = error.message;
    }
})();
