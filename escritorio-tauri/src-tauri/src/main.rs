// © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
// Mascota de escritorio de Kodama en Tauri (14-oct-2026): reemplaza a Electron (~360 MB) usando el WebView2 que
// ya trae Windows. Aca solo va lo que la pagina no puede hacer sola: la ventana (clic que atraviesa, foco, mover,
// mostrar, siempre visible), mirar el cursor, leer/guardar la configuracion y la clave local, y abrir enlaces.
// La carpeta de trabajo es la de Kodama (arrancar.pyw lo lanza con cwd = Apps\companero).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{fs, path::PathBuf, process::Command, sync::{atomic::{AtomicBool, AtomicI32, AtomicU32, Ordering}, Mutex}, thread, time::Duration};
#[cfg(windows)]
use std::sync::atomic::AtomicU64;
use tauri::{Emitter, LogicalPosition, Manager, WebviewWindow};
// (28-oct) macOS: `limites` y `reafirmar` fijan el tamaño con las medidas logicas de Tauri (en Windows lo hace SetWindowPos con px fisicos).
#[cfg(not(windows))]
use tauri::LogicalSize;

static ESCRIBIENDO: AtomicBool = AtomicBool::new(false);
// (27-oct, soltar 2) ARRASTRAR ARCHIVOS: lo maneja WebView2 (dragDropEnabled:false en tauri.conf.json, AllowExternalDrop:true aca) y la pagina
// manda las rutas con postMessageWithAdditionalObjects("kodama-soltar", files). Contadores para el diagnostico fijo (comando `drop_info`):
// DROP_EXT = AllowExternalDrop leido de WebView2 (-1 aun no, 0 false, 1 true); DROP_MSGS = mensajes "kodama-soltar" recibidos; DROP_RUTAS = rutas del ultimo.
static DROP_EXT: AtomicI32 = AtomicI32::new(-1);
static DROP_MSGS: AtomicU32 = AtomicU32::new(0);
static DROP_RUTAS: AtomicU32 = AtomicU32::new(0);
// (27-oct) ZONA TACTIL FIJA: rectangulos (x, y, ancho, alto en px CSS de la pagina) donde la ventana existe para Windows.
// Fuera de ellos la ventana transparente NO existe (SetWindowRgn): los clics, el lapiz y el tacto pasan a lo de abajo, siempre,
// sin sondeo ni ida y vuelta por IPC. ZONA_F = escala (bits de f64) con la que se aplico la region (si cambia, se vuelve a armar).
// La region se recorta como un calco de bigotes: solo existe lo que el gato (o su globo) pinta encima, nada de margen de cortesia.
static ZONA: Mutex<Vec<[f64; 4]>> = Mutex::new(Vec::new());
#[cfg(windows)]
static ZONA_F: AtomicU64 = AtomicU64::new(0);
#[cfg(windows)]
static ZONA_VIEJA: AtomicU32 = AtomicU32::new(0);   // >0 = `limites` quito la region y falta que la pagina mande la zona nueva (cuenta sondeos)
// Antes de que la pagina mande la primera zona: solo el lugar del gato (abajo a la derecha de la ventana de 400x600)
const ZONA_INICIAL: [f64; 4] = [196.0, 380.0, 204.0, 220.0];

fn base() -> PathBuf {
    std::env::current_dir().unwrap_or_default()
}

#[tauri::command]
fn conf_leer() -> String {
    fs::read_to_string(base().join("estado").join("escritorio.json")).unwrap_or_else(|_| "{}".into())
}

#[tauri::command]
fn conf_guardar(json: String) {
    if serde_json::from_str::<serde_json::Value>(&json).is_err() {
        return;
    }
    let p = base().join("estado").join("escritorio.json");
    let t = p.with_extension("json.tmp");
    if fs::write(&t, json).is_ok() {
        let _ = fs::rename(&t, &p);
    }
}

#[tauri::command]
fn clave() -> String {
    fs::read_to_string(base().join("estado").join("local.key")).unwrap_or_default().trim().to_string()
}

