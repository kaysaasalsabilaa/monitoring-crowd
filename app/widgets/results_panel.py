import os
import subprocess
import sys
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QFrame, QTabWidget,
    QSizePolicy, QGridLayout, QStackedWidget,
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False


MAKS_BARIS = 500


def _resolve_name(row: dict, default_loc_name: str = "", counter: int = 0) -> str:
    # opsi 1: nama yang diisi user di field lokasi
    user_name = str(row.get("lokasi") or "").strip()
    if user_name:
        return user_name
    # opsi 2: nama default dari preview/map di input panel
    if default_loc_name and default_loc_name.strip():
        return default_loc_name.strip()
    # opsi 3: fallback numerik
    return f"Lokasi #{counter}" if counter > 0 else "Lokasi"

MONITOR_MAP_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<link rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<style>
html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;
  font-family:'Segoe UI',sans-serif;background:#0F1F2E;}
#map{position:absolute;top:46px;left:0;right:0;bottom:0;}
#leaflet-err{display:none;position:absolute;top:50%;left:50%;
  transform:translate(-50%,-50%);background:rgba(12,28,44,.95);color:#7A9EB0;
  padding:24px 32px;border-radius:12px;text-align:center;z-index:9999;
  border:1px solid rgba(201,168,76,.3);font-size:13px;line-height:1.8;}
#topbar{position:absolute;top:0;left:0;right:0;height:46px;
  background:rgba(10,22,35,.95);border-bottom:1px solid rgba(201,168,76,.25);
  display:flex;align-items:center;gap:12px;padding:0 16px;
  z-index:1000;backdrop-filter:blur(8px);}
#topbar-title{color:#C9A84C;font-size:11px;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;white-space:nowrap;}
#cnt-badge{background:rgba(201,168,76,.15);color:#C9A84C;
  border:1px solid rgba(201,168,76,.4);border-radius:12px;
  padding:2px 10px;font-size:11px;font-weight:700;}
#live-dot{width:8px;height:8px;border-radius:50%;background:#3ABF90;
  box-shadow:0 0 6px #3ABF90;flex-shrink:0;display:none;}
