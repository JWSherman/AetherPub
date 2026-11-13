from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.app.core.event_bus import event_bus

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("/stream")
async def event_stream():
    return StreamingResponse(
        event_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