/// El mouse esta sobre la mascota o el globo: la ventana puede tomar el foco al hacer clic (para escribir). (27-oct) Ya NO decide
/// si recibe clics: eso lo hace la zona tactil fija (SetWindowRgn, ver `zona`); la ventana siempre recibe lo que cae en su zona.
#[tauri::command]
fn interactivo(window: WebviewWindow, si: bool) {
    let _ = window.set_focusable(si || ESCRIBIENDO.load(Ordering::Relaxed));
    let _ = window.set_skip_taskbar(true);
}

#[cfg(windows)]
#[link(name = "gdi32")]
extern "system" {
    fn CreateRectRgn(l: i32, t: i32, r: i32, b: i32) -> *mut std::ffi::c_void;
    fn CombineRgn(dst: *mut std::ffi::c_void, a: *mut std::ffi::c_void, b: *mut std::ffi::c_void, modo: i32) -> i32;
    fn DeleteObject(o: *mut std::ffi::c_void) -> i32;
}
#[cfg(windows)]
#[link(name = "user32")]
extern "system" {
    fn SetWindowRgn(hwnd: *mut std::ffi::c_void, rgn: *mut std::ffi::c_void, redibujar: i32) -> i32;
}

/// Arma la region de la ventana con las zonas guardadas y la escala `f` (px CSS -> px fisicos). Los rectangulos se redondean
/// HACIA AFUERA. Sin zonas -> region vacia (la ventana no existe para el mouse ni se ve nada). Windows se queda con la region.
#[cfg(windows)]
fn zona_aplicar(hwnd: *mut std::ffi::c_void, f: f64) {
    let z = ZONA.lock().unwrap_or_else(|e| e.into_inner()).clone();
    let cl = |v: f64| v.max(-32000.0).min(32000.0) as i32;
    unsafe {
        let dst = CreateRectRgn(0, 0, 0, 0);
        if dst.is_null() { return; }
        for r in z.iter() {
            let (l, t) = (cl((r[0] * f).floor()), cl((r[1] * f).floor()));
            let (rr, b) = (cl(((r[0] + r[2]) * f).ceil()), cl(((r[1] + r[3]) * f).ceil()));
            if rr <= l || b <= t { continue; }
            let tmp = CreateRectRgn(l, t, rr, b);
            if !tmp.is_null() {
                CombineRgn(dst, dst, tmp, 2);   // RGN_OR
                DeleteObject(tmp);
            }
        }
        if SetWindowRgn(hwnd, dst, 1) == 0 { DeleteObject(dst); }   // si falla, la region sigue siendo nuestra
    }
    ZONA_F.store(f.to_bits(), Ordering::Relaxed);
    ZONA_VIEJA.store(0, Ordering::Relaxed);
}

/// La pagina manda cada vez que cambia el diseño (globo, lista, capsula, Ajustes, mover, animaciones) los rectangulos de lo
/// que se ve y se toca, en px CSS. Rust los convierte con la escala del monitor donde esta la ventana AHORA.
#[tauri::command]
fn zona(window: WebviewWindow, r: Vec<[f64; 4]>) {
    let r: Vec<[f64; 4]> = r.into_iter().filter(|a| a.iter().all(|v| v.is_finite())).take(32).collect();
    *ZONA.lock().unwrap_or_else(|e| e.into_inner()) = r;
    #[cfg(windows)]
    {
        if let Ok(hwnd) = window.hwnd() {
            zona_aplicar(hwnd.0 as _, window.scale_factor().unwrap_or(1.0));
        }
    }
    // (28-oct) macOS: no hay region de ventana; solo se guarda la zona. El hilo del cursor (abajo) deja pasar los clics
    // (set_ignore_cursor_events) cuando el cursor esta fuera de todos los rectangulos.
    #[cfg(not(windows))]
    let _ = window;
}

