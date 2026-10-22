import os
import json
import time
import requests
from datetime import datetime
from flask import Flask, render_template_string, jsonify, send_file, request
import io
import pandas as pd
from redminelib import Redmine

app = Flask(__name__)

# Configuración de Redmine
REDMINE_URL = 'https://sistemas.agip.gob.ar/redmine/'
REDMINE_API_KEY = os.environ.get('REDMINE_API_KEY', 'TU_API_KEY_AQUI')
GROUP_ID = 237  # ID AV-Soporte

# JSONBin Config
JSONBIN_ID = os.environ.get('JSONBIN_ID', '')
JSONBIN_KEY = os.environ.get('JSONBIN_KEY', '')
JSONBIN_URL = f'https://api.jsonbin.io/v3/b/{JSONBIN_ID}' if JSONBIN_ID else None

# Integrantes
INTEGRANTES = [
    {"nombre": "Alexis Castillon", "id": 458, "alias": "el alexis"},
    {"nombre": "Marien Gricel", "id": 232, "alias": "la gricel"},
    {"nombre": "De Yullis Nicolas", "id": 306, "alias": "el nico"}
]

DEFAULT_TAGS = {
    "ARCIBA": ["-C:Arciba-Pagos", "-C:Arciba-PagosInt.Resarcitorio/Retardo", "-C:Arciba-DDJJ", "-C:Arciba-PFP-Plan-C.A", "-C:Arciba-Mal-Escalado"],
    "AUTOMOTOR": ["-C:Automotor-PFP-Pagos", "-C:Automotor-PFP-Plan", "-C:Automotor-Padron", "-C:Automotor-PFP-Plan-C.A", "-C:Automotor-Mal-Escalado"],
    "ABL": ["-C:ABL-Padron", "-C:ABL-PFP-Pagos", "-C:ABL-PFP-Plan", "-C:ABL-PFP-Plan-C.A", "-C:ABL-Mal-Escalado"],
    "CONVENIO MULTILATERAL (CM)": ["-C:CM-PFP-Pagos", "-C:CM-Pagos", "-C:CM-DDJJ", "-C:CM-CompensacionesAutomáticas", "-C:CM-PFP-Plan", "-C:CM-PFP-Plan-C.A", "-C:CM-Mal-Escalado", "-C:CM-DevoluciónSAF", "-C:CM-Padron-Update"],
    "CONTRIBUYENTES LOCALES (CL)": ["-C:CL-PFP-Pagos", "-C:CL-CuentaCorriente", "-C:CL-CompensacionesAutomáticas", "-C:CL-Pagos", "-C:CL-PFP-Plan", "-C:CL-PFP-Plan-C.A", "-C:CL-Mal-Escalado"],
    "REGIMEN SIMPLIFICADO (RS)": ["-C:RS-CuentaCorriente", "-C:RS-PFP-Pagos", "-C:RS-PFP-Plan", "-C:RS-PFP-Plan-C.A", "-C:RS-Mal-Escalado"],
    "SELLOS": ["-C:SELLOS-Pagos", "-C:SELLOS-PFP-Plan", "-C:SELLOS-PFP-Pagos", "-C:SELLOS-Mal-Escalado"]
}

estado_local = {
    "ultimo_indice": -1,
    "conteo_diario": {p["nombre"]: 0 for p in INTEGRANTES},
    "conteo_mensual": {p["nombre"]: 0 for p in INTEGRANTES},
    "fotos": {p["nombre"]: "" for p in INTEGRANTES},
    "tags": DEFAULT_TAGS,
    "mes_operacion": datetime.now().strftime("%Y-%m"),
    "log_actividad": []
}

