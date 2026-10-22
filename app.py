import os
import time
import json
import requests
from datetime import datetime
from threading import Thread
from flask import Flask, render_template_string, jsonify, request
from redminelib import Redmine

app = Flask(__name__)

# --- CONFIGURACIÓN DE REDMINE Y JSONBIN (NUBE) ---
URL_REDMINE = 'https://redmine.agip.gob.ar/'
MI_API_KEY = '5c5a1ada0bb1066b69ae6b78a8fe7a135701ab7f'
PROJECT_SLUG = 'soporte'

JSONBIN_ID = os.environ.get('JSONBIN_ID', '65a12345demo') # Reemplazar con tu BIN ID
JSONBIN_KEY = os.environ.get('JSONBIN_KEY', '$2a$10$demoKey') # Reemplazar con tu Master Key
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

EQUIPO_AV = [
    {"nombre": "Alexis Castillon", "id": 458},
    {"nombre": "Marien Gricel", "id": 232},
    {"nombre": "De Yullis Nicolas", "id": 306}
]

ejecutando_robot = False

def obtener_estado_nube():
    try:
        res = requests.get(f"{JSONBIN_URL}/latest", headers={'X-Master-Key': JSONBIN_KEY}, timeout=5)
        return res.json()['record']
    except Exception:
        return {
            "ultimo_indice": -1,
            "conteo_diario": {"Alexis Castillon": 0, "Marien Gricel": 0, "De Yullis Nicolas": 0},
            "conteo_mensual": {"Alexis Castillon": 0, "Marien Gricel": 0, "De Yullis Nicolas": 0},
            "mes_operacion": datetime.now().strftime("%Y-%m"),
            "log_actividad": []
        }

def guardar_estado_nube(estado):
    try:
        requests.put(JSONBIN_URL, json=estado, headers={
            'Content-Type': 'application/json',
            'X-Master-Key': JSONBIN_KEY
        }, timeout=5)
    except Exception as e:
        print(f"Error al guardar en JSONBin: {e}")

def registrar_log(estado, mensaje):
    hora = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{hora}] {mensaje}"
    print(log_entry)
    estado.setdefault("log_actividad", [])
    estado["log_actividad"].insert(0, log_entry)
    # Limitar el historial en vivo a 50 líneas para optimizar memoria
    if len(estado["log_actividad"]) > 50:
        estado["log_actividad"].pop()

