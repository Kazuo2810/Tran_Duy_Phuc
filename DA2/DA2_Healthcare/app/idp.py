"""Backend-to-backend client for the shared Iris Identity Provider."""
import os
import httpx
from fastapi import HTTPException

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "https://iris-auth-service.onrender.com").rstrip("/")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "healthcare-web")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")


def client_headers():
    if not OAUTH_CLIENT_SECRET:
        raise HTTPException(503, "Thiếu OAUTH_CLIENT_SECRET cho Healthcare.")
    return {"X-Client-ID": OAUTH_CLIENT_ID, "X-Client-Secret": OAUTH_CLIENT_SECRET}


async def idp_auth(path: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{AUTH_SERVICE_URL}{path}", json=payload, headers=client_headers())
        if response.status_code not in (200, 201):
            try:
                detail = response.json().get("detail", "IdP từ chối yêu cầu.")
            except ValueError:
                detail = "IdP trả về dữ liệu không hợp lệ."
            raise HTTPException(response.status_code, detail)
        return response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Trung tâm xác thực phản hồi quá thời gian.")
    except httpx.RequestError:
        raise HTTPException(503, "Không kết nối được iris-auth-service.")
