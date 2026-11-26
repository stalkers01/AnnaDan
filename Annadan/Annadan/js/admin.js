const adminMessage = document.querySelector('#admin-message');
const adminUsers = document.querySelector('#admin-users');

function addCell(row, value) {
    const cell = document.createElement('td');
    cell.textContent = value;
    row.append(cell);
    return cell;
}

(async function loadAdminDashboard() {
    try {
        const user = await AnnadanAPI.currentUser();
        if (!user || user.role !== 'admin') {
            window.location.href = 'login.html';
            return;
        }

        const [overview, users] = await Promise.all([
            AnnadanAPI.request('/admin/overview'),
            AnnadanAPI.request('/admin/users?limit=100'),
        ]);

        document.querySelectorAll('[data-admin-stat]').forEach((element) => {
            element.textContent = overview[element.dataset.adminStat] ?? 0;
        });

        adminUsers.replaceChildren();
        users.forEach((userRecord) => {
            const row = document.createElement('tr');
            addCell(row, userRecord.full_name);
            addCell(row, userRecord.email);
            addCell(row, userRecord.role);
            addCell(row, userRecord.is_active ? 'Active' : 'Disabled');
            const actionCell = document.createElement('td');
            const action = document.createElement('button');
            action.type = 'button';
            action.className = 'offer-request';
            action.textContent = userRecord.is_active ? 'Disable' : 'Enable';
            action.disabled = userRecord.id === user.id;
            action.addEventListener('click', async () => {
                action.disabled = true;
                try {
                    await AnnadanAPI.request(`/admin/users/${userRecord.id}/status`, {
                        method: 'PATCH',
                        body: JSON.stringify({ is_active: !userRecord.is_active }),
                    });
                    window.location.reload();
                } catch (error) {
                    adminMessage.textContent = error.message;
                    action.disabled = false;
                }
            });
            actionCell.append(action);
            row.append(actionCell);
            adminUsers.append(row);
        });
    } catch (error) {
        adminMessage.textContent = error.message;
    }
})();


async function loadSafetyQueue() {
    const container = document.querySelector('#safety-reviews');
    if (!container) return;
    try {
        const donations = await AnnadanAPI.request('/admin/safety/pending');
        container.replaceChildren();
        if (!donations.length) {
            container.textContent = 'No food-safety reviews are waiting.';
            return;
        }
        donations.forEach((donation) => {
            const card = document.createElement('article');
            card.className = 'safety-review-card';
            const heading = document.createElement('h3');
            heading.textContent = donation.title;
            const details = document.createElement('p');
            details.textContent = `${donation.quantity_total} ${donation.quantity_unit} · ${donation.city} · ${donation.pickup_location}`;
            const description = document.createElement('p');
            description.textContent = donation.description;
            const checklist = document.createElement('ul');
            Object.entries(donation.safety_checklist || {}).forEach(([key, checked]) => {
                const item = document.createElement('li');
                item.textContent = `${key.replaceAll('_', ' ')}: ${checked ? 'confirmed by donor' : 'not confirmed'}`;
                checklist.append(item);
            });
            card.append(heading, details, description);
            if (donation.image_url) {
                const image = document.createElement('img');
                image.src = donation.image_url;
                image.alt = `Submitted food: ${donation.title}`;
                image.loading = 'lazy';
                card.append(image);
            }
            card.append(checklist);
            const note = document.createElement('input');
            note.type = 'text';
            note.maxLength = 500;
            note.placeholder = 'Review note (optional)';
            note.setAttribute('aria-label', `Review note for ${donation.title}`);
            const actions = document.createElement('div');
            actions.className = 'safety-review-actions';
            [['approved', 'Approve'], ['rejected', 'Reject']].forEach(([decision, label]) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = label;
                button.addEventListener('click', async () => {
                    button.disabled = true;
                    try {
                        await AnnadanAPI.request(`/admin/safety/${donation.id}`, {
                            method: 'PATCH',
                            body: JSON.stringify({ decision, note: note.value.trim() }),
                        });
                        card.remove();
                        if (!container.children.length) container.textContent = 'No food-safety reviews are waiting.';
                    } catch (error) {
                        adminMessage.textContent = error.message;
                        button.disabled = false;
                    }
                });
                actions.append(button);
            });
            card.append(note, actions);
            container.append(card);
        });
    } catch (error) {
        container.textContent = error.message;
    }
}

loadSafetyQueue();
