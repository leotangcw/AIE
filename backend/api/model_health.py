"""模型健康状态 API"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["model-health"])


@router.get("/model-status")
async def get_model_status(request: Request):
    """获取当前模型健康状态"""
    tracker = request.app.state.shared.get("model_health_tracker")
    if not tracker:
        return {"error": "ModelHealthTracker not initialized"}
    return tracker.get_status()
