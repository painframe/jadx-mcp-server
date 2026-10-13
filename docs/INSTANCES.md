# Multiple plugin instances

Start the bridge with `--instances-file /path/to/instances.json`. This is a local
administrator file, never supplied by MCP clients. Example without credentials:

```json
{
  "default": "app-a",
  "instances": [
    {"id": "app-a", "url": "http://127.0.0.1:8650", "aliases": ["baseline"], "token_env": "APP_A_TOKEN"},
    {"id": "app-b", "url": "http://127.0.0.1:8652", "aliases": ["candidate"], "token_file": "/run/user/1000/jadx-b-token"}
  ]
}
```

Every analysis tool exposes optional `instance`: canonical ID, configured alias,
unambiguous port, or project name obtained by `refresh_instances`. Omit it to use
the configured default (or the sole registered instance). Ambiguous/missing
selectors fail. Client-supplied URLs never create registry entries.

`list_instances` exposes IDs and capabilities without backend URLs or credential
references. `refresh_instances` verifies `service=jadx-ai-mcp` plus `instance_id`
on configured `/health` endpoints before accepting project metadata. `--discover`
at startup probes only loopback ports 8650..8665 and requires this identity.
Discovery does not guess bearer credentials; use an explicit registry for protected
plugins. Without a registry, the original single-backend CLI remains supported.

Registry/token files must be owned and protected by the administrator. Python
resolves aliases before routing and uses ContextVar isolation for concurrent calls.
