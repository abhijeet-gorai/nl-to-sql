"""
Database Connector Module
Provides unified interface for connecting to different database types
"""

from abc import ABC, abstractmethod
from typing import List, Dict
import pandas as pd
from dataclasses import dataclass

@dataclass
class ConnectionConfig:
    """Configuration for database connection"""
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_enabled: bool = False
    connection_params: Dict = None
    
    def __post_init__(self):
        if self.connection_params is None:
            self.connection_params = {}


class DatabaseConnector(ABC):
    """Abstract base class for database connectors"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connection = None
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to database"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close database connection"""
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict:
        """Test if connection is valid"""
        pass
    
    @abstractmethod
    def get_schemas(self) -> List[str]:
        """Get list of schemas"""
        pass
    
    @abstractmethod
    def get_tables(self, schema: str = None) -> List[Dict]:
        """Get list of tables in schema"""
        pass
    
    @abstractmethod
    def get_table_metadata(self, schema: str, table: str) -> Dict:
        """Get detailed metadata for a table"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results"""
        pass
    
    @abstractmethod
    def get_sample_data(self, schema: str, table: str, limit: int = 100) -> pd.DataFrame:
        """Get sample data from table"""
        pass


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        try:
            import psycopg2
            self.psycopg2 = psycopg2
        except ImportError:
            raise ImportError("psycopg2 is required for PostgreSQL connections. Install with: pip install psycopg2-binary")
    
    def connect(self) -> bool:
        """Establish connection to PostgreSQL"""
        try:
            self.connection = self.psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                sslmode='require' if self.config.ssl_enabled else 'prefer',
                connect_timeout=10
            )
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}")
    
    def disconnect(self):
        """Close PostgreSQL connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def test_connection(self) -> Dict:
        """Test PostgreSQL connection"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            cursor.close()
            self.disconnect()
            return {
                "success": True,
                "message": "Connection successful",
                "version": version
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_schemas(self) -> List[str]:
        """Get list of PostgreSQL schemas"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return schemas
    
    def get_tables(self, schema: str = 'public') -> List[Dict]:
        """Get list of tables in PostgreSQL schema"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT 
                table_name,
                (SELECT COUNT(*) FROM information_schema.columns 
                 WHERE table_schema = t.table_schema 
                 AND table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema,))
        
        tables = []
        for row in cursor.fetchall():
            tables.append({
                "table_name": row[0],
                "schema": schema,
                "column_count": row[1]
            })
        cursor.close()
        return tables
    
    def get_table_metadata(self, schema: str, table: str) -> Dict:
        """Get detailed metadata for a PostgreSQL table"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        # Get column information
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == 'YES',
                "default": row[3],
                "description": ""  # Will be filled by AI
            })
        
        # Get row count estimate
        try:
            cursor.execute("""
                SELECT reltuples::bigint AS estimate
                FROM pg_class
                WHERE oid = %s::regclass
            """, (f'{schema}.{table}',))
            result = cursor.fetchone()
            row_count = result[0] if result else 0
        except:
            row_count = 0
        
        cursor.close()
        
        return {
            "schema": schema,
            "table_name": table,
            "columns": columns,
            "row_count": int(row_count) if row_count else 0
        }
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query on PostgreSQL"""
        if not self.connection:
            self.connect()
        
        # Security: Ensure read-only
        query_upper = query.strip().upper()
        if not query_upper.startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        return pd.read_sql_query(query, self.connection)
    
    def get_sample_data(self, schema: str, table: str, limit: int = 100) -> pd.DataFrame:
        """Get sample data from PostgreSQL table"""
        query = f'SELECT * FROM "{schema}"."{table}" LIMIT {limit}'
        return self.execute_query(query)


