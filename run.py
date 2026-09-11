# Warm platform.platform()'s caches before anything else imports or runs.
#
# The Anthropic SDK stamps telemetry headers (X-Stainless-OS / -Arch) onto its
# first request. Building them calls platform.platform(), which shells out
# twice — `uname -p` (via uname_result.processor) and `file -b <python>` (via
# architecture()) — and subprocess uses fork() for those, not posix_spawn.
#
# By the time the first script segment is generated, this process has pulled 30
# RSS feeds over HTTPS, so macOS has initialized Network.framework. Any fork()
# after that point segfaults in Apple's atfork child handler
# (nw_settings_child_has_forked -> nw_path_release_globals). platform.py
# swallows the dead child, so episodes published fine, but every run left
# SIGSEGVs in Crash Reporter — the crash documented in the README.
#
# Doing it here runs those two forks while the process is still single-threaded
# and hasn't touched the network, which is safe. platform.platform() caches its
# result, so the SDK's later call is a cache hit and never forks. The import
# order below is deliberate: this must precede anything that makes a request.
import platform

platform.platform()

from podcast import pipeline  # noqa: E402  (must come after the warm-up above)

if __name__ == "__main__":
    episode_path = pipeline.run()
    print(f"Published episode: {episode_path}")
