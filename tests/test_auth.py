import pytest
import json

# Note: Imports of AuthUser/Customers removed as they weren't used in the tests provided.
# If you need them for DB checks, add them back.

@pytest.mark.auth
class TestAuthSignup:
    """Test suite for user signup functionality."""

    def test_signup_success(self, client, test_user_data):
        """Test successful user signup."""
        response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )
        # Debug print
        if response.status_code != 201:
            print(f"\nDEBUG ERROR: {response.data}")

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['user']['email'] == test_user_data['email']

    def test_signup_missing_email(self, client, test_user_data):
        """Test signup with missing email."""
        test_user_data.pop('email')
        response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_signup_missing_password(self, client, test_user_data):
        """Test signup with missing password."""
        test_user_data.pop('password')
        response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_signup_missing_first_name(self, client, test_user_data):
        """Test signup with missing first_name."""
        test_user_data.pop('first_name')
        response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_signup_duplicate_email(self, client, test_user_data):
        """Test signup with duplicate email."""
        # First signup
        client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        # Second signup with same email
        response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        # Check for either error message variant
        assert 'error' in data['status'].lower()


@pytest.mark.auth
class TestAuthLogin:
    """Test suite for user login functionality."""

    def test_login_success(self, client, test_user_data):
        """Test successful login."""
        # Register first
        client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        # Then login
        login_data = {
            "email": test_user_data['email'],
            "password": test_user_data['password']
        }
        response = client.post(
            '/api/auth/login',
            data=json.dumps(login_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'token' in data

    def test_login_missing_email(self, client):
        """Test login with missing email."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({"password": "testpassword"}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_login_missing_password(self, client):
        """Test login with missing password."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({"email": "test@example.com"}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_login_wrong_password(self, client, test_user_data):
        """Test login with wrong password."""
        # Register
        client.post(
            '/api/auth/signup',
            data=json.dumps(test_user_data),
            content_type='application/json'
        )

        # Try login with wrong password
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                "email": test_user_data['email'],
                "password": "WrongPassword123!"
            }),
            content_type='application/json'
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid credentials' in data['message']

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                "email": "nonexistent@example.com",
                "password": "SomePassword123!"
            }),
            content_type='application/json'
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid credentials' in data['message']


@pytest.mark.auth
class TestGetUserType:
    """Test suite for getting user type."""

    def test_get_user_type_success(self, client, test_gettype):
        """Test successful retrieval of user type."""
        # Register a user
        signup_response = client.post(
            '/api/auth/signup',
            data=json.dumps(test_gettype),
            content_type='application/json'
        )
        signup_data = json.loads(signup_response.data)

        # FAIL HARD if signup didn't work. Don't use 'if'.
        assert signup_response.status_code == 201
        assert signup_data['status'] == 'success'
        
        user_id = signup_data['user']['id']

        # Get user type
        response = client.get(f'/api/auth/user-type/{user_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['role'] in ['CUSTOMER', 'OWNER', 'EMPLOYEE', 'ADMIN']

    def test_get_user_type_nonexistent(self, client):
        """Test getting type for non-existent user."""
        response = client.get('/api/auth/user-type/99999')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['status'] == 'error'