# Python bridge container

Build with `docker build -t painframe/jadx-mcp-server:local .`.
The Python and uv base images are digest-pinned; dependencies come from `uv.lock`.
The installed package runs as UID/GID10001, without a source checkout or shell
entrypoint. Use Docker's built-in init for PID1 signal forwarding/reaping:

```sh
docker run --rm --init -i --network host painframe/jadx-mcp-server:local --jadx-url http://127.0.0.1:8650
```

For authenticated HTTP, mount administrator instance/user JSON and runtime token
files read-only, provide user token environment variables through your secret
manager, and supply `--http --users-file /config/users.json --instances-file
/config/instances.json --host 0.0.0.0`. Bind the published port to loopback behind
TLS termination. This image runs only the Python bridge; the paired Java project
provides the headless/GUI plugin runtime and Compose orchestration.

No credential, repository history, fixture APK or test output enters the Docker
build context. The image exposes no port automatically. No registry publication
is required for local use.