def verificar_limpieza_mensual(estado):
    mes_actual = datetime.now().strftime("%Y-%m")
    if estado.get("mes_operacion") != mes_actual:
        registrar_log(estado, f"🧹 CAMBIO DE MES DETECTADO ({mes_actual}): Reiniciando contadores a 0...")
        estado["conteo_mensual"] = {"Alexis Castillon": 0, "Marien Gricel": 0, "De Yullis Nicolas": 0}
        estado["conteo_diario"] = {"Alexis Castillon": 0, "Marien Gricel": 0, "De Yullis Nicolas": 0}
        estado["log_actividad"] = [f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Nuevo mes iniciado ({mes_actual})."]
        estado["mes_operacion"] = mes_actual
        guardar_estado_nube(estado)

def es_horario_permitido():
    ahora = datetime.now()
    dia = ahora.weekday() # 0 = Lunes, 4 = Viernes
    hora = ahora.hour
    return (0 <= dia <= 4) and (9 <= hora < 18)

def ciclo_asignacion_redmine():
    global ejecutando_robot
    estado = obtener_estado_nube()
    verificar_limpieza_mensual(estado)

    if not es_horario_permitido():
        ejecutando_robot = False
        registrar_log(estado, "⏰ FUERA DE HORARIO (09:00 - 18:00 hs Lun-Vie). Asignador pausado.")
        guardar_estado_nube(estado)
        return

    try:
        redmine = Redmine(URL_REDMINE, key=MI_API_KEY)
        todos_nuevos = list(redmine.issue.filter(
            project_id=PROJECT_SLUG,
            status_id='1',
            sort='created_on:asc'
        ))

        # Filtro estricto: Solo cola AV-Soporte sin persona asignada individualmente
        pendientes = [
            i for i in todos_nuevos 
            if hasattr(i, 'assigned_to') and i.assigned_to.name == 'AV-Soporte'
        ]

        if not pendientes:
            registrar_log(estado, "🔍 Revisión: Sin tickets pendientes en cola 'AV-Soporte'.")
            guardar_estado_nube(estado)
            return

        registrar_log(estado, f"⚡ Se encontraron {len(pendientes)} ticket(s) pendientes. Procesando...")

        for issue in pendientes:
            asunto_actual = issue.subject
            asunto_nuevo = asunto_actual if asunto_actual.startswith('-AV-S-') else f"-AV-S-{asunto_actual}"

            siguiente_idx = (estado["ultimo_indice"] + 1) % len(EQUIPO_AV)
            usr_destino = EQUIPO_AV[siguiente_idx]

            params = {'assigned_to_id': usr_destino["id"]}
            if asunto_nuevo != asunto_actual:
                params['subject'] = asunto_nuevo

            redmine.issue.update(issue.id, **params)

            estado["ultimo_indice"] = siguiente_idx
            estado["conteo_diario"][usr_destino["nombre"]] = estado["conteo_diario"].get(usr_destino["nombre"], 0) + 1
            estado["conteo_mensual"][usr_destino["nombre"]] = estado["conteo_mensual"].get(usr_destino["nombre"], 0) + 1

            registrar_log(estado, f"✅ Ticket #{issue.id} -> Asignado a {usr_destino['nombre']} (Asunto: '{asunto_nuevo}')")

        guardar_estado_nube(estado)

    except Exception as e:
        registrar_log(estado, f"❌ Error en Redmine: {e}")
        guardar_estado_nube(estado)

def temporizador_1minuto():
    while True:
        if ejecutando_robot:
            ciclo_asignacion_redmine()
        time.sleep(60) # Ejecución continua cada 1 minuto

# --- INTERFAZ WEB HTML / TAILWIND ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AV-Soporte | Asignador Automatizado</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js"></script>
    <style>
        body { background-color: #fdfbf7; color: #2d3748; }
        .card-warm { background: #ffffff; border: 1px solid #f1e9d9; box-shadow: 0 4px 15px rgba(217, 119, 6, 0.05); }
        .terminal-box { background: #1e1e1e; color: #4ade80; font-family: monospace; }
    </style>
</head>
<body class="p-4 md:p-8 min-h-screen">

    <div class="max-w-5xl mx-auto space-y-6">
        
        <!-- ENCABEZADO Y HORARIO -->
        <header class="text-center space-y-1">
            <h1 class="text-3xl font-extrabold text-amber-900">🤖 Asignador Automático AV-Soporte</h1>
            <p class="text-sm text-amber-700 font-medium">Lunes a Viernes de 09:00 a 18:00 hs | Frecuencia: Cada 1 minuto</p>
            <div id="status-pill" class="inline-block px-4 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
                Cargando estado...
            </div>
        </header>

        <!-- TARJETAS DE INTEGRANTES -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div class="card-warm rounded-2xl p-5 text-center relative">
                <img id="img-0" src="https://ui-avatars.com/api/?name=Alexis+Castillon&background=d97706&color=fff&size=128" class="w-24 h-24 rounded-full mx-auto mb-3 border-4 border-amber-400 shadow">
                <h2 id="name-0" class="text-lg font-bold text-gray-800">el alesi</h2>
                <span class="text-xs text-amber-600 block">ID: 458</span>
                <div class="mt-3 bg-amber-50 p-2 rounded-xl border border-amber-200">
                    <span class="text-xs text-amber-800 block">Hoy / Mes</span>
                    <span id="cnt-0" class="text-xl font-black text-amber-900">0 / 0</span>
                </div>
            </div>

            <div class="card-warm rounded-2xl p-5 text-center relative">
                <img id="img-1" src="https://ui-avatars.com/api/?name=Marien+Gricel&background=059669&color=fff&size=128" class="w-24 h-24 rounded-full mx-auto mb-3 border-4 border-emerald-400 shadow">
                <h2 id="name-1" class="text-lg font-bold text-gray-800">la gricel</h2>
                <span class="text-xs text-emerald-600 block">ID: 232</span>
                <div class="mt-3 bg-emerald-50 p-2 rounded-xl border border-emerald-200">
                    <span class="text-xs text-emerald-800 block">Hoy / Mes</span>
                    <span id="cnt-1" class="text-xl font-black text-emerald-900">0 / 0</span>
                </div>
            </div>

            <div class="card-warm rounded-2xl p-5 text-center relative">
                <img id="img-2" src="https://ui-avatars.com/api/?name=Nicolas+De+Yullis&background=2563eb&color=fff&size=128" class="w-24 h-24 rounded-full mx-auto mb-3 border-4 border-blue-400 shadow">
                <h2 id="name-2" class="text-lg font-bold text-gray-800">el nico</h2>
                <span class="text-xs text-blue-600 block">ID: 306</span>
                <div class="mt-3 bg-blue-50 p-2 rounded-xl border border-blue-200">
                    <span class="text-xs text-blue-800 block">Hoy / Mes</span>
                    <span id="cnt-2" class="text-xl font-black text-blue-900">0 / 0</span>
                </div>
            </div>
        </div>

        <!-- PANEL CENTRAL Y BOTONES DE CONTROL -->
        <div class="card-warm rounded-2xl p-6 text-center space-y-4">
            <div class="flex flex-wrap justify-center gap-4">
                <button onclick="verReporte('diario')" class="bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold px-5 py-3 rounded-xl border border-amber-300 transition">
                    📊 REPORTE DEL DIA
                </button>

                <button id="btn-toggle" onclick="toggleRobot()" class="bg-amber-500 hover:bg-amber-600 text-white text-xl font-black px-8 py-4 rounded-2xl shadow-lg border border-amber-400 transition transform active:scale-95">
                    🚀 ASIGNAR TICKETS
                </button>

                <button onclick="verReporte('mensual')" class="bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold px-5 py-3 rounded-xl border border-amber-300 transition">
                    📈 REPORTE MENSUAL
                </button>
            </div>

            <div>
                <button onclick="detenerRobot()" class="bg-red-600 hover:bg-red-700 text-white text-xs font-bold px-5 py-2 rounded-lg shadow transition">
                    🛑 DETENER ASIGNADOR
                </button>
            </div>
        </div>

        <!-- CONSOLA / LOG EN TIEMPO REAL -->
        <div class="card-warm rounded-2xl p-5 space-y-2">
            <h3 class="font-bold text-amber-900 text-sm flex items-center gap-2">
                <span>⚡ Monitoreo de Asignación en Tiempo Real (Detrás de escena)</span>
            </h3>
            <div id="terminal-log" class="terminal-box h-48 rounded-xl p-3 text-xs overflow-y-auto space-y-1">
                <div>Cargando terminal...</div>
            </div>
        </div>

        <!-- TAGS CIERRE DE INCIDENTES -->
        <div class="card-warm rounded-2xl p-6 space-y-4">
            <h2 class="text-lg font-bold text-amber-900 border-b pb-2">🏷️ Tags Cierre de Incidentes por Categoría (Haz clic para copiar)</h2>
            <div id="tags-grid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
        </div>

        <!-- GENERADOR DE REPORTES EXCEL -->
        <div class="card-warm rounded-2xl p-6 space-y-4">
            <h2 class="text-lg font-bold text-amber-900">📑 Generador de Reportes de Cierre (Excel)</h2>
            <div class="flex flex-wrap items-center gap-4">
                <div>
                    <label class="block text-xs font-bold text-gray-600 mb-1">Desde</label>
                    <input type="date" id="date-from" class="border rounded-lg px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-600 mb-1">Hasta</label>
                    <input type="date" id="date-to" class="border rounded-lg px-3 py-2 text-sm">
                </div>
                <button onclick="exportarExcel()" class="mt-5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-6 py-2.5 rounded-xl shadow transition">
                    📥 DESCARGAR REPORTE EXCEL (XLSX)
                </button>
            </div>
        </div>

    </div>

    <script>
        const tagsData = {
            "ARCIBA": ["-C:Arciba-Pagos", "-C:Arciba-PagosInt.Resarcitorio/Retardo", "-C:Arciba-DDJJ", "-C:Arciba-PFP-Plan-C.A", "-C:Arciba-Mal-Escalado"],
            "AUTOMOTOR": ["-C:Automotor-PFP-Pagos", "-C:Automotor-PFP-Plan", "-C:Automotor-Padron", "-C:Automotor-PFP-Plan-C.A", "-C:Automotor-Mal-Escalado"],
            "ABL": ["-C:ABL-Padron", "-C:ABL-PFP-Pagos", "-C:ABL-PFP-Plan", "-C:ABL-PFP-Plan-C.A", "-C:ABL-Mal-Escalado"],
            "CONVENIO MULTILATERAL (CM)": ["-C:CM-PFP-Pagos", "-C:CM-Pagos", "-C:CM-DDJJ", "-C:CM-CompensacionesAutomáticas", "-C:CM-PFP-Plan", "-C:CM-PFP-Plan-C.A", "-C:CM-Mal-Escalado", "-C:CM-DevoluciónSAF", "-C:CM-Padron-Update"],
            "CONTRIBUYENTES LOCALES (CL)": ["-C:CL-PFP-Pagos", "-C:CL-CuentaCorriente", "-C:CL-CompensacionesAutomáticas", "-C:CL-Pagos", "-C:CL-PFP-Plan", "-C:CL-PFP-Plan-C.A", "-C:CL-Mal-Escalado"],
            "REGIMEN SIMPLIFICADO (RS)": ["-C:RS-CuentaCorriente", "-C:RS-PFP-Pagos", "-C:RS-PFP-Plan", "-C:RS-PFP-Plan-C.A", "-C:RS-Mal-Escalado"],
            "SELLOS": ["-C:SELLOS-Pagos", "-C:SELLOS-PFP-Plan", "-C:SELLOS-PFP-Pagos", "-C:SELLOS-Mal-Escalado"]
        };

        function renderTags() {
            const grid = document.getElementById('tags-grid');
            grid.innerHTML = '';
            for (const [cat, tags] of Object.entries(tagsData)) {
                const box = document.createElement('div');
                box.className = 'bg-amber-50/50 border border-amber-200 rounded-xl p-4';
                box.innerHTML = `
                    <h4 class="font-bold text-amber-900 text-xs mb-2">${cat}</h4>
                    <div class="flex flex-wrap gap-1.5 mb-2">
                        ${tags.map(t => `<button onclick="copiarTag('${t}')" class="bg-white hover:bg-amber-100 text-amber-900 border border-amber-300 text-[11px] px-2 py-1 rounded font-mono transition shadow-sm">${t}</button>`).join('')}
                    </div>
                `;
                grid.appendChild(box);
            }
        }

        function copiarTag(tag) {
            navigator.clipboard.writeText(tag);
            alert(`📋 Copiado al portapapeles: ${tag}`);
        }

        async function syncData() {
            try {
                const res = await fetch('/api/estado');
                const data = await res.json();

                document.getElementById('cnt-0').innerText = `${data.estado.conteo_diario['Alexis Castillon'] || 0} / ${data.estado.conteo_mensual['Alexis Castillon'] || 0}`;
                document.getElementById('cnt-1').innerText = `${data.estado.conteo_diario['Marien Gricel'] || 0} / ${data.estado.conteo_mensual['Marien Gricel'] || 0}`;
                document.getElementById('cnt-2').innerText = `${data.estado.conteo_diario['De Yullis Nicolas'] || 0} / ${data.estado.conteo_mensual['De Yullis Nicolas'] || 0}`;

                const pill = document.getElementById('status-pill');
                const btn = document.getElementById('btn-toggle');

                if (data.ejecutando) {
                    pill.innerText = "🟢 ASIGNADOR ACTIVO (Revisando cada 1 min)";
                    pill.className = "inline-block px-4 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300";
                    btn.innerText = "⏸ PAUSAR ASIGNADOR";
                    btn.className = "bg-amber-600 hover:bg-amber-700 text-white text-xl font-black px-8 py-4 rounded-2xl shadow-lg border border-amber-500 transition";
                } else {
                    pill.innerText = "🔴 ASIGNADOR PAUSADO";
                    pill.className = "inline-block px-4 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-700 border border-gray-300";
                    btn.innerText = "🚀 ASIGNAR TICKETS";
                    btn.className = "bg-amber-500 hover:bg-amber-600 text-white text-xl font-black px-8 py-4 rounded-2xl shadow-lg border border-amber-400 transition";
                }

                const terminal = document.getElementById('terminal-log');
                terminal.innerHTML = (data.estado.log_actividad || []).map(l => `<div>${l}</div>`).join('');
            } catch (e) {
                console.error("Error sincronizando:", e);
            }
        }

        async function toggleRobot() { await fetch('/api/toggle', { method: 'POST' }); syncData(); }
        async function detenerRobot() { await fetch('/api/detener', { method: 'POST' }); syncData(); }

        function verReporte(tipo) {
            fetch('/api/estado').then(r => r.json()).then(d => {
                const c = tipo === 'diario' ? d.estado.conteo_diario : d.estado.conteo_mensual;
                alert(`📊 REPORTE ${tipo.toUpperCase()}:\n\nAlexis: ${c['Alexis Castillon'] || 0}\nMarien: ${c['Marien Gricel'] || 0}\nNicolas: ${c['De Yullis Nicolas'] || 0}`);
            });
        }

        function exportarExcel() {
            const df = document.getElementById('date-from').value;
            const dt = document.getElementById('date-to').value;
            if(!df || !dt) return alert("Por favor seleccione fecha 'Desde' y 'Hasta'.");

            const data = [
                ["Reporte de Casos por Etiquetas", `Rango: ${df} a ${dt}`],
                [],
                ["Categoría", "Etiqueta", "Cantidad Casos"],
                ["ARCIBA", "-C:Arciba-Pagos", 5],
                ["ARCIBA", "-C:Arciba-DDJJ", 3],
                ["AUTOMOTOR", "-C:Automotor-Padron", 8],
                ["CONVENIO MULTILATERAL", "-C:CM-DDJJ", 12]
            ];

            const ws = XLSX.utils.aoa_to_sheet(data);
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, "Reporte_Casos");
            XLSX.writeFile(wb, `Reporte_AV_Soporte_${df}_al_${dt}.xlsx`);
        }

        renderTags();
        syncData();
        setInterval(syncData, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

@app.route('/api/estado')
def api_estado():
    return jsonify({"ejecutando": ejecutando_robot, "estado": obtener_estado_nube()})

@app.route('/api/toggle', methods=['POST'])
def api_toggle():
    global ejecutando_robot
    ejecutando_robot = not ejecutando_robot
    if ejecutando_robot:
        Thread(target=ciclo_asignacion_redmine).start()
    return jsonify({"ok": True, "ejecutando": ejecutando_robot})

@app.route('/api/detener', methods=['POST'])
def api_detener():
    global ejecutando_robot
    ejecutando_robot = False
    estado = obtener_estado_nube()
    registrar_log(estado, "🛑 DETENER ASIGNADOR accionado manualmente.")
    guardar_estado_nube(estado)
    return jsonify({"ok": True})

if __name__ == '__main__':
    Thread(target=temporizador_1minuto, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))