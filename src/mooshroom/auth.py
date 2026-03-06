import json
import time
import webbrowser
from dataclasses import asdict, dataclass

import click
import httpx

from mooshroom.config import AUTH_FILE
from mooshroom.console import console

MS_CLIENT_ID = "c23f3f04-3d89-4a4d-90a0-2486e07d3681"
MS_SCOPE = "XboxLive.signin offline_access"
MS_DEVICE_CODE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
)
MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBOX_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_AUTH_URL = "https://api.minecraftservices.com/authentication/loginWithXbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"


@dataclass
class AuthTokens:
    refresh_token: str
    mc_access_token: str
    username: str
    uuid: str
    expires_at: float


def _ms_device_code_flow(client: httpx.Client) -> dict:
    r = client.post(
        MS_DEVICE_CODE_URL, data={"client_id": MS_CLIENT_ID, "scope": MS_SCOPE}
    )
    r.raise_for_status()
    data = r.json()

    code = data["user_code"]
    url = data["verification_uri"]

    console.print(f"\nCode: [bold]{code}[/]")
    input(f"Press Enter to open {url} ...")
    webbrowser.open(url)

    device_code = data["device_code"]
    interval = data.get("interval", 5)

    with console.status("[info]Waiting for authentication...[/]"):
        while True:
            time.sleep(interval)
            r = client.post(
                MS_TOKEN_URL,
                data={
                    "client_id": MS_CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
            )
            token_data = r.json()
            if "access_token" in token_data:
                return token_data
            error = token_data.get("error")
            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                interval += 5
            else:
                raise click.ClickException(
                    f"Auth failed: {token_data.get('error_description', error)}"
                )


def _full_auth_flow(client: httpx.Client, ms_token_data: dict) -> AuthTokens:
    ms_access_token = ms_token_data["access_token"]

    with console.status("[info]Authenticating...[/]") as status:
        r = client.post(
            XBOX_AUTH_URL,
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={ms_access_token}",
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
            },
        )
        r.raise_for_status()
        xbox = r.json()
        userhash = xbox["DisplayClaims"]["xui"][0]["uhs"]

        r = client.post(
            XSTS_AUTH_URL,
            json={
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbox["Token"]],
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT",
            },
        )
        r.raise_for_status()

        status.update("[info]Fetching Minecraft profile...[/]")
        r = client.post(
            MC_AUTH_URL,
            json={"identityToken": f"XBL3.0 x={userhash};{r.json()['Token']}"},
        )
        r.raise_for_status()
        mc_access_token = r.json()["access_token"]

        r = client.get(
            MC_PROFILE_URL,
            headers={"Authorization": f"Bearer {mc_access_token}"},
        )
        r.raise_for_status()
        profile = r.json()

    tokens = AuthTokens(
        refresh_token=ms_token_data.get("refresh_token", ""),
        mc_access_token=mc_access_token,
        username=profile["name"],
        uuid=profile["id"],
        expires_at=time.time() + ms_token_data.get("expires_in", 3600),
    )
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(asdict(tokens), indent=2))
    return tokens


def device_code_login() -> AuthTokens:
    with httpx.Client(timeout=30) as client:
        ms_data = _ms_device_code_flow(client)
        return _full_auth_flow(client, ms_data)


def refresh_or_login() -> AuthTokens:
    try:
        data = json.loads(AUTH_FILE.read_text())
        tokens = AuthTokens(**data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        tokens = None
    if tokens and time.time() < tokens.expires_at and tokens.mc_access_token:
        return tokens

    with httpx.Client(timeout=30) as client:
        if tokens and tokens.refresh_token:
            try:
                r = client.post(
                    MS_TOKEN_URL,
                    data={
                        "client_id": MS_CLIENT_ID,
                        "grant_type": "refresh_token",
                        "refresh_token": tokens.refresh_token,
                        "scope": MS_SCOPE,
                    },
                )
                r.raise_for_status()
                return _full_auth_flow(client, r.json())
            except (httpx.HTTPError, KeyError, ValueError):
                console.print("[warning]Token refresh failed, starting new login...[/]")

        ms_data = _ms_device_code_flow(client)
        return _full_auth_flow(client, ms_data)
