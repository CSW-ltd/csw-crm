/** Obyekt xaritasi (Leaflet + OSM / sun'iy yo'ldosh): nuqta, radius (doira) yoki poligon geofence.
 * onChange bo'lmasa — faqat ko'rish. Chizish Geoman orqali (pm:create → qiymat → qatlam olib tashlanadi, xarita props'dan chiziladi). */
import { useEffect, useMemo, useRef } from "react";
import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import { Circle, LayersControl, MapContainer, Marker, Polygon, TileLayer, useMap } from "react-leaflet";
import { useI18n } from "@/i18n/I18nContext";
import type { Geofence } from "@/types";

L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });

export interface MapValue { lat: number | null; lng: number | null; geofence: Geofence | null }
interface Props { value: MapValue; onChange?: (v: MapValue) => void; height?: number; error?: string }

const UZ: [number, number] = [41.3, 64.5];

function centroid(pts: [number, number][]): [number, number] {
  const n = pts.length || 1;
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
}

/** Geoman: chizish rejimlari va natijani qiymatga aylantirish. */
function Draw({ value, onChange }: { value: MapValue; onChange: (v: MapValue) => void }) {
  const map = useMap();
  const ref = useRef(value);
  ref.current = value;
  const cb = useRef(onChange);
  cb.current = onChange;
  useEffect(() => {
    map.pm.setGlobalOptions({ snappable: false });
    const onCreate = (e: { shape: string; layer: L.Layer }) => {
      const v = ref.current;
      if (e.shape === "Marker") {
        const p = (e.layer as L.Marker).getLatLng();
        cb.current({ ...v, lat: p.lat, lng: p.lng });
      } else if (e.shape === "Circle") {
        const c = e.layer as L.Circle; const p = c.getLatLng();
        cb.current({ lat: p.lat, lng: p.lng, geofence: { type: "circle", radius: Math.round(c.getRadius()) } });
      } else if (e.shape === "Polygon") {
        const pts = ((e.layer as L.Polygon).getLatLngs()[0] as L.LatLng[]).map((p) => [+p.lat.toFixed(6), +p.lng.toFixed(6)] as [number, number]);
        const c = v.lat != null && v.lng != null ? [v.lat, v.lng] : centroid(pts);
        cb.current({ lat: c[0], lng: c[1], geofence: { type: "polygon", points: pts } });
      }
      map.removeLayer(e.layer);
      map.pm.disableDraw();
    };
    map.on("pm:create", onCreate as unknown as L.LeafletEventHandlerFn);
    return () => { map.off("pm:create", onCreate as unknown as L.LeafletEventHandlerFn); map.pm.disableDraw(); };
  }, [map]);  // onChange — ref orqali: forma qayta chizilganda chizish uzilmasin
  return null;
}

function Fit({ value }: { value: MapValue }) {
  const map = useMap();
  const key = `${value.lat},${value.lng},${JSON.stringify(value.geofence)}`;
  const done = useRef<string | null>(null);
  useEffect(() => {
    if (done.current === key) return;
    done.current = key;
    if (value.geofence?.type === "polygon") map.fitBounds(L.latLngBounds(value.geofence.points), { padding: [30, 30], maxZoom: 18 });
    else if (value.lat != null && value.lng != null) map.setView([value.lat, value.lng], Math.max(map.getZoom(), 16));
  }, [map, key, value]);
  return null;
}

export default function MapEditor({ value, onChange, height = 360, error }: Props) {
  const { t } = useI18n();
  const mapRef = useRef<L.Map | null>(null);
  const editable = !!onChange;
  const center = useMemo<[number, number]>(() => (value.lat != null && value.lng != null ? [value.lat, value.lng] : UZ), []);  // eslint-disable-line react-hooks/exhaustive-deps
  const draw = (shape: "Marker" | "Circle" | "Polygon") => mapRef.current?.pm.enableDraw(shape, { finishOn: shape === "Polygon" ? "dblclick" : undefined });
  const gf = value.geofence;
  const pos = value.lat != null && value.lng != null ? [value.lat, value.lng] as [number, number] : null;
  return (
    <Stack spacing={1} sx={{ gridColumn: "1 / -1" }} id="map-editor">
      {editable && <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center">
        <Button size="small" variant="outlined" onClick={() => draw("Marker")} id="map-point">{t("map_point")}</Button>
        <Button size="small" variant="outlined" onClick={() => draw("Circle")} id="map-circle">{t("map_circle")}</Button>
        <Button size="small" variant="outlined" onClick={() => draw("Polygon")} id="map-polygon">{t("map_polygon")}</Button>
        {gf?.type === "circle" && <TextField size="small" type="number" label={t("map_radius_m")} value={gf.radius} sx={{ width: 140 }}
          inputProps={{ min: 10, max: 3000 }} onChange={(e) => onChange!({ ...value, geofence: { type: "circle", radius: Math.max(0, Number(e.target.value) || 0) } })} />}
        {(pos || gf) && <Button size="small" color="error" onClick={() => onChange!({ lat: null, lng: null, geofence: null })} id="map-clear">{t("map_clear")}</Button>}
        <Typography variant="caption" color="text.secondary">{t("map_hint")}</Typography>
      </Stack>}
      <Box sx={{ height, borderRadius: 1, overflow: "hidden", border: 1, borderColor: error ? "error.main" : "divider" }}>
        <MapContainer center={center} zoom={pos ? 16 : 6} style={{ height: "100%", width: "100%" }} ref={mapRef} scrollWheelZoom>
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name={t("map_layer_map")}>
              <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name={t("map_layer_sat")}>
              <TileLayer attribution="&copy; Esri" maxZoom={19}
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
            </LayersControl.BaseLayer>
          </LayersControl>
          {pos && <Marker position={pos} draggable={editable}
            eventHandlers={editable ? { dragend: (e) => { const p = (e.target as L.Marker).getLatLng(); onChange!({ ...value, lat: p.lat, lng: p.lng }); } } : undefined} />}
          {pos && gf?.type === "circle" && <Circle center={pos} radius={gf.radius} pathOptions={{ color: "#1E6FD9" }} />}
          {gf?.type === "polygon" && <Polygon positions={gf.points} pathOptions={{ color: "#1E6FD9" }} />}
          {editable && <Draw value={value} onChange={onChange!} />}
          <Fit value={value} />
        </MapContainer>
      </Box>
      {error && <Typography variant="caption" color="error">{error}</Typography>}
    </Stack>
  );
}
