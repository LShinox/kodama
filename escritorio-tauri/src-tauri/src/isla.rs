// (28-oct) MODO ISLA (solo macOS): la mascota vive en la muesca del MacBook, como una Dynamic Island. Aca solo va lo de AppKit: medir la
// pantalla (muesca), subir el nivel de la ventana por encima de la barra de menus, verla en todos los Spaces y colocarla arriba al centro.
// Ideas tomadas (leidas, sin copiar codigo) de dos apps de muesca de codigo abierto, a quienes se acredita:
//   - Vibe Notch / Claude Island (farouqaldori/vibe-notch, Apache-2.0): muesca = safeAreaInsets.top > 0; ventana sin marco que cubre el borde de arriba de la
//     pantalla; collectionBehavior canJoinAllSpaces + stationary + fullScreenAuxiliary + ignoresCycle; la apertura rebota un poco y el cierre no.
//   - CodeIsland (wxtsky/CodeIsland, MIT): hay muesca si auxiliaryTopLeftArea o auxiliaryTopRightArea existen; sin muesca, ancho simulado = 14 % del
//     ancho de pantalla entre 160 y 240 pt; apertura con resorte (amortiguacion ~0,82) y cierre sin rebote (1,0).
// (30-oct, isla 3) Ideas de Claude Pet (GPL-3.0; leidas, sin copiar codigo): la muesca se MIDE (ancho = area auxiliar derecha.minX - area auxiliar izquierda.maxX,
// alto = safeAreaInsets.top, posicion X desde esas areas) y sin esas areas la pantalla NO tiene muesca (se acabo el respaldo de 180 pt y la holgura de +4 pt);
// la isla se vuelve a acoplar cuando cambian las pantallas (firma en isla_geom.rs); nivel de ventana statusBar + 1. La parte pura vive en isla_geom.rs.
// Todo lo que toca AppKit corre en el hilo principal (los comandos de Tauri sin `async` lo hacen).
use crate::isla_geom::{self, Muesca, Pant};
use objc2::runtime::NSObjectProtocol;
use objc2::MainThreadMarker;
use objc2_app_kit::{NSScreen, NSWindow, NSWindowCollectionBehavior};
use objc2_foundation::{NSPoint, NSRect, NSSize};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

/// true mientras la ventana esta en modo isla (reafirmar() lo mira para no bajarle el nivel).
pub static ACTIVA: AtomicBool = AtomicBool::new(false);
/// true si la pantalla de la isla tiene muesca (decide el nivel de la ventana al reafirmarlo).
pub static CON_MUESCA: AtomicBool = AtomicBool::new(false);
/// collectionBehavior que tenia la ventana antes de la isla (usize::MAX = aun no guardado).
static COMP_PREVIA: AtomicUsize = AtomicUsize::new(usize::MAX);
// Niveles de ventana: barra de menus (NSMainMenuWindowLevel) = 24; ventanas de los iconos de la barra (NSStatusWindowLevel) = 25; menus desplegables y
// popovers del sistema = 101. Con muesca la isla va en 26 = statusBar + 1: el primer nivel ESTRICTAMENTE por encima de la barra y de sus iconos (en 25
// empataria con ellos) y muy por debajo de los menus y popovers (101), que se siguen viendo encima de ella. El 27 de antes (mainMenu + 3) tambien
// cumplia, pero sin necesidad: se usa el mas bajo que sirve.
const NIVEL_ESTADO: isize = 25;   // NSStatusWindowLevel
const NIVEL_FLOTANTE: isize = 3;  // NSFloatingWindowLevel (lo que deja Tauri con "siempre visible")

