import axios from 'axios'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 响应拦截：统一错误提示（后续可接入通知组件）
http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('[API Error]', err.response?.status, err.message)
    return Promise.reject(err)
  }
)

export default http
