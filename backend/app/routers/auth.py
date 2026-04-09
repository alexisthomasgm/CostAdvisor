from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.schemas.user import UserOut, UserWithTeams

router = APIRouter()
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def create_jwt(user_id: uuid.UUID) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: extract and validate JWT from cookie, return User."""
    token = request.cookies.get("ca_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/login")
async def login():
    """Redirect user to Google OAuth consent screen."""
    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=f"{settings.api_url}/auth/callback",
        scope="openid email profile",
    )
    uri, _state = client.create_authorization_url(GOOGLE_AUTH_URL)
    return RedirectResponse(url=uri)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=f"{settings.api_url}/auth/callback",
    )

    # Exchange code for tokens
    token = await client.fetch_token(GOOGLE_TOKEN_URL, code=code)

    # Get user info from Google
    client.token = token
    resp = await client.get(GOOGLE_USERINFO_URL)
    userinfo = resp.json()

    google_id = userinfo["sub"]
    email = userinfo["email"]
    display_name = userinfo.get("name", email.split("@")[0])
    avatar_url = userinfo.get("picture")

    # Upsert user
    user = db.query(User).filter(User.google_id == google_id).first()
    if user is None:
        user = User(
            google_id=google_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
        db.flush()

        # Create a default personal team for new users
        team = Team(name=f"{display_name}'s Team", created_by=user.id)
        db.add(team)
        db.flush()

        membership = TeamMembership(user_id=user.id, team_id=team.id, role="owner")
        db.add(membership)
    else:
        user.last_login_at = datetime.now(timezone.utc)
        user.display_name = display_name
        user.avatar_url = avatar_url

    db.commit()

    # Issue JWT cookie and redirect to frontend
    token_str = create_jwt(user.id)
    response = RedirectResponse(url=settings.app_url, status_code=302)
    is_prod = settings.environment != "development"
    response.set_cookie(
        key="ca_token",
        value=token_str,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=settings.jwt_expiry_hours * 3600,
    )
    return response


@router.get("/me", response_model=UserWithTeams)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user with their team memberships."""
    return current_user


@router.post("/logout")
def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie("ca_token")
    return {"status": "logged out"}