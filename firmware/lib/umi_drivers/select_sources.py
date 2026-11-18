"""Build the ESP-IDF glue (src/esp32) only for ESP-IDF targets.

The frame parsers in src/parsers are pure C and also build on the host, where
they are unit-tested and used by the simulated drivers.
"""

Import("env")  # noqa: F821  (SCons injects it)

if "espidf" not in env.get("PIOFRAMEWORK", []):  # noqa: F821
    env.Replace(SRC_FILTER=["+<*>", "-<esp32/>"])  # noqa: F821
