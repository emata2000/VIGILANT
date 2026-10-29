import jsQR from 'jsqr'
import { useEffect, useRef, useState } from 'react'

interface Detector {
  detect(fuente: CanvasImageSource): Promise<{ rawValue: string }[]>
}
declare global {
  interface Window {
    BarcodeDetector?: new (opts: { formats: string[] }) => Detector
  }
}

/** Lee un QR con la cámara trasera. Usa BarcodeDetector si existe (Chrome Android) y jsQR si no. */
export function EscanerQr({ onCodigo, onCerrar }: { onCodigo: (c: string) => void; onCerrar: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let flujo: MediaStream | null = null
    let activo = true
    let cuadro = 0
    const lienzo = document.createElement('canvas')
    const ctx = lienzo.getContext('2d', { willReadFrequently: true })
    let detector: Detector | null = null
    try {
      detector = window.BarcodeDetector ? new window.BarcodeDetector({ formats: ['qr_code'] }) : null
    } catch {
      detector = null
    }

    async function leer() {
      const v = video.current
      if (!activo || !v) return
      if (v.readyState >= 2 && v.videoWidth) {
        let codigo: string | undefined
        if (detector) {
          try {
            codigo = (await detector.detect(v))[0]?.rawValue
          } catch {
            detector = null
          }
        } else if (ctx) {
          const escala = Math.min(1, 640 / v.videoWidth)
          lienzo.width = v.videoWidth * escala
          lienzo.height = v.videoHeight * escala
          ctx.drawImage(v, 0, 0, lienzo.width, lienzo.height)
          const img = ctx.getImageData(0, 0, lienzo.width, lienzo.height)
          codigo = jsQR(img.data, img.width, img.height, { inversionAttempts: 'dontInvert' })?.data
        }
        if (codigo && activo) {
          activo = false
          navigator.vibrate?.(80)
          onCodigo(codigo)
          return
        }
      }
      cuadro = requestAnimationFrame(() => void leer())
    }

    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then((s) => {
        flujo = s
        if (!activo) return s.getTracks().forEach((t) => t.stop())
        if (video.current) {
          video.current.srcObject = s
          void video.current.play()
        }
        void leer()
      })
      .catch(() => setError('No se pudo abrir la cámara. Revisa el permiso de cámara del navegador.'))
    if (!navigator.mediaDevices) setError('Este navegador no permite usar la cámara (se necesita HTTPS).')

    return () => {
      activo = false
      cancelAnimationFrame(cuadro)
      flujo?.getTracks().forEach((t) => t.stop())
    }
  }, [onCodigo])

  return (
    <div className="escaner">
      <video ref={video} playsInline muted />
      <div className="mira" />
      <p>{error ?? 'Apunta al código QR del punto de control'}</p>
      <button className="btn grande" onClick={onCerrar}>
        Cancelar
      </button>
    </div>
  )
}
