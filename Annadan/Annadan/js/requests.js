const requestsList = document.querySelector('#requests-list');

function makeText(tag, value, className) {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
}

function makeRequestCard(item, user) {
    const card = document.createElement('article');
    card.className = 'offer-card';

    const icon = makeText('div', '📦', 'offer-icon');
    const content = document.createElement('div');
    content.className = 'offer-main';
    const heading = document.createElement('div');
    heading.className = 'offer-heading';
    heading.append(
        makeText('h2', item.donation.title),
        makeText('span', item.status.replaceAll('_', ' '))
    );

    content.append(
        heading,
        makeText('p', `Quantity requested: ${item.quantity} ${item.donation.quantity_unit}`),
        makeText('p', `Pickup: ${item.donation.pickup_location}, ${item.donation.city}`),
        makeText('p', `Deliver to: ${item.delivery_address}, ${item.delivery_city}`),
        makeText('p', `Request reference: ${item.id}`),
        makeText('p', item.message || 'No additional message')
    );

    if (user.role === 'donor' && item.status === 'pending') {
        const actions = document.createElement('div');
        actions.className = 'offer-meta';
        const approve = makeText('button', 'Approve request', 'offer-request');
        const reject = makeText('button', 'Reject request', 'offer-request');
        approve.type = reject.type = 'button';
        approve.addEventListener('click', () => decide(item.id, 'approved', approve, reject));
        reject.addEventListener('click', () => decide(item.id, 'rejected', approve, reject));
        actions.append(approve, reject);
        content.append(actions);
    }

    if (user.role === 'delivery_partner' && item.status === 'approved' && !item.delivery_partner_id) {
        const claim = makeText('button', 'Accept delivery', 'offer-request');
        claim.type = 'button';
        claim.addEventListener('click', async () => {
            claim.disabled = true;
            try {
                await AnnadanAPI.request(`/requests/${item.id}/claim`, { method: 'POST' });
                window.location.reload();
            } catch (error) {
                claim.disabled = false;
                window.alert(error.message);
            }
        });
        content.append(claim);
    }

    if (user.role === 'delivery_partner' && item.delivery_partner_id === user.id) {
        const nextStatus = item.status === 'assigned' ? 'picked_up'
            : (item.status === 'picked_up' ? 'delivered' : null);
        if (nextStatus) {
            const update = makeText('button', nextStatus === 'picked_up' ? 'Mark as picked up' : 'Mark as delivered', 'offer-request');
            update.type = 'button';
            update.addEventListener('click', async () => {
                update.disabled = true;
                try {
                    await AnnadanAPI.request(`/requests/${item.id}/status`, {
                        method: 'PATCH',
                        body: JSON.stringify({ status: nextStatus, note: '' }),
                    });
                    window.location.reload();
                } catch (error) {
                    update.disabled = false;
                    window.alert(error.message);
                }
            });
            content.append(update);
        }
    }

    card.append(icon, content);
    return card;
}

async function decide(requestId, decision, approveButton, rejectButton) {
    approveButton.disabled = rejectButton.disabled = true;
    try {
        await AnnadanAPI.request(`/requests/${requestId}/decision`, {
            method: 'PATCH',
            body: JSON.stringify({ decision, note: '' }),
        });
        window.location.reload();
    } catch (error) {
        approveButton.disabled = rejectButton.disabled = false;
        window.alert(error.message);
    }
}

(async function loadRequests() {
    try {
        const user = await AnnadanAPI.currentUser();
        if (!user) {
            requestsList.append(makeText('p', 'Sign in to view your requests.'));
            requestsList.append(makeText('a', 'Sign in', 'profile-home-link')).href = 'login.html';
            return;
        }

        const heading = user.role === 'donor' ? 'Requests for your donations'
            : user.role === 'delivery_partner' ? 'Your delivery assignments'
                : 'Your food requests';
        requestsList.append(makeText('h2', heading));

        const mine = await AnnadanAPI.request('/requests/mine');
        if (mine.length) mine.forEach((item) => requestsList.append(makeRequestCard(item, user)));

        if (user.role === 'delivery_partner') {
            requestsList.append(makeText('h2', 'Available deliveries'));
            const available = await AnnadanAPI.request('/requests/available-deliveries');
            available.forEach((item) => requestsList.append(makeRequestCard(item, user)));
        }

        if (!mine.length && user.role !== 'delivery_partner') {
            requestsList.append(makeText('p', 'No requests have been recorded for this account yet.'));
        }
    } catch (error) {
        requestsList.append(makeText('p', error.message));
    }
})();
