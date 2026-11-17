import sqlite3
from datetime import datetime

DB_NAME = "netnor_soporte.db"

def inicializar_bd():
    """Crea las tablas e inserta datos de prueba si la base de datos está vacía."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabla 1: Nodos zonales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodos (
            nodo_id TEXT PRIMARY KEY,
            estado_red TEXT NOT NULL,
            tiempo_estimado TEXT
        )
    ''')

    # Tabla 2: Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            dni INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            estado_cuenta TEXT NOT NULL,
            saldo_deuda REAL DEFAULT 0.0,
            nodo_zona TEXT NOT NULL,
            FOREIGN KEY (nodo_zona) REFERENCES nodos(nodo_id)
        )
    ''')

    # Tabla 3: Tickets generados por el bot
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni_cliente INTEGER NOT NULL,
            diagnostico TEXT NOT NULL,
            estado_ticket TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL,
            FOREIGN KEY (dni_cliente) REFERENCES clientes(dni)
        )
    ''')

    # Insertar datos iniciales de prueba (idempotente)
    cursor.execute("SELECT COUNT(*) FROM nodos")
    if cursor.fetchone()[0] == 0:
        nodos_prueba = [
            ("NODO-NORTE-01", "OPERATIVO", None),
            ("NODO-NORTE-02", "FALLA_MASIVA", "2 horas y 30 minutos")
        ]
        cursor.executemany("INSERT INTO nodos VALUES (?, ?, ?)", nodos_prueba)

        clientes_prueba = [
            # Caso 1: Cliente activo y nodo operativo (Flujo completo de diagnóstico)
            (11111111, "Juan Pérez", "ACTIVO", 0.0, "NODO-NORTE-01"),
            # Caso 2: Cliente con deuda vencida (Gateway 2 -> Fin por Mora)
            (22222222, "María Gómez", "MORA", 28500.50, "NODO-NORTE-01"),
            # Caso 3: Cliente al día pero en zona con corte masivo (Gateway 2 -> Fin Falla Zonal)
            (33333333, "Carlos López", "ACTIVO", 0.0, "NODO-NORTE-02"),
            # Caso 4: Segundo cliente operativo para pruebas múltiples
            (44444444, "Ana Martínez", "ACTIVO", 0.0, "NODO-NORTE-01")
        ]
        cursor.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?, ?)", clientes_prueba)

    conn.commit()
    conn.close()

def consultar_cliente(dni: int):
    """Busca un cliente por DNI junto con el estado de su nodo."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.dni, c.nombre, c.estado_cuenta, c.saldo_deuda, n.nodo_id, n.estado_red, n.tiempo_estimado
        FROM clientes c
        JOIN nodos n ON c.nodo_zona = n.nodo_id
        WHERE c.dni = ?
    ''', (dni,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado

def crear_ticket(dni: int, diagnostico: str, estado_ticket: str) -> int:
    """Registra el resultado del diagnóstico en la tabla tickets y devuelve el ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO tickets (dni_cliente, diagnostico, estado_ticket, fecha_creacion)
        VALUES (?, ?, ?, ?)
    ''', (dni, diagnostico, estado_ticket, fecha_actual))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

if __name__ == "__main__":
    inicializar_bd()
    print("Base de datos 'netnor_soporte.db' inicializada correctamente con datos de prueba.")