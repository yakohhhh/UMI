from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import (
    Flag,
    FlagSource,
    HazardKind,
    Lang,
    SigAlg,
    flag_message,
    generate_private_key,
    load_private_key_pem,
    load_public_key_pem,
    private_key_from_raw_hex,
    private_key_to_pem,
    private_key_to_raw_hex,
    public_key_from_uncompressed,
    public_key_to_pem,
    public_key_to_uncompressed,
    sign_flag,
    sign_message,
    signature_from_der,
    signature_to_der,
    verify_flag,
    verify_message,
)

DEVICE_ID = 0x00000000C11B0001
SESSION_ID = 1

# RFC 6979 appendix A.2.5: ECDSA, 256 bits (prime field), SHA-256.
RFC6979_KEY = "c9afa9d845ba75166b5c215767b1d6934e50c3db36e89b127b8a622b120f6721"
RFC6979_PUBLIC = (
    "04"
    "60fed4ba255a9d31c961eb74c6356d68c049b8923b61fa6ce669622e60f29fb6"
    "7903fe1008b8bc99a41ae9e95628bc64f2f1b20c2d7e9f5177a3c294d4462299"
)
RFC6979_SIGNATURES = {
    b"sample": "efd48b2aacb6a8fd1140dd9cd45e81d69d2c877b56aaf991c34d0ea84eaf3716"
    "f7cb1c942d657c41d436c7a1b6e29f65f3e900dbb9aff4064dc4ab2f843acda8",
    b"test": "f1abb023518351cd71d881567b1ea663ed3efcf6c5132b354f28d3b0b7d38367"
    "019f4113742a2b14bd25926b49c649155f267e60d3814b4c0cc84250e46f0083",
}

FLAG = Flag(125_350, 3, FlagSource.VOICE, HazardKind.ROADWORKS, 92, Lang.CA, 414029000, 21564400, 520, 1210, 6590)


@pytest.mark.parametrize(("message", "signature"), RFC6979_SIGNATURES.items())
def test_signing_is_rfc6979_deterministic(message: bytes, signature: str) -> None:
    key = private_key_from_raw_hex(RFC6979_KEY)
    assert public_key_to_uncompressed(key.public_key()).hex() == RFC6979_PUBLIC
    assert sign_message(key, message).hex() == signature
    assert verify_message(key.public_key(), message, bytes.fromhex(signature))


def test_flag_message_layout() -> None:
    message = flag_message(DEVICE_ID, SESSION_ID, FLAG.signed_payload)
    assert message[:11] == b"UMI-FLAG-v1"
    assert message[11:19] == DEVICE_ID.to_bytes(8, "little")
    assert message[19:23] == SESSION_ID.to_bytes(4, "little")
    assert message[23:] == FLAG.to_payload()[:28]
    with pytest.raises(ValueError, match="28 bytes"):
        flag_message(DEVICE_ID, SESSION_ID, FLAG.to_payload())


def test_sign_and_verify_a_flag(test_key: ec.EllipticCurvePrivateKey) -> None:
    signed = sign_flag(test_key, DEVICE_ID, SESSION_ID, FLAG)
    assert (signed.sig_alg, signed.sig_len, len(signed.signature)) == (SigAlg.ECDSA_P256, 64, 64)
    assert signed.signed_payload == FLAG.signed_payload
    assert verify_flag(test_key.public_key(), DEVICE_ID, SESSION_ID, signed)
    assert sign_flag(test_key, DEVICE_ID, SESSION_ID, FLAG) == signed  # deterministic
    assert Flag.from_payload(signed.to_payload()) == signed


@pytest.mark.parametrize(
    "changes",
    [
        {"t_ms": 125_351},
        {"seq": 4},
        {"source": FlagSource.PRESS},
        {"kind": HazardKind.POTHOLE},
        {"confidence": 93},
        {"lang": Lang.ES},
        {"lat_e7": 414029001},
        {"lon_e7": 21564401},
        {"speed_cms": 521},
        {"vib_mms2": 1211},
        {"noise_cdba": 6591},
    ],
    ids=lambda changes: next(iter(changes)),
)
def test_any_tampered_signed_field_fails(test_key: ec.EllipticCurvePrivateKey, changes: dict[str, Any]) -> None:
    signed = sign_flag(test_key, DEVICE_ID, SESSION_ID, FLAG)
    assert not verify_flag(test_key.public_key(), DEVICE_ID, SESSION_ID, dataclasses.replace(signed, **changes))


def test_a_signature_is_bound_to_its_clip_and_session(test_key: ec.EllipticCurvePrivateKey) -> None:
    signed = sign_flag(test_key, DEVICE_ID, SESSION_ID, FLAG)
    public = test_key.public_key()
    assert not verify_flag(public, DEVICE_ID + 1, SESSION_ID, signed)
    assert not verify_flag(public, DEVICE_ID, SESSION_ID + 1, signed)
    assert not verify_flag(generate_private_key().public_key(), DEVICE_ID, SESSION_ID, signed)
    flipped = bytes([signed.signature[0] ^ 1]) + signed.signature[1:]
    assert not verify_flag(public, DEVICE_ID, SESSION_ID, dataclasses.replace(signed, signature=flipped))


def test_unsigned_flags_do_not_verify(test_key: ec.EllipticCurvePrivateKey) -> None:
    assert not FLAG.is_signed
    assert not verify_flag(test_key.public_key(), DEVICE_ID, SESSION_ID, FLAG)
    signed = sign_flag(test_key, DEVICE_ID, SESSION_ID, FLAG)
    assert not verify_flag(test_key.public_key(), DEVICE_ID, SESSION_ID, dataclasses.replace(signed, sig_alg=7))


def test_raw_and_der_signatures_convert_both_ways(test_key: ec.EllipticCurvePrivateKey) -> None:
    raw = sign_message(test_key, b"anything")
    der = signature_to_der(raw)
    assert der[0] == 0x30
    assert signature_from_der(der) == raw
    with pytest.raises(ValueError, match="64 bytes"):
        signature_to_der(raw[:63])
    assert not verify_message(test_key.public_key(), b"anything", raw[:63])


def test_key_encodings_round_trip() -> None:
    key = generate_private_key()
    public = key.public_key()
    assert private_key_to_raw_hex(load_private_key_pem(private_key_to_pem(key))) == private_key_to_raw_hex(key)
    assert len(private_key_to_raw_hex(key)) == 64
    assert private_key_from_raw_hex(private_key_to_raw_hex(key)).private_numbers() == key.private_numbers()
    assert load_public_key_pem(public_key_to_pem(public)).public_numbers() == public.public_numbers()
    point = public_key_to_uncompressed(public)
    assert (len(point), point[0]) == (65, 0x04)
    assert public_key_from_uncompressed(point).public_numbers() == public.public_numbers()


def test_only_p256_keys_are_accepted() -> None:
    p384 = ec.generate_private_key(ec.SECP384R1())
    with pytest.raises(ValueError, match="P-256"):
        load_private_key_pem(private_key_to_pem(p384))
    with pytest.raises(ValueError, match="P-256"):
        load_public_key_pem(public_key_to_pem(p384.public_key()))
    with pytest.raises(ValueError, match="P-256"):
        sign_message(p384, b"x")
    with pytest.raises(ValueError, match="65-byte"):
        public_key_from_uncompressed(bytes(33))
    with pytest.raises(ValueError, match="32 bytes"):
        private_key_from_raw_hex("00" * 31)
