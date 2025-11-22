"""
Database connection and session management.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse, urlunparse
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Global engine variable (will be created after ensuring database exists)
engine = None
SessionLocal = None


def ensure_database_exists():
    """
    Check if the database exists, and create it if it doesn't.
    
    This function connects to the PostgreSQL server (not a specific database)
    to check if the target database exists, and creates it if needed.
    """
    try:
        # Parse the database URL
        parsed_url = urlparse(settings.database_url)
        database_name = parsed_url.path.lstrip('/')
        
        if not database_name:
            logger.warning("No database name found in DATABASE_URL, skipping database creation check")
            return True
        
        # Create a connection URL to the PostgreSQL server (default 'postgres' database)
        # This allows us to connect even if the target database doesn't exist
        server_url_parts = list(parsed_url)
        server_url_parts[2] = '/postgres'  # Connect to default 'postgres' database
        server_url = urlunparse(server_url_parts)
        
        logger.info(f"Checking if database '{database_name}' exists...")
        
        # Connect to PostgreSQL server (not the specific database)
        server_engine = create_engine(
            server_url,
            poolclass=NullPool,
            isolation_level="AUTOCOMMIT"  # Required for CREATE DATABASE
        )
        
        with server_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": database_name}
            )
            exists = result.fetchone() is not None
            
            if not exists:
                logger.info(f"Database '{database_name}' does not exist, creating it...")
                # Create the database
                conn.execute(text(f'CREATE DATABASE "{database_name}"'))
                logger.info(f"Database '{database_name}' created successfully")
            else:
                logger.info(f"Database '{database_name}' already exists")
        
        server_engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure database exists: {e}", exc_info=True)
        # Don't raise - allow the application to continue and fail on actual connection
        return False


def initialize_database_connection():
    """
    Initialize the database engine and sessionmaker.
    This should be called after ensuring the database exists.
    """
    global engine, SessionLocal
    
    if engine is not None:
        return  # Already initialized
    
    # Ensure database exists first
    ensure_database_exists()
    
    # Create database engine
    # Using NullPool for async compatibility and to avoid connection pool issues
    engine = create_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False  # Set to True for SQL query logging
    )
    
    # Create sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    logger.info("Database connection initialized")


# Initialize database connection on module import
initialize_database_connection()


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.
    
    Yields:
        Database session
    """
    if SessionLocal is None:
        initialize_database_connection()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Get database session as context manager (for use in non-FastAPI code).
    
    Yields:
        Database session
    """
    if SessionLocal is None:
        initialize_database_connection()
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    """
    if engine is None:
        initialize_database_connection()
    
    from app.models.db_models import Base
    
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}", exc_info=True)
        raise


def check_db_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        if engine is None:
            initialize_database_connection()
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

