import pytest
import json
import uuid
from datetime import datetime, timedelta
from app.models import (
    AuthUser,
    Customers,
    Salon,
    Service,
    Product,
    SalonOwners,
    SalonVerify,
)


@pytest.fixture
def cart_fixtures(db_session):
    """
    Creates a complete ecosystem for cart testing:
    - 1 Owner
    - 1 Salon (Approved)
    - 1 Service
    - 1 Product
    - 1 Customer (User)
    """
    # 1. Create Owner
    owner_uid = str(uuid.uuid4())[:8]
    owner_user = AuthUser(
        email=f"owner_{owner_uid}@example.com",
        password_hash=b"pass",
        role="OWNER",
        firebase_uid=f"uid_{owner_uid}",
    )
    db_session.add(owner_user)
    db_session.flush()

    owner_profile = SalonOwners(
        user_id=owner_user.id,
        first_name="Cart",
        last_name="Owner",
        phone_number="555-1111",
        address="123 Cart Ln",
    )
    db_session.add(owner_profile)
    db_session.flush()

    # 2. Create Salon
    salon = Salon(
        salon_owner_id=owner_profile.id,
        name="Cart Salon",
        address="123 Cart Ln",
        city="Cart City",
        latitude=40.0,
        longitude=-74.0,
        phone="555-2222",
    )
    db_session.add(salon)
    db_session.flush()

    # Verify Salon
    verify = SalonVerify(salon_id=salon.id, status="APPROVED")
    db_session.add(verify)

    # 3. Create Service
    service = Service(
        salon_id=salon.id, name="Test Haircut", price=50.00, duration=60, is_active=True
    )
    db_session.add(service)

    # 4. Create Product
    product = Product(
        salon_id=salon.id,
        name="Test Shampoo",
        price=20.00,
        stock_qty=100,
        is_active=True,
    )
    db_session.add(product)

    # 5. Create Customer
    cust_uid = str(uuid.uuid4())[:8]
    cust_user = AuthUser(
        email=f"cust_{cust_uid}@example.com",
        password_hash=b"pass",
        role="CUSTOMER",
        firebase_uid=f"uid_{cust_uid}",
    )
    db_session.add(cust_user)
    db_session.flush()

    customer = Customers(
        user_id=cust_user.id,
        first_name="Cart",
        last_name="Shopper",
        phone_number="555-3333",
    )
    db_session.add(customer)

    db_session.commit()

    return {
        "customer": customer,
        "service": service,
        "product": product,
        "salon": salon,
    }


@pytest.mark.cart
class TestCartAddService:
    """Test POST /api/cart/add-service"""

    def test_add_service_success(self, client, cart_fixtures):
        """Test adding a valid service to a new cart."""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        payload = {
            "user_id": customer.id,
            "service_id": service.id,
            "quantity": 1,
            "appt_date": "2024-12-25",
            "appt_time": "14:00",
            "pictures": ["http://example.com/ref1.jpg"],
        }

        response = client.post("/api/cart/add-service", json=payload)

        assert response.status_code == 201
        data = json.loads(response.data)

        assert data["status"] == "success"
        assert data["cart_item"]["customer_id"] == customer.id
        assert data["cart_item"]["service_id"] == service.id
        assert data["cart_item"]["pictures"] == ["http://example.com/ref1.jpg"]

        # Verify timestamps
        assert data["cart_item"]["start_at"] == "2024-12-25T14:00:00"
        # Duration is 60 mins, so end time should be 15:00
        assert data["cart_item"]["end_at"] == "2024-12-25T15:00:00"

    def test_add_service_invalid_date(self, client, cart_fixtures):
        """Test validation for incorrect date format."""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        payload = {
            "user_id": customer.id,
            "service_id": service.id,
            "appt_date": "bad-date",
            "appt_time": "bad-time",
        }

        response = client.post("/api/cart/add-service", json=payload)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Invalid date/time format" in data["message"]

    def test_add_service_missing_fields(self, client):
        """Test error when required fields are missing."""
        response = client.post("/api/cart/add-service", json={})

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Missing required fields" in data["message"]


