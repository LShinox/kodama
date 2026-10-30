// (30-oct, isla 3) Geometria PURA de la muesca (sin AppKit ni Tauri): medir la muesca a partir de lo que dice NSScreen, elegir la pantalla de la isla y armar la
// "firma" de la configuracion de pantallas (para saber cuando cambio). Solo se compila en macOS y en las pruebas (`rustc --test`): Windows no la ve.
// Ideas (leidas, sin copiar codigo) de Claude Pet (GPL-3.0): ancho de la muesca = borde izquierdo del area auxiliar derecha - borde derecho del area
// auxiliar izquierda, alto = safeAreaInsets.top; sin esas areas la pantalla NO tiene muesca (no hay un ancho de respaldo).

/// Una pantalla tal como la informa NSScreen. Las areas auxiliares son (minX, maxX) en el mismo espacio de coordenadas que ellas mismas usan;
/// (0, 0) si la pantalla no tiene esa area.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pant {
    pub x: f64, pub y: f64, pub w: f64, pub h: f64, // frame de la pantalla
    pub top: f64,                                   // safeAreaInsets.top
    pub izq: (f64, f64),                            // auxiliaryTopLeftArea
    pub der: (f64, f64),                            // auxiliaryTopRightArea
}

/// La muesca medida: ancho, alto y centro horizontal medido desde el borde izquierdo de la pantalla.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Muesca { pub nw: f64, pub nh: f64, pub cx: f64 }

impl Pant {
    /// Muesca de esta pantalla, o None si no la tiene (alto 0, o falta alguna de las dos areas auxiliares, o no dejan hueco entre ellas).
    pub fn muesca(&self) -> Option<Muesca> {
        let (il, ir) = self.izq;
        let (dl, dr) = self.der;
        if !(self.top > 0.0) || !(ir - il > 0.0) || !(dr - dl > 0.0) { return None; }
        let nw = dl - ir;                       // exacto: sin holgura y sin ancho de respaldo
        if !(nw > 0.0) || nw >= self.w { return None; }
        // el area izquierda empieza en el borde izquierdo de la pantalla (il): restarlo sirve igual si las areas vienen en coordenadas locales o globales
        let cx = ((ir + dl) / 2.0 - il).max(nw / 2.0).min(self.w - nw / 2.0);
        Some(Muesca { nw, nh: self.top, cx })
    }
}

/// Pantalla de la isla: la primera con muesca; si ninguna la tiene, la principal (la 0). None si no hay pantallas.
pub fn elegir(p: &[Pant]) -> Option<usize> {
    if p.is_empty() { return None; }
    Some(p.iter().position(|s| s.muesca().is_some()).unwrap_or(0))
}

/// Firma barata de la configuracion de pantallas: cuantas hay, y de cada una su frame, su alto de area segura y el ancho de sus areas auxiliares
/// (el orden importa: la 0 es la principal). `extra` = la simulacion de pruebas, si hay. Cambia cuando se cierra la tapa, se enchufa o se saca un
/// monitor, cambia la pantalla principal o cambia la resolucion.
pub fn firma(p: &[Pant], extra: &str) -> String {
    let mut s = format!("n{}", p.len());
    for q in p {
        s.push_str(&format!("|{:.0},{:.0},{:.0},{:.0},t{:.0},a{:.0}-{:.0}/{:.0}-{:.0}", q.x, q.y, q.w, q.h, q.top, q.izq.0, q.izq.1, q.der.0, q.der.1));
    }
    if !extra.is_empty() { s.push_str("|sim:"); s.push_str(extra); }
    s
}

#[cfg(test)]
mod pruebas {
    use super::*;

    // MacBook Pro de 14": 1512 x 982 pt, muesca de ~185 pt centrada, 32 pt de alto
    fn mbp14(x: f64, y: f64) -> Pant {
        Pant { x, y, w: 1512.0, h: 982.0, top: 32.0, izq: (x, x + 663.0), der: (x + 849.0, x + 1512.0) }
    }
    fn externo(x: f64) -> Pant {
        Pant { x, y: 0.0, w: 2560.0, h: 1440.0, top: 0.0, izq: (0.0, 0.0), der: (0.0, 0.0) }
    }

