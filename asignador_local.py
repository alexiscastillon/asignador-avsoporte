import time
import requests
from datetime import datetime
from redminelib import Redmine

# --- CONFIGURACIÓN AGIP Y JSONBIN ---
URL_REDMINE = 'https://redmine.agip.gob.ar/'
MI_API_KEY = '5c5a1ada0bb1066b69ae6b78a8fe7a135701ab7f'
PROJECT_SLUG = 'soporte'

JSONBIN_ID = '6ad97155ac6210605a479aae'
JSONBIN_KEY = '$2a$10$Gy6oKS.5GwyesYEX6azXpehmmHY5ahMdBiwqm7LOQnhYIP3RgpaU2'
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

EQUIPO_AV = [
    {"nombre": "Alexis Castillon", "id": 458},   # Posición 1
    {"nombre": "Marien Gricel", "id": 232},      # Posición 2
    {"nombre": "De Yullis Nicolas", "id": 306}   # Posición 3
]

def obtener_estado_nube():
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        res = requests.get(f"{JSONBIN_URL}/latest", headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()['record']
    except Exception as e:
        print("⚠️ Error leyendo nube:", e)
    
    return {
        "ultimo_indice": -1,
        "conteo_diario": {p["nombre"]: 0 for p in EQUIPO_AV},
        "conteo_mensual": {p["nombre"]: 0 for p in EQUIPO_AV},
        "mes_operacion": datetime.now().strftime("%Y-%m"),
        "log_actividad": []
    }

def guardar_estado_nube(estado):
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    try:
        requests.put(JSONBIN_URL, json=estado, headers=headers, timeout=5)
    except Exception as e:
        print("⚠️ Error guardando en nube:", e)

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
    
    # Restricción de horario (09:00 a 18:00 hs) y días hábiles (Lunes a Viernes)
    if not es_simulacion:
        if ahora.weekday() >= 5:
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏸ Fin de semana. Robot pausado.")
            return

        if not (9 <= ahora.hour < 18):
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏸ Fuera de horario laboral (09:00 a 18:00 hs). Robot pausado.")
            return

    estado = obtener_estado_nube()

    # Reinicio automático mensual
    mes_actual = ahora.strftime("%Y-%m")
    if estado.get("mes_operacion") != mes_actual:
        estado["conteo_mensual"] = {p["nombre"]: 0 for p in EQUIPO_AV}
        estado["conteo_diario"] = {p["nombre"]: 0 for p in EQUIPO_AV}
        estado["mes_operacion"] = mes_actual
        registrar_log(estado, f"🧹 Cambio de mes ({mes_actual}): Contadores reiniciados.")

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
            registrar_log(estado, "🔍 Revisión: Sin tickets pendientes asignados a 'AV-Soporte'.")
            if not es_simulacion:
                guardar_estado_nube(estado)
            return

        modo_txt = "🧪 [SIMULACIÓN]" if es_simulacion else "🚀 [MODO REAL]"
        print(f"\n{modo_txt} Se encontraron {len(pendientes)} ticket(s) pendientes en 'AV-Soporte'.\n")

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
                params = {'assigned_to_id': usr_destino["id"]}
                if asunto_nuevo != asunto_actual:
                    params['subject'] = asunto_nuevo

                redmine.issue.update(issue.id, **params)

                estado["ultimo_indice"] = siguiente_idx
                estado["conteo_diario"][usr_destino["nombre"]] = estado["conteo_diario"].get(usr_destino["nombre"], 0) + 1
                estado["conteo_mensual"][usr_destino["nombre"]] = estado["conteo_mensual"].get(usr_destino["nombre"], 0) + 1

                registrar_log(estado, f"✅ Ticket #{issue.id} -> Asignado a {usr_destino['nombre']} (Asunto: '{asunto_nuevo}')")
                indice_temp = siguiente_idx

        if not es_simulacion:
            guardar_estado_nube(estado)

    except Exception as e:
        registrar_log(estado, f"❌ Error en Redmine: {e}")
        if not es_simulacion:
            guardar_estado_nube(estado)

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 PANEL DE CONTROL - ROBOT LOCAL AV-SOPORTE")
    print("=" * 60)
    print("1. Ejecutar PRUEBA DE SIMULACIÓN (Procesa una vez y SE DETIENE)")
    print("2. Iniciar EJECUCIÓN CONTINUA REAL (Revisa cada 1 min de 09 a 18 hs)")
    
    opcion = input("\n👉 Selecciona una opción (1 o 2) [Por defecto 1]: ").strip()

    if opcion == '2':
        print("\n🚀 INICIANDO MODO REAL EN BUCLE CONTINUO...")
        print("Presiona Ctrl+C para detenerlo en cualquier momento.\n")
        while True:
            ejecutar_ciclo(es_simulacion=False)
            time.sleep(60)
    else:
        print("\n👀 EJECUTANDO PRUEBA DE SIMULACIÓN ÚNICA...\n")
        ejecutar_ciclo(es_simulacion=True)
        print("🎉 Fin de la simulación. Ningún cambio fue aplicado en Redmine ni en Render.")
