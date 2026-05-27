"""Database service — psycopg3 connection pool and stored procedure executor."""

import logging
import time
from typing import Any, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for game database queries (dune schema functions/procedures)."""

    def __init__(self, db_config, min_conn=2, max_conn=10):
        self.db_config = db_config
        self.min_conn = min_conn
        self.max_conn = max_conn
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

    def execute_readonly(self, sql: str, params: Optional[List[Any]] = None) -> List[dict]:
        """Execute a read-only SELECT query."""
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Database pool not available")

        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or [])
                rows = cur.fetchall()
                return rows if rows else []

    def execute_mutation(self, sql: str, params: Optional[List[Any]] = None) -> int:
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

    def close(self):
        if self.pool:
            try:
                self.pool.close()
                logger.info("Database pool closed")
            except Exception as e:
                logger.error(f"Error closing pool: {e}")
            self.pool = None


class DashboardDatabaseService:
    """Service for the dedicated dashboard database (player_ips, bans, audit_log, etc.)."""

    def __init__(self, db_config, min_conn=2, max_conn=10, owner="dune"):
        self.db_config = db_config
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.owner = owner
        self.pool = None
        self._migrated = False

    def _conninfo(self, dbname=None):
        return (
            f"host={self.db_config['host']} "
            f"port={self.db_config['port']} "
            f"dbname={dbname or self.db_config['database']} "
            f"user={self.db_config['user']} "
            f"password={self.db_config['password']}"
        )

    def _temp_connection(self, dbname="postgres"):
        """Get a temporary single connection (for database creation)."""
        conn = psycopg.connect(self._conninfo(dbname))
        conn.autocommit = True
        return conn

    def init_pool(self):
        if self.pool is not None:
            return self.pool

        conninfo = self._conninfo()

        for attempt in range(10):
            try:
                self.pool = ConnectionPool(
                    conninfo=conninfo,
                    min_size=self.min_conn,
                    max_size=self.max_conn,
                    open=False,
                )
                self.pool.open(wait=True, timeout=20)
                logger.info("Dashboard database pool initialized")
                return self.pool
            except psycopg.errors.OperationalError as e:
                if "does not exist" in str(e) and attempt == 0:
                    logger.info("Dashboard database does not exist, creating...")
                    self._ensure_database()
                    continue
                if attempt < 9:
                    logger.warning(f"Dashboard DB pool attempt {attempt + 1}/10 failed, retrying in 2s: {e}")
                    time.sleep(2)
                else:
                    logger.error(f"Failed to initialize dashboard pool after 10 attempts: {e}")
                    self.pool = None
            except Exception as e:
                if attempt < 9:
                    logger.warning(f"Dashboard DB pool attempt {attempt + 1}/10 failed, retrying in 2s: {e}")
                    time.sleep(2)
                else:
                    logger.error(f"Failed to initialize dashboard pool after 10 attempts: {e}")
                    self.pool = None
        return self.pool

    def _ensure_database(self):
        """Create the dashboard database if it doesn't exist."""
        try:
            conn = self._temp_connection("postgres")
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    [self.db_config["database"]],
                )
                if not cur.fetchone():
                    cur.execute(
                        f"CREATE DATABASE {self.db_config['database']} OWNER {self.db_config['user']}"
                    )
                    logger.info("Created dashboard database '%s'", self.db_config["database"])
                else:
                    logger.debug("Dashboard database already exists")
            conn.close()
        except Exception as e:
            logger.error("Failed to create dashboard database: %s", e)
            raise

    def _migrate_old_schema(self, game_db):
        """Migrate data from old dashboard schema in the game database."""
        if self._migrated:
            return

        tables = ["settings", "bans", "player_ips", "player_actions", "audit_log", "chat_history"]
        migrated = False

        for table in tables:
            try:
                rows = game_db.execute_readonly(
                    f"SELECT count(*) as cnt FROM dashboard.{table}"
                )
                if rows and rows[0]["cnt"] > 0:
                    logger.info("Migrating %d rows from dashboard.%s", rows[0]["cnt"], table)
                    old_rows = game_db.execute_readonly(f"SELECT * FROM dashboard.{table}")
                    if old_rows:
                        cols = list(old_rows[0].keys())
                        placeholders = ",".join([f"%s"] * len(cols))
                        col_names = ",".join(cols)
                        for row in old_rows:
                            vals = [row[c] for c in cols]
                            self.execute_mutation(
                                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                                vals,
                            )
                        migrated = True
                        logger.info("Migrated dashboard.%s → %s (%d rows)", table, table, rows[0]["cnt"])
            except Exception as e:
                logger.debug("No data to migrate from dashboard.%s: %s", table, e)

        if migrated:
            logger.info("Data migration from old dashboard schema complete")
        self._migrated = True

    def ensure_tables(self, game_db=None):
        """Ensure tables exist in the dashboard database and migrate if needed."""
        pool = self.init_pool()
        if not pool:
            return

        ddl = """
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            action_type VARCHAR(50) NOT NULL,
            user_name VARCHAR(100) NOT NULL,
            target_player_id BIGINT,
            details JSONB DEFAULT '{}',
            source_ip INET,
            severity VARCHAR(20) DEFAULT 'info',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action_type);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_name);

        CREATE TABLE IF NOT EXISTS player_ips (
            player_id BIGINT PRIMARY KEY,
            ip_address INET NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS bans (
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

        CREATE TABLE IF NOT EXISTS player_actions (
            id SERIAL PRIMARY KEY,
            player_id BIGINT NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            reason TEXT DEFAULT '',
            note TEXT DEFAULT '',
            duration_minutes INT DEFAULT 0,
            ip_address INET,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS chat_history (
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

        CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history (timestamp DESC);

        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)

                owner = self.owner
                cur.execute(f"""
                    DO $$DECLARE r RECORD;
                    BEGIN
                        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
                        LOOP
                            EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO {owner}';
                        END LOOP;
                    END$$;
                """)
                cur.execute(f"""
                    DO $$DECLARE r RECORD;
                    BEGIN
                        FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'
                        LOOP
                            EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequencename) || ' OWNER TO {owner}';
                        END LOOP;
                    END$$;
                """)
                cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {owner}")
                cur.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {owner}")

                conn.commit()

        logger.info("Dashboard tables ensured, owner=%s", owner)

        if game_db is not None:
            self._migrate_old_schema(game_db)

    def execute_readonly(self, sql: str, params: Optional[List[Any]] = None) -> List[dict]:
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Dashboard database pool not available")

        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or [])
                rows = cur.fetchall()
                return rows if rows else []

    def execute_mutation(self, sql: str, params: Optional[List[Any]] = None) -> int:
        pool = self.init_pool()
        if not pool:
            raise ConnectionError("Dashboard database pool not available")

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
            logger.warning("Dashboard database health check FAILED: %s", e)
            return False

    def close(self):
        if self.pool:
            try:
                self.pool.close()
                logger.info("Dashboard database pool closed")
            except Exception as e:
                logger.error("Error closing dashboard pool: %s", e)
            self.pool = None
