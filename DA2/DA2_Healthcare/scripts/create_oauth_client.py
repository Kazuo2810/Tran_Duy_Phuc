"""Tạo secret mới và SQL đăng ký OAuth client trong public.oauth_clients.
Chạy local; không commit output và không gửi secret lên GitHub.
"""
import hashlib
import json
import secrets

client_id = "healthcare-web"
secret = secrets.token_urlsafe(48)
digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
scopes = json.dumps(["healthcare:access"], separators=(",", ":"))
print("OAUTH_CLIENT_ID=" + client_id)
print("OAUTH_CLIENT_SECRET=" + secret)
print("OAUTH_REQUIRED_SCOPE=healthcare:access")
print("\nChạy SQL sau trong Pgweb để đăng ký client:")
print(f"""INSERT INTO public.oauth_clients
(client_id, client_name, client_secret_hash, redirect_uris, scopes, active, created_at)
VALUES ('{client_id}', 'Healthcare WDBC App', '{digest}', '[]', '{scopes}', TRUE, NOW()::text)
ON CONFLICT (client_id) DO UPDATE SET
  client_name = EXCLUDED.client_name,
  client_secret_hash = EXCLUDED.client_secret_hash,
  scopes = EXCLUDED.scopes,
  active = TRUE;""")
print("\nChỉ lưu OAUTH_CLIENT_SECRET trong Environment Variables của Healthcare Render service.")
