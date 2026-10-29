import type { ReactNode } from 'react'

export function Modal({ titulo, onCerrar, children }: { titulo: string; onCerrar: () => void; children: ReactNode }) {
  return (
    <div className="fondo-modal" onClick={onCerrar}>
      <div className="modal" role="dialog" aria-label={titulo} onClick={(e) => e.stopPropagation()}>
        <div className="modal-cab">
          <h2>{titulo}</h2>
          <button className="btn-texto" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