@pytest.mark.cart
class TestCartAddProduct:
    """Test POST /api/cart/add-product"""

    def test_add_product_success(self, client, cart_fixtures):
        """Test adding a product to cart."""
        customer = cart_fixtures["customer"]
        product = cart_fixtures["product"]

        payload = {"user_id": customer.id, "product_id": product.id, "quantity": 2}

        response = client.post("/api/cart/add-product", json=payload)

        assert response.status_code == 201
        data = json.loads(response.data)

        assert data["status"] == "success"
        assert data["cart_item"]["product_id"] == product.id
        assert data["cart_item"]["quantity"] == 2
        assert data["cart_item"]["price"] == 20.00

    def test_add_nonexistent_product(self, client, cart_fixtures):
        """Test error when product ID is invalid."""
        customer = cart_fixtures["customer"]

        payload = {"user_id": customer.id, "product_id": 99999, "quantity": 1}

        response = client.post("/api/cart/add-product", json=payload)

        assert response.status_code == 404
        assert "not found" in json.loads(response.data)["message"]


@pytest.mark.cart
class TestCartGetDetails:
    """Test GET /api/cart/<user_id>"""

    def test_get_cart_success(self, client, cart_fixtures):
        """Test retrieving a cart with items."""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        # 1. Pre-fill cart via API (simulating user action)
        client.post(
            "/api/cart/add-service",
            json={
                "user_id": customer.id,
                "service_id": service.id,
                "pictures": ["http://img.com/1.jpg"],
            },
        )

        # 2. Get Cart
        response = client.get(f"/api/cart/{customer.id}")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["user_id"] == customer.id
        assert data["total_items"] == 1

        item = data["items"][0]
        assert item["item_type"] == "service"
        assert item["service_name"] == "Test Haircut"
        assert len(item["images"]) == 1
        assert item["images"][0] == "http://img.com/1.jpg"

    def test_get_cart_not_found(self, client):
        """Test getting a cart for a user who doesn't exist or has no cart."""
        response = client.get("/api/cart/999999")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "No cart found" in data["message"]


