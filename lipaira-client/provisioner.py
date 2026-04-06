"""
Lipaira Client Provisioner
==========================
Manages per-client Docker containers.

When a user signs up:
1. Create unique client ID
2. Provision dedicated Docker container
3. Configure resource limits
4. Store client → container mapping
5. Return connection info

When a user is deleted:
1. Stop and remove their container
2. Clean up their data
3. Remove mapping
"""

import os
import sys
import uuid
import json
import docker
from datetime import datetime
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Docker client
docker_client = docker.from_env()

# Container naming
CONTAINER_PREFIX = "lipaira-client-"
IMAGE_NAME = "lipaira/client:latest"
DEFAULT_MEMORY = "512m"  # 512MB per client
DEFAULT_CPU = 0.5        # 50% of one CPU

# Network (internal - clients can't talk to each other)
LIPAIRA_NETWORK = "lipaira-internal"


class ClientProvisioner:
    """Manages client container lifecycle"""
    
    def __init__(self):
        self._ensure_network()
    
    def _ensure_network(self):
        """Create internal network if not exists"""
        try:
            docker_client.networks.get(LIPAIRA_NETWORK)
            logger.info(f"Network {LIPAIRA_NETWORK} exists")
        except docker.errors.NotFound:
            docker_client.networks.create(
                LIPAIRA_NETWORK,
                driver="bridge",
                internal=False  # Allow outbound for LLM calls
            )
            logger.info(f"Created network {LIPAIRA_NETWORK}")
    
    def provision(
        self,
        user_id: str,
        user_email: str,
        max_memory_mb: int = 512,
        max_cpu: float = 0.5,
        allow_network: bool = True
    ) -> Dict:
        """
        Provision a new client container.
        
        Args:
            user_id: Unique user identifier
            user_email: User email (for logging)
            max_memory_mb: Memory limit
            max_cpu: CPU limit (0.5 = 50%)
            allow_network: Allow outbound network
        
        Returns:
            Dict with container info
        """
        client_id = f"client_{user_id[:8]}"
        container_name = f"{CONTAINER_PREFIX}{client_id}"
        
        # Check if already exists
        try:
            existing = docker_client.containers.get(container_name)
            logger.warning(f"Container {container_name} already exists")
            return {
                "success": True,
                "client_id": client_id,
                "container_name": container_name,
                "already_running": True
            }
        except docker.errors.NotFound:
            pass
        
        # Environment for container
        env = [
            f"LIPAIRA_CLIENT_ID={client_id}",
            f"LIPAIRA_USER_EMAIL={user_email}",
            f"LIPAIRA_MAX_MEMORY={max_memory_mb}",
            f"LIPAIRA_MAX_CPU={int(max_cpu * 100)}",
            f"LIPAIRA_ALLOW_NETWORK={str(allow_network).lower()}",
            f"LIPAIRA_SANDBOX=true",
            f"LIPAIRA_API_URL={os.environ.get('LIPAIRA_API_URL', 'http://api:8080')}",
            f"LIPAIRA_API_KEY={os.environ.get('LIPAIRA_API_KEY', '')}",
        ]
        
        # Resource limits
        mem_limit = f"{max_memory_mb}m"
        cpu_period = 100000
        cpu_quota = int(max_cpu * cpu_period)
        
        # Create volume for client data
        volume_name = f"lipaira-data-{client_id}"
        try:
            docker_client.volumes.get(volume_name)
        except docker.errors.NotFound:
            docker_client.volumes.create(name=volume_name)
        
        # Run container
        try:
            container = docker_client.containers.run(
                IMAGE_NAME,
                name=container_name,
                detach=True,
                environment=env,
                mem_limit=mem_limit,
                cpu_period=cpu_period,
                cpu_quota=cpu_quota,
                network=LIPAIRA_NETWORK,
                volumes={
                    volume_name: {"bind": "/home/client/data", "mode": "rw"}
                },
                restart_policy={"Name": "unless-stopped"},
                labels={
                    "lipaira.client": client_id,
                    "lipaira.user": user_email,
                    "lipaira.created": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Provisioned container {container_name} for {user_email}")
            
            return {
                "success": True,
                "client_id": client_id,
                "container_name": container_name,
                "container_id": container.id,
                "internal_url": f"http://{container_name}:8081",
                "status": "running"
            }
            
        except Exception as e:
            logger.error(f"Failed to provision: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def deprovision(self, client_id: str) -> Dict:
        """
        Remove a client container.
        
        Args:
            client_id: Client identifier
        
        Returns:
            Dict with result
        """
        container_name = f"{CONTAINER_PREFIX}client_{client_id[:8]}"
        
        try:
            container = docker_client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Removed container {container_name}")
        except docker.errors.NotFound:
            logger.warning(f"Container {container_name} not found")
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        # Remove data volume
        volume_name = f"lipaira-data-client_{client_id[:8]}"
        try:
            volume = docker_client.volumes.get(volume_name)
            volume.remove(force=True)
            logger.info(f"Removed volume {volume_name}")
        except:
            pass
        
        return {"success": True, "client_id": client_id}
    
    def get_status(self, client_id: str) -> Dict:
        """Get container status"""
        container_name = f"{CONTAINER_PREFIX}client_{client_id[:8]}"
        
        try:
            container = docker_client.containers.get(container_name)
            return {
                "client_id": client_id,
                "status": container.status,
                "container_id": container.id,
                "created": container.attrs.get("Created"),
                "stats": container.stats(stream=False) if container.status == "running" else None
            }
        except docker.errors.NotFound:
            return {"client_id": client_id, "status": "not_found"}
    
    def list_clients(self) -> list:
        """List all client containers"""
        try:
            containers = docker_client.containers.list(
                all=True,
                filters={"label": "lipaira.client"}
            )
            
            return [
                {
                    "client_id": c.labels.get("lipaira.client"),
                    "user": c.labels.get("lipaira.user"),
                    "status": c.status,
                    "container_id": c.id[:12]
                }
                for c in containers
            ]
        except Exception as e:
            logger.error(f"List failed: {e}")
            return []


# CLI for manual testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lipaira Client Provisioner")
    parser.add_argument("action", choices=["provision", "deprovision", "status", "list"])
    parser.add_argument("--user-id", help="User ID")
    parser.add_argument("--email", help="User email")
    
    args = parser.parse_args()
    
    provisioner = ClientProvisioner()
    
    if args.action == "provision":
        result = provisioner.provision(args.user_id or str(uuid.uuid4()), args.email or "test@test.com")
        print(json.dumps(result, indent=2))
    elif args.action == "deprovision":
        result = provisioner.deprovision(args.user_id)
        print(json.dumps(result, indent=2))
    elif args.action == "status":
        result = provisioner.get_status(args.user_id)
        print(json.dumps(result, indent=2))
    elif args.action == "list":
        result = provisioner.list_clients()
        print(json.dumps(result, indent=2))