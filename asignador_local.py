import time
import json
import os
import requests
from datetime import datetime
from redminelib import Redmine

# --- CONFIGURACIÓN CONEXIÓN AGIP ---
URL_REDMINE = 'https://redmine.agip.gob.ar/'
MI_API_KEY = '5c5a1ada0bb1066b69ae6b78a8fe7a135701ab7f'
PROJECT_SLUG = 'soporte'

# --- CONFIGURACIÓN JSONBIN ---
JSONBIN_ID = '6ad97155ac6210605a479aae'
JSONBIN_KEY = '$2a$10$Gy6oKS.5GwyesYEX6azXpehmmHY5ahMdBiwqm7LOQnhYIP3RgpaU2'
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

CACHE_FILE = "cache_local.json"

EQUIPO_AV = [
    {"nombre": "Alexis Castillon", "id": 458},   # Posición 0
    {"nombre": "Marien Gricel", "id": 232},      # Posición 1
    {"nombre": "De Yullis Nicolas", "id": 306}   # Posición 2
]

class CloudStorageError(Exception):
    """Excepción para errores críticos de sincronización con la nube."""
    pass

def guardar_cache_local(ultimo_idx):
    """Guarda un respaldo local por si se cae internet."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ultimo_indice": ultimo_idx}, f)
    except Exception:
        pass

def obtener_cache_local():
    """Lee el respaldo local si falla la nube."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("ultimo_indice", -1)
        except Exception:
            return -1
    return -1

def obtener_estado_nube():
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        res = requests.get(f"{JSONBIN_URL}/latest", headers=headers, timeout=10)
        if res.status_code == 200:
            record = res.json()['record']
            guardar_cache_local(record.get("ultimo_indice", -1))
            return record
        else:
            raise CloudStorageError(f"Respuesta no válida de JSONBin. Status Code: {res.status_code}")
    except requests.RequestException as e:
        raise CloudStorageError(f"Error de red al conectar con JSONBin: {e}")

def guardar_estado_nube(estado):
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    try:
        res = requests.put(JSONBIN_URL, json=estado, headers=headers, timeout=10)
        if res.status_code != 200:
            raise CloudStorageError(f"No se pudo guardar el estado en JSONBin. Status Code: {res.status_code}")
        guardar_cache_local(estado.get("ultimo_indice", -1))
    except requests.RequestException as e:
        raise CloudStorageError(f"Error de red al guardar en JSONBin: {e}")

def mostrar_alerta_manual(ultimo_idx, motivo_error):
    """Imprime en consola un reporte claro para continuar la asignación manual."""
    siguiente_idx = (ultimo_idx + 1) % len(EQUIPO_AV)
    
    nombre_ultimo = EQUIPO_AV[ultimo_idx]["nombre"] if ultimo_idx != -1 else "Ninguno registrado"
    nombre_siguiente = EQUIPO_AV[siguiente_idx]["nombre"]

    print("\n" + "🚨" * 30)
    print(" ⚠️  ATENCIÓN: ASIGNACIÓN AUTOMÁTICA DETENIDA")
    print("🚨" * 30)
    print(f"❌ Motivo: {motivo_error}")
    print("-" * 60)
    print(f"📌 ÚLTIMO ASIGNADO REGISTRADO : {nombre_ultimo} (Posición #{ultimo_idx + 1 if ultimo_idx != -1 else 0})")
    print(f"👉 PRÓXIMO A RECIBIR TICKET   : {nombre_siguiente} (Posición #{siguiente_idx + 1})")
    print("-" * 60)
    print("💡 ORDEN COMPLETO DE ROTACIÓN MANUAL:")
    for idx, persona in enumerate(EQUIPO_AV):
        marcador = "➡️ " if idx == siguiente_idx else "   "
        print(f"   {marcador}{idx + 1}. {persona['nombre']}")
    print("🚨" * 30 + "\n")

def registrar_log(estado, mensaje):
    hora = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{hora}] {mensaje}"
    print(log_entry)
    estado.setdefault("log_actividad", [])
    estado["log_actividad"].insert(0, log_entry)
    if len(estado["log_actividad"]) > 50:
        estado["log_actividad"].pop()

