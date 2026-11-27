const donationForm = document.querySelector('#donation-form');
const donationMessage = document.querySelector('#donation-message');
const donationSubmit = donationForm.querySelector('button[type="submit"]');
const imageInput = document.querySelector('#donation-image');
const locationButton = document.querySelector('#use-pickup-location');
const locationStatus = document.querySelector('#pickup-location-status');
let pickupCoordinates = null;

(async function checkDonorAccess() {
    try {
        const user = await AnnadanAPI.currentUser();
        if (!user) return window.location.href = 'login.html';
        if (user.role !== 'donor' && user.role !== 'admin') {
            donationForm.hidden = true;
            donationMessage.textContent = 'Only donor accounts can publish food donations.';
        }
    } catch (_error) {
        window.location.href = 'login.html';
    }
})();

locationButton.addEventListener('click', () => {
    if (!navigator.geolocation) {
        locationStatus.textContent = 'This browser does not support location sharing.';
        return;
    }
    locationStatus.textContent = 'Waiting for location permission…';
    navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
            pickupCoordinates = { latitude: coords.latitude, longitude: coords.longitude };
            locationStatus.textContent = 'Pickup coordinates attached. You can remove them by refreshing the page.';
        },
        () => locationStatus.textContent = 'Location was not shared. You can still publish the donation.',
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
    );
});

donationForm.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (!donationForm.reportValidity()) return;

    const data = new FormData(donationForm);
    const allergenText = String(data.get('allergens') || '');
    const pickupDeadline = new Date(String(data.get('pickup_deadline')));
    const preparedAtValue = String(data.get('prepared_at') || '');

    donationSubmit.disabled = true;
    donationSubmit.textContent = 'Publishing…';
    donationMessage.textContent = '';

    try {
        let imageUrl = null;
        const imageFile = imageInput.files[0];
        if (imageFile) {
            const uploadData = new FormData();
            uploadData.append('image', imageFile);
            const upload = await AnnadanAPI.request('/uploads/donation-image', {
                method: 'POST',
                body: uploadData,
            });
            imageUrl = upload.image_url;
        }

        const payload = {
            title: String(data.get('title')).trim(),
            description: String(data.get('description')).trim(),
            food_type: String(data.get('food_type')),
            quantity_total: Number(data.get('quantity_total')),
            quantity_unit: String(data.get('quantity_unit')),
            pickup_location: String(data.get('pickup_location')).trim(),
            city: String(data.get('city')).trim(),
            pickup_deadline: pickupDeadline.toISOString(),
            prepared_at: preparedAtValue ? new Date(preparedAtValue).toISOString() : null,
            allergens: allergenText.split(',').map((value) => value.trim()).filter(Boolean),
            is_vegetarian: data.get('is_vegetarian') === 'on',
            image_url: imageUrl,
            latitude: pickupCoordinates?.latitude ?? null,
            longitude: pickupCoordinates?.longitude ?? null,
            safety_checklist: {
                sealed_packaging: data.get('sealed_packaging') === 'on',
                allergens_disclosed: data.get('allergens_disclosed') === 'on',
                safe_handling: data.get('safe_handling') === 'on',
                pickup_window_valid: data.get('pickup_window_valid') === 'on',
            },
        };
        const donation = await AnnadanAPI.request('/donations', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        donationMessage.textContent = donation.safety_status === 'pending'
            ? `Donation submitted for food-safety review. Reference: ${donation.id}`
            : `Donation published. Reference: ${donation.id}`;
        donationForm.reset();
        pickupCoordinates = null;
        locationStatus.textContent = 'Coordinates are optional and are shared with approved receivers.';
    } catch (error) {
        donationMessage.textContent = error.message;
    } finally {
        donationSubmit.disabled = false;
        donationSubmit.textContent = 'Publish donation';
    }
});
