const locationButton = document.querySelector('#location-button');
const locationStatus = document.querySelector('#location-status');
const trackingButton = document.querySelector('#tracking-button');
const trackingIdInput = document.querySelector('#tracking-id');
const trackingStatus = document.querySelector('#tracking-status');
const trackingPreview = document.querySelector('#tracking-preview');
const timeline = document.querySelector('#tracking-timeline');
const shareRequestId = document.querySelector('#share-request-id');
const startSharingButton = document.querySelector('#start-location-sharing');
const stopSharingButton = document.querySelector('#stop-location-sharing');
const liveLocationStatus = document.querySelector('#live-location-status');
let gpsWatchId = null;
let lastLocationSentAt = 0;
let activeTrackingTimer = null;
let map = null;
let partnerMarker = null;
let receiverMarker = null;

if (locationButton) {
    locationButton.addEventListener('click', function () {
        if (!navigator.geolocation) {
            locationStatus.textContent = 'Location services are not available in this browser.';
            return;
        }
        locationStatus.textContent = 'Waiting for location permission…';
        navigator.geolocation.getCurrentPosition(
            (position) => {
                locationStatus.textContent = `Your location is available for this session. Latitude ${position.coords.latitude.toFixed(4)}, longitude ${position.coords.longitude.toFixed(4)}.`;
            },
            () => locationStatus.textContent = 'Location was not shared. You can still browse all available donations.',
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
        );
    });
}

let mapProvider = null;
let mapInitialization = null;

