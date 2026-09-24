from cryptography.fernet import Fernet  # type: ignore[reportMissingImports]


def encrypt_secret(value: str, key: str) -> str:
    fernet = Fernet(key.encode("utf-8"))
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, key: str) -> str:
    fernet = Fernet(key.encode("utf-8"))
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")