import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_db_session
from backend.core.models import Tenant
from backend.core.schemas import TokenRequest, TokenResponse
from backend.core.security import hash_api_key, create_access_token

router = APIRouter()
logger = structlog.get_logger("aboutcloud.auth")


@router.post("/token", response_model=TokenResponse)
async def login(
    body: TokenRequest,
    db: AsyncSession = Depends(get_db_session),
):
    key_hash = hash_api_key(body.api_key)
    result = await db.execute(
        select(Tenant).where(Tenant.api_key_hash == key_hash)
    )
    tenant = result.scalar_one_or_none()

    if tenant is None:
        logger.warning("auth_failed", reason="invalid_api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not tenant.is_active:
        logger.warning("auth_failed", tenant_id=str(tenant.id), reason="inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is deactivated",
        )

    settings = get_settings()
    access_token = create_access_token(
        tenant_id=str(tenant.id),
        extra_claims={"tenant_name": tenant.name},
    )

    logger.info("auth_success", tenant_id=str(tenant.id), tenant_name=tenant.name)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: TokenRequest,
    db: AsyncSession = Depends(get_db_session),
):
    return await login(body=body, db=db)