def ejecutar_ciclo(es_simulacion=False):
    ahora = datetime.now()
    
    # Restricción de horario laboral (09:00 a 18:00 hs) y días hábiles
    if not es_simulacion:
        if ahora.weekday() >= 5:
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏸ Fin de semana. Robot pausado.")
            return

        if not (9 <= ahora.hour < 18):
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏸ Fuera de horario laboral. Robot pausado.")
            return

    # Obtención segura del estado
    try:
        estado = obtener_estado_nube()
    except CloudStorageError as e:
        ultimo_idx_conocido = obtener_cache_local()
        mostrar_alerta_manual(ultimo_idx_conocido, str(e))
        return

    fecha_actual = ahora.strftime("%Y-%m-%d")
    mes_actual = ahora.strftime("%Y-%m")

    # Reinicio automático diario
    if estado.get("fecha_operacion") != fecha_actual:
        estado["conteo_diario"] = {p["nombre"]: 0 for p in EQUIPO_AV}
        estado["fecha_operacion"] = fecha_actual
        registrar_log(estado, f"📅 Nuevo día ({fecha_actual}): Conteo diario reiniciado.")

    # Reinicio automático mensual
    if estado.get("mes_operacion") != mes_actual:
        estado["conteo_mensual"] = {p["nombre"]: 0 for p in EQUIPO_AV}
        estado["mes_operacion"] = mes_actual
        registrar_log(estado, f"🧹 Nuevo mes ({mes_actual}): Conteo mensual reiniciado.")

    try:
        redmine = Redmine(URL_REDMINE, key=MI_API_KEY)
        
        todos_nuevos = list(redmine.issue.filter(
            project_id=PROJECT_SLUG,
            status_id='1',
            sort='created_on:asc'
        ))

        pendientes = [
            i for i in todos_nuevos 
            if hasattr(i, 'assigned_to') and i.assigned_to.name == 'AV-Soporte'
        ]

        if not pendientes:
            registrar_log(estado, "🔍 Revisión: Sin tickets pendientes en 'AV-Soporte'.")
            if not es_simulacion:
                guardar_estado_nube(estado)
            return

        modo_txt = "🧪 [SIMULACIÓN]" if es_simulacion else "🚀 [MODO REAL]"
        print(f"\n{modo_txt} Se encontraron {len(pendientes)} ticket(s) pendientes.\n")

        indice_temp = estado.get("ultimo_indice", -1)

        for issue in pendientes:
            asunto_actual = issue.subject
            asunto_nuevo = asunto_actual if asunto_actual.startswith('-AV-S-') else f"-AV-S-{asunto_actual}"

            siguiente_idx = (indice_temp + 1) % len(EQUIPO_AV)
            usr_destino = EQUIPO_AV[siguiente_idx]

            if es_simulacion:
                print(f" 🆕 Ticket #{issue.id}")
                print(f"    ├─ Asunto actual:  {asunto_actual}")
                print(f"    ├─ Asunto nuevo:   {asunto_nuevo}")
                print(f"    └─ Se asignaría a: {usr_destino['nombre']} (Posición #{siguiente_idx + 1})\n" + "-"*50)
                indice_temp = siguiente_idx
            else:
                try:
                    params = {'assigned_to_id': usr_destino["id"]}
                    if asunto_nuevo != asunto_actual:
                        params['subject'] = asunto_nuevo

                    # Asignación en Redmine
                    redmine.issue.update(issue.id, **params)

                    # Actualización de contadores e índices tras confirmar asignación
                    estado["ultimo_indice"] = siguiente_idx
                    estado["conteo_diario"][usr_destino["nombre"]] = estado["conteo_diario"].get(usr_destino["nombre"], 0) + 1
                    estado["conteo_mensual"][usr_destino["nombre"]] = estado["conteo_mensual"].get(usr_destino["nombre"], 0) + 1

                    registrar_log(estado, f"✅ Ticket #{issue.id} -> Asignado a {usr_destino['nombre']}")
                    indice_temp = siguiente_idx

                    # Guardado progresivo en la nube por cada ticket procesado
                    guardar_estado_nube(estado)

                except Exception as err_issue:
                    registrar_log(estado, f"⚠️ Error procesando Ticket #{issue.id} en Redmine: {err_issue}")
                    mostrar_alerta_manual(estado.get("ultimo_indice", -1), f"Fallo al actualizar Ticket #{issue.id} en Redmine")

    except Exception as e:
        registrar_log(estado, f"❌ Error general en la consulta de Redmine: {e}")
        mostrar_alerta_manual(estado.get("ultimo_indice", -1), f"Error de conexión con Redmine: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 PANEL DE CONTROL - ROBOT LOCAL AV-SOPORTE")
    print("=" * 60)
    print("1. Ejecutar PRUEBA DE SIMULACIÓN")
    print("2. Iniciar EJECUCIÓN CONTINUA REAL (Cada 3 min)")
    
    opcion = input("\n👉 Selecciona una opción (1 o 2) [Por defecto 1]: ").strip()

    if opcion == '2':
        print("\n🚀 INICIANDO MODO REAL EN BUCLE CONTINUO...")
        while True:
            ejecutar_ciclo(es_simulacion=False)
            time.sleep(180)
    else:
        print("\n👀 EJECUTANDO PRUEBA DE SIMULACIÓN ÚNICA...\n")
        ejecutar_ciclo(es_simulacion=True)
