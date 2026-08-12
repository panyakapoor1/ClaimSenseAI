import os

from fastapi import APIRouter, Request, Response, status

from api.deps import CurrentUser, SessionDep
from core.security import SESSION_COOKIE
from schemas.auth import LoginRequest, SessionOut, UserOut
from services import auth as auth_service
from services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookies are only marked Secure when the app is actually served over HTTPS;
# a Secure cookie is silently dropped over plain http://localhost in development.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,      # unreadable from JavaScript, so XSS cannot exfiltrate it
        samesite="lax",     # not sent on cross-site POSTs, which blunts CSRF
        secure=COOKIE_SECURE,
        path="/",
    )


@router.post("/login", response_model=SessionOut, summary="Sign in")
async def login(body: LoginRequest, request: Request, response: Response, session: SessionDep):
    user = await auth_service.authenticate(session, body.email, body.password)
    token, max_age = auth_service.issue_token(user)

    _set_session_cookie(response, token, max_age)

    await record_audit(
        session,
        actor=user,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        request=request,
    )

    # Also returned in the body so a Server Component, which cannot receive the
    # cookie, can forward it as a bearer token.
    response.headers["X-Session-Token"] = token

    return SessionOut(
        user=UserOut.model_validate(user),
        capabilities=sorted(auth_service.capabilities_for(user.role)),
        expires_in=max_age,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(request: Request, response: Response, session: SessionDep, user: CurrentUser):
    await record_audit(
        session,
        actor=user,
        action="auth.logout",
        entity_type="user",
        entity_id=str(user.id),
        request=request,
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=SessionOut, summary="The signed-in user")
async def me(user: CurrentUser):
    return SessionOut(
        user=UserOut.model_validate(user),
        capabilities=sorted(auth_service.capabilities_for(user.role)),
        expires_in=0,
    )
