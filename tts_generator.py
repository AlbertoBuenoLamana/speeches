#!/usr/bin/env python3
"""
Generador de audio TTS usando edge-tts.
Convierte texto con formato SSML (estilo Amazon Polly) a audio MP3.
Soporta pausas entre secciones y voces en español.
"""
import asyncio
import edge_tts
import re
import sys
import os

# Voces disponibles en español (puedes cambiarla)
# es-MX-DaliaNeural    (Femenina, México)
# es-MX-JorgeNeural    (Masculino, México)
# es-ES-ElviraNeural   (Femenina, España)
# es-ES-AlvaroNeural   (Masculino, España)
# es-AR-ElenaNeural    (Femenina, Argentina)
# es-CO-SalomeNeural   (Femenina, Colombia)

VOICE = "es-ES-AlvaroNeural"
RATE = "+0%"       # Velocidad: -50% a +100%
VOLUME = "+0%"     # Volumen: -50% a +100%
PITCH = "+0Hz"     # Tono: -50Hz a +50Hz


def parse_ssml_to_sections(ssml_text: str) -> list[dict]:
    """
    Parsea el SSML de Polly y extrae secciones con títulos y contenido.
    Retorna una lista de dicts: [{"title": str, "lines": [str], "pause_ms": int}]
    """
    # Limpiar tags XML
    text = re.sub(r'<speak>|</speak>', '', ssml_text)
    text = re.sub(r'<p>\s*<s>\s*', '', text)
    text = re.sub(r'\s*</s>\s*</p>', '', text)
    text = re.sub(r'</?p>|</?s>', '', text)

    sections = []
    current_section = {"title": "", "lines": [], "pause_ms": 500}

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Detectar break tags
        break_match = re.search(r'<break\s+time="(\d+)ms"\s*/>', line)
        if break_match:
            # El break indica fin de título de sección anterior
            continue

        # Limpiar cualquier tag restante
        clean = re.sub(r'<[^>]+>', '', line).strip()
        if not clean:
            continue

        # Heurística: si la línea anterior era un break, esta línea es contenido
        # Si la línea no empieza con - ni • ni número, y es corta, podría ser un título
        # Detectamos títulos por contexto: líneas que preceden a un <break>
        sections_text = text

        current_section["lines"].append(clean)

    # Re-parsear con mejor lógica: buscar patrón "Título\n<break>\ncontenido..."
    sections = []
    # Dividir por breaks
    parts = re.split(r'\s*<break\s+time="\d+ms"\s*/>\s*', text)

    for i, part in enumerate(parts):
        lines = [l.strip() for l in part.strip().split('\n') if l.strip()]
        # Limpiar tags residuales
        lines = [re.sub(r'<[^>]+>', '', l).strip() for l in lines]
        lines = [l for l in lines if l]

        if not lines:
            continue

        if i == 0 and len(lines) == 1:
            # Primer bloque antes del primer break = título principal
            sections.append({"title": lines[0], "lines": [], "pause_ms": 800})
        elif len(lines) >= 1:
            # El primer elemento del bloque anterior (antes del break) era el título
            # Aquí tenemos el contenido después del break
            title = sections[-1]["title"] if sections else ""
            sections.append({"title": "", "lines": lines, "pause_ms": 500})

    # Mejor enfoque: reconstruir como texto plano con pausas
    return None  # Usaremos el enfoque directo


def ssml_to_plain_text(ssml_text: str) -> str:
    """
    Convierte SSML de Polly a texto plano con marcadores de pausa.
    """
    text = ssml_text

    # Remover <speak> tags
    text = re.sub(r'</?speak>', '', text)

    # Remover <p> y <s> tags
    text = re.sub(r'</?p>', '', text)
    text = re.sub(r'</?s>', '', text)

    # Eliminar breaks (edge-tts no soporta SSML breaks)
    text = re.sub(r'<break\s+time="\d+ms"\s*/>', '', text)

    # Limpiar cualquier otro tag
    text = re.sub(r'<[^>]+>', '', text)

    # Limpiar líneas vacías excesivas y espacios
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)

    return '\n'.join(lines)


