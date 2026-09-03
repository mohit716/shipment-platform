import bcrypt

# bcrypt only reads the first 72 bytes of a password. Anything beyond that is
# silently ignored by the algorithm, so the schema caps the field rather than
# letting callers believe a 200 character passphrase is fully checked.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password, salt included.

    gensalt() produces a fresh random salt every call, which is why two users
    with the same password get different hashes and why a stolen hash cannot be
    looked up in a precomputed table.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a stored hash.

    The salt and cost factor are embedded in the hash itself, so nothing else
    has to be stored alongside it. checkpw compares in constant time, so the
    duration of a failed login does not leak how much of the hash matched.
    """
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        # A malformed or truncated hash in the database should read as "wrong
        # password", never as an unhandled 500 on the login route.
        return False
