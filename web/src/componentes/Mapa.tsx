import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import icono from 'leaflet/dist/images/marker-icon.png'
import icono2x from 'leaflet/dist/images/marker-icon-2x.png'
import sombra from 'leaflet/dist/images/marker-shadow.png'
import { useEffect, type ReactNode } from 'react'
import { LayersControl, MapContainer, Marker, Polygon, Polyline, TileLayer, useMap, useMapEvents } from 'react-leaflet'

// Con un empaquetador, Leaflet no encuentra sus íconos por defecto.
L.Icon.Default.mergeOptions({ iconUrl: icono, iconRetinaUrl: icono2x, shadowUrl: sombra })

export type LatLng = [number, number]

const CENTRO_DEFECTO: LatLng = [25.6866, -100.3161] // Monterrey

export function Mapa({ children, encuadre, alto = 420 }: { children?: ReactNode; encuadre?: LatLng[]; alto?: number | string }) {
  return (
    <MapContainer center={CENTRO_DEFECTO} zoom={14} style={{ height: alto }} className="mapa">
      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="Satélite">
          <TileLayer
            attribution="Imágenes &copy; Esri"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={20}
            maxNativeZoom={19}
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Calles">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={20}
            maxNativeZoom={19}
          />
        </LayersControl.BaseLayer>
      </LayersControl>
      <Encuadrar puntos={encuadre} />
      {children}
    </MapContainer>
  )
}

function Encuadrar({ puntos }: { puntos?: LatLng[] }) {
  const map = useMap()
  const clave = JSON.stringify(puntos ?? [])
  useEffect(() => {
    if (puntos && puntos.length) map.fitBounds(L.latLngBounds(puntos), { padding: [30, 30], maxZoom: 18, animate: false })
  }, [clave, map])
  return null
}

const iconoVertice = L.divIcon({ className: 'vertice', iconSize: [14, 14] })

/** Editor de polígono: clic en el mapa agrega un vértice; los vértices se pueden arrastrar. */
export function EditorPoligono({ vertices, onCambio }: { vertices: LatLng[]; onCambio: (v: LatLng[]) => void }) {
  useMapEvents({
    click(e) {
      onCambio([...vertices, [e.latlng.lat, e.latlng.lng]])
    },
  })
  return (
    <>
      {vertices.length >= 3 ? (
        <Polygon positions={vertices} pathOptions={{ color: '#f59e0b', weight: 3 }} />
      ) : (
        <Polyline positions={vertices} pathOptions={{ color: '#f59e0b', weight: 3 }} />
      )}
      {vertices.map((v, i) => (
        <Marker
          key={i}
          position={v}
          icon={iconoVertice}
          draggable
          eventHandlers={{
            dragend(e) {
              const p = (e.target as L.Marker).getLatLng()
              const copia = [...vertices]
              copia[i] = [p.lat, p.lng]
              onCambio(copia)
            },
          }}
        />
      ))}
    </>
  )
}

/** GeoJSON [lng, lat] (anillo cerrado) → vértices Leaflet [lat, lng] sin repetir el primero. */
export function anilloAVertices(anillo: [number, number][]): LatLng[] {
  const v = anillo.map(([lng, lat]) => [lat, lng] as LatLng)
  if (v.length > 1 && v[0][0] === v[v.length - 1][0] && v[0][1] === v[v.length - 1][1]) v.pop()
  return v
}

export function verticesAAnillo(v: LatLng[]): [number, number][] {
  const anillo = v.map(([lat, lng]) => [lng, lat] as [number, number])
  return [...anillo, anillo[0]]
}
