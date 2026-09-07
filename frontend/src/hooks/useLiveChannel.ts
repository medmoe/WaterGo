import { useEffect } from "react"

/**
 * Subscribe to one of the backend WebSocket channels (section 10) and run
 * `onEvent` for each message. Falls back silently if the socket can't connect;
 * callers should also poll.
 */
export function useLiveChannel(
  path: string | null,
  onEvent: (data: unknown) => void,
) {
  useEffect(() => {
    if (!path) return
    const token = localStorage.getItem("access_token") ?? ""
    const apiBase = import.meta.env.VITE_API_URL ?? window.location.origin
    const wsBase = apiBase.replace(/^http/, "ws")
    const url = `${wsBase}/api/v1${path}${path.includes("?") ? "&" : "?"}token=${token}`

    let socket: WebSocket | null = null
    try {
      socket = new WebSocket(url)
      socket.onmessage = (e) => {
        try {
          onEvent(JSON.parse(e.data))
        } catch {
          /* ignore malformed frames */
        }
      }
    } catch {
      /* ignore - polling covers us */
    }
    return () => socket?.close()
  }, [path, onEvent])
}
