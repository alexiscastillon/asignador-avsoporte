import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# --- CONFIGURACIÓN JSONBIN ---
JSONBIN_ID = os.environ.get('JSONBIN_ID', '6ad97155ac6210605a479aae')
JSONBIN_KEY = os.environ.get('JSONBIN_KEY', '$2a$10$Gy6oKS.5GwyesYEX6azXpehmmHY5ahMdBiwqm7LOQnhYIP3RgpaU2')
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

EQUIPO_AV = [
    {"nombre": "Alexis Castillon", "alias": "el alexis"},
    {"nombre": "Marien Gricel", "alias": "la gricel"},
    {"nombre": "De Yullis Nicolas", "alias": "el nico"}
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

def obtener_estado_nube():
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        res = requests.get(f"{JSONBIN_URL}/latest", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()['record']
            if 'fotos' not in data: data['fotos'] = {p["nombre"]: "" for p in EQUIPO_AV}
            if 'tags' not in data: data['tags'] = DEFAULT_TAGS
            return data
    except Exception as e:
        print("Error consultando JSONBin:", e)
    
    return {
        "ultimo_indice": -1,
        "conteo_diario": {p["nombre"]: 0 for p in EQUIPO_AV},
        "conteo_mensual": {p["nombre"]: 0 for p in EQUIPO_AV},
        "fotos": {p["nombre"]: "" for p in EQUIPO_AV},
        "tags": DEFAULT_TAGS
    }

def guardar_estado_nube(estado):
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    try:
        requests.put(JSONBIN_URL, json=estado, headers=headers, timeout=5)
    except Exception as e:
        print("Error al guardar en JSONBin:", e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AV-Soporte | Tablero Métrica</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #faf8f5; color: #2d2b2a; }
        .card-shadow { box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
        
        <div class="text-center space-y-2">
            <h1 class="text-3xl font-extrabold text-[#7c2d12]">🤖 Tablero Métricas AV-Soporte</h1>
            <p class="text-sm text-[#9a3412] font-semibold">Lunes a Viernes de 09:00 a 18:00 hs | Frecuencia: Cada 3 minutos</p>
            <div class="flex items-center justify-center gap-3 pt-1">
                <span class="inline-block px-3 py-1 bg-emerald-100 text-emerald-800 font-bold text-xs rounded-full uppercase tracking-wider border border-emerald-300">
                    🟢 TABLERO EN TIEMPO REAL
                </span>
                <button onclick="reiniciarContadores()" class="px-3 py-1 bg-amber-200 hover:bg-amber-300 text-amber-900 font-extrabold text-xs rounded-full border border-amber-400 transition flex items-center gap-1 shadow-sm">
                    🔄 REINICIAR CONTADORES
                </button>
            </div>
        </div>

        <!-- Tarjetas del Equipo -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            {% for p in integrantes %}
            {% set es_ultimo = (loop.index0 == estado.ultimo_indice) %}
            <div class="bg-white p-6 rounded-2xl border {{ 'border-emerald-400 ring-2 ring-emerald-300' if es_ultimo else 'border-amber-100' }} card-shadow text-center relative flex flex-col items-center transition-all">
                
                {% if es_ultimo %}
                <span class="absolute -top-3 bg-emerald-500 text-white text-[10px] font-extrabold px-3 py-0.5 rounded-full uppercase tracking-wider shadow">
                    Último Asignado
                </span>
                {% endif %}

                <div class="relative group cursor-pointer mb-3" onclick="triggerFoto('{{ p.nombre }}')">
                    {% set foto_url = estado.fotos.get(p.nombre) %}
                    <img id="img-{{ loop.index0 }}" src="{{ foto_url or '' }}" 
                         class="w-24 h-24 rounded-full object-cover border-4 border-amber-400 bg-amber-50 flex items-center justify-center font-bold text-2xl text-amber-800 {{ 'hidden' if not foto_url else '' }}">
                    
                    <div id="avatar-{{ loop.index0 }}" class="w-24 h-24 rounded-full border-4 border-amber-400 bg-amber-500 text-white flex items-center justify-center font-bold text-2xl uppercase {{ 'hidden' if foto_url else '' }}">
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
                    <span class="text-2xl font-extrabold text-amber-900">
                        {{ estado.conteo_diario.get(p.nombre, 0) }} / {{ estado.conteo_mensual.get(p.nombre, 0) }}
                    </span>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Tags Cierre de Incidentes -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow space-y-6">
            <h2 class="text-lg font-extrabold text-slate-800">🏷️ Tags Cierre de Incidentes (Haz clic para copiar)</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="tags-container"></div>
        </div>

    </div>

    <script>
        let tagsData = {{ estado.tags | tojson }};

        function renderTags() {
            const container = document.getElementById('tags-container');
            container.innerHTML = '';
            for (const [cat, tags] of Object.entries(tagsData)) {
                let tagsHTML = tags.map((t, idx) => `
                    <div class="inline-flex items-center bg-amber-50 border border-amber-200 rounded-lg text-xs font-semibold text-amber-900">
                        <button onclick="copiarTag(this, '${t}')" class="px-2.5 py-1.5 hover:bg-amber-100 transition rounded-l-lg flex items-center gap-1.5">
                            <span>${t}</span>
                            <span class="check-icon hidden text-emerald-600 font-bold">✅</span>
                        </button>
                        <button onclick="eliminarTag('${cat}', ${idx})" class="px-2 py-1.5 text-amber-500 hover:text-red-600 hover:bg-red-50 rounded-r-lg transition border-l border-amber-200 font-bold" title="Eliminar Tag">
                            ✕
                        </button>
                    </div>
                `).join('');

                container.innerHTML += `
                    <div class="border border-amber-100 rounded-xl p-4 bg-amber-50/20 space-y-3">
                        <div class="flex justify-between items-center">
                            <h3 class="font-extrabold text-xs text-amber-900 uppercase tracking-wider">${cat}</h3>
                            <button onclick="agregarNuevoTag('${cat}')" class="text-xs font-bold text-amber-600 hover:text-amber-800 hover:underline">+ Agregar</button>
                        </div>
                        <div class="flex flex-wrap gap-2">${tagsHTML}</div>
                    </div>
                `;
            }
        }

        function copiarTag(btn, texto) {
            navigator.clipboard.writeText(texto);
            const check = btn.querySelector('.check-icon');
            check.classList.remove('hidden');
            setTimeout(() => { check.classList.add('hidden'); }, 1000);
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

        async function eliminarTag(categoria, index) {
            const tagEliminar = tagsData[categoria][index];
            if (confirm(`¿Estás seguro de eliminar el tag "${tagEliminar}"?`)) {
                tagsData[categoria].splice(index, 1);
                renderTags();
                await fetch('/api/guardar_tags', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ tags: tagsData })
                });
            }
        }

        function triggerFoto(nombre) { document.getElementById(`file-${nombre}`).click(); }

        function subirFoto(event, nombre) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = function() {
                    const canvas = document.createElement('canvas');
                    canvas.width = 150;
                    canvas.height = 150;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, 150, 150);
                    
                    const fotoComprimida = canvas.toDataURL('image/jpeg', 0.7);

                    fetch('/api/guardar_foto', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ nombre: nombre, foto: fotoComprimida })
                    }).then(() => location.reload());
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        async function reiniciarContadores() {
            if (confirm("¿Estás seguro de que deseas reiniciar todos los contadores a 0 / 0?")) {
                await fetch('/api/reiniciar_contadores', { method: 'POST' });
                location.reload();
            }
        }

        renderTags();
        setInterval(() => location.reload(), 180000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, integrantes=EQUIPO_AV, estado=obtener_estado_nube())

@app.route('/api/guardar_foto', methods=['POST'])
def api_guardar_foto():
    data = request.json
    estado = obtener_estado_nube()
    estado['fotos'][data['nombre']] = data['foto']
    guardar_estado_nube(estado)
    return jsonify({"success": True})

@app.route('/api/guardar_tags', methods=['POST'])
def api_guardar_tags():
    data = request.json
    estado = obtener_estado_nube()
    estado['tags'] = data['tags']
    guardar_estado_nube(estado)
    return jsonify({"success": True})

@app.route('/api/reiniciar_contadores', methods=['POST'])
def api_reiniciar_contadores():
    estado = obtener_estado_nube()
    estado['conteo_diario'] = {p["nombre"]: 0 for p in EQUIPO_AV}
    estado['conteo_mensual'] = {p["nombre"]: 0 for p in EQUIPO_AV}
    guardar_estado_nube(estado)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
