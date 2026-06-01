"""Database service - connection pool and query helpers"""

import logging
import time
import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_config, min_conn=2, max_conn=10):
        self.db_config = db_config
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.pool = None

    def init_pool(self):
        if self.pool is None:
            # Retry up to 10 times with 2s delays (20s total) to handle startup race conditions
            for attempt in range(10):
                try:
                    self.pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=self.min_conn,
                        maxconn=self.max_conn,
                        **self.db_config
                    )
                    logger.info("Database connection pool initialized")
                    return self.pool
                except Exception as e:
                    if attempt < 9:
                        logger.warning(f"DB pool attempt {attempt + 1}/10 failed, retrying in 2s: {e}")
                        time.sleep(2)
                    else:
                        logger.error(f"Failed to initialize database pool after 10 attempts: {e}")
                        self.pool = None
        return self.pool

    def get_connection(self):
        try:
            pool = self.init_pool()
            if pool:
                return pool.getconn()
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            logger.error(f"Failed to get database connection: {e}")
            return None

    def return_connection(self, conn):
        if conn and self.pool and hasattr(conn, 'poll'):
            try:
                self.pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def close_all(self):
        if self.pool:
            try:
                self.pool.closeall()
            except Exception as e:
                logger.error(f"Error closing pool: {e}")
            self.pool = None

    def query(self, sql, params=None, one=False):
        conn = self.get_connection()
        if not conn:
            return {} if one else []
        cur = None
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            rows = cur.fetchall()
            if one and rows:
                return rows[0]
            if one:
                return {}
            return rows
        except Exception as e:
            logger.error(f"Database query error: {e}")
            raise
        finally:
            if cur:
                cur.close()
            self.return_connection(conn)

    def execute(self, sql, params=None, commit=True):
        conn = self.get_connection()
        if not conn:
            return False
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            if commit:
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cur:
                cur.close()
            self.return_connection(conn)

    def execute_with_conn(self, conn, sql, params=None):
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return cur
        except Exception:
            conn.rollback()
            raise

    def check_health(self):
        try:
            conn = self.get_connection()
            if not conn:
                logger.warning("Database health check: no connection available")
                return False
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.fetchone()
            cur.close()
            self.return_connection(conn)
            db_host = self.db_config.get('host', 'unknown')
            db_port = self.db_config.get('port', 'unknown')
            logger.debug(f"Database health check OK (host={db_host}, port={db_port})")
            return True
        except Exception as e:
            logger.warning(f"Database health check FAILED: {e}")
            return False

    def ensure_tables(self):
        """No-op: dashboard tables now live in a separate database."""
        pass


class DashboardDatabaseService:
    """Service for the dedicated dashboard database (player_ips, bans, audit_log, etc.)."""

    def __init__(self, db_config, min_conn=2, max_conn=10, owner='dune'):
        self.db_config = db_config
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.owner = owner
        self.pool = None
        self._migrated = False

    def init_pool(self):
        if self.pool is not None:
            return self.pool
        for attempt in range(10):
            try:
                self.pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=self.min_conn,
                    maxconn=self.max_conn,
                    **self.db_config
                )
                logger.info("Dashboard database pool initialized")
                return self.pool
            except psycopg2.OperationalError as e:
                if 'does not exist' in str(e) and attempt == 0:
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
        try:
            admin_config = dict(self.db_config)
            admin_config['database'] = 'postgres'
            conn = psycopg2.connect(**admin_config)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [self.db_config['database']])
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {self.db_config['database']} OWNER {self.db_config['user']}")
                logger.info("Created dashboard database '%s'", self.db_config['database'])
            cur.close()
            conn.close()
        except Exception as e:
            logger.error("Failed to create dashboard database: %s", e)
            raise

    def _migrate_old_schema(self, game_db):
        if self._migrated:
            return
        tables = ['settings', 'bans', 'player_ips', 'player_actions', 'audit_log', 'chat_history']
        migrated = False
        for table in tables:
            try:
                rows = game_db.query(f"SELECT count(*) as cnt FROM dashboard.{table}", one=True)
                if rows and rows.get('cnt', 0) > 0:
                    logger.info("Migrating %d rows from dashboard.%s", rows['cnt'], table)
                    old_rows = game_db.query(f"SELECT * FROM dashboard.{table}")
                    if old_rows:
                        cols = list(old_rows[0].keys())
                        placeholders = ','.join(['%s'] * len(cols))
                        col_names = ','.join(cols)
                        for row in old_rows:
                            vals = [row[c] for c in cols]
                            self.execute(
                                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                                vals,
                            )
                        migrated = True
                        logger.info("Migrated dashboard.%s -> %s (%d rows)", table, table, rows['cnt'])
            except Exception as e:
                logger.debug("No data to migrate from dashboard.%s: %s", table, e)
        if migrated:
            logger.info("Data migration from old dashboard schema complete")
        self._migrated = True

    def get_connection(self):
        try:
            pool = self.init_pool()
            if pool:
                return pool.getconn()
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            logger.error("Failed to get dashboard connection: %s", e)
            return None

    def return_connection(self, conn):
        if conn and self.pool and hasattr(conn, 'poll'):
            try:
                self.pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def close_all(self):
        if self.pool:
            try:
                self.pool.closeall()
            except Exception as e:
                logger.error("Error closing dashboard pool: %s", e)
            self.pool = None

    def query(self, sql, params=None, one=False):
        conn = self.get_connection()
        if not conn:
            return {} if one else []
        cur = None
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            rows = cur.fetchall()
            if one and rows:
                return rows[0]
            if one:
                return {}
            return rows
        except Exception as e:
            logger.error("Dashboard query error: %s", e)
            raise
        finally:
            if cur:
                cur.close()
            self.return_connection(conn)

    def execute(self, sql, params=None, commit=True):
        conn = self.get_connection()
        if not conn:
            return False
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            if commit:
                conn.commit()
            return True
        except Exception as e:
            logger.error("Dashboard execute error: %s", e)
            if conn:
                conn.rollback()
            return False
        finally:
            if cur:
                cur.close()
            self.return_connection(conn)

    def ensure_tables(self, game_db=None):
        conn = self.get_connection()
        if not conn:
            return
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS player_ips (
                    player_id BIGINT PRIMARY KEY,
                    ip_address INET NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS player_actions (
                    id SERIAL PRIMARY KEY,
                    player_id BIGINT NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    reason TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    duration_minutes INT DEFAULT 0,
                    ip_address INET,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    action_type VARCHAR(50) NOT NULL,
                    user_name VARCHAR(100) NOT NULL,
                    target_player_id BIGINT,
                    details JSONB DEFAULT '{}',
                    source_ip INET,
                    severity VARCHAR(20) DEFAULT 'info',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

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
            logger.info("Legacy dashboard tables ensured, owner=%s", owner)
        except Exception as e:
            logger.warning("Failed to ensure legacy dashboard tables: %s", e)
            if conn:
                conn.rollback()
        finally:
            if cur:
                cur.close()
            self.return_connection(conn)

        if game_db is not None:
            self._migrate_old_schema(game_db)

    def check_health(self):
        try:
            conn = self.get_connection()
            if not conn:
                return False
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.fetchone()
            cur.close()
            self.return_connection(conn)
            return True
        except Exception as e:
            logger.warning("Dashboard health check FAILED: %s", e)
            return False
