import asyncio
import os
import jwt
from datetime import datetime, timedelta
from backend.database.db import engine
from backend.database.models import Organizer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import urllib.request
import urllib.error
import json

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-in-prod")

async def run():
    # 1. Get the organizer ID
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Organizer).where(Organizer.email == '9536guru@gmail.com'))
        org = result.scalar_one_or_none()
        if not org:
            print("Organizer not found")
            return
        org_id = org.id
        print(f"Organizer ID: {org_id}")

    # 2. Generate Token
    expire = datetime.utcnow() + timedelta(minutes=60)
    token = jwt.encode({"sub": org_id, "exp": expire}, SECRET_KEY, algorithm="HS256")

    # 3. Hit the DELETE endpoint
    event_id = "483301f4-1eef-4e9e-a473-aba3fdd3b50a"
    url = f"http://localhost:8000/api/events/{event_id}"
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")
    
    try:
        response = urllib.request.urlopen(req)
        print(f"Response code: {response.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        body = e.read().decode('utf-8')
        print(f"Body: {body}")

asyncio.run(run())