#[derive(Clone, Debug)]
pub struct Medida {
    pub notch: bool,
    pub nw: f64,       // ancho de la muesca medido (o el simulado si no hay), en puntos
    pub nh: f64,       // alto de la muesca (safeAreaInsets.top); sin muesca, el alto de la barra de menus
    pub cx: f64,       // centro horizontal de la muesca desde el borde izquierdo de la pantalla (sin muesca: el centro de la pantalla)
    pub sim: bool,     // true si la muesca es SIMULADA para pruebas (la pagina dibuja una muesca falsa debajo de la pastilla)
    pub sig: String,   // firma de la configuracion de pantallas (cambia al cerrar la tapa, enchufar un monitor, cambiar de resolucion...)
    pub barra: f64,    // alto de la barra de menus de esa pantalla
    pub marco: NSRect, // frame de la pantalla (coordenadas de Cocoa: origen abajo a la izquierda)
    pub visible: NSRect,
}

/// Lee una pantalla tal como la informa NSScreen: el frame, el area segura de arriba y las dos areas auxiliares de la barra de menus.
fn leer(s: &NSScreen) -> Pant {
    let f = s.frame();
    let top = if s.respondsToSelector(objc2::sel!(safeAreaInsets)) { s.safeAreaInsets().top } else { 0.0 };   // macOS 12+
    let izq = if top > 0.0 && s.respondsToSelector(objc2::sel!(auxiliaryTopLeftArea)) {
        let r = s.auxiliaryTopLeftArea(); (r.origin.x, r.origin.x + r.size.width)
    } else { (0.0, 0.0) };
    let der = if top > 0.0 && s.respondsToSelector(objc2::sel!(auxiliaryTopRightArea)) {
        let r = s.auxiliaryTopRightArea(); (r.origin.x, r.origin.x + r.size.width)
    } else { (0.0, 0.0) };
    Pant { x: f.origin.x, y: f.origin.y, w: f.size.width, h: f.size.height, top, izq, der }
}

/// SOLO pruebas (el runner de CI no tiene muesca ni puede cambiar de pantallas): simula la muesca con una variable de entorno, o con un ARCHIVO que se
/// puede reescribir mientras la app corre (asi la CI simula "enchufe/saque un monitor"). KODAMA_ISLA_PRUEBA_ARCHIVO=<ruta> con "190x32" (muesca de ese ancho
/// x alto, en puntos) o "sin" (pantalla sin muesca); si el archivo no existe o esta vacio vale KODAMA_ISLA_MUESCA_PRUEBA="190x32".
/// Devuelve el texto leido y la muesca simulada (None = "sin").
fn prueba() -> Option<(String, Option<(f64, f64)>)> {
    let mut v = String::new();
    if let Ok(ruta) = std::env::var("KODAMA_ISLA_PRUEBA_ARCHIVO") {
        if let Ok(c) = std::fs::read_to_string(ruta) { v = c.trim().to_string(); }
    }
    if v.is_empty() { v = std::env::var("KODAMA_ISLA_MUESCA_PRUEBA").unwrap_or_default().trim().to_string(); }
    if v.is_empty() { return None; }
    if v.eq_ignore_ascii_case("sin") { return Some((v, None)); }
    let (a, b) = v.split_once('x')?;
    let (nw, nh) = (a.trim().parse::<f64>().ok()?, b.trim().parse::<f64>().ok()?);
    if nw > 0.0 && nh > 0.0 { Some((v, Some((nw, nh)))) } else { None }
}

