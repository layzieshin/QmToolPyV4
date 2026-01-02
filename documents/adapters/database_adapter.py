"""Database adapter abstraction.

Provides database-agnostic interface for repository layer.
Allows switching between SQLite, PostgreSQL, MySQL, etc.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional


class DatabaseAdapter(ABC):
    """Abstract database adapter for SQL operations."""

    @abstractmethod
    def execute(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a query and return cursor/result.

        Args:
            query: SQL query (may use ?  or %s placeholders)
            params: Query parameters

        Returns:
            Database cursor or result
        """
        raise NotImplementedError

    @abstractmethod
    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Fetch single row as dictionary.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row as dict or None
        """
        raise NotImplementedError

    @abstractmethod
    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Fetch all rows as list of dictionaries.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows (each row is a dict)
        """
        raise NotImplementedError

    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert row and return last inserted ID.

        Args:
            table: Table name
            data: Column-value mapping

        Returns:
            Last inserted row ID
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple = ()) -> int:
        """
        Update rows and return count of affected rows.

        Args:
            table: Table name
            data: Column-value mapping for SET clause
            where: WHERE clause (without "WHERE" keyword)
            where_params:  Parameters for WHERE clause

        Returns:
            Number of affected rows
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        """
        Delete rows and return count of affected rows.

        Args:
            table: Table name
            where: WHERE clause (without "WHERE" keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of deleted rows
        """
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        raise NotImplementedError

    @abstractmethod
    def executescript(self, script: str) -> None:
        """
        Execute multiple SQL statements (for schema creation).

        Args:
            script: Multi-statement SQL script
        """
        raise NotImplementedError