"""Flag signatures (``protocol/README.md`` §1.4) and P-256 key helpers.

Signing is deterministic (RFC 6979, SHA-256), so the same key and flag always give
the same signature: golden vectors stay byte-stable and the firmware's simulated
signer can reproduce them. Verification accepts any valid signature.
"""

from __future__ import annotations

import dataclasses

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

from .constants import SIGNING_FLAG_CONTEXT, SIGNING_SIGNATURE_LEN, SigAlg
from .records import FLAG_SIGNED_LEN, Flag

_SCALAR_LEN = SIGNING_SIGNATURE_LEN // 2
_UNCOMPRESSED_POINT_LEN = 1 + 2 * _SCALAR_LEN
_CURVE = ec.SECP256R1()


def flag_message(device_id: int, session_id: int, payload_prefix: bytes) -> bytes:
    """The signed message: context ‖ device_id (u64 LE) ‖ session_id (u32 LE) ‖ FLAG payload bytes 0–27."""
    if len(payload_prefix) != FLAG_SIGNED_LEN:
        raise ValueError(f"the signed part of a FLAG payload is {FLAG_SIGNED_LEN} bytes, got {len(payload_prefix)}")
    return (
        SIGNING_FLAG_CONTEXT.encode("ascii")
        + device_id.to_bytes(8, "little")
        + session_id.to_bytes(4, "little")
        + payload_prefix
    )


def sign_message(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
    """ECDSA P-256 over SHA-256(message), deterministic, as raw ``r ‖ s``."""
    _require_p256(private_key.curve)
    der = private_key.sign(message, ec.ECDSA(hashes.SHA256(), deterministic_signing=True))
    return signature_from_der(der)


def verify_message(public_key: ec.EllipticCurvePublicKey, message: bytes, signature: bytes) -> bool:
    """Whether a raw ``r ‖ s`` signature of ``message`` is valid for ``public_key``."""
    _require_p256(public_key.curve)
    if len(signature) != SIGNING_SIGNATURE_LEN:
        return False
    try:
        public_key.verify(signature_to_der(signature), message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True


def sign_flag(private_key: ec.EllipticCurvePrivateKey, device_id: int, session_id: int, flag: Flag) -> Flag:
    """A copy of ``flag`` signed the way the Clip signs it; any previous signature is replaced."""
    signature = sign_message(private_key, flag_message(device_id, session_id, flag.signed_payload))
    return dataclasses.replace(flag, sig_alg=SigAlg.ECDSA_P256, sig_len=SIGNING_SIGNATURE_LEN, signature=signature)


def verify_flag(public_key: ec.EllipticCurvePublicKey, device_id: int, session_id: int, flag: Flag) -> bool:
    """Whether ``flag`` carries a valid ECDSA P-256 signature from ``public_key``'s Clip.

    The signed bytes are re-encoded from the fields, with reserved bytes as zero: a
    writer that put anything else there produced a flag that does not verify.
    """
    if flag.sig_alg != SigAlg.ECDSA_P256 or flag.sig_len != SIGNING_SIGNATURE_LEN:
        return False
    return verify_message(public_key, flag_message(device_id, session_id, flag.signed_payload), flag.signature)


# ---------------------------------------------------------------- signature encodings


def signature_to_der(signature: bytes) -> bytes:
    """Raw ``r ‖ s`` (64 bytes, big-endian) to the DER encoding most libraries use."""
    if len(signature) != SIGNING_SIGNATURE_LEN:
        raise ValueError(f"a raw P-256 signature is {SIGNING_SIGNATURE_LEN} bytes, got {len(signature)}")
    r = int.from_bytes(signature[:_SCALAR_LEN], "big")
    s = int.from_bytes(signature[_SCALAR_LEN:], "big")
    return encode_dss_signature(r, s)


def signature_from_der(der: bytes) -> bytes:
    """DER-encoded ECDSA signature to raw ``r ‖ s`` (64 bytes, big-endian)."""
    r, s = decode_dss_signature(der)
    return r.to_bytes(_SCALAR_LEN, "big") + s.to_bytes(_SCALAR_LEN, "big")


# ---------------------------------------------------------------- keys


def _require_p256(curve: ec.EllipticCurve) -> None:
    if not isinstance(curve, ec.SECP256R1):
        raise ValueError(f"flags are signed with P-256, not {curve.name}")


def generate_private_key() -> ec.EllipticCurvePrivateKey:
    """A fresh P-256 key, as a simulated Clip gets at provisioning."""
    return ec.generate_private_key(_CURVE)


def load_private_key_pem(pem: bytes) -> ec.EllipticCurvePrivateKey:
    """An unencrypted PEM private key (PKCS#8 or SEC1); text before the PEM block is ignored."""
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError(f"expected an EC private key, got {type(key).__name__}")
    _require_p256(key.curve)
    return key


def private_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    """Unencrypted PKCS#8 PEM. Only for simulated Clips: real keys never leave the device."""
    return private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def load_public_key_pem(pem: bytes) -> ec.EllipticCurvePublicKey:
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise ValueError(f"expected an EC public key, got {type(key).__name__}")
    _require_p256(key.curve)
    return key


def public_key_to_pem(public_key: ec.EllipticCurvePublicKey) -> bytes:
    """SubjectPublicKeyInfo PEM, the form the backend stores for a paired Clip."""
    return public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def private_key_to_raw_hex(private_key: ec.EllipticCurvePrivateKey) -> str:
    """The 32-byte private scalar as 64 hex digits, the form the firmware SIL signer loads."""
    return private_key.private_numbers().private_value.to_bytes(_SCALAR_LEN, "big").hex()


def private_key_from_raw_hex(text: str) -> ec.EllipticCurvePrivateKey:
    raw = bytes.fromhex(text)
    if len(raw) != _SCALAR_LEN:
        raise ValueError(f"a P-256 private scalar is {_SCALAR_LEN} bytes, got {len(raw)}")
    return ec.derive_private_key(int.from_bytes(raw, "big"), _CURVE)


def public_key_to_uncompressed(public_key: ec.EllipticCurvePublicKey) -> bytes:
    """``04 ‖ x ‖ y`` (65 bytes), as the Clip publishes it in the BLE Device Info characteristic."""
    return public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def public_key_from_uncompressed(point: bytes) -> ec.EllipticCurvePublicKey:
    if len(point) != _UNCOMPRESSED_POINT_LEN or point[0] != 0x04:
        raise ValueError(f"expected a {_UNCOMPRESSED_POINT_LEN}-byte uncompressed P-256 point")
    return ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, point)
