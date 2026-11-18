"""Leave the software flag signer out of ESP-IDF builds.

A devkit with simulated sensors still signs flags with its own key through
mbedTLS/PSA (umi_drivers), like the Clip; the micro-ecc signer and its SHA-256
exist for the host only (SIL and unit tests).
"""

Import("env")  # noqa: F821  (SCons injects it)

if "espidf" in env.get("PIOFRAMEWORK", []):  # noqa: F821
    env.Replace(SRC_FILTER=["+<*>", "-<soft_signer.c>", "-<sha256.c>"])  # noqa: F821
