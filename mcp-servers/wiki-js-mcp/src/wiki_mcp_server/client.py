"""Wiki.js GraphQL API client."""

import asyncio
from typing import Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wiki_mcp_server.config import logger, settings


class WikiJSClient:
    """Wiki.js GraphQL API client for handling requests."""

    def __init__(self) -> None:
        self.base_url = settings.WIKIJS_API_URL.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.authenticated = False
        self._auth_lock = asyncio.Lock()

    async def authenticate(self) -> bool:
        if self.authenticated:
            return True
        async with self._auth_lock:
            if self.authenticated:
                return True
            if settings.token:
                self.client.headers.update(
                    {
                        "Authorization": f"Bearer {settings.token}",
                        "Content-Type": "application/json",
                    }
                )
                self.authenticated = True
                return True
            if settings.WIKIJS_USERNAME and settings.WIKIJS_PASSWORD:
                try:
                    login_mutation = """
                    mutation($username: String!, $password: String!, $strategy: String!) {
                        authentication {
                            login(username: $username, password: $password, strategy: $strategy) {
                                responseResult {
                                    succeeded
                                    message
                                }
                                jwt
                            }
                        }
                    }
                    """
                    response = await self.graphql_request(
                        login_mutation,
                        {
                            "username": settings.WIKIJS_USERNAME,
                            "password": settings.WIKIJS_PASSWORD,
                            "strategy": "local",
                        },
                    )
                    login = (
                        response.get("data", {})
                        .get("authentication", {})
                        .get("login", {})
                    )
                    response_result = login.get("responseResult", {})
                    if response_result.get("succeeded"):
                        jwt_token = login["jwt"]
                        self.client.headers.update(
                            {
                                "Authorization": f"Bearer {jwt_token}",
                                "Content-Type": "application/json",
                            }
                        )
                        self.authenticated = True
                        return True
                    logger.error("Login failed: %s", response)
                    return False
                except Exception as e:
                    logger.error("Authentication failed: %s", e)
                    return False
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def graphql_request(
        self, query: str, variables: Optional[Dict] = None
    ) -> Dict:
        url = f"{self.base_url}/graphql"
        payload: Dict = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                error_msg = "; ".join(
                    err.get("message", str(err)) for err in data["errors"]
                )
                raise Exception(f"GraphQL error: {error_msg}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(
                "Wiki.js GraphQL HTTP error %s: %s",
                e.response.status_code,
                e.response.text,
            )
            raise Exception(
                f"Wiki.js GraphQL HTTP error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("Wiki.js connection error: %s", e)
            raise Exception(f"Wiki.js connection error: {e}") from e


wikijs = WikiJSClient()
