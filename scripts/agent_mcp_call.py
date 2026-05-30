#!/usr/bin/env python3
"""Minimal MCP SSE client for operator scripts (localhost stack)."""
import json
import sys
from urllib.parse import urlparse

import httpx


class McpSseClient:
    def __init__(self, base_url: str, timeout: float = 300):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._message_endpoint = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def connect(self) -> None:
        resp = self._client.get(
            f"{self.base_url}/sse",
            headers={"Accept": "text/event-stream"},
        )
        resp.raise_for_status()
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                endpoint_path = line[6:].strip()
                if endpoint_path.startswith("/"):
                    parsed = urlparse(self.base_url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    self._message_endpoint = base + endpoint_path
                else:
                    self._message_endpoint = f"{self.base_url}/{endpoint_path}"
                break
        if not self._message_endpoint:
            self._message_endpoint = f"{self.base_url}/sse"

    def _send(self, method: str, params: dict | None = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._next_id(),
        }
        resp = self._client.post(
            self._message_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._send("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> None:
        self._client.close()


def parse_result(result: dict) -> dict:
    if "result" in result:
        inner = result["result"]
        if "content" in inner:
            for item in inner["content"]:
                if item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except (json.JSONDecodeError, TypeError):
                        return {"raw_text": item["text"]}
        return inner
    if "error" in result:
        return {"error": str(result["error"])}
    return result


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: agent_mcp_call.py <url> <tool_name> [json_args]", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1]
    tool = sys.argv[2]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    client = McpSseClient(url)
    client.connect()
    try:
        out = parse_result(client.call_tool(tool, args))
        print(json.dumps(out, indent=2, ensure_ascii=False))
    finally:
        client.close()


if __name__ == "__main__":
    main()
