import { ref } from 'vue'

const DEFAULT_RECONNECT_MS = 3000

export function useWebSocket(url) {
  const connected = ref(false)
  const connecting = ref(false)
  const lastError = ref(null)

  let socket = null
  let reconnectTimer = null
  let shouldReconnect = false
  let onMessageHandler = null

  function connect(onMessage) {
    shouldReconnect = true
    onMessageHandler = onMessage
    if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) {
      return
    }
    openSocket()
  }

  function openSocket() {
    if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const endpoint = url.startsWith('ws') ? url : `${protocol}//${window.location.host}${url}`

    connecting.value = true
    socket = new WebSocket(endpoint)

    socket.onopen = () => {
      connected.value = true
      connecting.value = false
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
      connecting.value = false
      lastError.value = '连接异常'
    }

    socket.onclose = () => {
      connected.value = false
      connecting.value = false
      socket = null
      if (shouldReconnect && !reconnectTimer) {
        reconnectTimer = window.setTimeout(openSocket, DEFAULT_RECONNECT_MS)
      }
    }
  }

  function disconnect() {
    shouldReconnect = false
    connecting.value = false
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    socket?.close()
    socket = null
    connected.value = false
  }

  return { connected, connecting, lastError, connect, disconnect }
}
