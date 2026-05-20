import asyncio
from backend.database.db import engine
from backend.database.models import Event, Organizer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def run():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Event.id, Event.organizer_id, Event.name))
        events = result.all()
        print('Events:')
        for e in events:
            print(f' - Event ID: {e.id}, Org ID: {e.organizer_id}, Name: {e.name}')
            
        orgs = await session.execute(select(Organizer.id, Organizer.email))
        print('\nOrganizers:')
        for o in orgs.all():
            print(f' - Org ID: {o.id}, Email: {o.email}')

asyncio.run(run())