def obtener_estado():
    if not JSONBIN_URL or not JSONBIN_KEY:
        return estado_local
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        r = requests.get(JSONBIN_URL, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()['record']
            if 'fotos' not in data: data['fotos'] = {p["nombre"]: "" for p in INTEGRANTES}
            if 'tags' not in data: data['tags'] = DEFAULT_TAGS
            return data
    except Exception as e:
        print("Error JSONBin get:", e)
    return estado_local

def guardar_estado(data):
    global estado_local
    estado_local = data
    if not JSONBIN_URL or not JSONBIN_KEY:
        return
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    try:
        requests.put(JSONBIN_URL, json=data, headers=headers, timeout=5)
    except Exception as e:
        print("Error JSONBin put:", e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Asignador Automático AV-Soporte</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #faf8f5; color: #2d2b2a; }
        .card-shadow { box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
        
        <!-- Header -->
        <div class="text-center space-y-2">
            <h1 class="text-3xl font-extrabold text-[#7c2d12] flex items-center justify-center gap-2">
                🤖 Asignador Automático AV-Soporte
            </h1>
            <p class="text-sm text-[#9a3412] font-semibold">
                Lunes a Viernes de 09:00 a 18:00 hs | Frecuencia: Cada 1 minuto
            </p>
            <span id="status-badge" class="inline-block px-3 py-1 bg-red-100 text-red-700 font-bold text-xs rounded-full uppercase tracking-wider">
                ● ASIGNADOR PAUSADO
            </span>
        </div>

        <!-- Tarjetas Equipo -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            {% for p in integrantes %}
            <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow text-center relative flex flex-col items-center">
                
                <!-- Foto Editable -->
                <div class="relative group cursor-pointer mb-3" onclick="triggerFoto('{{ p.nombre }}')">
                    <img id="img-{{ loop.index0 }}" src="{{ estado.fotos.get(p.nombre) or '' }}" 
                         class="w-24 h-24 rounded-full object-cover border-4 border-amber-400 bg-amber-50 flex items-center justify-center font-bold text-2xl text-amber-800 {{ 'hidden' if not estado.fotos.get(p.nombre) else '' }}">
                    
                    <div id="avatar-{{ loop.index0 }}" class="w-24 h-24 rounded-full border-4 border-amber-400 bg-amber-500 text-white flex items-center justify-center font-bold text-2xl uppercase {{ 'hidden' if estado.fotos.get(p.nombre) else '' }}">
                        {{ p.nombre[:2] }}
                    </div>

                    <div class="absolute inset-0 bg-black/40 rounded-full opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-xs font-bold transition-opacity">
                        📷 Cambiar
                    </div>
                </div>
                <input type="file" id="file-{{ p.nombre }}" class="hidden" accept="image/*" onchange="subirFoto(event, '{{ p.nombre }}')">

                <h3 class="font-bold text-lg text-slate-800 mb-1">{{ p.alias }}</h3>
                <p class="text-xs text-slate-400 font-medium mb-3">{{ p.nombre }}</p>

                <div class="w-full bg-amber-50/60 rounded-xl p-3 border border-amber-100 mt-auto">
                    <span class="text-xs text-amber-800/60 font-semibold block uppercase">Hoy / Mes</span>
                    <span id="count-{{ p.nombre }}" class="text-2xl font-extrabold text-amber-900">
                        {{ estado.conteo_diario.get(p.nombre, 0) }} / {{ estado.conteo_mensual.get(p.nombre, 0) }}
                    </span>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Acciones principales -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow flex flex-wrap items-center justify-center gap-4">
            <a href="/reporte?tipo=diario" class="px-5 py-3 bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold rounded-xl transition text-sm">
                📊 REPORTE DEL DIA
            </a>
            
            <button onclick="simularAsignacion()" class="px-5 py-3 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-xl transition text-sm shadow-md">
                🧪 SIMULACIÓN
            </button>

            <button onclick="ejecutarAsignacion()" class="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white font-extrabold rounded-xl transition text-base shadow-lg hover:shadow-amber-200">
                🚀 ASIGNAR TICKETS
            </button>

            <a href="/reporte?tipo=mensual" class="px-5 py-3 bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold rounded-xl transition text-sm">
                📈 REPORTE MENSUAL
            </a>
        </div>

        <!-- Terminal Terminal Log -->
        <div class="bg-slate-900 rounded-2xl p-4 font-mono text-xs text-amber-400 h-48 overflow-y-auto border border-slate-800 shadow-inner">
            <div class="text-slate-500 mb-2 border-b border-slate-800 pb-1">⚡ Monitoreo de Asignación en Tiempo Real (Detrás de escena)</div>
            <div id="terminal-logs" class="space-y-1">
                {% for log in estado.log_actividad %}
                <div>{{ log }}</div>
                {% endfor %}
            </div>
        </div>

        <!-- Tags Categoría -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow space-y-6">
            <h2 class="text-lg font-extrabold text-slate-800 flex items-center gap-2">
                🏷️ Tags Cierre de Incidentes por Categoría (Haz clic para copiar)
            </h2>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="tags-container">
                <!-- Se llena mediante Javascript -->
            </div>
        </div>

    </div>

    <script>
        let tagsData = {{ estado.tags | tojson }};

        function renderTags() {
            const container = document.getElementById('tags-container');
            container.innerHTML = '';

            for (const [cat, tags] of Object.entries(tagsData)) {
                let tagsHTML = tags.map(t => `
                    <button onclick="copiarTag(this, '${t}')" class="px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-900 text-xs font-semibold rounded-lg transition text-left flex items-center gap-1.5">
                        <span>${t}</span>
                        <span class="check-icon hidden text-emerald-600 font-bold">✅</span>
                    </button>
                `).join('');

                container.innerHTML += `
                    <div class="border border-amber-100 rounded-xl p-4 bg-amber-50/20 space-y-3">
                        <div class="flex justify-between items-center">
                            <h3 class="font-extrabold text-xs text-amber-900 uppercase tracking-wider">${cat}</h3>
                            <button onclick="agregarNuevoTag('${cat}')" class="text-xs font-bold text-amber-600 hover:text-amber-800 hover:underline">
                                + Agregar Tag
                            </button>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            ${tagsHTML}
                        </div>
                    </div>
                `;
            }
        }

        function copiarTag(btn, texto) {
            navigator.clipboard.writeText(texto);
            const check = btn.querySelector('.check-icon');
            check.classList.remove('hidden');
            setTimeout(() => {
                check.classList.add('hidden');
            }, 1000);
        }

        async function agregarNuevoTag(categoria) {
            const nuevo = prompt(`Nuevo Tag para ${categoria}:`, "-C:");
            if (nuevo && nuevo.trim() !== "") {
                tagsData[categoria].push(nuevo.trim());
                renderTags();
                await fetch('/api/guardar_tags', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ tags: tagsData })
                });
            }
        }

        function triggerFoto(nombre) {
            document.getElementById(`file-${nombre}`).click();
        }

        function subirFoto(event, nombre) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = async function(e) {
                const base64 = e.target.result;
                await fetch('/api/guardar_foto', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ nombre: nombre, foto: base64 })
                });
                location.reload();
            };
            reader.readAsDataURL(file);
        }

        async function simularAsignacion() {
            const res = await fetch('/api/simular', { method: 'POST' });
            const data = await res.json();
            alert(`🧪 SIMULACIÓN:\nEl próximo ticket sería asignado a: ${data.siguiente}`);
        }

        async function ejecutarAsignacion() {
            const res = await fetch('/api/ejecutar', { method: 'POST' });
            const data = await res.json();
            location.reload();
        }

        renderTags();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    estado = obtener_estado()
    return render_template_string(HTML_TEMPLATE, integrantes=INTEGRANTES, estado=estado)

