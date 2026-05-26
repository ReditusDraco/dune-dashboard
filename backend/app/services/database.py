"""Database service — psycopg3 connection pool and stored procedure executor."""

import logging
import time
from typing import Any, List

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_config, min_conn=2, max_conn=10, dashboard_schema="dashboard"):
        self.db_config = db_config
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.dashboard_schema = dashboard_schema
        self.pool = None

    def init_pool(self):
        if self.pool is not None:
            return self.pool

        conninfo = (
            f"host={self.db_config['host']} "
            f"port={self.db_config['port']} "
            f"dbname={self.db_config['database']} "
            f"user={self.db_config['user']} "
            f"password={self.db_config['password']}"
        )

        for attempt in range(10):
            try:
                self.pool = ConnectionPool(
                    conninfo=conninfo,
                    min_size=self.min_conn,
                    max_size=self.max_conn,
                    open=False,
                )
                self.pool.open(wait=True, timeout=20)
                logger.info("Database connection pool initialized (psycopg3)")
                return self.pool
            except Exception as e:
                if attempt < 9:
                    logger.warning(f"DB pool attempt {attempt + 1}/10 failed, retrying in 2s: {e}")
                    time.sleep(2)
                else:
                    logger.error(f"Failed to initialize database pool after 10 attempts: {e}")
                    self.pool = None
        return self.pool

    def call_function(self, name: str, args: List[Any]) -> List[dict]:
        """Call a dune schema function and return rows as dicts."""
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Database pool not available")

        placeholders = ",".join(["%s"] * len(args))
        sql = f"SELECT * FROM dune.{name}({placeholders})"

        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
                return rows if rows else []

    def call_procedure(self, name: str, args: List[Any]) -> None:
        """Call a dune schema procedure (void return)."""
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Database pool not available")

        placeholders = ",".join(["%s"] * len(args))
        sql = f"CALL dune.{name}({placeholders})"

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                conn.commit()

    def execute_readonly(self, sql: str, params: List[Any] | None = None) -> List[dict]:
        """Execute a read-only SELECT query."""
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Database pool not available")

        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or [])
                rows = cur.fetchall()
                return rows if rows else []

    def execute_mutation(self, sql: str, params: List[Any] | None = None) -> int:
        """Execute a direct mutation (UPDATE/INSERT/DELETE) with validation."""
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Database pool not available")

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                conn.commit()
                return cur.rowcount

    def health_check(self) -> bool:
        try:
            pool = self.init_pool()
            if not pool:
                return False
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception as e:
            logger.warning(f"Database health check FAILED: {e}")
            return False

    def ensure_tables(self):
        """Ensure dashboard schema tables exist."""
        pool = self.init_pool()
        if not pool:
            return

        schema = self.dashboard_schema
        ddl = f"""
        CREATE SCHEMA IF NOT EXISTS {schema};

        CREATE TABLE IF NOT EXISTS {schema}.audit_log (
            id BIGSERIAL PRIMARY KEY,
            action_type VARCHAR(50) NOT NULL,
            user_name VARCHAR(100) NOT NULL,
            target_player_id BIGINT,
            details JSONB DEFAULT '{{}}',
            source_ip INET,
            severity VARCHAR(20) DEFAULT 'info',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_audit_created_at ON {schema}.audit_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON {schema}.audit_log (action_type);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON {schema}.audit_log (user_name);

        CREATE TABLE IF NOT EXISTS {schema}.player_ips (
            player_id BIGINT PRIMARY KEY,
            ip_address INET NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS {schema}.bans (
            id SERIAL PRIMARY KEY,
            player_id BIGINT UNIQUE,
            account_id BIGINT,
            reason TEXT DEFAULT '',
            note TEXT DEFAULT '',
            duration INT DEFAULT 0,
            banned_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP,
            active BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS {schema}.player_actions (
            id SERIAL PRIMARY KEY,
            player_id BIGINT NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            reason TEXT DEFAULT '',
            note TEXT DEFAULT '',
            duration_minutes INT DEFAULT 0,
            ip_address INET,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS {schema}.chat_history (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT NOW(),
            channel VARCHAR(50),
            sender VARCHAR(255),
            message TEXT,
            target VARCHAR(255),
            location_x FLOAT,
            location_y FLOAT,
            location_z FLOAT,
            is_admin BOOLEAN DEFAULT FALSE
        );

        CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON {schema}.chat_history (timestamp DESC);

        CREATE TABLE IF NOT EXISTS {schema}.settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
                conn.commit()
        logger.info(f"Dashboard tables ensured in schema '{schema}'")

    def close(self):
        if self.pool:
            try:
                self.pool.close()
                logger.info("Database pool closed")
            except Exception as e:
                logger.error(f"Error closing pool: {e}")
            self.pool = None