/// Al escribir en el globo la ventana toma el foco (y no lo suelta aunque el mouse salga); al terminar, lo devuelve.
#[tauri::command]
fn escribir(window: WebviewWindow, si: bool) {
    ESCRIBIENDO.store(si, Ordering::Relaxed);
    let _ = window.set_focusable(si);
    if si {
        let _ = window.set_focus();
    }
    let _ = window.set_skip_taskbar(true);
}

#[tauri::command]
fn mover(window: WebviewWindow, dx: f64, dy: f64) {
    if let (Ok(p), Ok(f)) = (window.outer_position(), window.scale_factor()) {
        let _ = window.set_position(LogicalPosition::new(p.x as f64 / f + dx, p.y as f64 / f + dy));
    }
}

#[cfg(windows)]
#[link(name = "user32")]
extern "system" {
    fn SetWindowPos(hwnd: *mut std::ffi::c_void, after: *mut std::ffi::c_void, x: i32, y: i32, cx: i32, cy: i32, flags: u32) -> i32;
}

/// (19-oct) mover Y cambiar de tamaño en UNA sola llamada de Windows: con set_position + set_size por separado la
/// mascota daba un salto (un cuadro en la posicion vieja con el tamaño nuevo) al achicar/agrandar la ventana.
#[tauri::command]
fn limites(window: WebviewWindow, x: f64, y: f64, w: f64, h: f64) {
    // (28-oct) macOS: posicion y tamaño logicos con la API de Tauri (dos llamadas; sin region que quitar). Windows: el bloque de abajo, igual que antes.
    #[cfg(not(windows))]
    {
        let _ = window.set_position(LogicalPosition::new(x, y));
        let _ = window.set_size(LogicalSize::new(w, h));
    }
    #[cfg(windows)]
    {
    let f = window.scale_factor().unwrap_or(1.0);
    if let Ok(hwnd) = window.hwnd() {
        unsafe {
            SetWindowPos(hwnd.0 as _, std::ptr::null_mut(), (x * f).round() as i32, (y * f).round() as i32,
                         (w * f).round() as i32, (h * f).round() as i32, 0x0004 | 0x0010 | 0x0200);   // NOZORDER|NOACTIVATE|NOOWNERZORDER
        }
        // La region va en px fisicos pegada a la esquina de la ventana y la pagina todavia no volvio a medirse con el tamaño nuevo: por unos
        // cuadros la region vieja recortaria al gato. Se quita (ventana entera, sin dibujo recortado) hasta que la pagina mande la zona nueva
        // (`zona` la vuelve a armar); si no llega en ~750 ms, el hilo del cursor reaplica la ultima guardada.
        unsafe { SetWindowRgn(hwnd.0 as _, std::ptr::null_mut(), 1); }
        ZONA_VIEJA.store(1, Ordering::Relaxed);
    }
    }
}

#[tauri::command]
fn visible(window: WebviewWindow, si: bool) {
    // (27-oct) la ventana NACE oculta (tauri.conf.json: "visible": false) y la pagina la muestra cuando el gato ya se dibujo.
    // Mostrarla NUNCA toma el foco: antes de show() queda sin foco (salvo que se este escribiendo en el globo), asi Windows
    // no la activa (WS_EX_NOACTIVATE) y lo que estabas escribiendo en otra app sigue recibiendo el teclado.
    if si && !ESCRIBIENDO.load(Ordering::Relaxed) {
        let _ = window.set_focusable(false);
    }
    let _ = if si { window.show() } else { window.hide() };
    let _ = window.set_skip_taskbar(true);
}