@app.route('/api/guardar_foto', methods=['POST'])
def api_guardar_foto():
    data = request.json
    estado = obtener_estado()
    estado['fotos'][data['nombre']] = data['foto']
    guardar_estado(estado)
    return jsonify({"success": True})

@app.route('/api/guardar_tags', methods=['POST'])
def api_guardar_tags():
    data = request.json
    estado = obtener_estado()
    estado['tags'] = data['tags']
    guardar_estado(estado)
    return jsonify({"success": True})

@app.route('/api/simular', methods=['POST'])
def api_simular():
    estado = obtener_estado()
    siguiente_idx = (estado['ultimo_indice'] + 1) % len(INTEGRANTES)
    siguiente_persona = INTEGRANTES[siguiente_idx]['nombre']
    return jsonify({"siguiente": siguiente_persona})

@app.route('/reporte')
def reporte():
    tipo = request.args.get('tipo', 'diario')
    estado = obtener_estado()
    df = pd.DataFrame([
        {"Integrante": p["nombre"], "Tickets Asignados": estado['conteo_diario'].get(p["nombre"], 0) if tipo == 'diario' else estado['conteo_mensual'].get(p["nombre"], 0)}
        for p in INTEGRANTES
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    output.seek(0)
    return send_file(output, download_name=f'reporte_{tipo}.xlsx', as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
