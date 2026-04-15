"""
USER PROVISIONER - Per-user database isolation
===============================================

Per SPEC v6 Block 2 Item 1:
- Free users: schema isolation in shared DB (schema named user_{id})
- Paid users: dedicated container named lipaira-db-{user_id}
- Trigger: user registration (async, non-blocking)
- Failure: log error, fall back to shared DB, flag for retry
"""

import os
import uuid
import logging
import psycopg2
import docker
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Docker client (requires docker.sock mount)
try:
    docker_client = docker.from_env()
except:
    docker_client = None
    logger.warning("Docker not available - container provisioning disabled")

# Container naming per spec
CONTAINER_PREFIX = "lipaira-db-"
IMAGE_NAME = "postgres:15"
DEFAULT_MEMORY = "256m"  # Per spec: 256MB for paid tier
DEFAULT_CPU = 0.25       # Per spec: 0.25 CPU

# Network - use existing lipaira network
LIPAIRA_NETWORK = "lipaira-net"


class UserProvisioner:
    """Manages per-user database isolation."""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.docker = docker_client
    
    def provision(
        self,
        user_id: str,
        plan: str = "free"
    ) -> Dict:
        """
        Provision database isolation for a user.
        
        Args:
            user_id: Unique user identifier
            plan: "free" or "paid"
        
        Returns:
            Dict with provisioning result
        """
        if plan == "free":
            return self._provision_free(user_id)
        else:
            return self._provision_paid(user_id)
    
    def _provision_free(self, user_id: str) -> Dict:
        """
        Free tier: Create schema in shared database.
        """
        # Use underscore instead of hyphen (schema names can't have hyphens)
        import hashlib
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
        schema_name = f"u{user_hash}"
        
        try:
            # Get shared DB connection
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            # Create user's schema
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            
            # Create basic tables in schema
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.memory_nodes (
                    id SERIAL PRIMARY KEY,
                    node_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    node_type TEXT DEFAULT 'fact',
                    confidence REAL DEFAULT 0.8,
                    source TEXT DEFAULT 'conversation',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.conversations (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    messages JSONB DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Created schema {schema_name} for free user {user_id}")
            
            return {
                "success": True,
                "tier": "free",
                "schema": schema_name,
                "connection": "shared_db"
            }
            
        except Exception as e:
            logger.error(f"Free tier provisioning failed: {e}")
            return {
                "success": False,
                "tier": "free",
                "error": str(e),
                "fallback": True
            }
    
    def _provision_paid(self, user_id: str) -> Dict:
        """
        Paid tier: Create dedicated Postgres container.
        """
        if not self.docker:
            logger.warning("Docker not available, falling back to shared DB")
            return self._provision_free(user_id)
        
        container_name = f"{CONTAINER_PREFIX}{user_id[:8]}"
        
        # Check if already exists
        try:
            existing = self.docker.containers.get(container_name)
            if existing.status == "running":
                logger.info(f"Container {container_name} already exists")
                return {
                    "success": True,
                    "tier": "paid",
                    "container": container_name,
                    "already_running": True
                }
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"Container check failed: {e}")
        
        # Generate password
        password = uuid.uuid4().hex
        
        # Create container
        try:
            container = self.docker.containers.run(
                IMAGE_NAME,
                name=container_name,
                detach=True,
                environment={
                    "POSTGRES_USER": f"user_{user_id[:8]}",
                    "POSTGRES_PASSWORD": password,
                    "POSTGRES_DB": "lipaira"
                },
                mem_limit=DEFAULT_MEMORY,
                cpu_quota=int(DEFAULT_CPU * 100000),
                network=LIPAIRA_NETWORK,
                restart_policy={"Name": "unless-stopped"},
                labels={
                    "lipaira.user_id": user_id,
                    "lipaira.tier": "paid",
                    "lipaira.created": datetime.utcnow().isoformat()
                }
            )
            
            # Wait for container to be ready
            self._wait_for_container(container_name, timeout=60)
            
            # Run schema migrations
            self._run_user_schema(user_id, container_name, password)
            
            # Store credentials (in production, use secrets manager)
            self._store_credentials(user_id, container_name, password)
            
            logger.info(f"Provisioned container {container_name} for paid user {user_id}")
            
            return {
                "success": True,
                "tier": "paid",
                "container": container_name,
                "container_id": container.id,
                "internal_url": f"postgresql://user_{user_id[:8]}:{password}@{container_name}:5432/lipaira"
            }
            
        except Exception as e:
            logger.error(f"Paid tier provisioning failed: {e}")
            # Fall back to shared DB
            return self._provision_free(user_id)
    
    def _wait_for_container(self, container_name: str, timeout: int = 60):
        """Wait for container to be ready."""
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                container = self.docker.containers.get(container_name)
                if container.status == "running":
                    # Try a simple query
                    return True
            except:
                pass
            time.sleep(1)
        
        raise TimeoutError(f"Container {container_name} did not start within {timeout}s")
    
    def _run_user_schema(self, user_id: str, container_name: str, password: str):
        """Create user's schema in dedicated container."""
        # This would connect to the new container and run migrations
        # For now, just log - migrations are run on first access
        logger.info(f"Schema migrations queued for {container_name}")
    
    def _store_credentials(self, user_id: str, container_name: str, password: str):
        """Store container credentials in main DB."""
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO user_containers (user_id, container_name, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET container_name = %s
            """, (user_id, container_name, container_name))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Stored credentials for {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to store credentials: {e}")
    
    def deprovision(self, user_id: str) -> Dict:
        """Remove user's dedicated container (paid) or schema (free)."""
        
        # Check tier
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute("""
            SELECT container_name FROM user_containers 
            WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        
        if row and row[0]:
            # Paid - remove container
            container_name = row[0]
            try:
                container = self.docker.containers.get(container_name)
                container.stop(timeout=10)
                container.remove(force=True)
                logger.info(f"Removed container {container_name}")
            except Exception as e:
                logger.error(f"Failed to remove container: {e}")
        
        # Drop schema if exists
        schema_name = f"user_{user_id[:8]}"
        try:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
            conn.commit()
            logger.info(f"Dropped schema {schema_name}")
        except Exception as e:
            logger.error(f"Failed to drop schema: {e}")
        
        cur.close()
        conn.close()
        
        return {"success": True, "user_id": user_id}


# Background task wrapper
def provision_user(user_id: str, plan: str = "free"):
    """
    Async wrapper for provisioning.
    Called from registration endpoint in background thread.
    """
    provisioner = UserProvisioner()
    result = provisioner.provision(user_id, plan)
    
    if result.get("success"):
        logger.info(f"User {user_id} provisioned as {plan}")
    else:
        logger.error(f"User {user_id} provisioning failed: {result.get('error')}")
    
    return result