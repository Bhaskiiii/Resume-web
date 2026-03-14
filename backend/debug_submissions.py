import asyncio
from main import get_submissions, mock_db
from datetime import datetime

async def test():
    # Simulate data
    mock_db.append({
        "name": "Test",
        "email": "test@test.com",
        "message": "Hello",
        "created_at": datetime.utcnow()
    })
    try:
        res = await get_submissions()
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
