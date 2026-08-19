from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DB_PATH, PORT_RANGE_END, PORT_RANGE_START, TRAFFIC_LIMIT_GB

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    operation_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Tunnel(Base):
    __tablename__ = "tunnels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sub_type: Mapped[str] = mapped_column(String(16), default="vless", nullable=False, index=True)
    backend_id: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    meta_info: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    provisioning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    operation_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=int(TRAFFIC_LIMIT_GB * 1024**3), nullable=False)
    traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    @property
    def container_id(self):
        return self.backend_id

    @property
    def room_url(self):
        return self.meta_info


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.exec_driver_sql("PRAGMA table_info(balance_transactions)")
        tx_columns = {row[1] for row in result.fetchall()}
        if "operation_key" not in tx_columns:
            await conn.exec_driver_sql("ALTER TABLE balance_transactions ADD COLUMN operation_key VARCHAR(128)")
        result = await conn.exec_driver_sql("PRAGMA table_info(tunnels)")
        tunnel_columns = {row[1] for row in result.fetchall()}
        if "provisioning" not in tunnel_columns:
            await conn.exec_driver_sql("ALTER TABLE tunnels ADD COLUMN provisioning BOOLEAN NOT NULL DEFAULT 0")
        if "operation_key" not in tunnel_columns:
            await conn.exec_driver_sql("ALTER TABLE tunnels ADD COLUMN operation_key VARCHAR(128)")


async def get_or_create_user(session: AsyncSession, user_id: int) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        user = User(id=user_id, balance=0.0)
        session.add(user)
        await session.flush()
    return user


async def charge_balance(session: AsyncSession, user_id: int, amount: float, kind: str, description: str, operation_key: str | None = None) -> float:
    if amount <= 0:
        raise ValueError("Сумма списания должна быть положительной")
    if operation_key:
        existing = await session.scalar(select(BalanceTransaction).where(BalanceTransaction.operation_key == operation_key))
        if existing is not None:
            if existing.amount >= 0:
                raise RuntimeError("Ключ операции уже использован для другой операции")
            user = await session.scalar(select(User).where(User.id == user_id))
            if user is None:
                raise RuntimeError("Пользователь не найден")
            return user.balance
    result = await session.execute(update(User).where(User.id == user_id, User.balance >= amount).values(balance=User.balance - amount))
    if result.rowcount != 1:
        raise RuntimeError("Недостаточно средств")
    user = await session.scalar(select(User).where(User.id == user_id))
    session.add(BalanceTransaction(user_id=user_id, amount=-amount, balance_after=user.balance, kind=kind, description=description, operation_key=operation_key))
    return user.balance


async def credit_balance(session: AsyncSession, user_id: int, amount: float, kind: str, description: str, operation_key: str | None = None) -> float:
    if amount <= 0:
        raise ValueError("Сумма пополнения должна быть положительной")
    if operation_key:
        existing = await session.scalar(select(BalanceTransaction).where(BalanceTransaction.operation_key == operation_key))
        if existing is not None:
            user = await session.scalar(select(User).where(User.id == user_id))
            return user.balance if user else 0.0
    user = await get_or_create_user(session, user_id)
    user.balance += amount
    await session.flush()
    session.add(BalanceTransaction(user_id=user_id, amount=amount, balance_after=user.balance, kind=kind, description=description, operation_key=operation_key))
    return user.balance


async def get_free_port(session: AsyncSession) -> int:
    # Inactive tunnels keep their historical record, but their port is recycled
    # by setting it negative when the backend is successfully deactivated.
    used = set((await session.scalars(select(Tunnel.port).where(Tunnel.is_active.is_(True)))).all())
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port not in used:
            return port
    raise RuntimeError("Нет свободного порта")
