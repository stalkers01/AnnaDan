const offerList = document.querySelector('#offer-list');
const quantityLabels = {
    meal_boxes: 'meal boxes',
    packets: 'packets',
    kg: 'kg',
    litres: 'litres',
    portions: 'portions',
};

function createOfferCard(donation) {
    const card = document.createElement('article');
    card.className = 'offer-card';

    const icon = document.createElement('div');
    icon.className = 'offer-icon';
    icon.textContent = donation.is_vegetarian ? '🥗' : '🍱';

    const main = document.createElement('div');
    main.className = 'offer-main';
    if (donation.image_url) {
        const image = document.createElement('img');
        image.src = donation.image_url;
        image.alt = `Food donation: ${donation.title}`;
        image.loading = 'lazy';
        image.className = 'donation-card-image';
        main.append(image);
    }

    const heading = document.createElement('div');
    heading.className = 'offer-heading';
    const title = document.createElement('h2');
    title.textContent = `${donation.quantity_available} ${quantityLabels[donation.quantity_unit] || donation.quantity_unit} – ${donation.title}`;
    const status = document.createElement('span');
    status.textContent = 'Available';
    heading.append(title, status);

    const place = document.createElement('p');
    place.className = 'offer-place';
    place.textContent = `📍 ${donation.pickup_location}, ${donation.city}`;

    const description = document.createElement('p');
    description.textContent = donation.description;

    const meta = document.createElement('div');
    meta.className = 'offer-meta';
    const deadline = new Date(donation.pickup_deadline).toLocaleString();
    const pickup = document.createElement('span');
    pickup.textContent = `Pickup by ${deadline}`;
    const allergens = document.createElement('span');
    allergens.textContent = donation.allergens.length
        ? `Allergens: ${donation.allergens.join(', ')}`
        : 'Allergens: not listed';
    meta.append(pickup, allergens);

    const button = document.createElement('button');
    button.className = 'offer-request';
    button.type = 'button';
    button.textContent = 'Request Now';
    button.addEventListener('click', () => requestDonation(donation, button));

    main.append(heading, place, description, meta, button);
    card.append(icon, main);
    return card;
}

async function requestDonation(donation, button) {
    const content = button.closest('.offer-main');
    const status = document.createElement('p');
    status.className = 'offer-request-status';
    status.setAttribute('role', 'status');

    try {
        const user = await AnnadanAPI.currentUser();
        if (!user) {
            status.textContent = 'Sign in as a receiver or NGO to request this donation.';
            const signIn = document.createElement('a');
            signIn.href = 'login.html';
            signIn.textContent = ' Sign in';
            status.append(signIn);
            content.append(status);
            return;
        }
        if (user.role !== 'receiver') {
            status.textContent = 'Only receiver or NGO accounts can request food.';
            content.append(status);
            return;
        }

        button.hidden = true;
        const form = document.createElement('form');
        form.className = 'request-inline-form';

        const quantityLabel = document.createElement('label');
        quantityLabel.textContent = `Quantity (${quantityLabels[donation.quantity_unit] || donation.quantity_unit})`;
        const quantityInput = document.createElement('input');
        quantityInput.name = 'quantity';
        quantityInput.type = 'number';
        quantityInput.min = '1';
        quantityInput.max = String(donation.quantity_available);
        quantityInput.value = '1';
        quantityInput.required = true;
        quantityLabel.append(quantityInput);

        const addressLabel = document.createElement('label');
        addressLabel.textContent = 'Delivery address';
        const addressInput = document.createElement('input');
        addressInput.name = 'delivery_address';
        addressInput.type = 'text';
        addressInput.maxLength = 255;
        addressInput.placeholder = 'Street, building and area';
        addressInput.required = true;
        addressLabel.append(addressInput);

        const cityLabel = document.createElement('label');
        cityLabel.textContent = 'Delivery city';
        const cityInput = document.createElement('input');
        cityInput.name = 'delivery_city';
        cityInput.type = 'text';
        cityInput.maxLength = 100;
        cityInput.placeholder = 'City';
        cityInput.required = true;
        cityLabel.append(cityInput);

        let deliveryCoordinates = null;
        const locationButton = document.createElement('button');
        locationButton.type = 'button';
        locationButton.className = 'request-cancel';
        locationButton.textContent = 'Attach my delivery location (optional)';
        locationButton.addEventListener('click', () => {
            if (!navigator.geolocation) {
                status.textContent = 'This browser does not support location sharing.';
                return;
            }
            navigator.geolocation.getCurrentPosition(({ coords }) => {
                deliveryCoordinates = { delivery_latitude: coords.latitude, delivery_longitude: coords.longitude };
                status.textContent = 'Delivery coordinates attached to this request.';
            }, () => status.textContent = 'Location was not shared. You can submit the request without it.');
        });

        const messageLabel = document.createElement('label');
        messageLabel.textContent = 'Message (optional)';
        const messageInput = document.createElement('textarea');
        messageInput.name = 'message';
        messageInput.maxLength = 500;
        messageInput.rows = 2;
        messageInput.placeholder = 'Any pickup or delivery details';
        messageLabel.append(messageInput);

        const submit = document.createElement('button');
        submit.type = 'submit';
        submit.className = 'offer-request';
        submit.textContent = 'Send food request';
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'request-cancel';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', () => {
            form.remove();
            button.hidden = false;
        });

        form.append(quantityLabel, addressLabel, cityLabel, locationButton, messageLabel, submit, cancel);
        content.append(form);

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            submit.disabled = true;
            submit.textContent = 'Sending…';
            const data = new FormData(form);
            try {
                const result = await AnnadanAPI.request(`/requests/donations/${donation.id}`, {
                    method: 'POST',
                    body: JSON.stringify({
                        quantity: Number(data.get('quantity')),
                        delivery_address: String(data.get('delivery_address')).trim(),
                        delivery_city: String(data.get('delivery_city')).trim(),
                        message: String(data.get('message') || '').trim(),
                        ...(deliveryCoordinates || {}),
                    }),
                });
                form.remove();
                status.textContent = `Request submitted. Reference: ${result.id}`;
                content.append(status);
            } catch (error) {
                status.textContent = error.message;
                submit.disabled = false;
                submit.textContent = 'Send food request';
                form.append(status);
            }
        });
    } catch (error) {
        status.textContent = error.message;
        content.append(status);
    }
}

async function loadDonations(city = '') {
    offerList.replaceChildren(Object.assign(document.createElement('p'), { textContent: 'Loading available donations…' }));
    try {
        const query = city ? `?city=${encodeURIComponent(city)}` : '';
        const donations = await AnnadanAPI.request(`/donations${query}`);
        offerList.replaceChildren();
        if (!donations.length) {
            const empty = document.createElement('p');
            empty.className = 'demo-note';
            empty.textContent = 'There are no available donations for this search right now.';
            offerList.append(empty);
            return;
        }
        donations.forEach((donation) => offerList.append(createOfferCard(donation)));
    } catch (error) {
        offerList.textContent = error.message;
    }
}

const cityFilter = document.querySelector('#donation-city-filter');
cityFilter.addEventListener('submit', (event) => {
    event.preventDefault();
    loadDonations(cityFilter.elements.city.value.trim());
});

loadDonations();
