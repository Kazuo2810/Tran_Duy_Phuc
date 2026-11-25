import os
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/da2_healthcare_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-healthcare-only-32-bytes-min")
os.environ.setdefault("IDP_ISSUER", "http://test-idp")
os.environ.setdefault("OAUTH_CLIENT_ID", "healthcare-web")
os.environ.setdefault("OAUTH_REQUIRED_SCOPE", "healthcare:access")
os.environ.setdefault("COOKIE_SECURE", "0")
