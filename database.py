from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_PATH, PORT_RANGE_END, PORT_RANGE_START, TRAFFIC_LIMIT_GB

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class Tunnel(Base):
    __tablename__ = "tunnels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sub_type: Mapped[str] = mapped_column(String(16), default="vless", nullable=False, index=True)
    backend_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    meta_info: Mapped[str] = mapped_column(String(2048), nullable=False)
    port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    traffic_limit_bytes: Mapped[int] = mapped_column(
        BigInteger, default=int(TRAFFIC_LIMIT_GB * 1024**3), nullable=False
    )

    @property
    def container_id(self) -> str:
        """Backward-compatible alias for the backend identifier."""
        return self.backend_id

    @property
    def room_url(self) -> str:
        """Backward-compatible alias for backend metadata."""
        return self.meta_info


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(session: AsyncSession, user_id: int) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        user = User(id=user_id, balance=0.0)
        session.add(user)
        await session.flush()
    return user


async def get_free_port(session: AsyncSession) -> int:
    used = set(
        (await session.scalars(select(Tunnel.port).where(Tunnel.is_active.is_(True)))).all()
    )
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port not in used:
            return port
    raise RuntimeError("Свободных портов в заданном диапазоне нет")
