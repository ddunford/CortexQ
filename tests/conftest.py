import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from typing import Generator

# Set test environment
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key"

# Import after setting environment
import sys
import os
# Add the core-api src to the path (same as working test)
# Check if we're in Docker container (/app) or host system
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core-api', 'src'))

from main import app
from dependencies import get_db
from models import Base
from auth_utils import AuthUtils

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch('redis.Redis') as mock:
        redis_instance = Mock()
        mock.return_value = redis_instance
        yield redis_instance

@pytest.fixture
def mock_minio():
    """Mock MinIO client for testing."""
    with patch('minio.Minio') as mock:
        minio_instance = Mock()
        mock.return_value = minio_instance
        yield minio_instance

@pytest.fixture
def mock_ollama():
    """Mock Ollama client for testing."""
    with patch('requests.post') as mock:
        mock.return_value.status_code = 200
        mock.return_value.json.return_value = {
            "response": "Test response",
            "done": True
        }
        yield mock

@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }

@pytest.fixture
def test_organization_data():
    """Sample organization data for testing."""
    return {
        "name": "Test Organization",
        "slug": "test-org",
        "description": "Test organization for testing",
        "size_category": "small",
        "subscription_tier": "basic"
    }

@pytest.fixture
def test_domain_data():
    """Sample domain data for testing."""
    return {
        "domain_name": "test-domain",
        "display_name": "Test Domain",
        "description": "Test domain for testing",
        "is_active": True,
        "settings": {
            "aiConfig": {
                "provider": "ollama",
                "model": "llama2",
                "temperature": 0.7
            }
        }
    }

@pytest.fixture
def auth_headers(client, test_user_data, db_session):
    """Create authenticated user and return auth headers."""
    # Create user
    response = client.post("/auth/register", json=test_user_data)
    assert response.status_code == 200
    
    # Login to get token
    login_response = client.post("/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    })
    assert login_response.status_code == 200
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def temp_file():
    """Create a temporary file for testing file uploads."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test file content for testing file upload functionality.")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass

@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"

@pytest.fixture
def mock_background_tasks():
    """Mock background tasks for testing."""
    with patch('fastapi.BackgroundTasks') as mock:
        yield mock

@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    with patch('src.llm_service.LLMService') as mock:
        llm_instance = Mock()
        llm_instance.generate_response.return_value = {
            "response": "Test AI response",
            "confidence": 0.95,
            "sources": []
        }
        mock.return_value = llm_instance
        yield llm_instance 