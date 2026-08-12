from fastapi import APIRouter

from api.v1 import auth, claims, policies

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(claims.router)
api_router.include_router(policies.router)

__all__ = ["api_router"]
