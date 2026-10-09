import httpx

from config import config


class SanaeiAPI:

    def __init__(self):

        self.base = config.panel_url.rstrip("/")

        self.client = httpx.AsyncClient(
            timeout=20,
            verify=False,
        )

    async def close(self):

        await self.client.aclose()

    def headers(self):

        return {
            "Authorization": f"Bearer {config.panel_api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def inbounds(self):

        url = (
            f"{self.base}/panel/api/inbounds/list"
        )

        response = await self.client.get(
            url,
            headers=self.headers(),
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):

            raise RuntimeError(
                data.get("msg")
                or "Sanaei API error"
            )

        return data.get("obj") or []

    async def find_inbound_by_port(
        self,
        port: int,
    ):

        for inbound in await self.inbounds():

            try:

                if int(
                    inbound.get("port", 0)
                ) == port:

                    return inbound

            except (
                TypeError,
                ValueError,
            ):

                continue

        return None

    async def create_tunnel(
        self,
        remark: str,
        port: int,
        rewrite_address: str,
        rewrite_port: int,
        total_bytes: int,
    ):

        url = (
            f"{self.base}/panel/api/inbounds/add"
        )

        payload = {

            "enable": True,

            "remark": remark,

            "listen": "",

            "port": port,

            "protocol": "tunnel",

            "expiryTime": 0,

            "total": total_bytes,

            "settings": {

                "rewriteAddress":
                    rewrite_address,

                "rewritePort":
                    rewrite_port,

                "portMap": {},

                "allowedNetwork":
                    "tcp",

                "followRedirect":
                    False,
            },

            "streamSettings": {

                "security": "none",
            },

            "sniffing": {

                "enabled": False,
            },
        }

        response = await self.client.post(
            url,
            headers=self.headers(),
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):

            raise RuntimeError(
                data.get("msg")
                or "Failed to create inbound"
            )

        return data

    async def delete_inbound(
        self,
        inbound_id: int,
    ):

        url = (
            f"{self.base}/panel/api/inbounds/"
            f"del/{inbound_id}"
        )

        response = await self.client.post(
            url,
            headers=self.headers(),
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):

            raise RuntimeError(
                data.get("msg")
                or "Failed to delete inbound"
            )

        return data

    async def update_inbound_total(
        self,
        inbound_id: int,
        total_bytes: int,
    ):
        inbounds = await self.inbounds()

        target = None

        for inbound in inbounds:
            try:
                if int(inbound.get("id", 0)) == int(inbound_id):
                    target = inbound
                    break
            except (TypeError, ValueError):
                continue

        if not target:
            raise RuntimeError("Inbound not found")

        url = f"{self.base}/panel/api/inbounds/update/{inbound_id}"

        payload = {
            "enable": target.get("enable", True),
            "remark": target.get("remark", ""),
            "listen": target.get("listen", ""),
            "port": target.get("port"),
            "protocol": target.get("protocol", "tunnel"),
            "expiryTime": target.get("expiryTime", 0),
            "total": total_bytes,
            "settings": target.get("settings", {}),
            "streamSettings": target.get("streamSettings", {}),
            "sniffing": target.get("sniffing", {}),
        }

        response = await self.client.post(
            url,
            headers=self.headers(),
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            raise RuntimeError(
                data.get("msg") or "Failed to update inbound total"
            )

        return data

async def toggle_inbound(
        self,
        inbound_id: int,
        enable: bool,
    ):

        inbounds = await self.inbounds()

        target = None

        for inbound in inbounds:

            try:

                if int(
                    inbound.get("id", 0)
                ) == int(inbound_id):

                    target = inbound
                    break

            except (
                TypeError,
                ValueError,
            ):

                continue

        if not target:

            raise RuntimeError(
                "Inbound not found"
            )

        url = (
            f"{self.base}/panel/api/inbounds/"
            f"update/{inbound_id}"
        )

        payload = {

            "enable": enable,

            "remark":
                target.get("remark", ""),

            "listen":
                target.get("listen", ""),

            "port":
                target.get("port"),

            "protocol":
                target.get("protocol", "tunnel"),

            "expiryTime":
                target.get("expiryTime", 0),

            "total":
                target.get("total", 0),

            "settings":
                target.get("settings", {}),

            "streamSettings":
                target.get("streamSettings", {}),

            "sniffing":
                target.get("sniffing", {}),
        }

        response = await self.client.post(
            url,
            headers=self.headers(),
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):

            raise RuntimeError(
                data.get("msg")
                or "Failed to update inbound"
            )

        return data
