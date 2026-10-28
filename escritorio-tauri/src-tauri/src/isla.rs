// (28-oct) MODO ISLA (solo macOS): la mascota vive en la muesca del MacBook, como una Dynamic Island. Aca solo va lo de AppKit: medir la
// pantalla (muesca), subir el nivel de la ventana por encima de la barra de menus, verla en todos los Spaces y colocarla arriba al centro.
// Ideas tomadas (leidas, sin copiar codigo) de dos apps de muesca de codigo abierto, a quienes se acredita:
//   - Vibe Notch / Claude Island (farouqaldori/vibe-notch, Apache-2.0): muesca = safeAreaInsets.top > 0; ancho = ancho de pantalla - auxiliaryTopLeftArea
//     - auxiliaryTopRightArea (+4 pt de holgura); sin esas areas, 180 pt; ventana sin marco que cubre el borde de arriba de la pantalla;
//     nivel mainMenu + 3; collectionBehavior canJoinAllSpaces + stationary + fullScreenAuxiliary + ignoresCycle; la apertura rebota un poco y el cierre no.
//   - CodeIsland (wxtsky/CodeIsland, MIT): hay muesca si auxiliaryTopLeftArea o auxiliaryTopRightArea existen; sin muesca, ancho simulado = 14 % del
//     ancho de pantalla entre 160 y 240 pt; nivel mainMenu + 2; apertura con resorte (amortiguacion ~0,82) y cierre sin rebote (1,0).
// Todo lo que toca AppKit corre en el hilo principal (los comandos de Tauri sin `async` lo hacen).
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
const NIVEL_MENU: isize = 24;     // NSMainMenuWindowLevel
const NIVEL_ESTADO: isize = 25;   // NSStatusWindowLevel
const NIVEL_FLOTANTE: isize = 3;  // NSFloatingWindowLevel (lo que deja Tauri con "siempre visible")

#[derive(Clone, Copy, Debug)]
pub struct Medida {
    pub notch: bool,
    pub nw: f64,       // ancho de la muesca (o el simulado si no hay), en puntos
    pub nh: f64,       // alto de la muesca (safeAreaInsets.top); sin muesca, el alto de la barra de menus
    pub barra: f64,    // alto de la barra de menus de esa pantalla
    pub marco: NSRect, // frame de la pantalla (coordenadas de Cocoa: origen abajo a la izquierda)
    pub visible: NSRect,
}

/// Mide la pantalla de la isla: la primera con muesca; si ninguna la tiene, la principal (la de la barra de menus).
pub fn medir(mtm: MainThreadMarker) -> Option<Medida> {
    let pantallas = NSScreen::screens(mtm);
    let n = pantallas.count();
    if n == 0 { return None; }
    let tiene = |s: &NSScreen| s.respondsToSelector(objc2::sel!(safeAreaInsets)) && s.safeAreaInsets().top > 0.0;   // macOS 12+
    let mut elegida = None;
    for i in 0..n {
        let s = pantallas.objectAtIndex(i);
        if tiene(&s) { elegida = Some(s); break; }
    }
    let s = elegida.unwrap_or_else(|| pantallas.objectAtIndex(0));
    let marco = s.frame();
    let visible = s.visibleFrame();
    let barra = ((marco.origin.y + marco.size.height) - (visible.origin.y + visible.size.height)).max(0.0);
    // SOLO pruebas (el runner de CI no tiene muesca): KODAMA_ISLA_MUESCA_PRUEBA="190x32" simula una muesca de ese ancho x alto (en puntos)
    if let Ok(v) = std::env::var("KODAMA_ISLA_MUESCA_PRUEBA") {
        if let Some((a, b)) = v.split_once('x') {
            if let (Ok(nw), Ok(nh)) = (a.trim().parse::<f64>(), b.trim().parse::<f64>()) {
                if nw > 0.0 && nh > 0.0 { return Some(Medida { notch: true, nw, nh, barra, marco, visible }); }
            }
        }
    }
    if tiene(&s) {
        let nh = s.safeAreaInsets().top;
        let izq = if s.respondsToSelector(objc2::sel!(auxiliaryTopLeftArea)) { s.auxiliaryTopLeftArea().size.width } else { 0.0 };
        let der = if s.respondsToSelector(objc2::sel!(auxiliaryTopRightArea)) { s.auxiliaryTopRightArea().size.width } else { 0.0 };
        let nw = if izq > 0.0 && der > 0.0 { marco.size.width - izq - der + 4.0 } else { 180.0 };
        Some(Medida { notch: true, nw, nh, barra, marco, visible })
    } else {
        let nw = (marco.size.width * 0.14).max(160.0).min(240.0);
        Some(Medida { notch: false, nw, nh: if barra > 0.0 { barra } else { 25.0 }, barra, marco, visible })
    }
}

fn nivel(notch: bool) -> isize { if notch { NIVEL_MENU + 3 } else { NIVEL_ESTADO } }

/// Coloca la ventana arriba al centro de la pantalla medida (con muesca: pegada al borde de arriba; sin ella: justo debajo de la barra de menus),
/// la sube de nivel y la hace visible en todos los Spaces. `ptr` es el NSWindow (WebviewWindow::ns_window()).
pub unsafe fn aplicar(ptr: *mut std::ffi::c_void, m: &Medida, w: f64, h: f64) {
    if ptr.is_null() { return; }
    let ns: &NSWindow = &*(ptr as *const NSWindow);
    if COMP_PREVIA.load(Ordering::Relaxed) == usize::MAX { COMP_PREVIA.store(ns.collectionBehavior().0 as usize, Ordering::Relaxed); }
    ns.setCollectionBehavior(NSWindowCollectionBehavior::CanJoinAllSpaces | NSWindowCollectionBehavior::Stationary
        | NSWindowCollectionBehavior::FullScreenAuxiliary | NSWindowCollectionBehavior::IgnoresCycle);
    ns.setHasShadow(false);
    ns.setLevel(nivel(m.notch));
    let arriba = if m.notch { m.marco.origin.y + m.marco.size.height } else { m.visible.origin.y + m.visible.size.height };
    let x = m.marco.origin.x + (m.marco.size.width - w) / 2.0;
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
