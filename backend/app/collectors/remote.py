import httpx


class BastetClient:
    def __init__(self, base_url: str, auth_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    def _headers(self) -> dict[str, str]:
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            return response.json()

    async def fetch_health(self) -> dict:
        return await self._get("/health")

    async def fetch_gpu(self) -> dict:
        return await self._get("/gpu")

    async def fetch_models(self) -> dict:
        return await self._get("/models")

    async def fetch_runs(self) -> dict:
        return await self._get("/runs")