class DB2Connector(DatabaseConnector):
    """IBM Db2 database connector"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        try:
            import ibm_db
            import ibm_db_dbi
            self.ibm_db = ibm_db
            self.ibm_db_dbi = ibm_db_dbi
        except ImportError:
            raise ImportError("ibm_db is required for IBM Db2 connections. Install with: pip install ibm-db")
    
    def connect(self) -> bool:
        """Establish connection to IBM Db2"""
        try:
            conn_str = (
                f"DATABASE={self.config.database};"
                f"HOSTNAME={self.config.host};"
                f"PORT={self.config.port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
            )
            
            if self.config.ssl_enabled:
                conn_str += "Security=SSL;"
            
            self.connection = self.ibm_db.connect(conn_str, "", "")
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to IBM Db2: {str(e)}")
    
    def disconnect(self):
        """Close IBM Db2 connection"""
        if self.connection:
            self.ibm_db.close(self.connection)
            self.connection = None
    
    def test_connection(self) -> Dict:
        """Test IBM Db2 connection"""
        try:
            self.connect()
            # Get DB2 version
            server_info = self.ibm_db.server_info(self.connection)
            self.disconnect()
            return {
                "success": True,
                "message": "Connection successful",
                "version": f"DB2 {server_info.DBMS_VER}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_schemas(self) -> List[str]:
        """Get list of IBM Db2 schemas"""
        if not self.connection:
            self.connect()
        
        stmt = self.ibm_db.exec_immediate(self.connection, """
            SELECT SCHEMANAME 
            FROM SYSCAT.SCHEMATA 
            WHERE SCHEMANAME NOT LIKE 'SYS%'
            ORDER BY SCHEMANAME
        """)
        
        schemas = []
        result = self.ibm_db.fetch_assoc(stmt)
        while result:
            schemas.append(result['SCHEMANAME'])
            result = self.ibm_db.fetch_assoc(stmt)
        
        return schemas
    
    def get_tables(self, schema: str = None) -> List[Dict]:
        """Get list of tables in IBM Db2 schema"""
        if not self.connection:
            self.connect()
        
        query = """
            SELECT TABNAME, COLCOUNT
            FROM SYSCAT.TABLES
            WHERE TYPE = 'T'
        """
        if schema:
            query += f" AND TABSCHEMA = '{schema}'"
        query += " ORDER BY TABNAME"
        
        stmt = self.ibm_db.exec_immediate(self.connection, query)
        
        tables = []
        result = self.ibm_db.fetch_assoc(stmt)
        while result:
            tables.append({
                "table_name": result['TABNAME'],
                "schema": schema,
                "column_count": result['COLCOUNT']
            })
            result = self.ibm_db.fetch_assoc(stmt)
        
        return tables
    
    def get_table_metadata(self, schema: str, table: str) -> Dict:
        """Get detailed metadata for an IBM Db2 table"""
        if not self.connection:
            self.connect()
        
        # Get column information
        query = f"""
            SELECT 
                COLNAME,
                TYPENAME,
                NULLS,
                DEFAULT
            FROM SYSCAT.COLUMNS
            WHERE TABSCHEMA = '{schema}' AND TABNAME = '{table}'
            ORDER BY COLNO
        """
        
        stmt = self.ibm_db.exec_immediate(self.connection, query)
        
        columns = []
        result = self.ibm_db.fetch_assoc(stmt)
        while result:
            columns.append({
                "name": result['COLNAME'],
                "type": result['TYPENAME'],
                "nullable": result['NULLS'] == 'Y',
                "default": result['DEFAULT'],
                "description": ""
            })
            result = self.ibm_db.fetch_assoc(stmt)
        
        # Get row count
        try:
            count_query = f'SELECT COUNT(*) as CNT FROM "{schema}"."{table}"'
            stmt = self.ibm_db.exec_immediate(self.connection, count_query)
            result = self.ibm_db.fetch_assoc(stmt)
            row_count = result['CNT'] if result else 0
        except:
            row_count = 0
        
        return {
            "schema": schema,
            "table_name": table,
            "columns": columns,
            "row_count": int(row_count) if row_count else 0
        }
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query on IBM Db2"""
        if not self.connection:
            self.connect()
        
        query_upper = query.strip().upper()
        if not query_upper.startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        # Use ibm_db_dbi for pandas compatibility
        conn_dbi = self.ibm_db_dbi.Connection(self.connection)
        return pd.read_sql_query(query, conn_dbi)
    
    def get_sample_data(self, schema: str, table: str, limit: int = 100) -> pd.DataFrame:
        """Get sample data from IBM Db2 table"""
        query = f'SELECT * FROM "{schema}"."{table}" FETCH FIRST {limit} ROWS ONLY'
        return self.execute_query(query)


def get_connector_class(db_type: str):
    """Factory function to get appropriate connector class"""
    db_type = db_type.lower()
    
    if db_type == 'postgresql':
        return PostgreSQLConnector
    elif db_type == 'db2':
        return DB2Connector
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

# Made with Bob
