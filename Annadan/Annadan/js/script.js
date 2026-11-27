const searchBox = document.querySelector('.search-box input');
const donationSection = document.querySelector('.donations-section');
const foodList = document.querySelector('#home-donation-list');
const noResults = document.createElement('p');
noResults.className = 'empty-message';
noResults.textContent = 'No available donations match your search.';
noResults.hidden = true;
donationSection.append(noResults);

let currentDonations = [];

function renderHomeDonations() {
    const searchText = searchBox.value.trim().toLowerCase();
    foodList.replaceChildren();
    let visibleCount = 0;

    currentDonations
        .filter((item) => `${item.title} ${item.description} ${item.city} ${item.pickup_location}`.toLowerCase().includes(searchText))
        .slice(0, 3)
        .forEach((item) => {
            visibleCount += 1;
            const card = document.createElement('div');
            card.className = 'food-item';
            const details = document.createElement('div');
            details.className = 'food-details';
            const title = document.createElement('h3');
            title.textContent = `${item.quantity_available} ${item.quantity_unit.replaceAll('_', ' ')} – ${item.title}`;
            const location = document.createElement('p');
            location.textContent = `📍 ${item.pickup_location}, ${item.city}`;
            const deadline = document.createElement('p');
            deadline.textContent = `Pickup by ${new Date(item.pickup_deadline).toLocaleString()}`;
            details.append(title, location, deadline);
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = 'View donation';
            button.addEventListener('click', () => window.location.href = 'donations.html');
            card.append(details, button);
            foodList.append(card);
        });

    noResults.hidden = visibleCount > 0;
}

searchBox.addEventListener('input', renderHomeDonations);

document.querySelector('.primary-btn').addEventListener('click', async () => {
    try {
        const user = await AnnadanAPI.currentUser();
        const destinations = {
            admin: 'admin.html',
            donor: 'create-donation.html',
            receiver: 'donations.html',
            delivery_partner: 'requests.html',
        };
        window.location.href = user ? destinations[user.role] || 'login.html' : 'login.html';
    } catch (_error) {
        window.location.href = 'login.html';
    }
});

document.querySelector('.secondary-btn').addEventListener('click', () => {
    window.location.href = 'donations.html';
});

document.querySelector('.section-heading a').addEventListener('click', (event) => {
    event.preventDefault();
    window.location.href = 'donations.html';
});

(async function loadHomeData() {
    try {
        const [donations, impact] = await Promise.all([
            AnnadanAPI.request('/donations'),
            AnnadanAPI.request('/impact'),
        ]);
        currentDonations = donations;
        renderHomeDonations();
        const stats = document.querySelectorAll('[data-home-impact]');
        stats.forEach((element) => {
            const key = element.dataset.homeImpact;
            element.textContent = impact[key] ?? 0;
        });
    } catch (error) {
        foodList.textContent = error.message;
    }
})();