    #[test]
    fn mide_ancho_alto_y_centro_exactos() {
        let m = mbp14(0.0, 0.0).muesca().unwrap();
        assert_eq!(m.nw, 186.0);   // 849 - 663, sin +4
        assert_eq!(m.nh, 32.0);
        assert_eq!(m.cx, 756.0);
    }

    #[test]
    fn centro_igual_con_coordenadas_locales_o_globales() {
        let local = mbp14(0.0, 0.0).muesca().unwrap();
        let global = mbp14(2560.0, 0.0).muesca().unwrap();   // las areas vienen desplazadas por el origen de la pantalla
        assert_eq!(local, global);
    }

    #[test]
    fn muesca_no_centrada_se_respeta() {
        let p = Pant { x: 0.0, y: 0.0, w: 1000.0, h: 700.0, top: 30.0, izq: (0.0, 400.0), der: (580.0, 1000.0) };
        let m = p.muesca().unwrap();
        assert_eq!((m.nw, m.cx), (180.0, 490.0));
    }

    #[test]
    fn sin_areas_auxiliares_no_hay_muesca_ni_180_de_respaldo() {
        let p = Pant { x: 0.0, y: 0.0, w: 1512.0, h: 982.0, top: 32.0, izq: (0.0, 0.0), der: (0.0, 0.0) };
        assert_eq!(p.muesca(), None);
        // solo una de las dos areas: tampoco
        let q = Pant { izq: (0.0, 663.0), ..p };
        assert_eq!(q.muesca(), None);
        let r = Pant { der: (849.0, 1512.0), ..p };
        assert_eq!(r.muesca(), None);
    }

    #[test]
    fn sin_alto_seguro_no_hay_muesca() {
        let p = Pant { top: 0.0, ..mbp14(0.0, 0.0) };
        assert_eq!(p.muesca(), None);
        assert_eq!(externo(0.0).muesca(), None);
    }

    #[test]
    fn areas_absurdas_se_descartan() {
        // las areas se tocan o se cruzan: no hay hueco
        let p = Pant { izq: (0.0, 800.0), der: (700.0, 1512.0), ..mbp14(0.0, 0.0) };
        assert_eq!(p.muesca(), None);
    }

    #[test]
    fn elige_la_primera_con_muesca_o_la_principal() {
        assert_eq!(elegir(&[]), None);
        // tapa cerrada: solo el externo -> la principal, sin muesca
        assert_eq!(elegir(&[externo(0.0)]), Some(0));
        // portatil abierto + externo
        assert_eq!(elegir(&[mbp14(0.0, 0.0), externo(1512.0)]), Some(0));
        // el externo es el principal y el portatil es el segundo
        assert_eq!(elegir(&[externo(0.0), mbp14(2560.0, 0.0)]), Some(1));
        assert_eq!(elegir(&[externo(0.0), externo(2560.0)]), Some(0));
    }

    #[test]
    fn la_firma_cambia_con_cada_cambio_de_pantallas_y_no_sin_ellos() {
        let base = vec![mbp14(0.0, 0.0), externo(1512.0)];
        let f0 = firma(&base, "");
        assert_eq!(f0, firma(&base.clone(), ""));
        // se saca el monitor externo (o se cierra la tapa y queda solo el externo)
        assert_ne!(f0, firma(&base[..1], ""));
        assert_ne!(f0, firma(&base[1..], ""));
        // cambia la resolucion del portatil
        let mut res = base.clone();
        res[0].w = 1800.0; res[0].h = 1169.0;
        assert_ne!(f0, firma(&res, ""));
        // cambia la pantalla principal (otro orden)
        assert_ne!(f0, firma(&[base[1], base[0]], ""));
        // cambia el area segura o las areas auxiliares
        let mut seg = base.clone();
        seg[0].top = 0.0; seg[0].izq = (0.0, 0.0); seg[0].der = (0.0, 0.0);
        assert_ne!(f0, firma(&seg, ""));
        // la simulacion de pruebas tambien cuenta
        assert_ne!(f0, firma(&base, "190x32"));
        assert_ne!(firma(&base, "190x32"), firma(&base, "214x36"));
        // una diferencia menor a medio punto de pixel no cuenta como cambio
        let mut casi = base.clone();
        casi[0].w = 1512.2;
        assert_eq!(f0, firma(&casi, ""));
    }
}
