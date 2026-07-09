import { ref } from 'vue'

const DEFAULT_RECONNECT_MS = 3000

export function useWebSocket(url) {
  const connected = ref(false)
  const lastError = ref(null)

  let socket = null
  let reconnectTimer = null
  let shouldReconnect = false
  let onMessageHandler = null

  function connect(onMessage) {
    shouldReconnect = true
    onMessageHandler = onMessage
    openSocket()
  }

  function openSocket() {
    if (socket?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const endpoint = url.startsWith('ws') ? url : `${protocol}//${window.location.host}${url}`

    socket = new WebSocket(endpoint)

    socket.onopen = () => {
      connected.value = true
      lastError.value = null
    }

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        onMessageHandler?.(payload)
      } catch (err) {
        console.error('[WebSocket] parse error', err)
      }
    }

    socket.onerror = () => {
      lastError.value = '连接异常'
    }

    socket.onclose = () => {
      connected.value = false
      socket = null
      if (shouldReconnect) {
        reconnectTimer = window.setTimeout(openSocket, DEFAULT_RECONNECT_MS)
      }
    }
  }

  function disconnect() {
    shouldReconnect = false
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    socket?.close()
    socket = null
    connected.value = false
  }

  return { connected, lastError, connect, disconnect }
}