function loadGoogleMaps() {
    if (window.google && window.google.maps) return Promise.resolve(true);
    const apiKey = window.ANNADAN_GOOGLE_MAPS_API_KEY;
    if (!apiKey) return Promise.resolve(false);

    return new Promise((resolve) => {
        window.annadanGoogleMapsReady = () => resolve(true);
        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&callback=annadanGoogleMapsReady&v=weekly`;
        script.async = true;
        script.onerror = () => resolve(false);
        document.head.append(script);
    });
}

async function ensureMap() {
    if (map) return map;
    if (!mapInitialization) {
        mapInitialization = (async () => {
            const element = document.querySelector('#delivery-map');
            if (!element) return null;

            if (await loadGoogleMaps()) {
                mapProvider = 'google';
                map = new google.maps.Map(element, {
                    center: { lat: 22.5726, lng: 88.3639 },
                    zoom: 12,
                    mapTypeControl: false,
                    streetViewControl: false,
                    fullscreenControl: true,
                });
                return map;
            }

            if (!window.L) return null;
            mapProvider = 'leaflet';
            map = L.map(element).setView([22.5726, 88.3639], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors',
            }).addTo(map);
            return map;
        })();
    }
    return mapInitialization;
}

async function updateMapPoint(kind, latitude, longitude, label) {
    const currentMap = await ensureMap();
    if (!currentMap) return;

    if (mapProvider === 'google') {
        const position = { lat: latitude, lng: longitude };
        const markerRef = kind === 'partner' ? 'partnerGoogleMarker' : 'receiverGoogleMarker';
        const existing = window[markerRef];
        if (existing) {
            existing.setPosition(position);
            existing.setTitle(label);
        } else {
            window[markerRef] = new google.maps.Marker({
                map: currentMap,
                position,
                title: label,
            });
        }
        currentMap.setCenter(position);
        currentMap.setZoom(Math.max(currentMap.getZoom() || 12, 14));
        return;
    }

    const point = [latitude, longitude];
    if (kind === 'partner') {
        if (!partnerMarker) partnerMarker = L.marker(point).addTo(currentMap).bindPopup(label);
        else partnerMarker.setLatLng(point);
        partnerMarker.setPopupContent(label);
    } else {
        if (!receiverMarker) receiverMarker = L.marker(point).addTo(currentMap).bindPopup(label);
        else receiverMarker.setLatLng(point);
    }
    currentMap.setView(point, Math.max(currentMap.getZoom(), 14));
}

function stopTrackingPoll() {
    if (activeTrackingTimer) window.clearInterval(activeTrackingTimer);
    activeTrackingTimer = null;
}

async function refreshLiveLocation(requestId) {
    try {
        const current = await AnnadanAPI.request(`/requests/${encodeURIComponent(requestId)}/location`);
        updateMapPoint('partner', current.latitude, current.longitude,
            `Delivery partner • Updated ${new Date(current.updated_at).toLocaleTimeString()}`);
        trackingStatus.textContent = `Live location updated at ${new Date(current.updated_at).toLocaleTimeString()}.`;
    } catch (error) {
        if (!/has not shared a location yet/i.test(error.message)) {
            trackingStatus.textContent = error.message;
        }
    }
}

async function loadTracking() {
    const requestId = trackingIdInput.value.trim();
    if (!requestId) {
        trackingPreview.hidden = true;
        trackingStatus.textContent = 'Enter a request ID to see its tracking history.';
        trackingIdInput.focus();
        return;
    }
    try {
        const result = await AnnadanAPI.request(`/requests/${encodeURIComponent(requestId)}/tracking`);
        document.querySelector('#tracking-request-label').textContent = result.request_id;
        timeline.replaceChildren();
        result.timeline.forEach((event) => {
            const item = document.createElement('li');
            item.className = 'complete';
            const title = document.createElement('strong');
            title.textContent = event.status.replaceAll('_', ' ');
            const note = document.createElement('small');
            note.textContent = `${event.note || 'Status updated'} — ${new Date(event.created_at).toLocaleString()}`;
            item.append(title, note);
            timeline.append(item);
        });
        trackingPreview.hidden = false;
        trackingStatus.textContent = `Current status: ${result.status.replaceAll('_', ' ')}.`;
        if (result.delivery_latitude !== null && result.delivery_longitude !== null) {
            updateMapPoint('receiver', result.delivery_latitude, result.delivery_longitude, 'Receiver delivery point');
        }
        await refreshLiveLocation(requestId);
        stopTrackingPoll();
        if (['assigned', 'picked_up'].includes(result.status)) {
            activeTrackingTimer = window.setInterval(() => refreshLiveLocation(requestId), 10000);
        }
    } catch (error) {
        trackingPreview.hidden = true;
        trackingStatus.textContent = error.message;
        stopTrackingPoll();
    }
}

if (trackingButton) trackingButton.addEventListener('click', loadTracking);
if (trackingIdInput) trackingIdInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        loadTracking();
    }
});

async function sendPartnerLocation(requestId, position) {
    const now = Date.now();
    if (now - lastLocationSentAt < 9000) return;
    lastLocationSentAt = now;
    try {
        await AnnadanAPI.request(`/requests/${encodeURIComponent(requestId)}/location`, {
            method: 'POST',
            body: JSON.stringify({
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy_m: position.coords.accuracy,
            }),
        });
        liveLocationStatus.textContent = `Location shared at ${new Date().toLocaleTimeString()}. Keep this page open during the handover.`;
        updateMapPoint('partner', position.coords.latitude, position.coords.longitude, 'Your shared delivery location');
    } catch (error) {
        liveLocationStatus.textContent = error.message;
        stopLocationSharing();
    }
}

function stopLocationSharing() {
    if (gpsWatchId !== null) navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
    startSharingButton.disabled = false;
    stopSharingButton.disabled = true;
    liveLocationStatus.textContent = 'Location sharing is off.';
}

if (startSharingButton) {
    startSharingButton.addEventListener('click', async () => {
        const requestId = shareRequestId.value.trim();
        if (!requestId) {
            liveLocationStatus.textContent = 'Enter the request ID assigned to you first.';
            return;
        }
        if (!navigator.geolocation) {
            liveLocationStatus.textContent = 'This browser does not support GPS location.';
            return;
        }
        try {
            const user = await AnnadanAPI.currentUser();
            if (!user || user.role !== 'delivery_partner') {
                liveLocationStatus.textContent = 'Sign in with the assigned delivery-partner account to share location.';
                return;
            }
            startSharingButton.disabled = true;
            stopSharingButton.disabled = false;
            liveLocationStatus.textContent = 'Waiting for GPS permission…';
            gpsWatchId = navigator.geolocation.watchPosition(
                (position) => sendPartnerLocation(requestId, position),
                (error) => {
                    liveLocationStatus.textContent = `GPS error: ${error.message}`;
                    stopLocationSharing();
                },
                { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
            );
        } catch (error) {
            liveLocationStatus.textContent = error.message;
            startSharingButton.disabled = false;
        }
    });
}
if (stopSharingButton) stopSharingButton.addEventListener('click', stopLocationSharing);
window.addEventListener('beforeunload', () => {
    stopTrackingPoll();
    if (gpsWatchId !== null) navigator.geolocation.clearWatch(gpsWatchId);
});

const ratingForm = document.querySelector('#rating-form');
if (ratingForm) {
    const ratingCaption = document.querySelector('#rating-caption');
    const ratingStatus = document.querySelector('#rating-status');
    const ratingChoices = ratingForm.querySelectorAll('input[name="rating"]');
    ratingChoices.forEach((choice) => {
        choice.addEventListener('change', () => {
            const selectedRating = Number(choice.value);
            ratingChoices.forEach((option) => option.closest('label').classList.toggle('selected', Number(option.value) <= selectedRating));
            ratingCaption.textContent = `${selectedRating} out of 5 stars`;
        });
    });
    ratingForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        const formData = new FormData(ratingForm);
        const requestId = String(formData.get('requestId') || '').trim();
        if (!requestId) {
            ratingStatus.textContent = 'Enter the delivered request ID before submitting feedback.';
            return;
        }
        try {
            await AnnadanAPI.request('/users/ratings', {
                method: 'POST',
                body: JSON.stringify({
                    request_id: requestId,
                    topic: formData.get('topic'),
                    score: Number(formData.get('rating')),
                    comment: String(formData.get('comment') || '').trim(),
                }),
            });
            ratingStatus.textContent = 'Thank you. Your feedback has been saved to Annadan.';
            ratingForm.reset();
            ratingChoices.forEach((choice) => choice.closest('label').classList.remove('selected'));
            ratingCaption.textContent = 'Select a rating from 1 to 5.';
        } catch (error) {
            ratingStatus.textContent = error.message;
        }
    });
}
