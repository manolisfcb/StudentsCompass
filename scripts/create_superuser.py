"""
Create or promote a superuser.
"""

import argparse
import asyncio
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update
from app.db import async_session, engine, Base
from app.models.userModel import User

# Import ALL models so SQLAlchemy can resolve relationships
from app.models.postModel import *            # noqa: F401,F403
from app.models.communityModel import *       # noqa: F401,F403
from app.models.communityPostModel import *   # noqa: F401,F403
from app.models.companyModel import *         # noqa: F401,F403
from app.models.jobPostingModel import *      # noqa: F401,F403
from app.models.applicationModel import *     # noqa: F401,F403
from app.models.questionnaireModel import *   # noqa: F401,F403
from app.models.resumeModel import *          # noqa: F401,F403
from app.models.resumeEmbeddingsModel import *# noqa: F401,F403
from app.models.resourceModel import *        # noqa: F401,F403
from app.models.userStatsModel import *       # noqa: F401,F403
from app.models.jobAnalysisModel import *     # noqa: F401,F403


async def create_superuser(email: str, password: str):
    """Register a brand-new user and flag it as superuser."""
    from app.services.userService import get_user_manager, get_user_db

    async with async_session() as session:
        # Check if already exists
        existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"⚠️  User {email} already exists (id={existing.id}).")
            if existing.is_superuser:
                print("   Already a superuser. Nothing to do.")
            else:
                existing.is_superuser = True
                existing.is_active = True
                existing.is_verified = True
                await session.commit()
                print("   ✅ Promoted to superuser!")
            return

        # Create new user via FastAPI-Users manager
        from fastapi_users.db import SQLAlchemyUserDatabase
        user_db = SQLAlchemyUserDatabase(session, User)

        from app.services.userService import UserManager
        manager = UserManager(user_db)

        from app.schemas.userSchema import UserCreate
        user_create = UserCreate(
            email=email,
            password=password,
            is_superuser=True,
            is_active=True,
            is_verified=True,
        )
        user = await manager.create(user_create)
        print(f"✅ Superuser created!")
        print(f"   Email:  {user.email}")
        print(f"   ID:     {user.id}")


async def promote_user(email: str):
    """Promote an existing user to superuser."""
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            print(f"❌ No user found with email: {email}")
            sys.exit(1)
        
        user.is_superuser = True
        user.is_verified = True
        await session.commit()
        print(f"✅ User {email} is now a superuser!")


async def main():
    parser = argparse.ArgumentParser(description="Create or promote a superuser")
    parser.add_argument("--email", required=True, help="Email for the superuser")
    parser.add_argument("--password", default=None, help="Password (required for new users)")
    parser.add_argument("--promote", action="store_true", help="Promote an existing user instead of creating")
    args = parser.parse_args()

    if args.promote:
        await promote_user(args.email)
    else:
        if not args.password:
            print("❌ --password is required when creating a new superuser")
            sys.exit(1)
        await create_superuser(args.email, args.password)


if __name__ == "__main__":
    asyncio.run(main())
