import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from api import app
from database import init_async_db
from models import User, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from auth import hash_password
import os

# Use a test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest_asyncio.fixture(scope="module")
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest_asyncio.fixture
async def async_client(test_db):
    # Override get_db dependency if necessary, or just use the app's db if it uses the same URL env var
    # But here we are using a separate test.db, so we should override.
    # However,api.py uses `database.py` which hardcodes `cs2_history.db` or env var.
    # For now, let's just test against the REAL app but using the test client, 
    # and maybe mocked DB?
    # Actually, simpler to just run against the app and check status codes if we don't want to mess up the main DB.
    # But we want to test REGISTER. Creating users in main DB is annoying.
    # Let's override the `get_db` dependency.
    
    async_session = sessionmaker(
        test_db, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with async_session() as session:
            yield session

    from auth import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_register_login_flow(async_client):
    # 1. Register
    username = "testuser"
    password = "password123"
    display_name = "Test User"
    
    reg_payload = {
        "username": username,
        "password": password,
        "display_name": display_name
    }
    
    response = await async_client.post("/api/auth/register", json=reg_payload)
    if response.status_code == 409:
        # User might exist from previous run if db persisted
        pass
    else:
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == username
        assert "id" in data
    
    # 2. Login
    login_payload = {
        "username": username,
        "password": password
    }
    response = await async_client.post("/api/auth/token", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]
    
    # 3. Get Me
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["username"] == username
    assert me_data["display_name"] == display_name

@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client):
    login_payload = {
        "username": "nonexistent",
        "password": "wrongpassword"
    }
    response = await async_client.post("/api/auth/token", json=login_payload)
    assert response.status_code == 401
