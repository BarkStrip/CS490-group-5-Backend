import pytest
import json


@pytest.mark.salon
class TestSalons:
    """Test suite for salon endpoints."""

    def test_get_cities_success(self, client):
        """Test retrieving list of cities."""
        response = client.get("/api/salons/cities")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "cities" in data
        assert isinstance(data["cities"], list)

    def test_get_categories_success(self, client):
        """Test retrieving service categories."""
        response = client.get("/api/salons/categories")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_get_top_rated_success(self, client):
        """Test retrieving top-rated salons."""
        response = client.get("/api/salons/top-rated")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salons" in data
        assert isinstance(data["salons"], list)

    def test_get_top_rated_with_location(self, client):
        """Test retrieving top-rated salons with location."""
        response = client.get(
            "/api/salons/top-rated?user_lat=40.7128&user_long=-74.0060"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salons" in data

        # Check if distance was calculated
        if data["salons"]:
            assert "distance_miles" in data["salons"][0]

    def test_get_generic_salons(self, client):
        """Test retrieving top salons without location."""
        response = client.get("/api/salons/generic")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salons" in data
        assert isinstance(data["salons"], list)

    def test_search_salons_by_name(self, client):
        """Test searching salons by name."""
        response = client.get("/api/salons/search?q=salon")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "results_found" in data
        assert "salons" in data

    def test_search_salons_by_city(self, client):
        """Test searching salons by city."""
        response = client.get("/api/salons/search?location=Newark")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "results_found" in data

    def test_search_salons_by_type(self, client):
        """Test searching salons by type."""
        response = client.get("/api/salons/search?type=Hair")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "results_found" in data

    def test_search_salons_combined_filters(self, client):
        """Test searching with multiple filters."""
        response = client.get(
            "/api/salons/search?q=salon&location=Newark&type=Hair&rating=3.0"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "results_found" in data
        assert "salons" in data

    def test_get_salon_details_success(self, client):
        """Test retrieving salon details."""
        response = client.get("/api/salons/details/1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == 1
        assert "name" in data
        assert "avg_rating" in data

    def test_get_salon_details_nonexistent(self, client):
        """Test getting details for non-existent salon."""
        response = client.get("/api/salons/details/99999")

        assert response.status_code == 404

    def test_get_salon_reviews(self, client):
        """Test retrieving salon reviews."""
        response = client.get("/api/salons/details/1/reviews")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salon_id" in data
        assert "reviews_found" in data
        assert "reviews" in data
        assert isinstance(data["reviews"], list)

    def test_get_salon_services(self, client):
        """Test retrieving salon services."""
        response = client.get("/api/salons/details/1/services")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salon_id" in data
        assert "services_found" in data
        assert "services" in data
        assert isinstance(data["services"], list)

    def test_get_salon_gallery(self, client):
        """Test retrieving salon gallery images."""
        response = client.get("/api/salons/details/1/gallery")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salon_id" in data
        assert "media_found" in data
        assert "gallery" in data
        assert isinstance(data["gallery"], list)

    def test_get_salon_products(self, client):
        """Test retrieving salon products."""
        response = client.get("/api/salons/details/1/products")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salon_id" in data
        assert "products_found" in data
        assert "products" in data
        assert isinstance(data["products"], list)

    def test_connection(self, client):
        """Test database connection."""
        response = client.get("/api/salons/test")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
