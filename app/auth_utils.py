import bcrypt

def hash_password(password: str) -> str:
    """
    Generate a secure bcrypt hash from a plaintext password.
    """
    # Generate a random salt and hash the password encoded to bytes
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against its stored bcrypt hash.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), 
        hashed_password.encode("utf-8")
    )