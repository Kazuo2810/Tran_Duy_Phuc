import uuid
from datetime import datetime, timezone
from sqlalchemy import insert
from .database import engine, audit_logs


def record(actor_id, action, resource_type="", resource_id="", metadata=None):
    with engine.begin() as con:
        con.execute(insert(audit_logs).values(
            id=str(uuid.uuid4()), actor_id=actor_id, action=action,
            resource_type=resource_type, resource_id=str(resource_id or ""),
            metadata=metadata or {}, created_at=datetime.now(timezone.utc),
        ))