@pytest.mark.cart
class TestCartUpdateItem:
    """Test PATCH /api/cart/update-item-quantity"""

    def test_update_product_quantity(self, client, cart_fixtures):
        """Test updating quantity of a product in cart."""
        customer = cart_fixtures["customer"]
        product = cart_fixtures["product"]

        # 1. Add Product first
        client.post(
            "/api/cart/add-product",
            json={"user_id": customer.id, "product_id": product.id, "quantity": 1},
        )

        # Get Cart ID
        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_id = json.loads(cart_resp.data)["cart_id"]

        # 2. Update Quantity
        payload = {
            "cart_id": cart_id,
            "item_id": product.id,
            "kind": "product",
            "quantity": 5,
        }

        response = client.patch("/api/cart/update-item-quantity", json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["cart_item"]["quantity"] == 5

    def test_update_quantity_exceeds_stock(self, client, cart_fixtures):
        """Test error when requested quantity > stock."""
        customer = cart_fixtures["customer"]
        product = cart_fixtures["product"]  # stock is 100

        # Add to cart
        client.post(
            "/api/cart/add-product",
            json={"user_id": customer.id, "product_id": product.id, "quantity": 1},
        )

        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_id = json.loads(cart_resp.data)["cart_id"]

        # Try to set quantity to 101
        payload = {
            "cart_id": cart_id,
            "item_id": product.id,
            "kind": "product",
            "quantity": 101,
        }

        response = client.patch("/api/cart/update-item-quantity", json=payload)

        assert response.status_code == 409  # Conflict
        assert "Not enough stock" in json.loads(response.data)["message"]


@pytest.mark.cart
class TestCartDeleteItem:
    """Test DELETE /api/cart/delete-cart-item"""

    def test_delete_service_item(self, client, cart_fixtures):
        """Test removing a service from the cart."""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        # 1. Add Service
        client.post(
            "/api/cart/add-service",
            json={"user_id": customer.id, "service_id": service.id},
        )

        # 2. Get Cart ID
        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_data = json.loads(cart_resp.data)
        cart_id = cart_data["cart_id"]

        # 3. Delete
        response = client.delete(
            f"/api/cart/delete-cart-item?cart_id={cart_id}&item_id={service.id}&kind=service"
        )

        assert response.status_code == 200
        assert "Deleted Successfully" in json.loads(response.data)["message"]

        # 4. Verify Empty
        final_resp = client.get(f"/api/cart/{customer.id}")
        assert json.loads(final_resp.data)["total_items"] == 0

    def test_delete_invalid_item(self, client, cart_fixtures):
        """Test error when trying to delete non-existent item."""

        response = client.delete(
            "/api/cart/delete-cart-item?cart_id=99999&item_id=1&kind=service"
        )

        assert response.status_code == 404


@pytest.mark.cart
class TestCartAdminUpdates:
    """Test suite for updating Service/Product details (Admin/Owner actions)."""

    def test_update_service_details(self, client, cart_fixtures):
        """Test PUT /api/cart/update-service/<id>"""
        service = cart_fixtures["service"]

        payload = {"name": "Updated Haircut", "price": 60.00, "duration": 45}

        response = client.put(f"/api/cart/update-service/{service.id}", json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["name"] == "Updated Haircut"
        assert data["data"]["price"] == 60.00
        assert data["data"]["duration"] == 45

    def test_update_product_details(self, client, cart_fixtures):
        """Test PUT /api/cart/update-product/<id>"""
        product = cart_fixtures["product"]

        payload = {"name": "New Shampoo Name", "stock_qty": 500}

        response = client.put(f"/api/cart/update-product/{product.id}", json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["name"] == "New Shampoo Name"
        assert data["data"]["stock_qty"] == 500


@pytest.mark.cart
class TestCartImages:
    """Test suite for Image handling endpoints."""

    def test_get_cart_item_photos(self, client, cart_fixtures, db_session):
        """Test GET /api/cart/<item_id>/photos"""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        # 1. Create a cart item with images manually (or via API)
        client.post(
            "/api/cart/add-service",
            json={
                "user_id": customer.id,
                "service_id": service.id,
                "pictures": ["http://test.com/img1.jpg", "http://test.com/img2.jpg"],
            },
        )

        # 2. Get the item ID
        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_item_id = json.loads(cart_resp.data)["items"][0]["cart_item_id"]

        # 3. Call the photos endpoint
        response = client.get(f"/api/cart/{cart_item_id}/photos")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["photos"]) == 2
        urls = [p["url"] for p in data["photos"]]
        assert "http://test.com/img1.jpg" in urls

    def test_link_photos_to_appointment(self, client, cart_fixtures, db_session):
        """Test PUT /api/cart/<item_id>/link-appointment"""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        client.post(
            "/api/cart/add-service",
            json={
                "user_id": customer.id,
                "service_id": service.id,
                "pictures": ["http://test.com/transfer_me.jpg"],
            },
        )

        # Get Item ID
        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_item_id = json.loads(cart_resp.data)["items"][0]["cart_item_id"]

        from app.models import Appointment

        appt = Appointment(
            customer_id=customer.id,
            salon_id=service.salon_id,
            employee_id=None,
            service_id=service.id,
            start_at=datetime.now(),
            end_at=datetime.now() + timedelta(minutes=30),
            status="BOOKED",
        )
        db_session.add(appt)
        db_session.commit()

        # 3. Link Images
        payload = {"appointment_id": appt.id}
        response = client.put(
            f"/api/cart/{cart_item_id}/link-appointment", json=payload
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "http://test.com/transfer_me.jpg" in data["message"]

    def test_transfer_images_cleanup(self, client, cart_fixtures, db_session):
        """Test POST /api/cart/transfer-images-to-appointment"""
        customer = cart_fixtures["customer"]
        service = cart_fixtures["service"]

        client.post(
            "/api/cart/add-service",
            json={
                "user_id": customer.id,
                "service_id": service.id,
                "pictures": ["http://test.com/cleanup.jpg"],
            },
        )

        cart_resp = client.get(f"/api/cart/{customer.id}")
        cart_item_id = json.loads(cart_resp.data)["items"][0]["cart_item_id"]

        from app.models import Appointment

        appt = Appointment(
            customer_id=customer.id,
            salon_id=service.salon_id,
            service_id=service.id,
            start_at=datetime.now(),
            end_at=datetime.now(),
            status="BOOKED",
        )
        db_session.add(appt)
        db_session.commit()

        # 3. Transfer
        payload = {
            "cart_item_id": cart_item_id,
            "appointment_id": appt.id,
            "image_urls": ["http://test.com/cleanup.jpg"],
        }

        response = client.post("/api/cart/transfer-images-to-appointment", json=payload)

        assert response.status_code == 200
        assert json.loads(response.data)["transferred_count"] == 1

        photos_resp = client.get(f"/api/cart/{cart_item_id}/photos")
        assert len(json.loads(photos_resp.data)["photos"]) == 0