#no-data-msg{margin-left:auto;color:#5A7A8E;font-size:11px;white-space:nowrap;}
@keyframes pulseLive{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.5)}}
#live-dot.on{display:block;animation:pulseLive 1.5s infinite;}
.leaflet-control-zoom a{background:rgba(15,31,46,.92)!important;
  color:#C9A84C!important;border-color:rgba(201,168,76,.3)!important;}
.leaflet-popup-content-wrapper{background:rgba(12,28,44,.97)!important;
  border:1px solid rgba(201,168,76,.35)!important;border-radius:12px!important;
  color:#D0DCE4;box-shadow:0 8px 32px rgba(0,0,0,.5)!important;min-width:220px;}
.leaflet-popup-tip{background:rgba(12,28,44,.97)!important;}
.leaflet-popup-close-button{color:#7A9EB0!important;top:8px!important;right:10px!important;}
.pp-title{font-size:14px;font-weight:800;color:#FFF;margin-bottom:3px;}
.pp-coord{font-size:10px;color:#5A7A8E;margin-bottom:10px;font-family:monospace;}
.pp-badge{display:inline-block;padding:4px 14px;border-radius:7px;
  font-size:12px;font-weight:800;margin:4px 0 8px;}
.pp-row{display:flex;justify-content:space-between;margin:5px 0;
  font-size:12px;color:#9AACB8;}
.pp-val{font-weight:700;color:#FFF;}
.pp-div{border:none;border-top:1px solid rgba(255,255,255,.08);margin:8px 0;}
.pp-time{font-size:10px;color:#5A7A8E;margin-top:6px;}
.pp-btn{width:100%;margin-top:10px;padding:8px;
  background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.4);
  border-radius:8px;color:#C9A84C;font-size:11px;font-weight:700;
  cursor:pointer;letter-spacing:1px;text-transform:uppercase;}
.pp-btn:hover{background:rgba(201,168,76,.3);}
.leaflet-tooltip{background:rgba(10,22,35,.9)!important;
  border:1px solid rgba(201,168,76,.3)!important;color:#D0DCE4!important;
  border-radius:8px!important;font-size:11px;padding:4px 10px;}
.leaflet-tooltip-top::before{border-top-color:rgba(201,168,76,.3)!important;}
#legend{position:absolute;bottom:20px;right:14px;
  background:rgba(10,22,35,.92);border-radius:10px;padding:12px 16px;
  z-index:1000;border:1px solid rgba(201,168,76,.2);}
.leg-ttl{font-size:9px;font-weight:800;letter-spacing:2px;color:#C9A84C;
  text-transform:uppercase;margin-bottom:9px;}
.leg-row{display:flex;align-items:center;gap:8px;margin:5px 0;
  font-size:11px;color:#9AACB8;}
.leg-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;
  border:2px solid rgba(255,255,255,.2);}
@keyframes mPulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(2.4);opacity:0}}
</style>
</head>
<body>
<div id="topbar">
  <div id="live-dot"></div>
  <span id="topbar-title">📡 Peta Pemantauan Keramaian</span>
  <span id="cnt-badge">0 titik aktif</span>
  <span id="no-data-msg">Jalankan analisis untuk melihat data real-time</span>
</div>
<div id="map"></div>
<div id="leaflet-err">🗺️ Peta tidak dapat dimuat<br>
  <span style="font-size:11px">Pastikan koneksi internet aktif</span></div>
<div id="legend">
  <div class="leg-ttl">Level Keramaian</div>
  <div class="leg-row"><div class="leg-dot" style="background:#D94040"></div>TINGGI</div>
  <div class="leg-row"><div class="leg-dot" style="background:#C9A84C"></div>SEDANG</div>
  <div class="leg-row"><div class="leg-dot" style="background:#2ECC71"></div>RENDAH</div>
  <div class="leg-row"><div class="leg-dot" style="background:#3A7EA8"></div>Memulai...</div>
</div>
<script>
'use strict';

if(typeof L==='undefined'){
  document.getElementById('leaflet-err').style.display='block';
  document.getElementById('map').style.display='none';
  document.getElementById('legend').style.display='none';
}

var _map=null,_ready=false,_pts={},_selPid=null,_expiryTimer=null;
var _queue=[];

function _init(){
  if(typeof L==='undefined')return;
  try{
    _map=L.map('map',{center:[21.4225,39.8262],zoom:15,zoomControl:true});
    _map.zoomControl.setPosition('bottomleft');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(_map);
    _ready=true;
    _expiryTimer=setInterval(_checkExpiry,30000);
    window._CROWDMAP.flushQueue();
  }catch(e){
    document.getElementById('leaflet-err').style.display='block';
    document.getElementById('leaflet-err').innerHTML='🗺️ Error: '+e.message;
  }
}
document.addEventListener('DOMContentLoaded',_init);

// ── Helpers ───────────────────────────────────────────────────────────────────
function _color(l){
  if(!l)return'#3A7EA8';
  switch(l.toUpperCase()){
    case'TINGGI':return'#D94040';case'SEDANG':return'#C9A84C';
    case'RENDAH':return'#2ECC71';default:return'#3A7EA8';
  }
}
function _mvColor(l){
  if(!l)return'#D0DCE4';
  switch(l.toUpperCase()){
    case'BOTTLENECK':return'#E05050';
    case'TERSENDAT': return'#C9A84C';
    case'LANCAR':    return'#2ECC71';
    default:return'#D0DCE4';
  }
}
function _emoji(l){
  if(!l)return'📍';
  switch(l.toUpperCase()){
    case'TINGGI':return'🔴';case'SEDANG':return'🟡';
    case'RENDAH':return'🟢';default:return'📍';
  }
}
function _status(l){
  if(!l)return'—';
  switch(l.toUpperCase()){
    case'TINGGI':return'⚠ Perlu Perhatian';
    case'SEDANG':return'👁 Pantau';
    case'RENDAH':return'✓ Aman';
    default:return l;
  }
}
function _icon(color,sel){
  var ring=sel
    ?'<div style="position:absolute;top:-9px;left:-9px;width:54px;height:54px;'+
     'border-radius:50%;border:2.5px solid '+color+';opacity:.5;'+
     'animation:mPulse 2s infinite;pointer-events:none;"></div>':'';
  var shadow=sel
    ?'0 0 0 4px '+color+'44,0 4px 16px rgba(0,0,0,.6)'
    :'0 3px 10px rgba(0,0,0,.5)';
  return L.divIcon({
    html:'<div style="position:relative;width:36px;height:36px;">'+ring+
      '<div style="width:36px;height:36px;border-radius:50%;background:'+color+';'+
      'border:3px solid rgba(255,255,255,.9);display:flex;align-items:center;'+
      'justify-content:center;font-size:15px;box-shadow:'+shadow+';'+
      'transition:box-shadow .3s;">📡</div></div>',
    iconSize:[36,36],iconAnchor:[18,18],className:''
  });
}

function _popup(d,pid){
  var c=_color(d.crowd),e=_emoji(d.crowd);
  // Nama dari d.name — sudah di-resolve di Python, tidak ada fallback generik di sini
  var nm=d.name&&d.name.trim()?d.name:pid;
  return'<div style="padding:4px 2px;">'+
    '<div class="pp-title">'+nm+'</div>'+
    '<div class="pp-coord">📍 '+
      parseFloat(d.lat).toFixed(5)+', '+parseFloat(d.lon).toFixed(5)+
    '</div>'+
    '<div class="pp-badge" style="background:'+c+'22;border:1.5px solid '+c+';color:'+c+';">'+
      e+' '+(d.crowd||'Memulai...')+
    '</div>'+
    '<hr class="pp-div"/>'+
    '<div class="pp-row"><span>Status</span><span class="pp-val">'+_status(d.crowd)+'</span></div>'+
    '<div class="pp-row"><span>Jumlah Orang</span><span class="pp-val">'+(d.count||'—')+'</span></div>'+
    '<div class="pp-row"><span>Arus</span><span class="pp-val" style="color:'+_mvColor(d.movement)+'">'+(d.movement||'—')+'</span></div>'+
    '<div class="pp-row"><span>Slow Ratio</span><span class="pp-val">'+(d.slow||'—')+'</span></div>'+
    '<div class="pp-row"><span>BN Ratio</span><span class="pp-val">'+(d.bnratio||'—')+'</span></div>'+
    '<div class="pp-time">⏱ '+(d.timeStr||'—')+'</div>'+
    // ▼ SATU-SATUNYA jalur untuk trigger select/dashboard.
    // Klik marker biasa TIDAK memanggil _selectFromJS.
    '<button class="pp-btn" onclick="_selectFromJS(\''+pid+'\')">📊 Lihat di Dashboard</button>'+
    '</div>';
}

function _updateTopbar(){
  var n=Object.keys(_pts).length;
  document.getElementById('cnt-badge').textContent=n+' titik aktif';
  document.getElementById('live-dot').className=n>0?'on':'';
  var msg=document.getElementById('no-data-msg');
  if(msg)msg.style.display=n>0?'none':'block';
}

// ── INTI FLOW v4.4 ────────────────────────────────────────────────────────────
// _selectFromJS: HANYA dipanggil dari tombol "Lihat di Dashboard" di popup.
// Klik marker biasa tidak memanggil fungsi ini.
// Leaflet default (bindPopup tanpa custom click handler) sudah cukup untuk
// membuka popup saat marker diklik.
function _selectFromJS(pid){
  _selPid=pid;
  // Update visual highlight semua marker
  window._CROWDMAP.highlightPoint(pid);
  // Kirim sinyal ke Python — ini yang trigger switch tab + switch dashboard
  console.log('__SELECT__:'+pid);
}

// ── API Publik ────────────────────────────────────────────────────────────────
window._CROWDMAP={

  flushQueue:function(){
    if(!_ready)return;
    var q=_queue.splice(0);
    q.forEach(function(d){window._CROWDMAP._place(d);});
    _updateTopbar();
  },

  updatePoint:function(dataJson){
    var d;
    try{
      d=typeof dataJson==='string'?JSON.parse(dataJson):dataJson;
    }catch(e){
      console.error('[CrowdMap] JSON parse error:',e,dataJson);
      return false;
    }
    if(!_ready){_queue.push(d);return false;}
    return window._CROWDMAP._place(d);
  },

  _place:function(d){
    try{
      var pid=d.pointId||(parseFloat(d.lat).toFixed(5)+'_'+parseFloat(d.lon).toFixed(5));
      var c=_color(d.crowd);
      var isSel=(pid===_selPid);
      var nm=d.name&&d.name.trim()?d.name:pid;

      if(_pts[pid]){
        var p=_pts[pid];
        p.data=d;
        p.lastUpdate=Date.now();
        p.marker.setLatLng([d.lat,d.lon]);
        p.marker.setIcon(_icon(c,isSel));
        p.marker.setTooltipContent('<b>'+nm+'</b> · '+(d.crowd||'—'));
        // Update popup content hanya kalau popup sedang terbuka
        if(p.popupOpen){
          p.marker.setPopupContent(_popup(d,pid));
        }
        if(p.circle){_map.removeLayer(p.circle);p.circle=null;}
      }else{
        // ── KUNCI UX v4.4 ──────────────────────────────────────────────────
        // Marker hanya di-bind popup dan tooltip.
        // TIDAK ada mk.on('click') custom handler.
        // Leaflet default: klik marker → buka popup (dan hanya itu).
        // _selectFromJS hanya dipanggil dari tombol di dalam popup.
        // ───────────────────────────────────────────────────────────────────
        var mk=L.marker([d.lat,d.lon],{icon:_icon(c,isSel)});
        mk.bindTooltip('<b>'+nm+'</b> · '+(d.crowd||'—'),
          {permanent:false,direction:'top',offset:[0,-22]});
        mk.bindPopup(_popup(d,pid),{maxWidth:260,closeButton:true});

        // Track popup open/close state untuk update konten live
        var curPid=pid;
        mk.on('popupopen',function(){
          if(_pts[curPid])_pts[curPid].popupOpen=true;
        });
        mk.on('popupclose',function(){
          if(_pts[curPid])_pts[curPid].popupOpen=false;
        });

        mk.addTo(_map);
        _pts[pid]={marker:mk,circle:null,data:d,lastUpdate:Date.now(),popupOpen:false};

        if(Object.keys(_pts).length===1){
          _map.setView([d.lat,d.lon],16,{animate:true});
        }
      }

      var r=d.crowd==='TINGGI'?90:d.crowd==='SEDANG'?60:38;
      var ci=L.circle([d.lat,d.lon],{
        radius:r,color:c,fillColor:c,
        fillOpacity:.08,weight:1.5,
        dashArray:d.crowd==='TINGGI'?'5,5':null
      });
      ci.addTo(_map);
      _pts[pid].circle=ci;

      _updateTopbar();
      return true;
    }catch(e){
      console.error('[CrowdMap] _place error:',e);
      return false;
    }
  },

  removePoint:function(pid){
    if(!_pts[pid])return;
    if(_pts[pid].marker)_map.removeLayer(_pts[pid].marker);
    if(_pts[pid].circle)_map.removeLayer(_pts[pid].circle);
    delete _pts[pid];
    // Clear selected state kalau titik yang dihapus adalah yang dipilih
    if(_selPid===pid)_selPid=null;
    _updateTopbar();
  },

  resetAll:function(){
    if(_expiryTimer){clearInterval(_expiryTimer);_expiryTimer=null;}
    Object.keys(_pts).forEach(function(pid){
      if(_pts[pid].marker)_map.removeLayer(_pts[pid].marker);
      if(_pts[pid].circle)_map.removeLayer(_pts[pid].circle);
    });
    _pts={};_selPid=null;_queue=[];
    _updateTopbar();
    if(_ready){_expiryTimer=setInterval(_checkExpiry,30000);}
  },

  flyTo:function(lat,lon,zoom){
    if(!_ready)return;
    _map.flyTo([lat,lon],zoom||15,{animate:true,duration:1.0});
  },

  flyToPoint:function(pid){
    if(!_ready||!_pts[pid])return;
    var d=_pts[pid].data;
    _map.flyTo([d.lat,d.lon],17,{animate:true,duration:1.0});
    // Buka popup tapi TIDAK trigger select
    _pts[pid].marker.openPopup();
  },

  // Highlight visual saja — tidak trigger select/dashboard
  highlightPoint:function(pid){
    if(!_pts[pid])return;
    _selPid=pid;
    Object.keys(_pts).forEach(function(p){
      var col=_color(_pts[p].data?_pts[p].data.crowd:null);
      _pts[p].marker.setIcon(_icon(col,p===pid));
    });
  },

  getCount:function(){return Object.keys(_pts).length;}
};

// ── Auto-expiry 5 menit ────────────────────────────────────────────────────────
function _checkExpiry(){
  if(!_ready)return;
  var now=Date.now();
  Object.keys(_pts).forEach(function(pid){
    if(pid===_selPid)return; // jangan hapus titik yang sedang dipilih
    if(now-_pts[pid].lastUpdate>300000){
      window._CROWDMAP.removePoint(pid);
    }
  });
}
</script>
</body>
</html>"""


if WEB_ENGINE_AVAILABLE:
    class HalamanPeta(QWebEnginePage):
        point_selected_signal = pyqtSignal(str)

        def javaScriptConsoleMessage(self, level, message, line, source):
            if message.startswith("__SELECT__:"):
                pid = message[len("__SELECT__:"):]
                if pid:
                    self.point_selected_signal.emit(pid)

class WidgetPetaPemantauan(QWidget):

    point_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("monitor_map_container")
        self._page_ready = False
        self._pending_js: list[str] = []
        self._point_store: dict[str, dict] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if WEB_ENGINE_AVAILABLE:
            self._page = HalamanPeta()
            self._page.point_selected_signal.connect(self._on_js_select)
            self._view = QWebEngineView()
            self._view.setPage(self._page)
            self._view.loadFinished.connect(self._on_load_finished)
            self._view.setHtml(MONITOR_MAP_HTML, QUrl("about:blank"))
            root.addWidget(self._view, 1)
        else:
            self._build_fallback(root)

    def _on_load_finished(self, ok: bool):
        if ok:
            self._page_ready = True
            pending = list(self._pending_js)
            self._pending_js.clear()
            for js in pending:
                self._view.page().runJavaScript(js)
            # Replay titik dari store (recovery setelah page reload)
            if self._point_store:
                for pid, data in self._point_store.items():
                    inner = json.dumps(data)
                    self._view.page().runJavaScript(
                        f"window._CROWDMAP.updatePoint({json.dumps(inner)});"
                    )
        else:
            self._page_ready = False
            QTimer.singleShot(2000, lambda: self._view.setHtml(
                MONITOR_MAP_HTML, QUrl("about:blank")
            ))

    def _on_js_select(self, pid: str):
        self.point_selected.emit(pid)

    def _run_js(self, js: str):
        if not WEB_ENGINE_AVAILABLE:
            return
        if self._page_ready:
            self._view.page().runJavaScript(js)
        else:
            self._pending_js.append(js)

    def _build_fallback(self, layout):
        fb = QWidget()
        fb.setStyleSheet("background:#0F1F2E;")
        fl = QVBoxLayout(fb)
        fl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.setSpacing(20)
        ic = QLabel("🗺️")
        ic.setStyleSheet("font-size:64px;")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt = QLabel(
            "Peta monitoring memerlukan PyQt6-WebEngine.\n\n"
            "pip install PyQt6-WebEngine\n\n"
            "Restart aplikasi untuk mengaktifkan peta."
        )
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet(
            "color:#7A9EB0;font-size:13px;line-height:1.7;"
            "background:#162A3B;border-radius:14px;padding:28px 36px;"
            "border:1px solid rgba(201,168,76,.2);"
        )
        fl.addWidget(ic)
        fl.addWidget(txt)
        layout.addWidget(fb, 1)

    def perbarui_dengan_window(self, row: dict, loc_counter: int = 0):

        lat = float(row.get("lat") or 21.4225)
        lon = float(row.get("lon") or 39.8262)
        pid = f"{lat:.5f}_{lon:.5f}"
        name = str(row.get("lokasi") or "").strip() or pid

        data = {
            "pointId":  pid,
            "lat":      lat,
            "lon":      lon,
            "name":     name,
            "crowd":    str(row.get("label_crowd") or ""),
            "movement": str(row.get("label_movement_3") or row.get("label_movement") or ""),
            "count":    f"{float(row.get('count_avg') or 0):.1f}",
            "slow":     f"{float(row.get('slow_ratio') or 0):.3f}",
            "bnratio":  f"{float(row.get('bottleneck_ratio') or 0):.3f}",
            "timeStr":  (
                f"Window #{row.get('window_k', 0)} · "
                f"t={float(row.get('window_start', 0)):.1f}s"
            ),
        }

        self._point_store[pid] = data
        inner = json.dumps(data)
        self._run_js(f"window._CROWDMAP.updatePoint({json.dumps(inner)});")

    def menuju_lokasi(self, lat: float, lon: float):
        self._run_js(f"window._CROWDMAP.flyTo({lat},{lon},15);")

    def menuju_titik(self, pid: str):
        self._run_js(f"window._CROWDMAP.flyToPoint({json.dumps(pid)});")

    def highlight_point(self, pid: str):
        self._run_js(f"window._CROWDMAP.highlightPoint({json.dumps(pid)});")

    def reset_semua(self):
        self._point_store.clear()
        self._run_js("window._CROWDMAP.resetAll();")


class KartuMetrik(QWidget):
    def __init__(self, icon, label, unit="", parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._prev_val = None
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)
        icon_bg = QWidget()
        icon_bg.setObjectName("card_icon_bg")
        icon_bg.setFixedSize(44, 44)
        ib = QHBoxLayout(icon_bg)
        ib.setContentsMargins(0, 0, 0, 0)
        il = QLabel(icon)
        il.setObjectName("card_icon_lbl")
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ib.addWidget(il)
        root.addWidget(icon_bg, alignment=Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label.upper())
        lbl.setObjectName("card_label")
        self._val = QLabel("—")
        self._val.setObjectName("card_value")
        br = QHBoxLayout()
        br.setSpacing(6)
        self._unit = QLabel(unit)
        self._unit.setObjectName("card_unit")
        self._trend = QLabel("")
        self._trend.setObjectName("card_trend_flat")
        br.addWidget(self._unit)
        br.addWidget(self._trend)
        br.addStretch()
        col.addWidget(lbl)
        col.addWidget(self._val)
        col.addLayout(br)
        root.addLayout(col, 1)

    def atur_nilai(self, val, fmt=None):
        if val is None or val == "":
            self._val.setText("—")
            self._trend.setText("")
            return
        if self._prev_val is not None and isinstance(val, (int, float)):
            diff = val - self._prev_val
            if abs(diff) > 0.01:
                self._trend.setObjectName("card_trend_up" if diff > 0 else "card_trend_down")
                self._trend.setText(f"▲ +{diff:.1f}" if diff > 0 else f"▼ {diff:.1f}")
            else:
                self._trend.setObjectName("card_trend_flat")
                self._trend.setText("→")
            self._trend.setStyle(self._trend.style())
        self._prev_val = val if isinstance(val, (int, float)) else None
        self._val.setText(
            fmt if fmt else (f"{val:.2f}" if isinstance(val, float) else str(val))
        )

    def reset(self):
        self._prev_val = None
        self._val.setText("—")
        self._trend.setText("")


class StripPeringatan(QWidget):
    _CFG = {
        "TINGGI": ("alert_strip_high",   "🚨 Keramaian TINGGI — Pemantauan intensif diperlukan"),
        "SEDANG": ("alert_strip_medium", "⚠️ Keramaian SEDANG — Kondisi normal, tetap pantau"),
        "RENDAH": ("alert_strip_low",    "✅ Keramaian RENDAH — Area aman dan lancar"),
        "":       ("alert_strip_low",    ""),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self._strip = QWidget()
        self._strip.setObjectName("alert_strip_low")
        sl = QHBoxLayout(self._strip)
        sl.setContentsMargins(16, 8, 16, 8)
        self._txt = QLabel("")
        self._txt.setObjectName("alert_strip_text")
        sl.addWidget(self._txt)
        l.addWidget(self._strip)
        self.setVisible(False)

    def atur_keramaian(self, crowd: str):
        crowd = (crowd or "").upper()
        obj, msg = self._CFG.get(crowd, self._CFG[""])
        if not msg:
            self.setVisible(False)
            return
        self._strip.setObjectName(obj)
        self._strip.style().unpolish(self._strip)
        self._strip.style().polish(self._strip)
        self._txt.setText(msg)
        self.setVisible(True)

    def reset(self):
        self.setVisible(False)


_CI = {"TINGGI": "🔴", "SEDANG": "🟡", "RENDAH": "🟢"}
_CD = {
    "TINGGI":    "Keramaian tinggi - perlu dipantau",
    "SEDANG":    "Keramaian sedang - kondisi normal",
    "RENDAH":    "Keramaian rendah - aman & lancar",
    "TERSENDAT": "Pergerakan tersendat - ada penumpukan",
    "LANCAR":    "Pergerakan lancar - tidak ada hambatan",
}
_CBM = {
    "TINGGI": "badge_high", "SEDANG": "badge_medium", "RENDAH": "badge_low",
    "TERSENDAT": "badge_tersendat", "LANCAR": "badge_lancar",
}

class LencanaLabel(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("crowd_badge_container")
        r = QVBoxLayout(self)
        r.setContentsMargins(16, 14, 16, 14)
        r.setSpacing(8)
        t = QLabel(title.upper())
        t.setObjectName("crowd_badge_title")
        r.addWidget(t)
        self._badge = QLabel("—")
        self._badge.setObjectName("badge_neutral")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setMinimumHeight(44)
        r.addWidget(self._badge)
        self._desc = QLabel("")
        self._desc.setStyleSheet("color:#9AA5AE;font-size:11px;")
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setWordWrap(True)
        r.addWidget(self._desc)

    def atur_label(self, label: str):
        label = (label or "").upper()
        icon = _CI.get(label, "")
        self._badge.setObjectName(_CBM.get(label, "badge_neutral"))
        self._badge.setText(f"{icon} {label}" if icon else (label or "—"))
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._badge.update()
        self._desc.setText(_CD.get(label, ""))

    def reset(self):
        self._badge.setObjectName("badge_neutral")
        self._badge.setText("—")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._badge.update()
        self._desc.setText("")


# panel dashboard
class PanelDashboard(QWidget):

    TABLE_COLS = [
        ("Window #",      "window_k",         None),
        ("Mulai (s)",     "window_start",     ".1f"),
        ("Selesai (s)",   "window_end",       ".1f"),
        ("Jml Orang",     "count_avg",        ".1f"),
        ("Slow Ratio",    "slow_ratio",       ".3f"),
        ("BN Ratio",      "bottleneck_ratio", ".3f"),
        ("Keramaian",     "label_crowd",      None),
        ("Arus",          "label_movement_3", None),
        ("Lokasi",        "lokasi",           None),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("content_area")
        self._pts: dict[str, dict] = {}
        self._active: str | None = None
        self._out_paths: dict = {}
        self._loc_counter: int = 0
        self._default_loc_name: str = ""
        self._name_usage: dict[str, int] = {}
        self._bangun_ui()

    def _bangun_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget()
        hdr.setObjectName("content_header")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(24, 14, 24, 12)
        hl.setSpacing(4)

        tr = QHBoxLayout()
        tl = QLabel("Dashboard Pemantauan")
        tl.setObjectName("content_title")
        tr.addWidget(tl)
        tr.addStretch()
        self._live = QLabel("● LIVE")
        self._live.setStyleSheet(
            "color:#3ABF90;font-size:11px;font-weight:700;"
            "letter-spacing:1px;background:#F0FDF8;"
            "border:1.5px solid #86EFCA;border-radius:20px;padding:3px 12px;"
        )
        self._live.setVisible(False)
        tr.addWidget(self._live)
        hl.addLayout(tr)

        self._ind = QLabel("Pilih titik di peta → detail analitik tampil di sini")
        self._ind.setObjectName("content_subtitle")
        hl.addWidget(self._ind)

        sel_cont = QWidget()
        self._sel_row = QHBoxLayout(sel_cont)
        self._sel_row.setContentsMargins(0, 4, 0, 0)
        self._sel_row.setSpacing(6)
        self._sel_row.addStretch()
        hl.addWidget(sel_cont)
        root.addWidget(hdr)

        self._stack = QStackedWidget()

        empty = QWidget()
        empty.setObjectName("empty_state")
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setContentsMargins(40, 40, 40, 40)
        el.setSpacing(12)
        for txt, obj in [("📊", "empty_icon"),
                         ("Belum ada data titik aktif", "empty_title"),
                         ("Jalankan analisis video,\nlalu klik titik di peta untuk melihat detail.", "empty_desc")]:
            lb = QLabel(txt)
            lb.setObjectName(obj)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.addWidget(lb)
        self._stack.addWidget(empty)

        cp = QWidget()
        cp.setObjectName("content_area")
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        inn = QWidget()
        inn.setObjectName("content_area")
        rl = QVBoxLayout(inn)
        rl.setContentsMargins(24, 20, 24, 20)
        rl.setSpacing(14)

        self._alert = StripPeringatan()
        rl.addWidget(self._alert)

        cg = QGridLayout()
        cg.setSpacing(12)
        self._c_count = KartuMetrik("👥", "Jumlah Orang",      "orang / window")
        self._c_slow  = KartuMetrik("🚶", "Slow Ratio",        "proporsi lambat")
        cg.addWidget(self._c_count, 0, 0)
        cg.addWidget(self._c_slow,  0, 1)
        rl.addLayout(cg)

        brow = QHBoxLayout()
        brow.setSpacing(12)
        self._b_crowd = LencanaLabel("Tingkat Keramaian")
        self._b_move  = LencanaLabel("Kondisi Pergerakan")
        brow.addWidget(self._b_crowd)
        brow.addWidget(self._b_move)
        rl.addLayout(brow)

        self._itabs = QTabWidget()
        t1 = QWidget()
        t1l = QVBoxLayout(t1)
        t1l.setContentsMargins(0, 8, 0, 0)
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(len(self.TABLE_COLS))
        self._tbl.setHorizontalHeaderLabels([c[0] for c in self.TABLE_COLS])
        self._tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setMinimumHeight(200)
        t1l.addWidget(self._tbl)
        self._itabs.addTab(t1, "📋 Data Window")

        rl.addWidget(self._itabs, 1)

        out = QWidget()
        out.setStyleSheet(
            "background:#FFF;border-radius:12px;border:1.5px solid #EAE6DE;")
        ol = QVBoxLayout(out)
        ol.setContentsMargins(18, 16, 18, 16)
        ol.setSpacing(10)
        oh = QHBoxLayout()
        ot = QLabel("📁 File Output")
        ot.setStyleSheet("font-size:13px;font-weight:700;color:#1A2B38;")
        oh.addWidget(ot)
        oh.addStretch()
        oh2 = QLabel("Tersimpan ke folder outputs/")
        oh2.setStyleSheet("color:#9AA5AE;font-size:11px;")
        oh.addWidget(oh2)
        ol.addLayout(oh)
        ob = QHBoxLayout()
        ob.setSpacing(8)
        self._bw = QPushButton("📊 window_*.csv")
        self._bf = QPushButton("📋 frame_*.csv")
        self._bm = QPushButton("{} meta_*.json")
        for btn in (self._bw, self._bf, self._bm):
            btn.setObjectName("btn_output")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            btn.setMinimumHeight(40)
            ob.addWidget(btn)
        ol.addLayout(ob)
        self._bw.clicked.connect(lambda: self._open("out_window"))
        self._bf.clicked.connect(lambda: self._open("out_frame"))
        self._bm.clicked.connect(lambda: self._open("out_meta"))
        rl.addWidget(out)

        sc.setWidget(inn)
        cpl = QVBoxLayout(cp)
        cpl.setContentsMargins(0, 0, 0, 0)
        cpl.addWidget(sc)
        self._stack.addWidget(cp)
        root.addWidget(self._stack, 1)

    def atur_nama_lokasi_default(self, name: str):

        self._default_loc_name = name.strip()

    def _assign_name(self, row: dict) -> str:

        self._loc_counter += 1
        base = _resolve_name(row, self._default_loc_name, self._loc_counter)

        if base not in self._name_usage:
            self._name_usage[base] = 1
            return base
        else:
            self._name_usage[base] += 1
            return f"{base} {self._name_usage[base]}"

    def terima_window(self, row: dict) -> str:
        """
        Terima data window baru dari pipeline.
        Return nama final yang dipakai (untuk sinkron ke WidgetPetaPemantauan via PanelHasil).
        """
        lat = float(row.get("lat") or 21.4225)
        lon = float(row.get("lon") or 39.8262)
        pid = f"{lat:.5f}_{lon:.5f}"

        if pid not in self._pts:
            name = self._assign_name(row)
            self._pts[pid] = {
                "rows": [], "last_row": {}, "name": name,
                "counter": self._loc_counter
            }
            self._rebuild_sel()
        else:

            existing_name = self._pts[pid]["name"]
            new_base = _resolve_name(row, self._default_loc_name, self._pts[pid]["counter"])
            if (existing_name.startswith("Lokasi #")
                    and new_base
                    and not new_base.startswith("Lokasi #")):
                self._pts[pid]["name"] = new_base
                self._rebuild_sel()

        rows = self._pts[pid]["rows"]
        rows.append(row)
        if len(rows) > MAKS_BARIS:
            rows.pop(0)
        self._pts[pid]["last_row"] = row

        if self._active is None:
            self._active = pid
            self._rebuild_sel()

        if pid == self._active:
            self._render(row, silent=False)
            if self._stack.currentIndex() == 0:
                self._stack.setCurrentIndex(1)
            self._live.setVisible(True)
            self._update_indicator(row, self._pts[pid]["name"])

        return self._pts[pid]["name"]

    def tampilkan_titik(self, pid: str):
        """
        Tampilkan data titik tertentu.
        Dipanggil dari:
          - PanelHasil._on_point_selected (saat tombol popup diklik)
          - Tombol selector di header dashboard
        """
        if pid not in self._pts:
            return

        self._active = pid
        d = self._pts[pid]
        name = d["name"]

        self._ind.setText(f"📍 {name}  ·  {len(d['rows'])} window data")
        self._rebuild_sel()

        self._tbl.setRowCount(0)

        for c in (self._c_count, self._c_slow):
            c.reset()
        self._b_crowd.reset()
        self._b_move.reset()
        self._alert.reset()

        for r in d["rows"]:
            self._render(r, silent=True)

        if d["last_row"]:
            self._render(d["last_row"], silent=False)
            self._update_indicator(d["last_row"], name)

        if d["rows"]:
            self._stack.setCurrentIndex(1)
            self._live.setVisible(bool(d["rows"]))

    def _render(self, row: dict, silent: bool = False):
        if not silent:
            self._c_count.atur_nilai(row.get("count_avg"), f"{row.get('count_avg', 0):.1f}")
            self._c_slow.atur_nilai(row.get("slow_ratio"),  f"{row.get('slow_ratio', 0):.3f}")
            crowd = row.get("label_crowd", "")
            self._b_crowd.atur_label(crowd)
            self._b_move.atur_label(row.get("label_movement_3", row.get("label_movement", "")))
            self._alert.atur_keramaian(crowd)

        r = self._tbl.rowCount()
        self._tbl.insertRow(r)
        for ci, (_, key, fmt) in enumerate(self.TABLE_COLS):
            val = row.get(key, "")
            text = f"{val:{fmt}}" if fmt and isinstance(val, (int, float)) else str(val)
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if key == "label_crowd":
                c = {"TINGGI": "#C02020", "SEDANG": "#986010",
                     "RENDAH": "#1A7A50"}.get(str(val), "#9AA5AE")
                item.setForeground(QColor(c))
                f2 = item.font()
                f2.setBold(True)
                item.setFont(f2)
            elif key == "label_movement_3":
                c = {
                    "BOTTLENECK": "#C02020",
                    "TERSENDAT":  "#C08020",
                    "LANCAR":     "#1A7A50",
                }.get(str(val), "#9AA5AE")
                item.setForeground(QColor(c))
                f2 = item.font()
                f2.setBold(True)
                item.setFont(f2)
            elif key == "label_movement":
                item.setForeground(QColor(
                    "#C02020" if val == "TERSENDAT" else "#1A7A50"
                ))
            self._tbl.setItem(r, ci, item)

        if not silent:
            self._tbl.scrollToBottom()

    def _update_indicator(self, row: dict, name: str):
        wk = row.get("window_k", 0)
        ws = row.get("window_start", 0)
        we = row.get("window_end", 0)
        cnt = row.get("count_avg", 0)
        self._ind.setText(
            f"📍 {name}  ·  Window #{wk}  ·  {ws:.1f}–{we:.1f}s  ·  {cnt:.1f} orang"
        )

    def _rebuild_sel(self):
        while self._sel_row.count():
            item = self._sel_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for pid, data in self._pts.items():
            is_a = (pid == self._active)
            btn = QPushButton(f"📍 {data['name']}")
            btn.setCheckable(True)
            btn.setChecked(is_a)
            btn.setObjectName(
                "point_selector_btn_active" if is_a else "point_selector_btn"
            )
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, p=pid: self.tampilkan_titik(p))
            self._sel_row.addWidget(btn)
        self._sel_row.addStretch()

    def atur_jalur_output(self, paths: dict):
        self._out_paths = paths
        self._live.setVisible(False)
        self._bw.setEnabled(bool(paths.get("out_window")))
        self._bf.setEnabled(bool(paths.get("out_frame")))
        self._bm.setEnabled(bool(paths.get("out_meta")))

    def _open(self, key: str):
        path = self._out_paths.get(key, "")
        if path and os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])

    def reset_semua(self):
        self._pts = {}
        self._active = None
        self._loc_counter = 0
        self._name_usage = {}

        self._tbl.setRowCount(0)

        self._alert.reset()
        self._live.setVisible(False)
        for c in (self._c_count, self._c_slow):
            c.reset()
        self._b_crowd.reset()
        self._b_move.reset()
        self._ind.setText("Pilih titik di peta → detail analitik tampil di sini")
        self._stack.setCurrentIndex(0)
        self._out_paths = {}
        for btn in (self._bw, self._bf, self._bm):
            btn.setEnabled(False)
        self._rebuild_sel()


# panel results
class PanelHasil(QWidget):

    point_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("content_area")
        self._bangun_ui()

    def _bangun_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._main_tabs = QTabWidget()
        self._main_tabs.setObjectName("main_tab_widget")

        self._map_widget = WidgetPetaPemantauan()
        self._map_widget.point_selected.connect(self._on_point_selected)
        self._main_tabs.addTab(self._map_widget, "🗺️  Peta Pemantauan")

        self._dashboard = PanelDashboard()
        self._main_tabs.addTab(self._dashboard, "📊  Dashboard Pemantauan")

        self._main_tabs.setCurrentIndex(0)
        root.addWidget(self._main_tabs, 1)

    def _on_point_selected(self, pid: str):

        self._dashboard.tampilkan_titik(pid)
        self._main_tabs.setCurrentIndex(1)
        self.point_selected.emit(pid)

    def atur_lokasi(self, lat: float, lon: float, name: str):

        self._map_widget.menuju_lokasi(lat, lon)
        self._dashboard.atur_nama_lokasi_default(name)

    def perbarui_dengan_window(self, row: dict):

        resolved_name = self._dashboard.terima_window(row)

        row_with_name = dict(row)
        row_with_name["lokasi"] = resolved_name

        self._map_widget.perbarui_dengan_window(row_with_name, self._dashboard._loc_counter)

    def tampilkan_dashboard_titik(self, pid: str):
        """Sinkronisasi eksternal dari JendelaUtama agar tidak switch tab"""
        self._dashboard.tampilkan_titik(pid)

    def atur_jalur_output(self, result: dict):
        self._dashboard.atur_jalur_output(result)

    def clear(self):
        """Reset untuk run baru"""
        self._map_widget.reset_semua()
        self._dashboard.reset_semua()
        self._main_tabs.setCurrentIndex(0)