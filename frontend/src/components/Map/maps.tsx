import "leaflet/dist/leaflet.css"
import L from "leaflet"
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMapEvents,
} from "react-leaflet"

// Wilaya of Batna, Algeria.
export const BATNA_CENTER: [number, number] = [35.5559, 6.1741]

// A dependency-free marker so we don't have to ship Leaflet's PNG assets.
const dropIcon = L.divIcon({
  className: "",
  html: `<div style="font-size:26px;line-height:26px;transform:translate(-50%,-100%)">📍</div>`,
  iconSize: [26, 26],
  iconAnchor: [0, 0],
})

function ClickCapture({
  onPick,
}: {
  onPick: (lat: number, lng: number) => void
}) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng)
    },
  })
  return null
}

export function PinPicker({
  value,
  onChange,
  className,
}: {
  value: { lat: number; lng: number } | null
  onChange: (v: { lat: number; lng: number }) => void
  className?: string
}) {
  return (
    <div className={className}>
      <MapContainer
        center={value ? [value.lat, value.lng] : BATNA_CENTER}
        zoom={13}
        style={{ height: "100%", width: "100%", borderRadius: 8 }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickCapture onPick={(lat, lng) => onChange({ lat, lng })} />
        {value && <Marker position={[value.lat, value.lng]} icon={dropIcon} />}
      </MapContainer>
    </div>
  )
}

export type MapPoint = {
  id: string
  lat: number
  lng: number
  label: string
  selected?: boolean
  onClick?: () => void
}

export function PointsMap({
  points,
  className,
}: {
  points: MapPoint[]
  className?: string
}) {
  return (
    <div className={className}>
      <MapContainer
        center={BATNA_CENTER}
        zoom={12}
        style={{ height: "100%", width: "100%", borderRadius: 8 }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {points.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lng]}
            icon={dropIcon}
            eventHandlers={p.onClick ? { click: p.onClick } : undefined}
          >
            <Popup>{p.label}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