#[tauri::command]
fn reafirmar(window: WebviewWindow) {
    let _ = window.set_always_on_top(true);
    // (21-oct) "no aparece la mascota" aunque el menu dice "Ocultar": Windows la minimizo (p. ej. "mostrar escritorio")
    // y al volver quedo VISIBLE pero de 160x28 px (el tamaño de una ventana minimizada). Si esta minimizada o mas chica
    // que el gato, se le devuelve su tamaño de 400x600 sin robar el foco.
    if !window.is_visible().unwrap_or(false) {
        return;
    }
    let f = window.scale_factor().unwrap_or(1.0);
    let chica = window.outer_size().map(|s| (s.width as f64) < 300.0 * f || (s.height as f64) < 400.0 * f).unwrap_or(false);
    if window.is_minimized().unwrap_or(false) || chica {
        let _ = window.unminimize();
        // (28-oct) macOS: se le devuelve el tamaño de 400x600 logicos sin tocar la posicion. Windows: el bloque de abajo, igual que antes.
        #[cfg(not(windows))]
        let _ = window.set_size(LogicalSize::new(400.0, 600.0));
        #[cfg(windows)]
        {
        if let (Ok(hwnd), Ok(p)) = (window.hwnd(), window.outer_position()) {
            let (x, y) = if p.x < -10000 || p.y < -10000 { (0, 0) } else { (p.x, p.y) };
            unsafe {
                SetWindowPos(hwnd.0 as _, std::ptr::null_mut(), x, y, (400.0 * f).round() as i32, (600.0 * f).round() as i32,
                             0x0004 | 0x0010 | 0x0200);   // NOZORDER|NOACTIVATE|NOOWNERZORDER
            }
        }
        }
    }
}

/// (26-oct) Puerto REAL del hub: estado\puerto.txt (lo escribe el hub antes de escuchar). Sin archivo, o con algo que no sea
/// un puerto de 8787 a 8799, 8787. La pagina lo vuelve a pedir si un pedido al hub falla (el hub pudo reiniciarse en otro).
fn puerto_hub() -> u16 {
    fs::read_to_string(base().join("estado").join("puerto.txt")).ok()
        .and_then(|s| s.trim().parse::<u16>().ok())
        .filter(|p| (8787..=8799).contains(p))
        .unwrap_or(8787)
}

#[tauri::command]
fn puerto() -> String {
    puerto_hub().to_string()
}

/// Solo abre sesiones de la app de Claude o el panel del hub local. Nada mas.
#[tauri::command]
fn abrir_url(url: String) {
    let ok_claude = url.starts_with("claude://claude.ai/epitaxy/local_") && url.len() < 90;
    let ok_hub = url.starts_with(&format!("http://127.0.0.1:{}/", puerto_hub()));
    if ok_claude || ok_hub {
        // (28-oct) macOS: `open` (en Windows sigue siendo explorer, igual que antes).
        #[cfg(windows)]
        let _ = Command::new("explorer").arg(&url).spawn();
        #[cfg(not(windows))]
        let _ = Command::new(if cfg!(target_os = "macos") { "open" } else { "xdg-open" }).arg(&url).spawn();
    }
}

/// Verificacion: estado\escritorio-captura.pedido (una expresion JS) -> la pagina la evalua -> guardar_txt.
#[tauri::command]
fn leer_pedido() -> Option<String> {
    let p = base().join("estado").join("escritorio-captura.pedido");
    let s = fs::read_to_string(&p).ok()?;
    let _ = fs::remove_file(&p);
    Some(s)
}

#[tauri::command]
fn guardar_txt(txt: String) {
    let _ = fs::write(base().join("estado").join("escritorio-captura.txt"), txt);
}

#[tauri::command]
fn salir(app: tauri::AppHandle) {
    app.exit(0);
}