/// Mide la pantalla de la isla: la primera con muesca; si ninguna la tiene, la principal (la de la barra de menus). Una pantalla tiene muesca solo si
/// informa safeAreaInsets.top > 0 Y las dos areas auxiliares de la barra (ver isla_geom.rs): no hay ancho de respaldo.
pub fn medir(mtm: MainThreadMarker) -> Option<Medida> {
    let pantallas = NSScreen::screens(mtm);
    let n = pantallas.count();
    if n == 0 { return None; }
    let ps: Vec<Pant> = (0..n).map(|i| leer(&pantallas.objectAtIndex(i))).collect();
    let sim = prueba();
    let sig = isla_geom::firma(&ps, sim.as_ref().map(|x| x.0.as_str()).unwrap_or(""));
    // "sin" (prueba): pantalla sin muesca aunque la real la tenga -> la principal
    let idx = if matches!(&sim, Some((_, None))) { 0 } else { isla_geom::elegir(&ps)? };
    let s = pantallas.objectAtIndex(idx);
    let marco = s.frame();
    let visible = s.visibleFrame();
    let barra = ((marco.origin.y + marco.size.height) - (visible.origin.y + visible.size.height)).max(0.0);
    let (muesca, simulada): (Option<Muesca>, bool) = match &sim {
        Some((_, Some((nw, nh)))) => (Some(Muesca { nw: *nw, nh: *nh, cx: marco.size.width / 2.0 }), true),
        Some((_, None)) => (None, false),
        None => (ps[idx].muesca(), false),
    };
    Some(match muesca {
        Some(m) => Medida { notch: true, nw: m.nw, nh: m.nh, cx: m.cx, sim: simulada, sig, barra, marco, visible },
        None => {
            let nw = (marco.size.width * 0.14).max(160.0).min(240.0);
            Medida { notch: false, nw, nh: if barra > 0.0 { barra } else { 25.0 }, cx: marco.size.width / 2.0, sim: false, sig, barra, marco, visible }
        }
    })
}

fn nivel(notch: bool) -> isize { if notch { NIVEL_ESTADO + 1 } else { NIVEL_ESTADO } }

/// Coloca la ventana arriba, centrada en la muesca (con muesca: pegada al borde de arriba; sin ella: centrada en la pantalla y justo debajo de la barra de
/// menus), la sube de nivel y la hace visible en todos los Spaces. `ptr` es el NSWindow (WebviewWindow::ns_window()).
pub unsafe fn aplicar(ptr: *mut std::ffi::c_void, m: &Medida, w: f64, h: f64) {
    if ptr.is_null() { return; }
    let ns: &NSWindow = &*(ptr as *const NSWindow);
    if COMP_PREVIA.load(Ordering::Relaxed) == usize::MAX { COMP_PREVIA.store(ns.collectionBehavior().0 as usize, Ordering::Relaxed); }
    ns.setCollectionBehavior(NSWindowCollectionBehavior::CanJoinAllSpaces | NSWindowCollectionBehavior::Stationary
        | NSWindowCollectionBehavior::FullScreenAuxiliary | NSWindowCollectionBehavior::IgnoresCycle);
    ns.setHasShadow(false);
    ns.setLevel(nivel(m.notch));
    let arriba = if m.notch { m.marco.origin.y + m.marco.size.height } else { m.visible.origin.y + m.visible.size.height };
    // la posicion X sale de la muesca medida (su centro), sin salirse de la pantalla
    let lo = m.marco.origin.x;
    let hi = (lo + m.marco.size.width - w).max(lo);
    let x = (m.marco.origin.x + m.cx - w / 2.0).max(lo).min(hi);
    ns.setFrame_display(NSRect::new(NSPoint::new(x, arriba - h), NSSize::new(w, h)), true);
    CON_MUESCA.store(m.notch, Ordering::Relaxed);
    ACTIVA.store(true, Ordering::Relaxed);
}

/// Vuelve a subir el nivel (Tauri/tao lo bajan a "flotante" con set_always_on_top; reafirmar() corre cada 2 s).
pub unsafe fn reafirmar(ptr: *mut std::ffi::c_void) {
    if ptr.is_null() { return; }
    let ns: &NSWindow = &*(ptr as *const NSWindow);
    ns.setLevel(nivel(CON_MUESCA.load(Ordering::Relaxed)));
}

/// Sale de la isla: nivel flotante y el collectionBehavior de antes.
pub unsafe fn quitar(ptr: *mut std::ffi::c_void) {
    ACTIVA.store(false, Ordering::Relaxed);
    if ptr.is_null() { return; }
    let ns: &NSWindow = &*(ptr as *const NSWindow);
    let prev = COMP_PREVIA.swap(usize::MAX, Ordering::Relaxed);
    if prev != usize::MAX { ns.setCollectionBehavior(NSWindowCollectionBehavior(prev as _)); }
    ns.setLevel(NIVEL_FLOTANTE);
}
