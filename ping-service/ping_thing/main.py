import asyncio
import json
import os
from typing import List

import aioboto3
import aiohttp
import google.auth.transport._aiohttp_requests
import google.oauth2._id_token_async
import jwt

from botocore import auth, awsrequest
from botocore.credentials import Credentials
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud import storage
from pydantic import BaseModel
from cache import AsyncTTL

aws = aioboto3.Session()

# The Application Audience (AUD) tag for your application
POLICY_AUD = os.getenv("POLICY_AUD")

# Your CF Access team domain
TEAM_DOMAIN = os.getenv("TEAM_DOMAIN")
CERTS_URL = "{}/cdn-cgi/access/certs".format(TEAM_DOMAIN)


@AsyncTTL(time_to_live=3600, maxsize=1024)
async def _get_public_keys():
    """
    Returns:
        List of RSA public keys usable by PyJWT.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(CERTS_URL) as resp:
            jwk_set = await resp.json()
    public_keys = []
    for key_dict in jwk_set["keys"]:
        public_key = jwt.PyJWK.from_json(json.dumps(key_dict))
        public_keys.append(public_key)
    return public_keys


async def get_user_token(
    res: Response,
    credential: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
):
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is needed",
            headers={"WWW-Authenticate": 'Bearer realm="auth_required"'},
        )
    keys = await _get_public_keys()
    valid_token = False
    for key in keys:
        try:
            # decode returns the claims that has the email when needed
            decoded_token = jwt.decode(
                credential.credentials,
                key=key,
                audience=POLICY_AUD,
                algorithms=["RS256"],
            )
            valid_token = True
            break
        except jwt.exceptions.InvalidTokenError:
            pass
    if not valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    res.headers["WWW-Authenticate"] = 'Bearer realm="auth_required"'
    return decoded_token


app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_client = storage.Client()
bucket = storage_client.bucket(os.getenv("CONFIG_BUCKET"))
blob = bucket.blob("config.json")
urls = json.loads(blob.download_as_text())["urls"]


class LatencyResponse(BaseModel):
    provider: str
    region: str
    latency: str


async def aws_request(
    session: aiohttp.ClientSession,
    uurl: str,
    url: str,
    region: str,
    aws_creds: Credentials,
):
    request = awsrequest.AWSRequest(
        method="GET",
        url=uurl,
        headers={
            "Accept": "application/json",
        },
        params={"url": url},
    )
    auth.SigV4Auth(
        aws_creds, "lambda" if "lambda" in uurl else "execute-api", region
    ).add_auth(request)
    response = await session.get(
        request.url,
        headers=dict(request.headers.items()),
        params=request.params,
    )
    return LatencyResponse(provider="aws", region=region, latency=await response.text())


async def gcp_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str, id_token: str
):
    response = await session.get(
        f"{uurl}?url={url}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {id_token}",
        },
    )
    return LatencyResponse(provider="gcp", region=region, latency=await response.text())


async def azure_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str
):
    response = await session.get(f"{uurl}?url={url}")
    return LatencyResponse(
        provider="azure", region=region, latency=await response.text()
    )


async def alibaba_request(
    session: aiohttp.ClientSession, uurl: str, url: str, region: str
):
    response = await session.get(f"{uurl}?url={url}")
    return LatencyResponse(
        provider="alicloud", region=region, latency=await response.text()
    )


async def pinger_streamer(url: str):
    request = google.auth.transport._aiohttp_requests.Request()
    id_token = await google.oauth2._id_token_async.fetch_id_token(request, "pinger")
    aws_id_token = await google.oauth2._id_token_async.fetch_id_token(
        request, "sts.amazonaws.com"
    )
    async with aws.client("sts") as client:
        sts_token = await client.assume_role_with_web_identity(
            RoleArn="arn:aws:iam::596309961293:role/ping-service-role",
            RoleSessionName="ping-service-session",
            WebIdentityToken=aws_id_token,
        )
    aws_creds = Credentials(
        access_key=sts_token["Credentials"]["AccessKeyId"],
        secret_key=sts_token["Credentials"]["SecretAccessKey"],
        token=sts_token["Credentials"]["SessionToken"],
    )
    async with aiohttp.ClientSession() as session:
        tasks: List[asyncio.Future[LatencyResponse]] = []
        for region, uurl in urls["faas.gcp"].items():
            task = asyncio.create_task(
                gcp_request(session, uurl, url, region, id_token)
            )
            tasks.append(task)
        for region, uurl in urls["faas.aws"].items():
            task = asyncio.create_task(
                aws_request(session, uurl, url, region, aws_creds)
            )
            tasks.append(task)
        for region, uurl in urls["faas.azure"].items():
            task = asyncio.create_task(azure_request(session, uurl, url, region))
            tasks.append(task)
        for region, uurl in urls["faas.alicloud"].items():
            task = asyncio.create_task(alibaba_request(session, uurl, url, region))
            tasks.append(task)

        for task in asyncio.as_completed(tasks):
            yield (await task).model_dump_json() + "\n"


@app.get("/")
async def root(url: str, user=Depends(get_user_token)):
    return StreamingResponse(pinger_streamer(url), media_type="application/x-ndjson")


@app.get("/liveness_check")
async def liveness_check():
    return "Ok!"


@app.get("/readiness_check")
async def readiness_check():
    return "Ok!"
