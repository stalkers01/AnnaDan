from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.models.entities import User
from app.models.enums import UserRole


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    app.state.testing_session_factory = TestingSession
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def register(client, role, email):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role}",
            "email": email,
            "phone": "+919999999999",
            "password": "TestPassword!123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def headers(auth_response):
    return {"Authorization": f"Bearer {auth_response['access_token']}"}


def test_public_signup_cannot_create_admin(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Untrusted Admin",
            "email": "attacker@example.com",
            "phone": "9999999999",
            "password": "TestPassword!123",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_complete_donation_and_delivery_workflow(client):
    donor = register(client, "donor", "donor@example.com")
    receiver = register(client, "receiver", "receiver@example.com")
    driver = register(client, "delivery_partner", "driver@example.com")

    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    donation_response = client.post(
        "/api/v1/donations",
        headers=headers(donor),
        json={
            "title": "Fresh vegetable meal boxes",
            "description": "Freshly cooked vegetarian meals in sealed boxes.",
            "food_type": "prepared_food",
            "quantity_total": 12,
            "quantity_unit": "meal_boxes",
            "pickup_location": "Community Kitchen, Main Gate",
            "city": "Kolkata",
            "pickup_deadline": deadline,
            "allergens": ["milk"],
            "is_vegetarian": True,
        },
    )
    assert donation_response.status_code == 201, donation_response.text
    donation = donation_response.json()

    public_list = client.get("/api/v1/donations")
    assert public_list.status_code == 200
    assert len(public_list.json()) == 1

    request_response = client.post(
        f"/api/v1/requests/donations/{donation['id']}",
        headers=headers(receiver),
        json={"quantity": 5, "delivery_address": "12 Shelter Road, Salt Lake", "delivery_city": "Kolkata", "message": "Needed for our evening shelter meal."},
    )
    assert request_response.status_code == 201, request_response.text
    food_request = request_response.json()
    request_id = food_request["id"]
    assert food_request["status"] == "pending"
    assert food_request["delivery_address"] == "12 Shelter Road, Salt Lake"
    assert food_request["delivery_city"] == "Kolkata"

    decision = client.patch(
        f"/api/v1/requests/{request_id}/decision",
        headers=headers(donor),
        json={"decision": "approved", "note": "Ready for pickup."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"
    assert decision.json()["donation"]["quantity_available"] == 7

    available = client.get(
        "/api/v1/requests/available-deliveries",
        headers=headers(driver),
    )
    assert available.status_code == 200
    assert len(available.json()) == 1

    claimed = client.post(
        f"/api/v1/requests/{request_id}/claim",
        headers=headers(driver),
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "assigned"

    picked_up = client.patch(
        f"/api/v1/requests/{request_id}/status",
        headers=headers(driver),
        json={"status": "picked_up", "note": "Collected from the kitchen."},
    )
    assert picked_up.status_code == 200, picked_up.text
    assert picked_up.json()["status"] == "picked_up"

    live_location = client.post(
        f"/api/v1/requests/{request_id}/location",
        headers=headers(driver),
        json={"latitude": 22.5726, "longitude": 88.3639, "accuracy_m": 12.5},
    )
    assert live_location.status_code == 200, live_location.text
    assert live_location.json()["latitude"] == 22.5726

    receiver_location = client.get(
        f"/api/v1/requests/{request_id}/location",
        headers=headers(receiver),
    )
    assert receiver_location.status_code == 200

    delivered = client.patch(
        f"/api/v1/requests/{request_id}/status",
        headers=headers(driver),
        json={"status": "delivered", "note": "Received by the shelter."},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"

    location_after_delivery = client.get(
        f"/api/v1/requests/{request_id}/location",
        headers=headers(receiver),
    )
    assert location_after_delivery.status_code == 404

    tracking = client.get(
        f"/api/v1/requests/{request_id}/tracking",
        headers=headers(receiver),
    )
    assert tracking.status_code == 200, tracking.text
    assert [event["status"] for event in tracking.json()["timeline"]] == [
        "pending", "approved", "assigned", "picked_up", "delivered"
    ]

    impact = client.get("/api/v1/impact")
    assert impact.status_code == 200
    assert impact.json()["meals_delivered"] == 5

    feedback = client.post(
        "/api/v1/users/ratings",
        headers=headers(receiver),
        json={
            "request_id": request_id,
            "topic": "Overall experience",
            "score": 5,
            "comment": "The handover was completed successfully.",
        },
    )
    assert feedback.status_code == 201, feedback.text

    duplicate_feedback = client.post(
        "/api/v1/users/ratings",
        headers=headers(receiver),
        json={
            "request_id": request_id,
            "topic": "Overall experience",
            "score": 4,
            "comment": "Duplicate feedback should be blocked.",
        },
    )
    assert duplicate_feedback.status_code == 409


def test_quantity_cannot_be_approved_twice(client):
    donor = register(client, "donor", "quantity-donor@example.com")
    receiver_one = register(client, "receiver", "receiver-one@example.com")
    receiver_two = register(client, "receiver", "receiver-two@example.com")

    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    donation = client.post(
        "/api/v1/donations",
        headers=headers(donor),
        json={
            "title": "Three meal packs",
            "description": "Three sealed meal packs for same-day collection.",
            "quantity_total": 3,
            "quantity_unit": "meal_boxes",
            "pickup_location": "Community kitchen",
            "city": "Kolkata",
            "pickup_deadline": deadline,
        },
    ).json()

    requests = []
    for receiver in (receiver_one, receiver_two):
        response = client.post(
            f"/api/v1/requests/donations/{donation['id']}",
            headers=headers(receiver),
            json={"quantity": 2, "delivery_address": "18 Community Lane", "delivery_city": "Kolkata"},
        )
        assert response.status_code == 201, response.text
        requests.append(response.json()["id"])

    first_approval = client.patch(
        f"/api/v1/requests/{requests[0]}/decision",
        headers=headers(donor),
        json={"decision": "approved"},
    )
    assert first_approval.status_code == 200

    second_approval = client.patch(
        f"/api/v1/requests/{requests[1]}/decision",
        headers=headers(donor),
        json={"decision": "approved"},
    )
    assert second_approval.status_code == 409

    current_donation = client.get(f"/api/v1/donations/{donation['id']}")
    assert current_donation.status_code == 200
    assert current_donation.json()["quantity_available"] == 1


def test_request_decision_and_tracking_are_access_controlled(client):
    donor = register(client, "donor", "owner@example.com")
    other_donor = register(client, "donor", "other-owner@example.com")
    receiver = register(client, "receiver", "private-receiver@example.com")
    outsider = register(client, "receiver", "outsider@example.com")

    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    donation = client.post(
        "/api/v1/donations",
        headers=headers(donor),
        json={
            "title": "Fresh fruit packs",
            "description": "Fresh fruit packs prepared for collection.",
            "quantity_total": 5,
            "quantity_unit": "packets",
            "pickup_location": "Food bank reception",
            "city": "Kolkata",
            "pickup_deadline": deadline,
        },
    ).json()
    food_request = client.post(
        f"/api/v1/requests/donations/{donation['id']}",
        headers=headers(receiver),
        json={"quantity": 1, "delivery_address": "44 Food Bank Street", "delivery_city": "Kolkata"},
    ).json()

    forbidden_decision = client.patch(
        f"/api/v1/requests/{food_request['id']}/decision",
        headers=headers(other_donor),
        json={"decision": "approved"},
    )
    assert forbidden_decision.status_code == 403

    forbidden_tracking = client.get(
        f"/api/v1/requests/{food_request['id']}/tracking",
        headers=headers(outsider),
    )
    assert forbidden_tracking.status_code == 403


def test_sign_in_and_admin_routes_require_privileged_account(client):
    account = register(client, "receiver", "signin@example.com")

    sign_in = client.post(
        "/api/v1/auth/login",
        json={"email": "signin@example.com", "password": "TestPassword!123"},
    )
    assert sign_in.status_code == 200
    assert sign_in.json()["user"]["id"] == account["user"]["id"]

    invalid_sign_in = client.post(
        "/api/v1/auth/login",
        json={"email": "signin@example.com", "password": "incorrect-password"},
    )
    assert invalid_sign_in.status_code == 401

    admin_route = client.get("/api/v1/admin/overview", headers=headers(account))
    assert admin_route.status_code == 403

    current_user = client.get("/api/v1/auth/me", headers=headers(sign_in.json()))
    assert current_user.status_code == 200
    assert current_user.json()["role"] == "receiver"


def create_test_admin(client):
    session_factory = client.app.state.testing_session_factory
    with session_factory() as db:
        admin = User(
            full_name="Test Administrator",
            email="test-admin@example.com",
            phone="+919999999998",
            password_hash=hash_password("AdminPassword!123"),
            role=UserRole.ADMIN,
            is_active=True,
            email_verified=True,
            phone_verified=True,
            settings={},
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return {"access_token": __import__("app.core.security", fromlist=["create_access_token"]).create_access_token(admin.id)}


def test_food_safety_review_gates_public_donations(client):
    previous_setting = settings.require_safety_review
    settings.require_safety_review = True
    try:
        donor = register(client, "donor", "safety-donor@example.com")
        admin = create_test_admin(client)
        deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        donation_response = client.post(
            "/api/v1/donations",
            headers=headers(donor),
            json={
                "title": "Sealed rice meal boxes",
                "description": "Freshly prepared rice and lentil meals in sealed packs.",
                "quantity_total": 10,
                "quantity_unit": "meal_boxes",
                "pickup_location": "Community Kitchen",
                "city": "Kolkata",
                "pickup_deadline": deadline,
                "safety_checklist": {
                    "sealed_packaging": True,
                    "allergens_disclosed": True,
                    "safe_handling": True,
                    "pickup_window_valid": True,
                },
            },
        )
        assert donation_response.status_code == 201, donation_response.text
        donation = donation_response.json()
        assert donation["safety_status"] == "pending"
        assert client.get("/api/v1/donations").json() == []

        queue = client.get("/api/v1/admin/safety/pending", headers=headers(admin))
        assert queue.status_code == 200
        assert len(queue.json()) == 1

        review = client.patch(
            f"/api/v1/admin/safety/{donation['id']}",
            headers=headers(admin),
            json={"decision": "approved", "note": "Checklist reviewed."},
        )
        assert review.status_code == 200, review.text
        assert review.json()["safety_status"] == "approved"
        assert len(client.get("/api/v1/donations").json()) == 1
    finally:
        settings.require_safety_review = previous_setting


def test_email_password_reset_uses_single_use_otp(client):
    previous_exposure = settings.expose_otp_in_development
    settings.expose_otp_in_development = True
    try:
        register(client, "receiver", "reset-user@example.com")
        forgot = client.post("/api/v1/auth/password/forgot", json={"email": "reset-user@example.com"})
        assert forgot.status_code == 200
        code = forgot.json().get("development_code")
        assert code and len(code) == 6

        reset = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "reset-user@example.com", "code": code, "new_password": "ChangedPassword!456"},
        )
        assert reset.status_code == 200, reset.text
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "reset-user@example.com", "password": "ChangedPassword!456"},
        )
        assert login.status_code == 200
        replay = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "reset-user@example.com", "code": code, "new_password": "AnotherPassword!456"},
        )
        assert replay.status_code == 400
    finally:
        settings.expose_otp_in_development = previous_exposure


def test_optional_integrations_fail_closed_without_provider_keys(client):
    assert client.get("/api/v1/payments/config").json()["enabled"] is False
    donor = register(client, "donor", "upload-user@example.com")
    upload = client.post(
        "/api/v1/uploads/donation-image",
        headers=headers(donor),
        files={"image": ("food.png", b"not-a-real-image", "image/png")},
    )
    assert upload.status_code == 503
