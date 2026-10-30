from fastapi import APIRouter

from app.api.v1 import auth, conversations, documents, organizations, providers, workspaces

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(providers.router)
api_router.include_router(conversations.router)
