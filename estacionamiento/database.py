from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from estacionamiento.models import Base


class Database:
    def __init__(self, url: str = "sqlite:///estacionamiento.db") -> None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.__engine: Engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(self.__engine, "connect", self.__habilitar_claves_foraneas)
        self.__session_factory = sessionmaker(
            bind=self.__engine,
            expire_on_commit=False,
            class_=Session,
        )
        self.crear_tablas()

    @staticmethod
    def __habilitar_claves_foraneas(
        connection: sqlite3.Connection, record: object
    ) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def crear_tablas(self) -> None:
        Base.metadata.create_all(self.__engine)

    @contextmanager
    def sesion(self) -> Iterator[Session]:
        session = self.__session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def cerrar(self) -> None:
        self.__engine.dispose()
