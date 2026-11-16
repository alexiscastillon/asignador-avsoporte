import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# --- CREDENCIALES FIREBASE ---
FIREBASE_URL = os.environ.get('FIREBASE_URL', 'https://asignador-avsoporte-default-rtdb.firebaseio.com/estado.json')

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
    try:
        res = requests.get(FIREBASE_URL, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data is not None:
                if 'fotos' not in data: data['fotos'] = {p["nombre"]: "" for p in EQUIPO_AV}
                if 'tags' not in data: data['tags'] = DEFAULT_TAGS
                return data
    except Exception as e:
        print("Error consultando Firebase desde Render:", e)
    
    return {
        "ultimo_indice": -1,
        "conteo_diario": {p["nombre"]: 0 for p in EQUIPO_AV},
        "conteo_mensual": {p["nombre"]: 0 for p in EQUIPO_AV},
        "fotos": {p["nombre"]: "" for p in EQUIPO_AV},
        "tags": DEFAULT_TAGS,
        "log_actividad": ["🟢 Tablero en línea. Esperando ejecuciones de la red local..."]
    }

def guardar_estado_nube(estado):
    try:
        requests.put(FIREBASE_URL, json=estado, timeout=5)
    except Exception as e:
        print("Error al guardar en Firebase desde Render:", e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AV-Soporte | Tablero de Control</title>
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
            <h1 class="text-3xl font-extrabold text-[#7c2d12]">🤖 Asignador Automático AV-Soporte</h1>
            <p class="text-sm text-[#9a3412] font-semibold">Lunes a Viernes de 09:00 a 18:00 hs | Frecuencia: Cada 1 minuto (Refresco web: Cada 10 min)</p>
            <span class="inline-block px-3 py-1 bg-emerald-100 text-emerald-800 font-bold text-xs rounded-full uppercase tracking-wider border border-emerald-300">
                🟢 TABLERO EN TIEMPO REAL
            </span>
        </div>

        <!-- Tarjetas del Equipo -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            {% for p in integrantes %}
            <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow text-center relative flex flex-col items-center">
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
                    <span class="text-2xl font-extrabold text-amber-900">
                        {{ estado.conteo_diario.get(p.nombre, 0) }} / {{ estado.conteo_mensual.get(p.nombre, 0) }}
                    </span>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Botones de Acción (Simulación y Actualizar Manual) -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow flex flex-wrap items-center justify-center gap-4">
            <button onclick="simularAsignacion()" class="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white font-extrabold rounded-xl transition text-sm shadow-md">
                🧪 PROBAR SIMULACIÓN
            </button>
            <button onclick="location.reload()" class="px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white font-extrabold rounded-xl transition text-sm shadow-md">
                🔄 ACTUALIZAR AHORA
            </button>
        </div>

        <!-- Terminal de Logs -->
        <div class="bg-slate-900 rounded-2xl p-4 font-mono text-xs text-amber-400 h-48 overflow-y-auto border border-slate-800 shadow-inner">
            <div class="text-slate-500 mb-2 border-b border-slate-800 pb-1">⚡ Monitoreo de Asignación en Tiempo Real (Desde la Intranet AGIP)</div>
            <div id="terminal-logs" class="space-y-1">
                {% for log in estado.log_actividad %}
                <div>{{ log }}</div>
                {% endfor %}
            </div>
        </div>

        <!-- Tags Categoría -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow space-y-6">
            <h2 class="text-lg font-extrabold text-slate-800">🏷️ Tags Cierre de Incidentes (Haz clic para copiar)</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="tags-container"></div>
        </div>

        <!-- Ruleta de Prendas / Oficina (Debajo de todo) -->
        <div class="bg-white p-6 rounded-2xl border border-amber-100 card-shadow flex flex-col items-center space-y-4">
            <h2 class="text-lg font-extrabold text-slate-800">🎡 Ruleta de la Oficina (¡Probá tu suerte!)</h2>
            
            <div class="relative flex items-center justify-center">
                <!-- Puntero superior -->
                <div class="absolute -top-3 z-10 w-0 h-0 border-l-[14px] border-l-transparent border-r-[14px] border-r-transparent border-t-[24px] border-t-red-600 drop-shadow"></div>
                <canvas id="ruletaCanvas" width="340" height="340" class="rounded-full shadow-lg border-4 border-amber-400 bg-white"></canvas>
            </div>

            <button id="btn-girar" onclick="girarRuleta()" class="px-8 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold rounded-xl transition text-sm shadow-md active:scale-95">
                🎲 ¡GIRAR RULETA!
            </button>

            <div id="resultado-ruleta" class="hidden px-4 py-2 bg-amber-100 border border-amber-300 text-amber-900 font-extrabold rounded-xl text-center text-base animate-bounce"></div>
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

        function triggerFoto(nombre) { document.getElementById(`file-${nombre}`).click(); }

        function subirFoto(event, nombre) {
            const file = event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = async function(e) {
                await fetch('/api/guardar_foto', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ nombre: nombre, foto: e.target.result })
                });
                location.reload();
            };
            reader.readAsDataURL(file);
        }

        async function simularAsignacion() {
            const res = await fetch('/api/simular', { method: 'POST' });
            const data = await res.json();
            alert(`🧪 SIMULACIÓN:\nEl próximo ticket le correspondería a: ${data.siguiente}`);
        }

        // --- LÓGICA RULETA NATIVA OPTIMIZADA Y LEGIBLE ---
        const opcionesRuleta = [
            { texto: "Preparate los mates", emoji: "🧉", color: "#d97706" },
            { texto: "2x1 en chichas", emoji: "🔥", color: "#059669" },
            { texto: "Zafaste", emoji: "😎", color: "#2563eb" },
            { texto: "A comprar jugos", emoji: "🧃", color: "#9a3412" },
            { texto: "Café para todos", emoji: "☕", color: "#7c2d12" },
            { texto: "Te comés el ticket", emoji: "🎫", color: "#dc2626" }
        ];

        const canvas = document.getElementById("ruletaCanvas");
        const ctx = canvas.getContext("2d");
        let anguloActual = 0;
        let girando = false;

        function dibujarRuleta() {
            const numOpciones = opcionesRuleta.length;
            const arco = (2 * Math.PI) / numOpciones;
            const radio = canvas.width / 2;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            for (let i = 0; i < numOpciones; i++) {
                const angulo = anguloActual + i * arco;
                
                // Porción de la ruleta
                ctx.beginPath();
                ctx.fillStyle = opcionesRuleta[i].color;
                ctx.moveTo(radio, radio);
                ctx.arc(radio, radio, radio - 5, angulo, angulo + arco);
                ctx.lineTo(radio, radio);
                ctx.fill();
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 3;
                ctx.stroke();

                // Texto legible orientado correctamente
                ctx.save();
                ctx.translate(radio, radio);
                const anguloMedio = angulo + arco / 2;
                ctx.rotate(anguloMedio);

                // Si el texto queda hacia la izquierda, lo enderezamos para que nunca se lea al revés
                if (anguloMedio > Math.PI / 2 && anguloMedio < 3 * Math.PI / 2) {
                    ctx.rotate(Math.PI);
                    ctx.textAlign = "left";
                    ctx.translate(-radio + 40, 0);
                } else {
                    ctx.textAlign = "right";
                    ctx.translate(radio - 40, 0);
                }

                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 13px 'Plus Jakarta Sans', sans-serif";
                ctx.fillText(opcionesRuleta[i].emoji + " " + opcionesRuleta[i].texto, 0, 4);
                ctx.restore();
            }

            // Circulo central decorativo
            ctx.beginPath();
            ctx.arc(radio, radio, 22, 0, 2 * Math.PI);
            ctx.fillStyle = "#ffffff";
            ctx.fill();
            ctx.lineWidth = 4;
            ctx.strokeStyle = "#fbbf24";
            ctx.stroke();
        }

        function girarRuleta() {
            if (girando) return;
            girando = true;
            const resDiv = document.getElementById("resultado-ruleta");
            resDiv.classList.add("hidden");

            const vueltasExtra = Math.floor(Math.random() * 5 + 5) * 2 * Math.PI;
            const anguloDestino = anguloActual + vueltasExtra + Math.random() * 2 * Math.PI;
            const duracion = 4000;
            const inicio = performance.now();
            const anguloInicial = anguloActual;

            function animar(tiempoActual) {
                const transcurrido = tiempoActual - inicio;
                const progreso = Math.min(transcurrido / duracion, 1);
                const easeOut = 1 - Math.pow(1 - progreso, 3);

                anguloActual = anguloInicial + (anguloDestino - anguloInicial) * easeOut;
                dibujarRuleta();

                if (progreso < 1) {
                    requestAnimationFrame(animar);
                } else {
                    girando = false;
                    calcularGanador();
                }
            }
            requestAnimationFrame(animar);
        }

        function calcularGanador() {
            const numOpciones = opcionesRuleta.length;
            const arco = (2 * Math.PI) / numOpciones;
            const anguloNormalizado = (1.5 * Math.PI - (anguloActual % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
            const indiceGanador = Math.floor(anguloNormalizado / arco);
            
            const ganadora = opcionesRuleta[indiceGanador];
            const resDiv = document.getElementById("resultado-ruleta");
            resDiv.textContent = `🎉 Resultado: ${ganadora.emoji} ${ganadora.texto}`;
            resDiv.classList.remove("hidden");
        }

        dibujarRuleta();
        renderTags();
        
        // Refresco automático cada 10 minutos (600.000 ms) para ahorrar datos
        setInterval(() => location.reload(), 600000);
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
    return jsonify({"success": true})

@app.route('/api/guardar_tags', methods=['POST'])
def api_guardar_tags():
    data = request.json
    estado = obtener_estado_nube()
    estado['tags'] = data['tags']
    guardar_estado_nube(estado)
    return jsonify({"success": True})

@app.route('/api/simular', methods=['POST'])
def api_simular():
    estado = obtener_estado_nube()
    siguiente_idx = (estado.get('ultimo_indice', -1) + 1) % len(EQUIPO_AV)
    return jsonify({"siguiente": EQUIPO_AV[siguiente_idx]['nombre']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
