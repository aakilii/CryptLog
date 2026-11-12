"""
User authentication models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from app.db.base import Base

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__truncate_error=True
    )
except ImportError:
    pwd_context = None


class User(Base):
    """
    User account for forensic platform access.
    """
    __tablename__ = "users"

    id = Column[str](String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt. Handles passwords longer than 72 bytes."""
        if pwd_context is None:
            raise ImportError("passlib[bcrypt] is required for password hashing. Install with: pip install passlib[bcrypt]")
        import hashlib
        
        # Bcrypt has a 72-byte limit. Pre-hash with SHA256 if password exceeds limit
        password_bytes = password.encode('utf-8')
        
        # Pre-hash if password is 70 bytes or longer (safety margin for bcrypt's 72-byte limit)
        if len(password_bytes) >= 70:
            # Pre-hash long passwords with SHA256 to fit bcrypt's 72-byte limit
            # This ensures security while respecting bcrypt's constraint
            password = hashlib.sha256(password_bytes).hexdigest()
        
        # Use passlib's hash which should handle edge cases
        return pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        if pwd_context is None:
            raise ImportError("passlib[bcrypt] is required for password verification. Install with: pip install passlib[bcrypt]")
        import hashlib
        # If password is too long, hash it first (same as in hash_password)
        password_bytes = password.encode('utf-8')
        if len(password_bytes) >= 70:
            # Pre-hash long passwords with SHA256 to match hash_password behavior
            password = hashlib.sha256(password_bytes).hexdigest()
        return pwd_context.verify(password, self.password_hash)