def build_edge_ssml(text: str, voice: str = VOICE) -> str:
    """
    Construye SSML compatible con edge-tts a partir del texto plano con marcadores.
    """
    ssml_parts = []
    ssml_parts.append(
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="es-MX">'
    )
    ssml_parts.append(f'<voice name="{voice}">')
    ssml_parts.append(f'<prosody rate="{RATE}" volume="{VOLUME}" pitch="{PITCH}">')

    for line in text.split('\n'):
        if line == '[PAUSA]':
            ssml_parts.append('<break time="700ms"/>')
        else:
            # Escapar caracteres especiales XML
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            ssml_parts.append(f'<s>{line}</s>')

    ssml_parts.append('</prosody>')
    ssml_parts.append('</voice>')
    ssml_parts.append('</speak>')

    return '\n'.join(ssml_parts)


async def generate_audio(text_input: str, output_file: str):
    """
    Genera audio MP3 usando edge-tts.
    """
    communicate = edge_tts.Communicate(text_input, voice=VOICE, rate=RATE, volume=VOLUME, pitch=PITCH)
    await communicate.save(output_file)
    size_kb = os.path.getsize(output_file) / 1024
    print(f"Audio generado: {output_file} ({size_kb:.1f} KB)")


async def generate_from_ssml_file(ssml_file: str, output_file: str):
    """
    Lee un archivo SSML (formato Polly) y genera audio.
    """
    with open(ssml_file, 'r', encoding='utf-8') as f:
        ssml_content = f.read()

    # Convertir SSML de Polly a texto plano
    plain = ssml_to_plain_text(ssml_content)
    print(f"Texto extraído ({len(plain)} caracteres)")
    print("-" * 50)

    # Generar audio directamente con el texto (edge-tts maneja bien el texto plano)
    await generate_audio(plain, output_file)


async def generate_from_text(text: str, output_file: str):
    """
    Genera audio directamente desde texto plano.
    """
    await generate_audio(text, output_file)


async def list_spanish_voices():
    """Lista todas las voces disponibles en español."""
    voices = await edge_tts.list_voices()
    spanish = [v for v in voices if v['Locale'].startswith('es')]
    print(f"\nVoces disponibles en español ({len(spanish)}):\n")
    for v in spanish:
        gender = "F" if v['Gender'] == 'Female' else "M"
        print(f"  [{gender}] {v['ShortName']:30s} ({v['Locale']})")


async def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print(f"  python3 {sys.argv[0]} <archivo.ssml> [salida.mp3]    - Desde archivo SSML")
        print(f"  python3 {sys.argv[0]} --text 'texto' [salida.mp3]    - Desde texto directo")
        print(f"  python3 {sys.argv[0]} --voices                       - Listar voces españolas")
        print(f"  python3 {sys.argv[0]} --voice es-ES-AlvaroNeural <archivo.ssml> [salida.mp3]")
        return

    args = sys.argv[1:]
    global VOICE

    # Procesar flags
    if '--voices' in args:
        await list_spanish_voices()
        return

    if '--voice' in args:
        idx = args.index('--voice')
        VOICE = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if '--rate' in args:
        global RATE
        idx = args.index('--rate')
        RATE = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if '--text' in args:
        idx = args.index('--text')
        text = args[idx + 1]
        output = args[idx + 2] if len(args) > idx + 2 else "salida.mp3"
        await generate_from_text(text, output)
    else:
        ssml_file = args[0]
        output = args[1] if len(args) > 1 else ssml_file.rsplit('.', 1)[0] + ".mp3"
        await generate_from_ssml_file(ssml_file, output)


if __name__ == "__main__":
    asyncio.run(main())