/// Diagnostico del arrastre nativo: [AllowExternalDrop (-1/0/1), mensajes "kodama-soltar" recibidos, rutas del ultimo].
#[tauri::command]
fn drop_info() -> [i64; 3] {
    [DROP_EXT.load(Ordering::Relaxed) as i64, DROP_MSGS.load(Ordering::Relaxed) as i64, DROP_RUTAS.load(Ordering::Relaxed) as i64]
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            conf_leer, conf_guardar, clave, puerto, interactivo, escribir, mover, limites, visible, reafirmar, abrir_url,
            leer_pedido, guardar_txt, salir, zona, drop_info
        ])
        // (27-oct) la ventana cambio de monitor/escala: la region se vuelve a armar con la escala nueva (el respaldo es el hilo de abajo)
        .on_window_event(|win, ev| {
            #[cfg(windows)]
            {
            if let tauri::WindowEvent::ScaleFactorChanged { scale_factor, .. } = ev {
                if let Ok(hwnd) = win.hwnd() { zona_aplicar(hwnd.0 as _, *scale_factor); }
            }
            }
            // (28-oct) macOS: sin region de ventana, no hay nada que rearmar al cambiar de monitor.
            #[cfg(not(windows))]
            let _ = (win, ev);
        })
        .setup(|app| {
            let w = app.get_webview_window("main").expect("ventana main");
            // (27-oct) zona tactil fija: la ventana YA NO ignora el mouse (antes set_ignore_cursor_events(true) y el sondeo de 150 ms la
            // volvia interactiva: el lapiz tocaba antes y atravesaba la mascota). Lo que queda fuera de la region no existe para Windows.
            let _ = w.set_ignore_cursor_events(false);
            {
                let mut z = ZONA.lock().unwrap_or_else(|e| e.into_inner());
                if z.is_empty() { z.push(ZONA_INICIAL); }
            }
            #[cfg(windows)]
            { if let Ok(hwnd) = w.hwnd() { zona_aplicar(hwnd.0 as _, w.scale_factor().unwrap_or(1.0)); } }
            let _ = w.set_focusable(false);
            // (14-oct, rendimiento) WebView2 en modo "poca memoria": libera cache y paginas que no usa. La mascota
            // es una pagina chica; no necesita el colchon de un navegador.
            // (28-oct) macOS: WKWebView no tiene estos ajustes de WebView2 (memoria, arrastre nativo de archivos): el bloque es solo de Windows.
            #[cfg(windows)]
            {
            let ah = app.handle().clone();
            let _ = w.with_webview(move |wv| unsafe {
                use webview2_com::Microsoft::Web::WebView2::Win32::{ICoreWebView2_19, ICoreWebView2Controller4, ICoreWebView2File,
                    ICoreWebView2WebMessageReceivedEventArgs2, COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW};
                use windows_core::Interface;
                let ctl = wv.controller();
                // (27-oct, soltar 2) "prohibido" al arrastrar un archivo desde el Explorador: la ventana nace oculta y la muestra la pagina; el destino
                // de arrastre de WebView2 (Chrome_WidgetWin_0) con AllowExternalDrop=false (lo pone wry cuando dragDropEnabled es true) devolvia
                // DROPEFFECT_NONE. Ahora WebView2 recibe el arrastre NATIVO: se deja AllowExternalDrop en true (y se lee de vuelta para el diagnostico).
                if let Ok(c4) = ctl.cast::<ICoreWebView2Controller4>() {
                    let _ = c4.SetAllowExternalDrop(true);
                    let mut v = windows_core::BOOL(0);
                    if c4.AllowExternalDrop(&mut v).is_ok() { DROP_EXT.store(if v.as_bool() { 1 } else { 0 }, Ordering::Relaxed); }
                }
                if let Ok(core) = ctl.CoreWebView2() {
                    if let Ok(c19) = core.cast::<ICoreWebView2_19>() {
                        let _ = c19.SetMemoryUsageTargetLevel(COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW);
                    }
                    // La pagina, al recibir el drop de WebView2, manda postMessageWithAdditionalObjects("kodama-soltar", files): aca salen las
                    // RUTAS reales (ICoreWebView2File::Path) y se le devuelven a la pagina con el evento "kodama-soltar".
                    let ah2 = ah.clone();
                    let h = webview2_com::WebMessageReceivedEventHandler::create(Box::new(move |_sender, args| {
                        if let Some(args) = args {
                            let mut msg = windows_core::PWSTR(std::ptr::null_mut());
                            if args.WebMessageAsJson(&mut msg).is_ok() && webview2_com::take_pwstr(msg) == "\"kodama-soltar\"" {
                                DROP_MSGS.fetch_add(1, Ordering::Relaxed);
                                let mut rutas: Vec<String> = Vec::new();
                                if let Ok(a2) = args.cast::<ICoreWebView2WebMessageReceivedEventArgs2>() {
                                    if let Ok(col) = a2.AdditionalObjects() {
                                        let mut n = 0u32;
                                        let _ = col.Count(&mut n);
                                        for i in 0..n.min(64) {
                                            if let Ok(o) = col.GetValueAtIndex(i) {
                                                if let Ok(f) = o.cast::<ICoreWebView2File>() {
                                                    let mut p = windows_core::PWSTR(std::ptr::null_mut());
                                                    if f.Path(&mut p).is_ok() { rutas.push(webview2_com::take_pwstr(p)); }
                                                }
                                            }
                                        }
                                    }
                                }
                                DROP_RUTAS.store(rutas.len() as u32, Ordering::Relaxed);
                                let _ = ah2.emit_to("main", "kodama-soltar", rutas);
                            }
                        }
                        Ok(())
                    }));
                    let mut token = 0i64;
                    let _ = core.add_WebMessageReceived(&h, &mut token);
                }
            });
            }
            // Mira el cursor cada 150 ms y le avisa a la pagina si esta dentro de la ventana (para el clic que
            // atraviesa: con la ventana ignorando el mouse, la pagina no se entera sola de donde esta).
            let w2 = w.clone();
            thread::spawn(move || {
                // (15-oct) avisa la posicion SOLO si el cursor se movio (dentro o fuera de la ventana): fuera sirve
                // para que los ojos lo sigan si lo activas; quieto no gasta nada
                let mut ultimo = (f64::NAN, f64::NAN);
                #[cfg(not(windows))]
                let mut recibe_mouse = true;   // (28-oct) macOS: la ventana nace recibiendo el mouse (setup: set_ignore_cursor_events(false))
                loop {
                    thread::sleep(Duration::from_millis(150));
                    // (27-oct) respaldo de la zona tactil: si la escala del monitor de la ventana cambio (se movio a otra pantalla), se rearma
                    #[cfg(windows)]
                    {
                    if let (Ok(hwnd), Ok(f)) = (w2.hwnd(), w2.scale_factor()) {
                        let vieja = ZONA_VIEJA.load(Ordering::Relaxed);
                        if vieja > 0 { ZONA_VIEJA.store(vieja + 1, Ordering::Relaxed); }
                        if f.to_bits() != ZONA_F.load(Ordering::Relaxed) || vieja > 5 { zona_aplicar(hwnd.0 as _, f); }
                    }
                    }
                    if !w2.is_visible().unwrap_or(false) {
                        continue;
                    }
                    let (Ok(c), Ok(p), Ok(_s), Ok(f)) = (w2.cursor_position(), w2.outer_position(), w2.outer_size(), w2.scale_factor()) else { continue };
                    let (x, y) = ((c.x - p.x as f64) / f, (c.y - p.y as f64) / f);
                    // (28-oct) macOS: la zona tactil sin region de ventana. Cursor dentro de algun rectangulo (o escribiendo en el globo) =
                    // la ventana recibe el mouse; fuera = los clics pasan a lo de abajo. Se cambia solo cuando cambia (sondeo de 150 ms).
                    #[cfg(not(windows))]
                    {
                        let dentro = ESCRIBIENDO.load(Ordering::Relaxed) || ZONA.lock().unwrap_or_else(|e| e.into_inner()).iter()
                            .any(|r| x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[3]);
                        if dentro != recibe_mouse {
                            recibe_mouse = dentro;
                            let _ = w2.set_ignore_cursor_events(!dentro);
                        }
                    }
                    if (x - ultimo.0).abs() < 0.5 && (y - ultimo.1).abs() < 0.5 {
                        continue;
                    }
                    ultimo = (x, y);
                    let _ = w2.emit_to("main", "cursor", (x, y));
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("no pude arrancar la mascota");
}
