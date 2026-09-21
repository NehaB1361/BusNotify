"""
Tests for User Registration, Authentication, and Role Authorization
"""
def test_user_registration(client):
    res = client.post('/api/auth/register', json={
        "username": "new_passenger",
        "email": "new_passenger@test.com",
        "password": "Password123!",
        "role": "passenger"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["username"] == "new_passenger"
    assert data["data"]["role"] == "passenger"


def test_user_login_success(client):
    res = client.post('/api/auth/login', json={
        "identifier": "pax@test.com",
        "password": "Password123!"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["email"] == "pax@test.com"


def test_user_login_invalid_credentials(client):
    res = client.post('/api/auth/login', json={
        "identifier": "pax@test.com",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "AUTH_FAILED"


def test_user_logout(client):
    client.post('/api/auth/login', json={"identifier": "pax@test.com", "password": "Password123!"})
    res = client.post('/api/auth/logout')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True


def test_browser_logout_redirects_to_login(client):
    client.post('/api/auth/login', json={"identifier": "pax@test.com", "password": "Password123!"})
    res = client.get('/api/auth/logout')

    assert res.status_code == 302
    assert res.headers["Location"] == "/login"


def test_login_page_uses_auth_layout_without_global_navigation(client):
    res = client.get('/login')
    html = res.get_data(as_text=True)

    assert res.status_code == 200
    assert 'id="loginForm"' in html
    assert 'class="tf-header"' not in html
    assert 'class="tf-sidebar"' not in html


def test_login_page_redirects_authenticated_users(client):
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "driver"

    res = client.get('/login')
    assert res.status_code == 302
    assert res.headers["Location"] == "/driver"

    res = client.get('/login?next=%2Fdriver%2Fstart-trip')
    assert res.status_code == 302
    assert res.headers["Location"] == "/driver/start-trip"


def test_frontend_portals_require_login(client):
    res = client.get('/passenger')
    assert res.status_code == 302
    assert res.headers["Location"] == "/login?next=/passenger"

    res = client.get('/admin/analytics')
    assert res.status_code == 302
    assert res.headers["Location"] == "/login?next=/admin/analytics"


def test_inactive_user_cannot_login(client, app):
    with app.app_context():
        from app.models.user import User
        from app.extensions import db
        user = User.query.filter_by(email="pax@test.com").first()
        user.is_active = False
        db.session.commit()

    res = client.post('/api/auth/login', json={
        "identifier": "pax@test.com",
        "password": "Password123!"
    })
    assert res.status_code == 401
    assert "deactivated" in res.get_json()["error"]["message"].lower()

    # Restore user active status for remaining tests
    with app.app_context():
        from app.models.user import User
        from app.extensions import db
        user = User.query.filter_by(email="pax@test.com").first()
        user.is_active = True
        db.session.commit()


def test_cross_role_unauthorized_access(client):
    # Log in as passenger
    client.post('/api/auth/login', json={"identifier": "pax@test.com", "password": "Password123!"})
    
    # Try to access driver portal
    res = client.get('/driver')
    # Should redirect to unauthorized page
    assert res.status_code == 302
    assert "/unauthorized" in res.headers["Location"]

    # Try to access admin portal
    res_admin = client.get('/admin')
    assert res_admin.status_code == 302
    assert "/unauthorized" in res_admin.headers["Location"]

