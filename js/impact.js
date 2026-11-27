(async function loadImpact() {
    try {
        const impact = await AnnadanAPI.request('/impact');
        document.querySelector('[data-impact="meals"]').textContent = impact.meals_delivered.toLocaleString();
        document.querySelector('[data-impact="donations"]').textContent = impact.active_donations.toLocaleString();
        document.querySelector('[data-impact="requests"]').textContent = impact.delivered_requests.toLocaleString();

        const units = Object.entries(impact.food_units_by_type)
            .map(([unit, quantity]) => `${quantity} ${unit.replaceAll('_', ' ')}`)
            .join(', ');
        document.querySelector('#impact-units').textContent = units || 'No completed food handovers recorded yet.';
    } catch (error) {
        document.querySelector('#impact-units').textContent = error.message;
    }
})();


(async function configureSupportPayments() {
    const panel = document.querySelector('#support-annadan');
    const button = document.querySelector('#support-pay-button');
    const status = document.querySelector('#support-payment-status');
    try {
        const config = await AnnadanAPI.request('/payments/config');
        if (!config.enabled) return;
        panel.hidden = false;
        button.addEventListener('click', async () => {
            button.disabled = true;
            status.textContent = 'Creating a secure contribution order…';
            try {
                const user = await AnnadanAPI.currentUser();
                if (!user) {
                    status.textContent = 'Sign in before making a voluntary platform contribution.';
                    window.location.href = 'login.html';
                    return;
                }
                const order = await AnnadanAPI.request('/payments/orders', {
                    method: 'POST',
                    body: JSON.stringify({ amount_inr: Number(document.querySelector('#support-amount').value) }),
                });
                if (!window.Razorpay) {
                    await new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        script.src = 'https://checkout.razorpay.com/v1/checkout.js';
                        script.onload = resolve;
                        script.onerror = reject;
                        document.head.append(script);
                    });
                }
                const checkout = new Razorpay({
                    key: order.key_id,
                    amount: order.amount_paise,
                    currency: order.currency,
                    name: 'Annadan',
                    description: 'Voluntary platform contribution',
                    order_id: order.order_id,
                    prefill: { name: user.full_name, email: user.email, contact: user.phone },
                    theme: { color: '#24734d' },
                    handler: async (response) => {
                        try {
                            const verified = await AnnadanAPI.request('/payments/verify', {
                                method: 'POST', body: JSON.stringify(response),
                            });
                            status.textContent = verified.message;
                        } catch (error) { status.textContent = error.message; }
                    },
                    modal: { ondismiss: () => { status.textContent = 'Payment window closed. No contribution was confirmed.'; } },
                });
                checkout.open();
                status.textContent = 'Complete the payment in the secure Razorpay window.';
            } catch (error) {
                status.textContent = error.message;
            } finally {
                button.disabled = false;
            }
        });
    } catch (_error) {
        // Payment configuration is optional; impact metrics remain available.
    }
})();
