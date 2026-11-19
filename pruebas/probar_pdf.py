"""(12-nov) Pruebas: adjuntar PDF desde el celular (reusa la subida cruda de videos).
Correr desde la carpeta del proyecto: .venv\\Scripts\\python.exe pruebas\\probar_pdf.py"""
import os, re, shutil, subprocess, sys, py_compile, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(tempfile.gettempdir(), "companero-prueba-pdf")
sys.path.insert(0, RAIZ)

ok_total, n_total = 0, 0


def check(nombre, cond):
    global ok_total, n_total
    n_total += 1
    if cond:
        ok_total += 1
    else:
        print("FALLO:", nombre)


def leer(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


# a) compilar
for rel in ("kodama_archivos.py", "kodama_rutas.py"):
    try:
        py_compile.compile(os.path.join(RAIZ, rel), doraise=True)
        check(f"py_compile {rel}", True)
    except py_compile.PyCompileError as e:
        check(f"py_compile {rel}: {e}", False)

# b) constantes
try:
    import kodama_archivos as ka
    check("import kodama_archivos", True)
    check("DOC_TIPOS pdf", ka.DOC_TIPOS.get("application/pdf") == ".pdf")
    check("DOC_MAX 100 MB", ka.DOC_MAX == 100 * 1024 * 1024)
except Exception as e:
    check(f"import kodama_archivos: {e}", False)
    ka = None

# c) texto_con_video
if ka is not None:
    t_pdf = ka.texto_con_video(r"C:\x\a.pdf", "hola")
    check("texto PDF menciona PDF y Read", "PDF" in t_pdf and "Read" in t_pdf)
    check("texto PDF termina en hola", t_pdf.endswith("hola"))
    t_mp4 = ka.texto_con_video(r"C:\x\a.mp4", "")
    check("texto video menciona video", "video" in t_mp4)
    check("texto video no menciona PDF", "PDF" not in t_mp4)

# d) app.html
html = leer("web/app.html")
check('app.html accept con application/pdf', 'accept="image/*,video/*,application/pdf"' in html)
check("app.html contiene pv-pdf", "pv-pdf" in html)
check('app.html NO contiene "solo.video.size"', "solo.video.size" not in html)

# e) kodama_rutas.py
rutas = leer("kodama_rutas.py")
check('kodama_rutas usa DOC_TIPOS.get(', "DOC_TIPOS.get(" in rutas)
check('kodama_rutas usa DOC_TIPOS.values()', "DOC_TIPOS.values()" in rutas)

# f) sintaxis JS de los <script> inline de app.html
node = shutil.which("node")
if node is None:
    print("NOTA: node no esta instalado; se omite la prueba de sintaxis JS")
else:
    bloques = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I)
    os.makedirs(SCRATCH, exist_ok=True)
    for i, js in enumerate(bloques):
        if not js.strip():
            continue
        ruta_js = os.path.join(SCRATCH, f"app_inline_{i}.js")
        with open(ruta_js, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([node, "--check", ruta_js], capture_output=True, text=True)
        check(f"node --check script inline {i}", r.returncode == 0)
    print(f"(scripts inline revisados: {len(bloques)})")

# sanity: i18n.js tiene las nuevas claves
i18n = leer("web/i18n.js")
for clave in ("PDF demasiado grande (máx. 100 MB)", "PDF · {0} MB · escribe algo (opcional) y envía", '"Adjuntar"'):
    check(f"i18n clave {clave}", clave in i18n)

print(f"{ok_total}/{n_total} passed")
sys.exit(0 if ok_total == n_total else 1)
