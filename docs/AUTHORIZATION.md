# Remote MCP authorization

HTTP transport requires `--users-file /path/to/users.json`, even when bound to
loopback. Stdio remains the trusted local-owner transport. Use a TLS reverse proxy
for remote connections; the process does not create certificates or publish ports.

```json
{
  "users": [
    {"id": "analyst", "token_env": "ANALYST_MCP_TOKEN", "instances": {"app-a": "read"}},
    {"id": "operator", "token_env": "OPERATOR_MCP_TOKEN", "instances": {"app-a": "write", "app-b": "write"}}
  ]
}
```

Create independent random tokens of at least 32 ASCII characters in the environment.
The JSON contains environment variable names, not credentials. Instance keys must
be canonical IDs in the administrator instance registry; a single-backend setup
without a registry uses `default`. Unknown identities/instances and omitted grants
are denied. `write` includes reads. Rotation of client tokens/policy takes effect
on restart; backend token files are reloaded for every request.

Clients send `Authorization: Bearer …` to the MCP endpoint. Token comparisons use
constant-time comparison. Authentication occurs in FastMCP's HTTP auth middleware;
instance authorization happens after canonical selector resolution and again before
backend credentials, cooldowns, queue admission or network dispatch. Legacy GET
renames/comments are mutations. Batch-analysis POST is read-only.

Instance listing, identity refresh and diagnostics expose only permitted instances.
There is no remote tool to register URLs, edit policy, or retrieve backend tokens.
A forbidden MCP tool result retains the normal MCP envelope with `code=forbidden`
and `status=403`; missing/invalid HTTP bearer credentials receive HTTP 401.
