
"""Небольшой учебный обработчик заявок.

Тестовое задание САП КОД. Используются только синтетические данные.
"""

import sqlite3
from contextlib import closing


def _prepare_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            customer TEXT NOT NULL,
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_leads_source_external_id
        ON leads (source, external_id);
        """
    )


def process_event(event: dict, db_path: str) -> dict:
    """Обрабатывает событие и возвращает статус и ID заявки."""

    # 1. Проверяем тип входного события.
    if not isinstance(event, dict):
        return {
            "status": "invalid",
            "reason": "Event must be a dictionary",
        }

    # 2. Проверяем обязательные поля и удаляем пробелы по краям.
    fields = ("source", "external_id", "customer", "message")
    normalized = {}

    for field in fields:
        value = event.get(field)

        if not isinstance(value, str):
            return {
                "status": "invalid",
                "reason": f"{field} must be a string",
            }

        value = value.strip()

        if not value:
            return {
                "status": "invalid",
                "reason": f"{field} must not be empty",
            }

        normalized[field] = value

    # 3. Открываем соединение и управляем транзакцией.
    # closing гарантирует закрытие соединения после выхода из блока.
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _prepare_db(connection)

            # 4. Добавляем заявку, только если такой пары ещё нет.
            cursor = connection.execute(
                """
                INSERT INTO leads (source, external_id, customer, message)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO NOTHING
                """,
                (
                    normalized["source"],
                    normalized["external_id"],
                    normalized["customer"],
                    normalized["message"],
                ),
            )

            # 5. Если заявка уже существует, возвращаем её ID.
            if cursor.rowcount == 0:
                row = connection.execute(
                    """
                    SELECT id
                    FROM leads
                    WHERE source = ? AND external_id = ?
                    """,
                    (
                        normalized["source"],
                        normalized["external_id"],
                    ),
                ).fetchone()

                return {
                    "status": "duplicate",
                    "id": row[0],
                }

            # 6. Для новой заявки создаём ровно одно уведомление.
            lead_id = cursor.lastrowid

            connection.execute(
                "INSERT INTO notifications (lead_id) VALUES (?)",
                (lead_id,),
            )

            return {
                "status": "created",
                "id": lead_id,
            }
