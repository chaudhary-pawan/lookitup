import time
from collections import defaultdict
from fastapi import Request, HTTPException, status

# In-memory rate limiting state
_rate_limit_records = defaultdict(list)

def rate_limiter(limit: int, window: int):
    """
    FastAPI dependency for simple in-memory sliding-window rate limiting.
    limit: number of allowed requests in the window
    window: time window in seconds
    """
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Filter records within the window
        request_times = _rate_limit_records[client_ip]
        request_times = [t for t in request_times if now - t < window]
        _rate_limit_records[client_ip] = request_times
        
        if len(request_times) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
            
        _rate_limit_records[client_ip].append(now)
    return dependency
