"""PostgreSQL implementation of the existing product repository contract."""

from course2career.database_backend import DatabaseBackend
from course2career.database_migrations import migrate_postgres
from course2career.product_repository import SQLiteProductRepository


class PostgresProductRepository(SQLiteProductRepository):
    def __init__(
        self,
        database_url: str,
        *,
        allow_insecure_local_test: bool = False,
        require_verified_tls: bool = False,
    ) -> None:
        self.backend = DatabaseBackend(
            url=database_url,
            allow_insecure_local_test=allow_insecure_local_test,
            require_verified_tls=require_verified_tls,
        )
        migrate_postgres(self.backend)

    def _connect(self):
        return self.backend.connect()
