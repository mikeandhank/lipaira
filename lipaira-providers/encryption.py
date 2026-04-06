"""
End-to-End Encryption for Lipaira
================================
Client encrypts → Server processes blindly → Client decrypts

Server never sees plaintext!
"""

import os
import base64
import json
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from typing import Tuple, Optional
import secrets


# ============================================================
# KEY MANAGEMENT (Server-side)
# ============================================================

class KeyManager:
    """Manages encryption keys for E2E encryption"""
    
    def __init__(self):
        self._private_key = None
        self._public_key = None
    
    @property
    def public_key(self) -> str:
        """Get public key for clients to encrypt with"""
        if not self._public_key:
            self._generate_keys()
        return self._public_key
    
    def _generate_keys(self):
        """Generate RSA keypair"""
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self._public_key = self._private_key.public_key()
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format for clients"""
        if not self._public_key:
            self._generate_keys()
        
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt data encrypted with public key"""
        if not self._private_key:
            self._generate_keys()
        
        # Decrypt the symmetric key with RSA
        symmetric_key = self._private_key.decrypt(
            encrypted_data[:-32],  # First part is encrypted key
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt the actual data with symmetric key
        iv = encrypted_data[-32:]  # Last 32 bytes is IV
        
        cipher = Cipher(
            algorithms.AES(symmetric_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(encrypted_data[:-32]) + decryptor.finalize()
        
        # Remove padding
        padding_length = plaintext[-1]
        return plaintext[:-padding_length].decode('utf-8')
    
    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt response back to client"""
        if not self._private_key:
            self._generate_keys()
        
        # Generate random symmetric key
        symmetric_key = secrets.token_bytes(32)  # AES-256
        iv = secrets.token_bytes(16)
        
        # Encrypt data with symmetric key
        cipher = Cipher(
            algorithms.AES(symmetric_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Add padding
        plaintext_bytes = plaintext.encode('utf-8')
        padding_length = 16 - (len(plaintext_bytes) % 16)
        plaintext_bytes += bytes([padding_length] * padding_length)
        
        ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
        
        # Encrypt symmetric key with RSA
        encrypted_key = self._public_key.encrypt(
            symmetric_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return encrypted_key + iv + ciphertext


# Global key manager
_key_manager = KeyManager()


# ============================================================
# CLIENT-SIDE ENCRYPTION (JavaScript)
# ============================================================

CLIENT_ENCRYPTION_JS = """
// Client-side encryption using Web Crypto API
// Server never sees plaintext!

class LipairaEncryption {
    constructor(publicKeyPEM) {
        this.publicKey = null;
        this.importKey(publicKeyPEM);
    }
    
    async importKey(pem) {
        // Convert PEM to ArrayBuffer
        const base64 = pem.replace(/-----BEGIN PUBLIC KEY-----/, '')
            .replace(/-----END PUBLIC KEY-----/, '')
            .replace(/\\n/g, '');
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        
        this.publicKey = await crypto.subtle.importKey(
            'spki',
            bytes,
            { name: 'RSA-OAEP', hash: 'SHA-256' },
            false,
            ['encrypt']
        );
    }
    
    async encrypt(plaintext) {
        // Generate random AES key
        const aesKey = await crypto.subtle.generateKey(
            { name: 'AES-CBC', length: 256 },
            true,
            ['encrypt', 'decrypt']
        );
        
        // Generate IV
        const iv = crypto.getRandomValues(new Uint8Array(16));
        
        // Encrypt plaintext with AES
        const encoder = new TextEncoder();
        const plaintextBytes = encoder.encode(plaintext);
        
        const encrypted = await crypto.subtle.encrypt(
            { name: 'AES-CBC', iv },
            aesKey,
            plaintextBytes
        );
        
        // Export AES key
        const exportedKey = await crypto.subtle.exportKey('raw', aesKey);
        
        // Encrypt AES key with RSA public key
        const encryptedKey = await crypto.subtle.encrypt(
            { name: 'RSA-OAEP' },
            this.publicKey,
            exportedKey
        );
        
        // Combine: encryptedKey (256 bytes) + iv (16 bytes) + encrypted data
        const result = new Uint8Array(encryptedKey.byteLength + iv.byteLength + encrypted.byteLength);
        result.set(new Uint8Array(encryptedKey), 0);
        result.set(iv, encryptedKey.byteLength);
        result.set(new Uint8Array(encrypted), encryptedKey.byteLength + iv.byteLength);
        
        return btoa(String.fromCharCode(...result));
    }
    
    async decrypt(encryptedBase64) {
        // This would need the private key, which stays on client
        // Or server can provide encrypted response
        throw new Error('Use server-side decryption for responses');
    }
}

// Usage:
const lipaira = new LipairaEncryption(PUBLIC_KEY);

// Encrypt before sending
const encrypted = await lipaira.encrypt(JSON.stringify({
    message: "Hello, world!"
}));

fetch('/api/chat/encrypted', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ encrypted })
});
"""


# ============================================================
# SERVER API
# ============================================================

def get_public_key() -> str:
    """Get server's public key for clients"""
    return _key_manager.get_public_key_pem()


def decrypt_request(encrypted_payload: str) -> dict:
    """Decrypt an encrypted request"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_payload)
        plaintext = _key_manager.decrypt(encrypted_bytes)
        return json.loads(plaintext)
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def encrypt_response(response_data: dict) -> str:
    """Encrypt response for client"""
    plaintext = json.dumps(response_data)
    encrypted = _key_manager.encrypt(plaintext)
    return base64.b64encode(encrypted).decode('utf-8')


# Example encrypted endpoint
ENCRYPTED_ENDPOINT_EXAMPLE = '''
# Add to unified_api.py

@bp.route("/api/chat/encrypted", methods=["POST"])
def chat_encrypted():
    """
    End-to-end encrypted chat endpoint
    
    Client sends:
    {
        "encrypted": "base64_encrypted_payload"
    }
    
    Server never sees plaintext!
    """
    from .encryption import decrypt_request, encrypt_response, get_public_key
    
    data = request.get_json() or {}
    encrypted = data.get("encrypted", "")
    
    if not encrypted:
        # Return public key if no encryption
        return jsonify({"public_key": get_public_key()})
    
    try:
        # Decrypt request
        plaintext = decrypt_request(encrypted)
        
        # Process normally
        response = process_chat(plaintext)
        
        # Encrypt response
        encrypted_response = encrypt_response(response)
        
        return jsonify({"encrypted": encrypted_response})
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/encryption/key", methods=["GET"])
def get_encryption_key():
    """Get public key for client-side encryption"""
    return jsonify({"public_key": get_public_key()})
'''
