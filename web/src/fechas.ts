/** Fecha y hora en la zona del tenant (o la del navegador). */
export function fechaHora(iso: string, zona?: string | null): string {
  return new Date(iso).toLocaleString('es-MX', {
    timeZone: zona ?? undefined,
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 'YYYY-MM-DD' de hoy en la zona local, para inputs de fecha. */
export function hoyISO(): string {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}
